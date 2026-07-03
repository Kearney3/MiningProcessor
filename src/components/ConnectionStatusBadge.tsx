import { useEffect, useRef, useState } from "react";
import type { BridgeInfo, ConnectionLog, ConnectionStatus } from "../lib/types";

interface ConnectionStatusBadgeProps {
  status: ConnectionStatus;
  error: string | null;
  logs: ConnectionLog[];
  bridgeInfo: BridgeInfo | null;
  onReconnect: () => void;
}

const STATUS_CONFIG: Record<
  ConnectionStatus,
  { dot: string; label: string; ring: string }
> = {
  connecting: {
    dot: "bg-amber-400 animate-pulse",
    label: "连接中...",
    ring: "ring-amber-100",
  },
  connected: {
    dot: "bg-green-500",
    label: "已连接",
    ring: "ring-green-50",
  },
  disconnected: {
    dot: "bg-red-500",
    label: "已断开",
    ring: "ring-red-50",
  },
  error: {
    dot: "bg-red-500",
    label: "错误",
    ring: "ring-red-50",
  },
};

const LEVEL_COLOR: Record<string, string> = {
  INFO: "text-blue-600",
  WARNING: "text-amber-600",
  ERROR: "text-red-600",
  STDERR: "text-red-600",
};

export function ConnectionStatusBadge({
  status,
  error,
  logs,
  bridgeInfo,
  onReconnect,
}: ConnectionStatusBadgeProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const cfg = STATUS_CONFIG[status];

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      {/* Badge 触发器 */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 ml-4 cursor-pointer hover:opacity-80 transition-opacity"
      >
        <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
        <span className="text-xs text-slate-400">{cfg.label}</span>
      </button>

      {/* Popover 浮层 */}
      {open && (
        <div
          className={`absolute top-full left-0 mt-1.5 w-80 bg-white rounded-lg shadow-lg border border-slate-200 z-50 ring-1 ${cfg.ring}`}
        >
          {/* 状态头部 */}
          <div className="px-3.5 py-2.5 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
              <span className="text-sm font-medium text-slate-700">{cfg.label}</span>
            </div>

            {/* 桥接信息 */}
            {bridgeInfo && status === "connected" && (
              <div className="mt-1.5 space-y-0.5 text-xs text-slate-500">
                {bridgeInfo.mode && (
                  <div>
                    模式: <span className="text-slate-700">{bridgeInfo.mode}</span>
                  </div>
                )}
                {bridgeInfo.pid != null && (
                  <div>
                    PID: <span className="font-mono text-slate-700">{bridgeInfo.pid}</span>
                  </div>
                )}
                {bridgeInfo.command && (
                  <div className="truncate" title={bridgeInfo.command}>
                    命令: <span className="font-mono text-slate-700">{bridgeInfo.command}</span>
                  </div>
                )}
              </div>
            )}

            {/* 错误信息 */}
            {error && (
              <div className="mt-1.5 text-xs text-red-600 bg-red-50 rounded px-2 py-1.5 break-all">
                {error}
              </div>
            )}
          </div>

          {/* 连接日志 */}
          <div className="max-h-48 overflow-y-auto thin-scrollbar">
            {logs.length === 0 ? (
              <div className="px-3.5 py-4 text-center text-xs text-slate-400">
                暂无连接日志
              </div>
            ) : (
              <div className="px-3.5 py-1.5">
                {logs.map((log, i) => (
                  <div
                    key={i}
                    className="py-0.5 flex items-baseline gap-2 text-xs font-mono"
                  >
                    <span className="shrink-0 text-slate-400">{log.timestamp}</span>
                    <span className={`shrink-0 font-medium ${LEVEL_COLOR[log.level] || "text-slate-500"}`}>
                      {log.level}
                    </span>
                    <span className="text-slate-600 break-all">{log.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 底部操作 */}
          {status !== "connected" && (
            <div className="px-3.5 py-2 border-t border-slate-100">
              <button
                onClick={() => {
                  onReconnect();
                }}
                disabled={status === "connecting"}
                className="w-full text-xs px-3 py-1.5 rounded-md bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {status === "connecting" ? "正在连接..." : "重新连接"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
