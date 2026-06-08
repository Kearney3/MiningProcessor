import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useCallback, useEffect, useState } from "react";
import type { BatchProgress, LogEntry, PythonEvent } from "../lib/types";

/**
 * Python 桥接 hook
 *
 * 提供 invoke（调用 Python 方法）、日志监听、进度监听、取消功能。
 */
export function usePythonBridge() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<BatchProgress | null>(null);

  // 初始化：ping Python 子进程
  useEffect(() => {
    invoke("invoke_python", { method: "ping", params: {} })
      .then(() => setIsConnected(true))
      .catch(() => setIsConnected(false));
  }, []);

  // 监听 Python 日志事件
  useEffect(() => {
    const unlisten = listen<PythonEvent>("python-log", (event) => {
      const data = event.payload;
      if (data.event === "log") {
        const entry = data.data as unknown as LogEntry;
        setLogs((prev) => {
          const next = [...prev, entry];
          // 保留最近 2000 条
          return next.length > 2000 ? next.slice(-2000) : next;
        });
      } else if (data.event === "progress") {
        setProgress(data.data as unknown as BatchProgress);
      }
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

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

  return {
    call,
    cancel,
    logs,
    clearLogs,
    isConnected,
    progress,
    setProgress,
  };
}
