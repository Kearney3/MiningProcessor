import { useRef, useEffect, useState, useCallback } from "react";
import type { LogEntry } from "../lib/types";

interface LogPanelProps {
  logs: LogEntry[];
  onClear: () => void;
}

/** Colored dot per level */
const LEVEL_DOT: Record<string, string> = {
  INFO: "bg-blue-400",
  WARNING: "bg-amber-400",
  ERROR: "bg-red-400",
  DEBUG: "bg-slate-400",
  STDERR: "bg-red-400",
};

const DEFAULT_DOT = "bg-slate-400";

// --- Toolbar SVG icons ---

function IconClipboard() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function IconTrash() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

export function LogPanel({ logs, onClear }: LogPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(180);
  const [isResizing, setIsResizing] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filterLevel, setFilterLevel] = useState<string>("ALL");
  const [copied, setCopied] = useState(false);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Drag to resize height
  useEffect(() => {
    if (!isResizing) return;
    const onMove = (e: MouseEvent) => {
      const newHeight = window.innerHeight - e.clientY;
      setHeight(Math.max(80, Math.min(500, newHeight)));
    };
    const onUp = () => setIsResizing(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [isResizing]);

  const filteredLogs =
    filterLevel === "ALL"
      ? logs
      : logs.filter((l) => l.level === filterLevel);

  const handleCopyAll = useCallback(() => {
    const text = filteredLogs
      .map((e) => `[${e.level}] ${e.message}`)
      .join("\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [filteredLogs]);

  return (
    <div
      className="bg-white border-t border-slate-200 shrink-0 flex flex-col transition-[height] duration-150 ease-out"
      style={{ height }}
    >
      {/* Drag handle */}
      <div
        className="h-1 cursor-row-resize flex items-center justify-center hover:bg-slate-100 group"
        onMouseDown={() => setIsResizing(true)}
      >
        <div className="flex items-center gap-1">
          <span className="w-[3px] h-[3px] rounded-full bg-slate-300 group-hover:bg-slate-400 transition-colors" />
          <span className="w-[3px] h-[3px] rounded-full bg-slate-300 group-hover:bg-slate-400 transition-colors" />
          <span className="w-[3px] h-[3px] rounded-full bg-slate-300 group-hover:bg-slate-400 transition-colors" />
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center px-3 py-1.5 border-b border-slate-100 shrink-0">
        <span className="text-xs font-medium text-slate-500">日志</span>
        <span className="inline-flex items-center justify-center min-w-[24px] h-4 px-1.5 ml-2 text-[10px] font-medium text-slate-400 bg-slate-50 rounded-full">
          {filteredLogs.length}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <select
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value)}
            className="text-xs bg-white border border-slate-200 rounded px-2 py-0.5 text-slate-500 cursor-pointer hover:border-slate-300 appearance-none"
          >
            <option value="ALL">全部</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARN</option>
            <option value="ERROR">ERROR</option>
          </select>
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`
              text-xs px-2 py-0.5 rounded cursor-pointer transition-colors
              ${autoScroll
                ? "text-blue-600 font-medium"
                : "text-slate-400 hover:text-slate-600"
              }
            `}
          >
            Auto
          </button>
          <button
            onClick={handleCopyAll}
            title={copied ? "已复制" : "复制全部"}
            className="p-1 rounded text-slate-400 hover:text-slate-600 cursor-pointer transition-colors"
          >
            {copied ? <IconCheck /> : <IconClipboard />}
          </button>
          <button
            onClick={onClear}
            title="清空"
            className="p-1 rounded text-slate-400 hover:text-slate-600 cursor-pointer transition-colors"
          >
            <IconTrash />
          </button>
        </div>
      </div>

      {/* Log entries */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto thin-scrollbar font-mono text-xs text-slate-600 px-4 py-1.5">
        {filteredLogs.length === 0 ? (
          <div className="text-slate-400 text-center py-6 text-xs">等待日志...</div>
        ) : (
          filteredLogs.map((entry, i) => {
            const dotColor = LEVEL_DOT[entry.level] || DEFAULT_DOT;
            return (
              <div
                key={i}
                className="py-0.5 flex items-baseline gap-3 hover:bg-slate-50 rounded px-1 -mx-1"
              >
                <span
                  className={`inline-block shrink-0 w-[3px] h-[3px] rounded-full mt-[5px] ${dotColor}`}
                />
                <span className="break-all">
                  {entry.message}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
