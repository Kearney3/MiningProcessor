import { memo, useRef, useEffect, useState, useCallback, useMemo } from "react";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";
import type { LogEntry } from "../lib/types";
import { ClipboardIcon, CheckIcon, TrashIcon, DownloadIcon } from "../lib/icons";
import { localTodayString } from "../lib/dateUtils";
import { useTranslation } from "react-i18next";

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
const MIN_HEIGHT = 80;
const MAX_HEIGHT = 500;

function defaultPanelHeight() {
  return Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, Math.round(window.innerHeight / 3)));
}

/** 数字越大级别越高，用于"选中级别及以上"筛选 */
const LEVEL_ORDER: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
  STDERR: 40,
};

function formatTimestamp(value: string) {
  if (!value) return "--:--:--";
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime()) && value.includes("T")) {
    return parsed.toLocaleTimeString("zh-CN", { hour12: false });
  }
  return value;
}

const LogRow = memo(function LogRow({ entry }: { entry: LogEntry }) {
  const dotColor = LEVEL_DOT[entry.level] || DEFAULT_DOT;
  return (
    <div className="py-0.5 flex items-baseline gap-3 hover:bg-slate-50 rounded px-1 -mx-1">
      <span className="w-[68px] shrink-0 tabular-nums text-[11px] text-slate-400">
        {formatTimestamp(entry.timestamp)}
      </span>
      <span
        className={`inline-block shrink-0 w-[3px] h-[3px] rounded-full mt-[5px] ${dotColor}`}
      />
      <span className="w-12 shrink-0 text-[11px] font-medium text-slate-500">
        {entry.level === "WARNING" ? "WARN" : entry.level}
      </span>
      <span className="break-all min-w-0">{entry.message}</span>
    </div>
  );
});

export function LogPanel({ logs, onClear }: LogPanelProps) {
  const { t } = useTranslation();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(defaultPanelHeight);
  const [collapsed, setCollapsed] = useState(false);
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
      setHeight(Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, newHeight)));
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
      showFeedback(t("components:LogPanel.logCopied"));
      setTimeout(() => setCopied(false), 2000);
    } catch {
      showFeedback(t("components:LogPanel.copyFailedCheckClipboardPermissions"));
    }
  }, [filteredLogs, showFeedback, t]);

  const handleExport = useCallback(async () => {
    const today = localTodayString();
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
      showFeedback(t("components:LogPanel.logExported"));
    } catch {
      try {
        await navigator.clipboard.writeText(text);
        showFeedback(t("components:LogPanel.exportFailedTheLogWasCopiedToTheClipboard"));
      } catch {
        showFeedback(t("components:LogPanel.logExportFailed"));
      }
    }
  }, [filteredLogs, showFeedback, t]);

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
      style={{ height: collapsed ? 42 : height }}
    >
      {/* Drag handle */}
      {!collapsed && <div
        role="separator"
        aria-label={t("components:LogPanel.resizeLogPanel")}
        aria-orientation="horizontal"
        aria-valuemin={MIN_HEIGHT}
        aria-valuemax={MAX_HEIGHT}
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
          setHeight((current) => Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, current + delta)));
        }}
      >
        <div className="flex items-center gap-1">
          <span className="w-[3px] h-[3px] rounded-full bg-slate-300 group-hover:bg-slate-400 transition-colors" />
          <span className="w-[3px] h-[3px] rounded-full bg-slate-300 group-hover:bg-slate-400 transition-colors" />
          <span className="w-[3px] h-[3px] rounded-full bg-slate-300 group-hover:bg-slate-400 transition-colors" />
        </div>
      </div>}

      {/* Toolbar */}
      <div className="flex items-center px-3 py-1.5 border-b border-slate-100 shrink-0">
        <span className="text-xs font-medium text-slate-500">{t("components:LogPanel.logs")}</span>
        <span className="inline-flex items-center justify-center min-w-[24px] h-4 px-1.5 ml-2 text-[10px] font-medium text-slate-400 bg-slate-50 rounded-full">
          {filteredLogs.length}
        </span>
        {filteredLogs.length > renderedLogs.length && (
          <span className="ml-2 text-xs text-slate-500">
            {t("components:LogPanel.showingLatest", { count: renderedLogs.length })}
          </span>
        )}
        <span className="ml-2 text-xs text-slate-600" role="status" aria-live="polite">
          {feedback}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <label htmlFor="log-level-filter" className="sr-only">{t("components:LogPanel.logLevel")}</label>
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
            title={followTail ? t("components:LogPanel.followingLatestLogs") : t("components:LogPanel.scrollToBottomAndResumeFollowing")}
            className={`
              text-xs px-2 py-1 rounded cursor-pointer transition-colors
              ${followTail
                ? "text-blue-600 font-medium"
                : "text-amber-700 hover:text-amber-800"
              }
            `}
          >
            {followTail ? t("components:LogPanel.following") : t("components:LogPanel.resume")}
          </button>
          <button
            onClick={handleCopyAll}
            title={copied ? t("components:LogPanel.copied") : t("components:LogPanel.copyAll")}
            aria-label={copied ? t("components:LogPanel.logCopied") : t("components:LogPanel.copyAllLogs")}
            disabled={filteredLogs.length === 0}
            className="p-1.5 rounded text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            {copied ? <CheckIcon /> : <ClipboardIcon />}
          </button>
          <button
            onClick={handleExport}
            title={t("components:LogPanel.exportLogs")}
            aria-label={t("components:LogPanel.exportLogs")}
            disabled={filteredLogs.length === 0}
            className="p-1.5 rounded text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            <DownloadIcon />
          </button>
          <button
            onClick={onClear}
            title={t("components:LogPanel.clear")}
            aria-label={t("components:LogPanel.clearLogs")}
            disabled={logs.length === 0}
            className="p-1.5 rounded text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            <TrashIcon />
          </button>
          <button
            onClick={() => setCollapsed((value) => !value)}
            title={collapsed ? t("components:LogPanel.expandLog") : t("components:LogPanel.collapseLog")}
            aria-label={collapsed ? t("components:LogPanel.expandLog") : t("components:LogPanel.collapseLog")}
            aria-expanded={!collapsed}
            className="p-1.5 rounded text-slate-500 hover:text-slate-700 cursor-pointer transition-colors"
          >
            <svg
              viewBox="0 0 20 20"
              aria-hidden="true"
              className={`w-4 h-4 transition-transform ${collapsed ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
            >
              <path d="m5 12 5-5 5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Log entries */}
      {!collapsed && <div
        ref={scrollRef}
        role="region"
        aria-label={t("components:LogPanel.processingLog")}
        onScroll={(event) => {
          const element = event.currentTarget;
          const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
          setFollowTail(distance <= SCROLL_BOTTOM_THRESHOLD);
        }}
        className="flex-1 overflow-y-auto thin-scrollbar font-mono text-xs text-slate-600 px-4 py-1.5"
      >
        {filteredLogs.length === 0 ? (
          <div className="text-slate-500 text-center py-6 text-xs">{t("components:LogPanel.waitingForLogs")}</div>
        ) : (
          renderedLogs.map((entry) => <LogRow key={entry.seq} entry={entry} />)
        )}
      </div>}
    </div>
  );
}
