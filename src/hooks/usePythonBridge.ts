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

const HEARTBEAT_INTERVAL = 30_000;
const MAX_FAIL_COUNT = 2;
const MAX_CONNECTION_LOGS = 50;

function now(): string {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
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

  // 添加连接日志
  const addConnectionLog = useCallback((level: string, message: string) => {
    setConnectionLogs((prev) => {
      const next = [...prev, { level, message, timestamp: now() }];
      return next.length > MAX_CONNECTION_LOGS ? next.slice(-MAX_CONNECTION_LOGS) : next;
    });
  }, []);

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
      addConnectionLog("WARNING", `心跳失败 (${failCountRef.current}/${MAX_FAIL_COUNT}): ${msg}`);
      if (failCountRef.current >= MAX_FAIL_COUNT) {
        setConnectionStatus("disconnected");
        setIsConnected(false);
        addConnectionLog("ERROR", "Python 进程已断开连接");
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
        addConnectionLog("INFO", `连接成功 (PID: ${result.pid})`);
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
          addConnectionLog("INFO", `Python bridge 启动 (${mode} 模式, PID: ${pid})`);
          setBridgeInfo({
            mode: (mode as "sidecar" | "dev") ?? null,
            pid: pid ?? null,
            alive: true,
            command: (connData.command as string) ?? null,
          });
        } else if (status === "error") {
          setConnectionStatus("error");
          setIsConnected(false);
          const errMsg = (connData.error as string) ?? "未知错误";
          setConnectionError(errMsg);
          addConnectionLog("ERROR", errMsg);
        }
        return;
      }

      // 普通日志事件
      if (data.event === "log") {
        const entry = data.data as unknown as LogEntry;
        setLogs((prev) => {
          const next = [...prev, entry];
          return next.length > 2000 ? next.slice(-2000) : next;
        });
        // 高级别日志也写入连接日志
        if (entry.level === "ERROR" || entry.level === "STDERR") {
          addConnectionLog(entry.level, entry.message);
        }
      } else if (data.event === "progress") {
        setProgress(data.data as unknown as BatchProgress);
      }
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [addConnectionLog]);

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
    setLogs([]);
  }, []);

  /**
   * 手动重连：重置状态并 ping
   */
  const reconnect = useCallback(async () => {
    setConnectionStatus("connecting");
    setConnectionError(null);
    failCountRef.current = 0;
    addConnectionLog("INFO", "正在重新连接...");
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
