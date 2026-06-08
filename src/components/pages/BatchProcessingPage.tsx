import { useState, useMemo, useCallback } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import type { BatchProgress, ScanResult } from "../../lib/types";

// ═══════════════════════════════════════
// Types
// ═══════════════════════════════════════

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
  cancel: () => Promise<void>;
  progress: BatchProgress | null;
  setProgress: (p: BatchProgress | null) => void;
}

type TableMergeMode = "split" | "merge" | "table_merge";
type BaseTableType = "fuel" | "worktime";

// ═══════════════════════════════════════
// Constants
// ═══════════════════════════════════════

const dataTypeConfig: Record<string, { icon: string; label: string; color: string; bg: string; border: string }> = {
  油耗:     { icon: "⛽", label: "油耗",     color: "text-cyan-600",    bg: "bg-cyan-50",    border: "border-cyan-200" },
  生产:     { icon: "🏗️", label: "生产",     color: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-200" },
  电力:     { icon: "⚡", label: "电力",     color: "text-amber-600",   bg: "bg-amber-50",   border: "border-amber-200" },
  工时:     { icon: "⏱️", label: "工时",     color: "text-blue-600",    bg: "bg-blue-50",    border: "border-blue-200" },
  production: { icon: "🏗️", label: "生产",  color: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-200" },
  fuel:     { icon: "⛽", label: "油耗",     color: "text-cyan-600",    bg: "bg-cyan-50",    border: "border-cyan-200" },
  electrical: { icon: "⚡", label: "电力",  color: "text-amber-600",   bg: "bg-amber-50",   border: "border-amber-200" },
  worktime: { icon: "⏱️", label: "工时",     color: "text-blue-600",    bg: "bg-blue-50",    border: "border-blue-200" },
  merge:    { icon: "📋", label: "合并",     color: "text-purple-600",  bg: "bg-purple-50",  border: "border-purple-200" },
};

const fallbackConfig = { icon: "📄", label: "", color: "text-slate-600", bg: "bg-slate-50", border: "border-slate-200" };

function getTypeConfig(type: string) {
  return dataTypeConfig[type] ?? { ...fallbackConfig, label: type };
}

function formatToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function shiftDate(dateStr: string, days: number): string {
  const d = new Date(dateStr + "T00:00:00");
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// ═══════════════════════════════════════
// Small reusable UI components
// ═══════════════════════════════════════

/** Collapsible section with a chevron */
function Collapsible({
  title,
  icon,
  defaultOpen = false,
  children,
}: {
  title: string;
  icon?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
      >
        {icon && <span className="text-base">{icon}</span>}
        <span className="flex-1 text-left">{title}</span>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      {open && <div className="px-4 pb-4 border-t border-slate-100">{children}</div>}
    </div>
  );
}

/** Section divider with optional label */
function SectionDivider({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 my-4">
      <div className="flex-1 h-px bg-slate-200" />
      {label && <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">{label}</span>}
      <div className="flex-1 h-px bg-slate-200" />
    </div>
  );
}

/** Chip-style toggle for mutually exclusive options */
function ChipToggle({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string; tip?: string }[];
}) {
  return (
    <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden">
      {options.map((o, i) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          title={o.tip}
          className={`text-xs px-3 py-1.5 transition-colors ${
            value === o.value
              ? "bg-cyan-500 text-white"
              : "bg-white text-slate-600 hover:bg-slate-50"
          } ${i > 0 ? "border-l border-slate-200" : ""}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Confirmation dialog overlay */
function ConfirmDialog({
  title,
  message,
  details,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  details?: string[];
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
        <div className="px-6 pt-6 pb-2">
          <div className="flex items-center gap-3 mb-3">
            <div className="shrink-0 w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
              <svg className="w-5 h-5 text-amber-600" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <h3 className="text-base font-semibold text-slate-800">{title}</h3>
          </div>
          <p className="text-sm text-slate-600 leading-relaxed">{message}</p>
          {details && details.length > 0 && (
            <ul className="mt-3 space-y-1">
              {details.map((d, i) => (
                <li key={i} className="flex items-center gap-2 text-xs text-slate-500">
                  <span className="text-orange-400">-</span>
                  {d}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex gap-3 px-6 py-4 bg-slate-50 border-t border-slate-100">
          <button
            onClick={onCancel}
            className="flex-1 text-sm font-medium px-4 py-2.5 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 transition-colors"
          >
            {cancelLabel ?? "取消"}
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 text-sm font-medium px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white transition-colors"
          >
            {confirmLabel ?? "继续处理"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// Animated progress bar
// ═══════════════════════════════════════

function AnimatedProgressBar({ percent, stage, detail }: { percent: number; stage: string; detail: string }) {
  const pct = Math.round(percent * 100);
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-cyan-500 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm font-medium text-slate-700">{stage}</span>
        </div>
        <span className="text-xs font-mono text-slate-500">{pct}%</span>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
        <div
          className="h-3 rounded-full transition-all duration-500 ease-out relative overflow-hidden"
          style={{ width: `${pct}%` }}
        >
          <div
            className="absolute inset-0 animate-gradient-shift"
            style={{
              background: "linear-gradient(90deg, #06b6d4, #3b82f6, #8b5cf6, #06b6d4)",
              backgroundSize: "200% 100%",
            }}
          />
        </div>
      </div>
      {detail && <p className="mt-2 text-xs text-slate-400 truncate">{detail}</p>}
    </div>
  );
}

// ═══════════════════════════════════════
// Cancel button with pulse animation
// ═══════════════════════════════════════

function PulsingCancelButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="relative text-sm font-medium px-5 py-2.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-600 transition-colors group"
    >
      <span className="absolute inset-0 rounded-lg bg-red-400/20 animate-ping" />
      <span className="relative flex items-center gap-1.5">
        <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z"
            clipRule="evenodd"
          />
        </svg>
        取消
      </span>
    </button>
  );
}

// ═══════════════════════════════════════
// Main page component
// ═══════════════════════════════════════

export function BatchProcessingPage({ bridge }: { bridge: BridgeProp }) {
  // -- Path & scan --
  const [folderPath, setFolderPath] = useState("");
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState(false);

  // -- Processing --
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // -- Confirmation dialog --
  const [showConfirm, setShowConfirm] = useState(false);

  // -- Basic params --
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [month, setMonth] = useState((new Date().getMonth() + 1).toString());
  const [rawStart, setRawStart] = useState("-1");

  // -- Output mode (replaces old mergeOutput boolean) --
  const [tableMergeMode, setTableMergeMode] = useState<TableMergeMode>("merge");
  const [baseTableType, setBaseTableType] = useState<BaseTableType>("fuel");

  // -- Ledger --
  const [useLedger, setUseLedger] = useState(false);

  // -- Date filter --
  const [dateFilterEnabled, setDateFilterEnabled] = useState(false);
  const [filterDate, setFilterDate] = useState(formatToday());

  // -- Header mapping --
  const [useHeaderMapping, setUseHeaderMapping] = useState(false);
  const [headerMode, setHeaderMode] = useState("position");
  const [fuzzyMatch, setFuzzyMatch] = useState(false);

  // ── Derived ──
  const hasMissing = useMemo(() => scanResult && scanResult.missing.length > 0, [scanResult]);

  // ── Handlers ──
  const browse = async () => {
    const selected = await open({ directory: true, multiple: false });
    if (selected) {
      setFolderPath(selected as string);
      setScanResult(null);
    }
  };

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setScanResult(null);
    try {
      const params: Record<string, unknown> = { folder_path: folderPath };
      if (dateFilterEnabled && filterDate) {
        params.filter_date = filterDate;
      }
      const res = await bridge.call<ScanResult>("batch_scan", params);
      setScanResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  };

  const doProcess = useCallback(async () => {
    if (!scanResult) return;
    setProcessing(true);
    setError(null);
    setResult(null);
    bridge.setProgress(null);
    try {
      const params: Record<string, unknown> = {
        folder_path: folderPath,
        matched: scanResult.matched,
        year: parseInt(year),
        month: parseInt(month),
        raw_start: parseInt(rawStart),
        use_ledger: useLedger,
      };

      // Table merge mode
      if (tableMergeMode === "merge") {
        params.merge_output = true;
      } else if (tableMergeMode === "table_merge") {
        params.merge_output = false;
        params.table_merge_config = { base_type: baseTableType };
      } else {
        params.merge_output = false;
      }

      // Date filter
      if (dateFilterEnabled && filterDate) {
        params.filter_date = filterDate;
      }

      // Header mapping
      if (useHeaderMapping) {
        params.use_worktime_header_mapping = true;
        params.header_mode = headerMode;
        params.fuzzy_match = fuzzyMatch;
      }

      await bridge.call("batch_process", params);
      setResult("批量处理完成");
    } catch (e) {
      const msg = String(e);
      if (msg.includes("cancel")) {
        setResult("已取消");
      } else {
        setError(msg);
      }
    } finally {
      setProcessing(false);
      bridge.setProgress(null);
    }
  }, [scanResult, folderPath, year, month, rawStart, useLedger, tableMergeMode, baseTableType, dateFilterEnabled, filterDate, useHeaderMapping, headerMode, fuzzyMatch, bridge]);

  const handleProcess = () => {
    if (hasMissing) {
      setShowConfirm(true);
    } else {
      doProcess();
    }
  };

  const handleCancel = async () => {
    await bridge.cancel();
  };

  // ═══════════════════════════════════════
  // Render
  // ═══════════════════════════════════════

  return (
    <div className="space-y-5">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">批量处理</h2>
          <p className="text-xs text-slate-400 mt-0.5">扫描文件夹并批量处理多种报表</p>
        </div>
      </div>

      {/* ════════════════════════════════════
          Section 1: Folder & Scan
          ════════════════════════════════════ */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex gap-2">
          <input
            type="text"
            value={folderPath}
            onChange={(e) => { setFolderPath(e.target.value); setScanResult(null); }}
            placeholder="选择包含报表的文件夹"
            className={`flex-1 text-sm border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-500 ${
              folderPath === "" ? "border-amber-300 bg-amber-50/30" : "border-slate-200"
            }`}
          />
          <button
            onClick={browse}
            className="shrink-0 flex items-center gap-1.5 text-sm bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-2 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
            </svg>
            浏览
          </button>
          <button
            onClick={handleScan}
            disabled={!folderPath || scanning}
            className={`shrink-0 flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg font-medium transition-colors ${
              !folderPath || scanning
                ? "bg-slate-100 text-slate-400"
                : "bg-slate-600 hover:bg-slate-700 text-white"
            }`}
          >
            {scanning ? (
              <>
                <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                扫描中...
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z"
                    clipRule="evenodd"
                  />
                </svg>
                扫描文件
              </>
            )}
          </button>
        </div>

        {/* ── Scan results as card grid ── */}
        {scanResult && (
          <div className="mt-4">
            <p className="text-xs font-medium text-slate-500 mb-3">扫描结果</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
              {Object.entries(scanResult.matched).map(([type, files]) => {
                const cfg = getTypeConfig(type);
                return (
                  <div
                    key={type}
                    className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg border ${cfg.bg} ${cfg.border} transition-colors`}
                  >
                    <span className="text-base shrink-0">{cfg.icon}</span>
                    <div className="min-w-0">
                      <p className={`text-xs font-semibold ${cfg.color} truncate`}>{cfg.label || type}</p>
                      <p className="text-[11px] text-slate-400">{(files as string[]).length} 个文件</p>
                    </div>
                    <svg className={`w-4 h-4 ml-auto shrink-0 text-green-500`} viewBox="0 0 20 20" fill="currentColor">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                );
              })}
              {scanResult.missing.map((type) => (
                <div
                  key={type}
                  className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg border bg-orange-50 border-orange-200"
                >
                  <span className="text-base shrink-0">❓</span>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-orange-600 truncate">{type}</p>
                    <p className="text-[11px] text-orange-400">未找到</p>
                  </div>
                  <svg className="w-4 h-4 ml-auto shrink-0 text-orange-400" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ════════════════════════════════════
          Section 2: Parameters
          ════════════════════════════════════ */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <svg className="w-4 h-4 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"
              clipRule="evenodd"
            />
          </svg>
          参数配置
        </h3>

        {/* ── Basic params grid ── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-slate-500 mb-1 block">年份</label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-500"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">月份</label>
            <input
              type="number"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              min={1}
              max={12}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-500"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">表头起始行</label>
            <input
              type="number"
              value={rawStart}
              onChange={(e) => setRawStart(e.target.value)}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-500"
            />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer select-none group pb-2">
              <button
                role="switch"
                aria-checked={useLedger}
                onClick={() => setUseLedger(!useLedger)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  useLedger ? "bg-cyan-500" : "bg-slate-300"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                    useLedger ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
              <span className="text-xs font-medium text-slate-600 group-hover:text-slate-800 transition-colors">
                台账匹配
              </span>
            </label>
          </div>
        </div>

        <SectionDivider label="输出方式" />

        {/* ── Table merge mode ── */}
        <div className="space-y-3">
          <ChipToggle
            value={tableMergeMode}
            onChange={(v) => setTableMergeMode(v as TableMergeMode)}
            options={[
              { label: "分表输出", value: "split", tip: "每个报表类型输出独立文件" },
              { label: "合并输出", value: "merge", tip: "所有结果合并为一个文件" },
              { label: "表内合并", value: "table_merge", tip: "以某类表为基准合并数据" },
            ]}
          />
          {tableMergeMode === "table_merge" && (
            <div className="flex items-center gap-3 pl-1">
              <span className="text-xs text-slate-500">基准表</span>
              <ChipToggle
                value={baseTableType}
                onChange={(v) => setBaseTableType(v as BaseTableType)}
                options={[
                  { label: "油耗", value: "fuel" },
                  { label: "工时", value: "worktime" },
                ]}
              />
            </div>
          )}
        </div>
      </div>

      {/* ════════════════════════════════════
          Section 3: Collapsible optional sections
          ════════════════════════════════════ */}

      {/* ── Date filter ── */}
      <Collapsible title="日期过滤" icon="📅">
        <div className="mt-3 space-y-3">
          <label className="flex items-center gap-2.5 cursor-pointer select-none group">
            <button
              role="switch"
              aria-checked={dateFilterEnabled}
              onClick={() => setDateFilterEnabled(!dateFilterEnabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                dateFilterEnabled ? "bg-cyan-500" : "bg-slate-300"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                  dateFilterEnabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
            <span className="text-sm font-medium text-slate-700 group-hover:text-slate-900 transition-colors">
              按日期过滤
            </span>
          </label>

          {dateFilterEnabled && (
            <div className="space-y-3 pl-1">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setFilterDate(shiftDate(filterDate, -1))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  上一天
                </button>
                <button
                  onClick={() => setFilterDate(formatToday())}
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  今天
                </button>
                <button
                  onClick={() => {
                    const el = document.getElementById("batch-filter-date") as HTMLInputElement | null;
                    el?.showPicker?.();
                  }}
                  className="text-xs px-3 py-1.5 rounded-lg border border-cyan-200 text-cyan-600 hover:bg-cyan-50 transition-colors"
                >
                  选择日期
                </button>
              </div>
              <div className="flex items-center gap-3">
                <label className="text-xs text-slate-500">日期</label>
                <input
                  id="batch-filter-date"
                  type="date"
                  value={filterDate}
                  onChange={(e) => setFilterDate(e.target.value)}
                  className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-500"
                />
                <span className="text-xs text-slate-400 font-mono">{filterDate}</span>
              </div>
            </div>
          )}
        </div>
      </Collapsible>

      {/* ── Header mapping ── */}
      <Collapsible title="工时表头映射" icon="📐">
        <div className="mt-3 space-y-3">
          <label className="flex items-center gap-2.5 cursor-pointer select-none group">
            <button
              role="switch"
              aria-checked={useHeaderMapping}
              onClick={() => setUseHeaderMapping(!useHeaderMapping)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                useHeaderMapping ? "bg-cyan-500" : "bg-slate-300"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                  useHeaderMapping ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
            <span className="text-sm font-medium text-slate-700 group-hover:text-slate-900 transition-colors">
              启用表头映射
            </span>
          </label>

          {useHeaderMapping && (
            <div className="space-y-3 pl-1">
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500">映射模式</span>
                <ChipToggle
                  value={headerMode}
                  onChange={setHeaderMode}
                  options={[
                    { label: "位置映射", value: "position" },
                    { label: "名称映射", value: "name" },
                  ]}
                />
              </div>
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={fuzzyMatch}
                  onChange={(e) => setFuzzyMatch(e.target.checked)}
                  className="rounded border-slate-300"
                />
                <span className="text-xs text-slate-600">启用模糊匹配</span>
              </label>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                映射规则可在「用户配置 &rarr; 工作效率表头映射配置」中编辑
              </p>
            </div>
          )}
        </div>
      </Collapsible>

      {/* ════════════════════════════════════
          Section 4: Progress
          ════════════════════════════════════ */}
      {processing && bridge.progress && (
        <AnimatedProgressBar
          percent={bridge.progress.percent}
          stage={bridge.progress.stage}
          detail={bridge.progress.detail}
        />
      )}

      {/* ════════════════════════════════════
          Section 5: Actions
          ════════════════════════════════════ */}
      <div className="flex gap-3">
        <button
          onClick={handleProcess}
          disabled={!scanResult || processing}
          className={`flex items-center gap-2 text-sm font-medium px-6 py-2.5 rounded-lg transition-colors ${
            !scanResult || processing
              ? "bg-slate-100 text-slate-400 cursor-not-allowed"
              : "bg-cyan-600 hover:bg-cyan-700 text-white"
          }`}
        >
          {!processing && (
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"
                clipRule="evenodd"
              />
            </svg>
          )}
          {processing ? "处理中..." : "开始批量处理"}
        </button>
        {processing && <PulsingCancelButton onClick={handleCancel} />}
      </div>

      {/* ── Result / Error ── */}
      {result && (
        <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
              clipRule="evenodd"
            />
          </svg>
          {result}
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clipRule="evenodd"
            />
          </svg>
          {error}
        </div>
      )}

      {/* ════════════════════════════════════
          Confirmation Dialog
          ════════════════════════════════════ */}
      {showConfirm && scanResult && (
        <ConfirmDialog
          title="部分文件缺失"
          message="扫描发现以下报表类型未找到对应文件，继续处理将仅处理已有数据。是否继续？"
          details={scanResult.missing}
          confirmLabel="继续处理"
          cancelLabel="返回"
          onConfirm={() => { setShowConfirm(false); doProcess(); }}
          onCancel={() => setShowConfirm(false)}
        />
      )}

      {/* ── Inline keyframes for gradient animation ── */}
      <style>{`
        @keyframes gradient-shift {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        .animate-gradient-shift {
          animation: gradient-shift 2s ease infinite;
        }
      `}</style>
    </div>
  );
}
