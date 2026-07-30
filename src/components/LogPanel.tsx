import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";
import type { LogEntry } from "../lib/types";
import { ClipboardIcon, CheckIcon, TrashIcon, DownloadIcon } from "../lib/icons";

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
const MAX_RENDERED_LOGS = 1000;
const SCROLL_BOTTOM_THRESHOLD = 48;

/** 数字越大级别越高，用于"选中级别及以上"筛选 */
const LEVEL_ORDER: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
  STDERR: 40,
};


export function LogPanel({ logs, onClear }: LogPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(280);
  const [isResizing, setIsResizing] = useState(false);
  const [followTail, setFollowTail] = useState(true);
  const [filterLevel, setFilterLevel] = useState<string>("INFO");
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState("");
  const feedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (followTail && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, followTail]);

  useEffect(() => () => {
    if (feedbackTimerRef.current !== null) {
      clearTimeout(feedbackTimerRef.current);
    }
  }, []);

  const showFeedback = useCallback((message: string) => {
    setFeedback(message);
    if (feedbackTimerRef.current !== null) {
      clearTimeout(feedbackTimerRef.current);
    }
    feedbackTimerRef.current = setTimeout(() => {
      setFeedback("");
      feedbackTimerRef.current = null;
    }, 2500);
  }, []);

  // Drag to resize height
  useEffect(() => {
    if (!isResizing) return;

    // 拖动调整高度时防止选中背景文本并禁用默认选择
    const prevUserSelect = document.body.style.userSelect;
    const prevCursor = document.body.style.cursor;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "row-resize";

    // 清除当前的文本选中范围
    window.getSelection()?.removeAllRanges();

    const onMove = (e: MouseEvent) => {
      e.preventDefault();
      window.getSelection()?.removeAllRanges();
      const newHeight = window.innerHeight - e.clientY;
      setHeight(Math.max(80, Math.min(500, newHeight)));
    };

    const onUp = () => setIsResizing(false);

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);

    return () => {
      document.body.style.userSelect = prevUserSelect;
      document.body.style.cursor = prevCursor;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [isResizing]);

  const filteredLogs = useMemo(
    () => logs.filter(
      (entry) => (LEVEL_ORDER[entry.level] ?? 0) >= (LEVEL_ORDER[filterLevel] ?? 0),
    ),
    [logs, filterLevel],
  );
  const renderedLogs = useMemo(
    () => filteredLogs.slice(-MAX_RENDERED_LOGS),
    [filteredLogs],
  );

  const handleCopyAll = useCallback(async () => {
    const text = filteredLogs
      .map((entry) => `[${entry.level}] ${entry.detail ?? entry.message}`)
      .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      showFeedback("日志已复制");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      showFeedback("复制失败，请检查剪贴板权限");
    }
  }, [filteredLogs, showFeedback]);

  const handleExport = useCallback(async () => {
    const today = new Date().toISOString().slice(0, 10);
    const filePath = await save({
      defaultPath: `logs-${today}.txt`,
      filters: [{ name: "Text", extensions: ["txt", "log"] }],
    });
    if (!filePath) return;
    const text = filteredLogs
      .map((entry) => `[${entry.level}] ${entry.detail ?? entry.message}`)
      .join("\n");
    try {
      await invoke("invoke_python", {
        method: "write_text_file",
        params: { path: filePath, content: text },
      });
      showFeedback("日志已导出");
    } catch {
      try {
        await navigator.clipboard.writeText(text);
        showFeedback("导出失败，日志已复制到剪贴板");
      } catch {
        showFeedback("日志导出失败");
      }
    }
  }, [filteredLogs, showFeedback]);

  const resumeFollowing = useCallback(() => {
    setFollowTail(true);
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  return (
    <div
      className={`bg-white border-t border-slate-200 shrink-0 flex flex-col ${
        isResizing ? "transition-none select-none" : "transition-[height] duration-150 ease-out"
      }`}
      style={{ height }}
    >
      {/* Drag handle */}
      <div
        role="separator"
        aria-label="调整日志面板高度"
        aria-orientation="horizontal"
        aria-valuemin={80}
        aria-valuemax={500}
        aria-valuenow={height}
        tabIndex={0}
        className="h-3 cursor-row-resize flex items-center justify-center hover:bg-slate-100 focus:bg-blue-50 group select-none"
        onMouseDown={(e) => {
          e.preventDefault();
          window.getSelection()?.removeAllRanges();
          setIsResizing(true);
        }}
        onKeyDown={(event) => {
          if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
          event.preventDefault();
          const delta = event.key === "ArrowUp" ? 20 : -20;
          setHeight((current) => Math.max(80, Math.min(500, current + delta)));
        }}
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
        {filteredLogs.length > renderedLogs.length && (
          <span className="ml-2 text-xs text-slate-500">
            显示最近 {renderedLogs.length} 条
          </span>
        )}
        <span className="ml-2 text-xs text-slate-600" role="status" aria-live="polite">
          {feedback}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <label htmlFor="log-level-filter" className="sr-only">日志级别</label>
          <select
            id="log-level-filter"
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value)}
            className="text-xs bg-white border border-slate-200 rounded px-2 py-1 text-slate-600 cursor-pointer hover:border-slate-300"
          >
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARN</option>
            <option value="ERROR">ERROR</option>
          </select>
          <button
            onClick={resumeFollowing}
            aria-pressed={followTail}
            title={followTail ? "正在跟随最新日志" : "滚动到底部并恢复跟随"}
            className={`
              text-xs px-2 py-1 rounded cursor-pointer transition-colors
              ${followTail
                ? "text-blue-600 font-medium"
                : "text-amber-700 hover:text-amber-800"
              }
            `}
          >
            {followTail ? "跟随中" : "继续跟随"}
          </button>
          <button
            onClick={handleCopyAll}
            title={copied ? "已复制" : "复制全部"}
            aria-label={copied ? "日志已复制" : "复制全部日志"}
            disabled={filteredLogs.length === 0}
            className="p-1.5 rounded text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            {copied ? <CheckIcon /> : <ClipboardIcon />}
          </button>
          <button
            onClick={handleExport}
            title="导出日志"
            aria-label="导出日志"
            disabled={filteredLogs.length === 0}
            className="p-1.5 rounded text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            <DownloadIcon />
          </button>
          <button
            onClick={onClear}
            title="清空"
            aria-label="清空日志"
            disabled={logs.length === 0}
            className="p-1.5 rounded text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            <TrashIcon />
          </button>
        </div>
      </div>

      {/* Log entries */}
      <div
        ref={scrollRef}
        role="region"
        aria-label="处理日志"
        onScroll={(event) => {
          const element = event.currentTarget;
          const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
          setFollowTail(distance <= SCROLL_BOTTOM_THRESHOLD);
        }}
        className="flex-1 overflow-y-auto thin-scrollbar font-mono text-xs text-slate-600 px-4 py-1.5"
      >
        {filteredLogs.length === 0 ? (
          <div className="text-slate-500 text-center py-6 text-xs">等待日志...</div>
        ) : (
          renderedLogs.map((entry) => {
            const dotColor = LEVEL_DOT[entry.level] || DEFAULT_DOT;
            return (
              <div
                key={entry.seq}
                className="py-0.5 flex items-baseline gap-3 hover:bg-slate-50 rounded px-1 -mx-1"
              >
                <span
                  className={`inline-block shrink-0 w-[3px] h-[3px] rounded-full mt-[5px] ${dotColor}`}
                />
                <span className="w-12 shrink-0 text-[11px] font-medium text-slate-500">
                  {entry.level === "WARNING" ? "WARN" : entry.level}
                </span>
                <span className="break-all min-w-0">
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
