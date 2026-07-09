import { useState, useMemo, useCallback } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import type { BridgeProp, BatchProgress, ScanResult } from "../../lib/types";
import { useToast } from "../Toast";
import { FolderIcon } from "../../lib/icons";
import { inputClass, btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { useLastDirectory } from "../../hooks/useLastDirectory";

// ═══════════════════════════════════════
// Types
// ═══════════════════════════════════════

interface BatchBridgeProp extends BridgeProp {
  cancel: () => Promise<void>;
  progress: BatchProgress | null;
  setProgress: (p: BatchProgress | null) => void;
}

type TableMergeMode = "split" | "merge" | "table_merge";
type BaseTableType = "fuel" | "worktime";

// ═══════════════════════════════════════
// Lucide-style SVG Icons (16x16, stroke-width 2)
// ═══════════════════════════════════════

const SearchIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
);

const SettingsIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
  </svg>
);

const CalendarIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
);

const RulerIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21.3 15.3a2.4 2.4 0 010 3.4l-2.6 2.6a2.4 2.4 0 01-3.4 0L2.7 8.7a2.4 2.4 0 010-3.4l2.6-2.6a2.4 2.4 0 013.4 0z" />
    <path d="M14.5 12.5l2-2" />
    <path d="M11.5 9.5l2-2" />
    <path d="M8.5 6.5l2-2" />
    <path d="M17.5 15.5l2-2" />
  </svg>
);

const PlayIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-3.5 h-3.5 shrink-0 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const XIcon = () => (
  <svg className="w-3.5 h-3.5 shrink-0 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const StopCircleIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <rect x="9" y="9" width="6" height="6" />
  </svg>
);

const CheckCircleIcon = () => (
  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);

const XCircleIcon = () => (
  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />
  </svg>
);

const AlertTriangleIcon = () => (
  <svg className="w-5 h-5 text-amber-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

/** 16x16 module icons for scan results */
const FuelIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);

const ProductionIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const ElectricalIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);

const WorktimeIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

const MergeIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" />
    <polyline points="2 12 12 17 22 12" />
  </svg>
);

const QuestionIcon = () => (
  <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

// ═══════════════════════════════════════
// Constants
// ═══════════════════════════════════════

const dataTypeConfig: Record<string, { icon: React.ReactNode; label: string }> = {
  油耗:       { icon: <FuelIcon />,         label: "油耗" },
  生产:       { icon: <ProductionIcon />,   label: "生产" },
  电力:       { icon: <ElectricalIcon />,   label: "电力" },
  工时:       { icon: <WorktimeIcon />,     label: "工时" },
  production: { icon: <ProductionIcon />,   label: "生产" },
  fuel:       { icon: <FuelIcon />,         label: "油耗" },
  electrical: { icon: <ElectricalIcon />,   label: "电力" },
  worktime:   { icon: <WorktimeIcon />,     label: "工时" },
  merge:      { icon: <MergeIcon />,        label: "合并" },
};

function getTypeConfig(type: string) {
  return dataTypeConfig[type] ?? { icon: <QuestionIcon />, label: type };
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

/** Collapsible section with chevron icon */
function Collapsible({
  title,
  icon,
  defaultOpen = false,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
      >
        {icon && <span className="text-slate-400">{icon}</span>}
        <span className="flex-1 text-left">{title}</span>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      <div
        className="overflow-hidden transition-all duration-300 ease-in-out"
        style={{ maxHeight: open ? "500px" : "0px", opacity: open ? 1 : 0 }}
      >
        <div className="px-4 pb-4 border-t border-slate-100">{children}</div>
      </div>
    </div>
  );
}

/** Section divider with optional label */
function SectionDivider({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 my-4">
      <div className="flex-1 h-px bg-slate-200" />
      {label && <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</span>}
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
    <div className="inline-flex rounded-md border border-slate-200 overflow-hidden">
      {options.map((o, i) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          title={o.tip}
          className={`text-xs px-3 py-1.5 transition-colors ${
            value === o.value
              ? "bg-slate-900 text-white"
              : "bg-white text-slate-600 hover:bg-slate-50"
          } ${i > 0 ? "border-l border-slate-200" : ""}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Toggle switch — restrained design */
function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer select-none">
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
          checked ? "bg-blue-600" : "bg-slate-200"
        }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
            checked ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>
      <span className="text-sm text-slate-700">{label}</span>
    </label>
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
      <div className="bg-white rounded-lg shadow-lg max-w-md w-full mx-4 overflow-hidden">
        <div className="px-6 pt-6 pb-2">
          <div className="flex items-center gap-3 mb-3">
            <div className="shrink-0 w-9 h-9 rounded-md bg-amber-50 flex items-center justify-center">
              <AlertTriangleIcon />
            </div>
            <h3 className="text-base font-semibold text-slate-800">{title}</h3>
          </div>
          <p className="text-sm text-slate-600 leading-relaxed">{message}</p>
          {details && details.length > 0 && (
            <ul className="mt-3 space-y-1">
              {details.map((d, i) => (
                <li key={i} className="flex items-center gap-2 text-xs text-slate-500">
                  <span className="w-1 h-1 rounded-full bg-slate-400 shrink-0" />
                  {d}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex gap-3 px-6 py-4 bg-slate-50 border-t border-slate-100">
          <button
            onClick={onCancel}
            className="flex-1 text-sm font-medium px-4 py-1.5 rounded-md border border-slate-300 text-slate-700 hover:bg-slate-100 transition-colors"
          >
            {cancelLabel ?? "取消"}
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 text-sm font-medium px-4 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 text-white transition-colors"
          >
            {confirmLabel ?? "继续处理"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// Progress bar — restrained
// ═══════════════════════════════════════

function ProgressBar({ percent, stage, detail }: { percent: number; stage: string; detail: string }) {
  const pct = Math.round(percent * 100);
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-slate-500 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm font-medium text-slate-700">{stage}</span>
        </div>
        <span className="text-xs font-mono text-slate-500">{pct}%</span>
      </div>
      <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-1.5 rounded-full bg-blue-600 transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      {detail && <p className="mt-2 text-xs text-slate-400 truncate">{detail}</p>}
    </div>
  );
}

// ═══════════════════════════════════════
// Main page component
// ═══════════════════════════════════════

export function BatchProcessingPage({ bridge }: { bridge: BatchBridgeProp }) {
  // -- Path & scan --
  const { notify } = useToast();
  const { initialDir, saveDir } = useLastDirectory(bridge);
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

  // -- Output mode --
  const [tableMergeMode, setTableMergeMode] = useState<TableMergeMode>("merge");
  const [baseTableType, setBaseTableType] = useState<BaseTableType>("fuel");

  // -- Ledger --
  const [useEquipmentLedger, setUseEquipmentLedger] = useState(false);
  const [useOilLedger, setUseOilLedger] = useState(false);
  const [skipHiddenRows, setSkipHiddenRows] = useState(false);
  const [skipHiddenCols, setSkipHiddenCols] = useState(false);

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
    const selected = await open({ directory: true, multiple: false, defaultPath: initialDir || undefined });
    if (selected) {
      const dir = selected as string;
      setFolderPath(dir);
      setScanResult(null);
      saveDir(dir);
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
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
      };

      if (tableMergeMode === "merge") {
        params.merge_output = true;
      } else if (tableMergeMode === "table_merge") {
        params.merge_output = false;
        params.table_merge_config = { base_type: baseTableType };
      } else {
        params.merge_output = false;
      }

      if (dateFilterEnabled && filterDate) {
        params.filter_date = filterDate;
      }

      if (useHeaderMapping) {
        params.use_worktime_header_mapping = true;
        params.header_mode = headerMode;
        params.fuzzy_match = fuzzyMatch;
      }

      await bridge.call("batch_process", params);
      setResult("批量处理完成");
      notify("批量处理完成", "success");
    } catch (e) {
      const msg = String(e);
      if (msg.includes("cancel")) {
        setResult("已取消");
        notify("批量处理已取消", "info");
      } else {
        setError(msg);
        notify(`批量处理失败: ${msg}`, "error");
      }
    } finally {
      setProcessing(false);
      bridge.setProgress(null);
    }
  }, [scanResult, folderPath, year, month, rawStart, useEquipmentLedger, useOilLedger, skipHiddenRows, skipHiddenCols, tableMergeMode, baseTableType, dateFilterEnabled, filterDate, useHeaderMapping, headerMode, fuzzyMatch, bridge]);

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
          <p className="text-sm text-slate-500">扫描文件夹并批量处理多种报表</p>
        </div>
      </div>

      {/* ════════════════════════════════════
          Section 1: Folder & Scan
          ════════════════════════════════════ */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={folderPath}
            onChange={(e) => { setFolderPath(e.target.value); setScanResult(null); }}
            placeholder="选择包含报表的文件夹"
            className={`${inputClass} flex-1 ${folderPath === "" ? "border-amber-300 bg-amber-50/30" : ""}`}
          />
          <button onClick={browse} className={btnSecondaryClass}>
            <FolderIcon />
            浏览
          </button>
          <button
            onClick={handleScan}
            disabled={!folderPath || scanning}
            className={`shrink-0 flex items-center gap-1.5 text-sm px-3.5 py-1.5 rounded-md font-medium transition-colors ${
              !folderPath || scanning
                ? "bg-slate-100 text-slate-400"
                : "bg-slate-900 hover:bg-slate-800 text-white"
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
                <SearchIcon />
                扫描文件
              </>
            )}
          </button>
        </div>

        {/* ── Scan results as simple text list ── */}
        {scanResult && (
          <div className="mt-3 space-y-1.5">
            {Object.entries(scanResult.matched).map(([type, files]) => {
              const cfg = getTypeConfig(type);
              return (
                <div key={type} className="flex items-center gap-2 text-sm text-slate-700 py-1">
                  <CheckIcon />
                  <span className="text-slate-500">{cfg.icon}</span>
                  <span className="text-slate-700">{cfg.label || type}</span>
                  <span className="text-xs text-slate-400">({(files as string[]).length} 个文件)</span>
                </div>
              );
            })}
            {scanResult.missing.map((type) => (
              <div key={type} className="flex items-center gap-2 text-sm py-1">
                <XIcon />
                <QuestionIcon />
                <span className="text-slate-500">{type}</span>
                <span className="text-xs text-slate-400">未找到</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ════════════════════════════════════
          Section 2: Parameters
          ════════════════════════════════════ */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-medium text-slate-700 mb-3 flex items-center gap-2">
          <SettingsIcon />
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
              className={inputClass}
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
              className={inputClass}
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">表头起始行</label>
            <input
              type="number"
              value={rawStart}
              onChange={(e) => setRawStart(e.target.value)}
              className={inputClass}
            />
          </div>
          <div className="flex items-end pb-0.5">
            <Toggle
              checked={useEquipmentLedger}
              onChange={setUseEquipmentLedger}
              label="设备台账匹配"
            />
          </div>
          <div className="flex items-end pb-0.5">
            <Toggle
              checked={useOilLedger}
              onChange={setUseOilLedger}
              label="油品台账匹配"
            />
          </div>
          <div className="flex items-end pb-0.5">
            <Toggle
              checked={skipHiddenRows}
              onChange={setSkipHiddenRows}
              label="跳过隐藏行"
            />
          </div>
          <div className="flex items-end pb-0.5">
            <Toggle
              checked={skipHiddenCols}
              onChange={setSkipHiddenCols}
              label="跳过隐藏列"
            />
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
      <Collapsible title="日期过滤" icon={<CalendarIcon />}>
        <div className="mt-3 space-y-3">
          <Toggle
            checked={dateFilterEnabled}
            onChange={setDateFilterEnabled}
            label="按日期过滤"
          />

          {dateFilterEnabled && (
            <div className="space-y-3 pl-1">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setFilterDate(shiftDate(filterDate, -1))}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  上一天
                </button>
                <button
                  onClick={() => setFilterDate(formatToday())}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  今天
                </button>
                <button
                  onClick={() => {
                    const el = document.getElementById("batch-filter-date") as HTMLInputElement | null;
                    el?.showPicker?.();
                  }}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors flex items-center gap-1"
                >
                  <CalendarIcon />
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
                  className={`${inputClass} w-auto`}
                />
                <span className="text-xs text-slate-400 font-mono">{filterDate}</span>
              </div>
            </div>
          )}
        </div>
      </Collapsible>

      {/* ── Header mapping ── */}
      <Collapsible title="工时表头映射" icon={<RulerIcon />}>
        <div className="mt-3 space-y-3">
          <Toggle
            checked={useHeaderMapping}
            onChange={setUseHeaderMapping}
            label="启用表头映射"
          />

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
              <p className="text-xs text-slate-400 leading-relaxed">
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
        <ProgressBar
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
          className={`${btnPrimaryClass} flex items-center gap-2`}
        >
          {!processing && <PlayIcon />}
          {processing ? "处理中..." : "开始批量处理"}
        </button>
        {processing && (
          <button
            onClick={handleCancel}
            className="flex items-center gap-1.5 text-sm text-red-600 hover:text-red-700 transition-colors px-3.5 py-1.5"
          >
            <StopCircleIcon />
            取消
          </button>
        )}
      </div>

      {/* ── Result / Error ── */}
      {result && (
        <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 rounded-md px-2.5 py-1.5">
          <CheckCircleIcon />
          {result}
        </div>
      )}
      {error && (
        <div className="flex items-start gap-2 text-xs text-red-700 bg-red-50 rounded-md px-2.5 py-1.5">
          <XCircleIcon />
          <span>{error}</span>
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
    </div>
  );
}
