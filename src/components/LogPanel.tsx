import { useRef, useEffect, useState, useCallback } from "react";
import type { LogEntry } from "../lib/types";

interface LogPanelProps {
  logs: LogEntry[];
  onClear: () => void;
}

const LEVEL_STYLES: Record<string, { pill: string; text: string }> = {
  INFO: {
    pill: "bg-blue-50 text-blue-600 border border-blue-200/50",
    text: "text-slate-600",
  },
  WARNING: {
    pill: "bg-amber-50 text-amber-600 border border-amber-200/50",
    text: "text-amber-700",
  },
  ERROR: {
    pill: "bg-red-50 text-red-600 border border-red-200/50",
    text: "text-red-600",
  },
  DEBUG: {
    pill: "bg-slate-50 text-slate-400 border border-slate-200/50",
    text: "text-slate-400",
  },
  STDERR: {
    pill: "bg-red-50 text-red-500 border border-red-200/50",
    text: "text-red-500",
  },
};

const DEFAULT_LEVEL_STYLE = {
  pill: "bg-slate-50 text-slate-500 border border-slate-200/50",
  text: "text-slate-600",
};

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
      className="log-panel-wrapper border-t border-slate-200/80 bg-white shrink-0 flex flex-col"
      style={{ height }}
    >
      {/* Drag handle */}
      <div
        className="h-1.5 cursor-row-resize hover:bg-cyan-100/60 transition-colors flex items-center justify-center group"
        onMouseDown={() => setIsResizing(true)}
      >
        <div className="w-8 h-0.5 bg-slate-300 rounded-full group-hover:bg-cyan-400 transition-colors" />
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-1.5 border-b border-slate-100 shrink-0">
        <span className="text-xs font-semibold text-slate-500 tracking-wide">日志</span>
        <span className="inline-flex items-center justify-center min-w-[24px] h-4 px-1.5 text-[10px] font-medium text-slate-500 bg-slate-100 rounded-full">
          {filteredLogs.length}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <select
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-md px-2 py-0.5 text-slate-600 cursor-pointer hover:border-slate-300"
          >
            <option value="ALL">全部</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARN</option>
            <option value="ERROR">ERROR</option>
          </select>
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`
              text-xs px-2 py-0.5 rounded-md font-medium cursor-pointer
              ${autoScroll
                ? "bg-cyan-50 text-cyan-700 border border-cyan-200/50"
                : "text-slate-400 hover:bg-slate-100 border border-transparent"
              }
            `}
          >
            ↓自动
          </button>
          <button
            onClick={handleCopyAll}
            className="text-xs text-slate-400 hover:text-slate-600 px-2 py-0.5 rounded-md hover:bg-slate-100 font-medium cursor-pointer border border-transparent hover:border-slate-200"
          >
            {copied ? "已复制 ✓" : "复制全部"}
          </button>
          <button
            onClick={onClear}
            className="text-xs text-slate-400 hover:text-slate-600 px-2 py-0.5 rounded-md hover:bg-slate-100 font-medium cursor-pointer border border-transparent hover:border-slate-200"
          >
            清空
          </button>
        </div>
      </div>

      {/* Log entries */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto thin-scrollbar font-mono text-xs px-4 py-1.5">
        {filteredLogs.length === 0 ? (
          <div className="text-slate-300 text-center py-6 text-sm">暂无日志</div>
        ) : (
          filteredLogs.map((entry, i) => {
            const style = LEVEL_STYLES[entry.level] || DEFAULT_LEVEL_STYLE;
            return (
              <div
                key={i}
                className="py-0.5 flex items-baseline gap-3 hover:bg-slate-50/60 rounded px-1 -mx-1"
              >
                <span
                  className={`
                    inline-flex items-center justify-center shrink-0
                    w-12 text-center text-[10px] font-semibold leading-tight
                    px-1.5 py-0.5 rounded-full
                    ${style.pill}
                  `}
                >
                  {entry.level}
                </span>
                <span className={`${style.text} break-all`}>
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
