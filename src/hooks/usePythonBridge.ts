import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  BatchProgress,
  BridgeInfo,
  ConnectionLog,
  ConnectionStatus,
  LogEntry,
  PythonEvent,
} from "../lib/types";
import { localDateTimeISO } from "../lib/dateUtils";
import i18n from "../i18n";

const HEARTBEAT_INTERVAL = 30_000;
const MAX_FAIL_COUNT = 2;
const MAX_CONNECTION_LOGS = 50;
const MAX_LOGS = 5000;
const MAX_PENDING_LOGS = 10_000;
const LOG_FLUSH_INTERVAL = 50;

function now(): string {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function levelOrder(level: string): number {
  return { DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50, STDERR: 40 }[level] ?? 0;
}

/** 保留最近日志；溢出时优先保留 WARNING 及以上。 */
function trimLogs(entries: LogEntry[], capacity: number): LogEntry[] {
  if (entries.length <= capacity) return entries;
  const important = entries.filter((entry) => levelOrder(entry.level) >= 30);
  if (important.length >= capacity) return important.slice(-capacity);
  const regular = entries.filter((entry) => levelOrder(entry.level) < 30);
  return [...regular.slice(-(capacity - important.length)), ...important]
    .sort((a, b) => a.seq - b.seq);
}

/**
 * Python 桥接 hook
 *
 * 提供 invoke（调用 Python 方法）、日志监听、进度监听、取消功能。
 * 增加：连接状态管理、心跳检测、手动重连。
 */
export function usePythonBridge() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<BatchProgress | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [connectionLogs, setConnectionLogs] = useState<ConnectionLog[]>([]);
  const [bridgeInfo, setBridgeInfo] = useState<BridgeInfo | null>(null);

  const failCountRef = useRef(0);
  const pendingLogsRef = useRef<LogEntry[]>([]);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clientSequenceRef = useRef(0);

  // 添加连接日志
  const addConnectionLog = useCallback((level: string, message: string) => {
    setConnectionLogs((prev) => {
      const next = [...prev, { level, message, timestamp: now() }];
      return next.length > MAX_CONNECTION_LOGS ? next.slice(-MAX_CONNECTION_LOGS) : next;
    });
  }, []);

  const queueLogEntries = useCallback((rawEntries: Record<string, unknown>[]) => {
    const normalized = rawEntries.map((raw): LogEntry => {
      const incomingSequence = Number(raw.seq);
      const sequence = Number.isFinite(incomingSequence)
        && incomingSequence > clientSequenceRef.current
        ? incomingSequence
        : clientSequenceRef.current + 1;
      clientSequenceRef.current = Math.max(clientSequenceRef.current, sequence);
      return {
        seq: sequence,
        timestamp: typeof raw.timestamp === "string" ? raw.timestamp : localDateTimeISO(),
        level: typeof raw.level === "string" ? raw.level : "INFO",
        logger: typeof raw.logger === "string" ? raw.logger : undefined,
        message: typeof raw.message === "string" ? raw.message : String(raw.message ?? ""),
        detail: typeof raw.detail === "string" ? raw.detail : undefined,
      };
    });

    pendingLogsRef.current = trimLogs(
      [...pendingLogsRef.current, ...normalized],
      MAX_PENDING_LOGS,
    );
    for (const entry of normalized) {
      if (entry.level === "ERROR" || entry.level === "CRITICAL" || entry.level === "STDERR") {
        addConnectionLog(entry.level, entry.message);
      }
    }
    if (flushTimerRef.current === null) {
      flushTimerRef.current = setTimeout(() => {
        const batch = pendingLogsRef.current;
        pendingLogsRef.current = [];
        flushTimerRef.current = null;
        if (batch.length > 0) {
          setLogs((previous) => trimLogs([...previous, ...batch], MAX_LOGS));
        }
      }, LOG_FLUSH_INTERVAL);
    }
  }, [addConnectionLog]);

  // 心跳检测：ping Python 子进程
  const doPing = useCallback(async () => {
    try {
      const result = await invoke<{ pong: boolean; pid: number; version?: string }>(
        "invoke_python",
        { method: "ping", params: {} },
      );
      failCountRef.current = 0;
      setConnectionStatus("connected");
      setConnectionError(null);
      setIsConnected(true);
      return result;
    } catch (err) {
      failCountRef.current += 1;
      const msg = err instanceof Error ? err.message : String(err);
      addConnectionLog("WARNING", i18n.t("hooks:usePythonBridge.心跳失败($/$):$_6496", { count: failCountRef.current, max: MAX_FAIL_COUNT, msg }));
      if (failCountRef.current >= MAX_FAIL_COUNT) {
        setConnectionStatus("disconnected");
        setIsConnected(false);
        addConnectionLog("ERROR", i18n.t("hooks:usePythonBridge.Python进程已断开连接_c558"));
      }
      return null;
    }
  }, [addConnectionLog]);

  // 获取桥接进程信息
  const fetchBridgeInfo = useCallback(async () => {
    try {
      const info = await invoke<BridgeInfo>("get_bridge_info");
      setBridgeInfo(info);
    } catch {
      // get_bridge_info 不可用（AppState 未注册），忽略
    }
  }, []);

  // 初始化：首次 ping + 获取桥接信息
  useEffect(() => {
    doPing().then((result) => {
      if (result) {
        addConnectionLog("INFO", i18n.t("hooks:usePythonBridge.连接成功(PID:$)_7a46", { pid: result.pid }));
      }
      fetchBridgeInfo();
    });
  }, [doPing, fetchBridgeInfo]);

  // 心跳定时器
  useEffect(() => {
    if (connectionStatus === "error") return; // 桥接未找到，不心跳

    const timer = setInterval(() => {
      doPing();
    }, HEARTBEAT_INTERVAL);

    return () => clearInterval(timer);
  }, [connectionStatus, doPing]);

  // 监听 Python 事件（日志 + 进度 + 连接事件）
  useEffect(() => {
    const unlisten = listen<PythonEvent>("python-log", (event) => {
      const data = event.payload;

      // 连接事件（来自 Rust init_bridge）
      if (data.event === "connection") {
        const connData = data.data as Record<string, unknown>;
        const status = connData.status as string;
        if (status === "connected") {
          setConnectionStatus("connected");
          setIsConnected(true);
          setConnectionError(null);
          const mode = connData.mode as string;
          const pid = connData.pid as number | undefined;
          addConnectionLog("INFO", i18n.t("hooks:usePythonBridge.Pythonbridge启动(_6754", { mode, pid }));
          setBridgeInfo({
            mode: (mode as "sidecar" | "dev") ?? null,
            pid: pid ?? null,
            alive: true,
            command: (connData.command as string) ?? null,
          });
        } else if (status === "error") {
          setConnectionStatus("error");
          setIsConnected(false);
          const errMsg = (connData.error as string) ?? i18n.t("hooks:usePythonBridge.未知错误_974e");
          setConnectionError(errMsg);
          addConnectionLog("ERROR", errMsg);
        }
        return;
      }

      // 普通日志事件
      if (data.event === "log") {
        queueLogEntries([data.data]);
      } else if (data.event === "log_batch") {
        const entries = (data.data as { entries?: PythonEvent[] }).entries ?? [];
        queueLogEntries(
          entries
            .filter((entry) => entry.event === "log")
            .map((entry) => entry.data),
        );
        // Extract progress events from the batch
        for (const entry of entries) {
          if (entry.event === "progress") {
            setProgress(entry.data as unknown as BatchProgress);
          }
        }
      } else if (data.event === "progress") {
        setProgress(data.data as unknown as BatchProgress);
      }
    });
    return () => {
      unlisten.then((fn) => fn());
      if (flushTimerRef.current !== null) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      pendingLogsRef.current = [];
    };
  }, [queueLogEntries]);

  /**
   * 调用 Python RPC 方法
   */
  const call = useCallback(
    async <T = unknown>(method: string, params: Record<string, unknown> = {}): Promise<T> => {
      const result = await invoke("invoke_python", { method, params });
      return result as T;
    },
    [],
  );

  /**
   * 取消当前批处理
   */
  const cancel = useCallback(async () => {
    await invoke("cancel_task");
  }, []);

  /**
   * 清空日志
   */
  const clearLogs = useCallback(() => {
    pendingLogsRef.current = [];
    if (flushTimerRef.current !== null) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    setLogs([]);
  }, []);

  /**
   * 手动重连：重置状态并 ping
   */
  const reconnect = useCallback(async () => {
    setConnectionStatus("connecting");
    setConnectionError(null);
    failCountRef.current = 0;
    addConnectionLog("INFO", i18n.t("hooks:usePythonBridge.正在重新连接..._de56"));
    const result = await doPing();
    if (result) {
      fetchBridgeInfo();
    } else {
      setConnectionStatus("disconnected");
    }
  }, [doPing, fetchBridgeInfo, addConnectionLog]);

  return {
    call,
    cancel,
    logs,
    clearLogs,
    isConnected,
    connectionStatus,
    connectionError,
    connectionLogs,
    bridgeInfo,
    reconnect,
    progress,
    setProgress,
  };
}
