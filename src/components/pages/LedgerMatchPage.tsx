import { useState, useRef } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

type ViewMode = "all" | "matched" | "unmatched";

interface MatchToggle {
  enabled: boolean;
  column: string;
}

interface SortState {
  column: string;
  direction: "asc" | "desc";
}

/* ── Inline SVG Icons (Lucide-style, stroke-width 2, 20x20) ── */

const UploadCloudIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
    <path d="M12 12v9" />
    <path d="m16 16-4-4-4 4" />
  </svg>
);

const TagIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z" />
    <circle cx="7.5" cy="7.5" r=".5" fill="currentColor" />
  </svg>
);

const HashIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <line x1="4" x2="20" y1="9" y2="9" />
    <line x1="4" x2="20" y1="15" y2="15" />
    <line x1="10" x2="8" y1="3" y2="21" />
    <line x1="16" x2="14" y1="3" y2="21" />
  </svg>
);

const DropletIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z" />
  </svg>
);

const ArrowUpIcon = ({ className = "w-3 h-3" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="m5 12 7-7 7 7" />
    <path d="M12 19V5" />
  </svg>
);

const ArrowDownIcon = ({ className = "w-3 h-3" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5v14" />
    <path d="m19 12-7 7-7-7" />
  </svg>
);

const ChevronsUpDownIcon = ({ className = "w-3 h-3" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="m7 15 5 5 5-5" />
    <path d="m7 9 5-5 5 5" />
  </svg>
);

const ChevronDownIcon = ({ className = "w-3.5 h-3.5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="m6 9 6 6 6-6" />
  </svg>
);

const DownloadIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" x2="12" y1="15" y2="3" />
  </svg>
);

const TrashIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18" />
    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
  </svg>
);

const SearchIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </svg>
);

const LayersIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z" />
    <path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65" />
    <path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65" />
  </svg>
);

const FolderOpenIcon = ({ className = "w-12 h-12" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1} strokeLinecap="round" strokeLinejoin="round">
    <path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2" />
  </svg>
);

const CheckCircleIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <path d="m9 11 3 3L22 4" />
  </svg>
);

const AlertCircleIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" x2="12" y1="8" y2="12" />
    <line x1="12" x2="12.01" y1="16" y2="16" />
  </svg>
);

const LoaderIcon = ({ className = "w-4 h-4 animate-spin" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);

const PlayIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <polygon points="6 3 20 12 6 21 6 3" />
  </svg>
);

const InfoIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <path d="M12 16v-4" />
    <path d="M12 8h.01" />
  </svg>
);

const ChevronLeftIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="m15 18-6-6 6-6" />
  </svg>
);

const ChevronRightIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="m9 18 6-6-6-6" />
  </svg>
);

const ColumnsIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
    <line x1="12" x2="12" y1="3" y2="21" />
  </svg>
);

/* ── Styled Toggle Switch (same as DataProcessingPage) ── */

function StyledToggle({
  checked,
  onChange,
  label,
  icon,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  icon: React.ReactNode;
}) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer select-none group">
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-10 items-center rounded-full transition-colors ${
          checked ? "bg-emerald-500" : "bg-slate-200"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
            checked ? "translate-x-5" : "translate-x-1"
          }`}
        />
      </button>
      <span className={`flex items-center gap-1.5 text-sm font-medium transition-colors ${
        checked ? "text-emerald-700" : "text-slate-500"
      } group-hover:text-slate-900`}>
        {icon}
        {label}
      </span>
    </label>
  );
}

/* ── Percentage Ring ── */

function PercentageRing({ percent, size = 40 }: { percent: number; size?: number }) {
  const r = (size - 4) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <svg width={size} height={size} className="shrink-0 -rotate-90">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="#e2e8f0"
        strokeWidth={3}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="#10b981"
        strokeWidth={3}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ── Main Component ── */

export function LedgerMatchPage({ bridge }: { bridge: BridgeProp }) {
  const [filePath, setFilePath] = useState("");
  const [sheetName, setSheetName] = useState("");
  const [availableSheets, setAvailableSheets] = useState<string[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [matchedCount, setMatchedCount] = useState(0);
  const [unmatchedCount, setUnmatchedCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [matching, setMatching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<SortState | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [showClearDialog, setShowClearDialog] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);
  const PAGE_SIZE = 20;

  // Independent match toggles
  const [nameToggle, setNameToggle] = useState<MatchToggle>({ enabled: false, column: "" });
  const [idToggle, setIdToggle] = useState<MatchToggle>({ enabled: false, column: "" });
  const [oilToggle, setOilToggle] = useState<MatchToggle>({ enabled: false, column: "" });

  // Dual-column production matching
  const [hasDualColumns, setHasDualColumns] = useState(false);
  const [dualTruckCol, setDualTruckCol] = useState("");
  const [dualExcavatorCol, setDualExcavatorCol] = useState("");

  // --- Auto-detection helpers ---

  const autoDetectNameColumn = (cols: string[]): string =>
    cols.find((c) => /名称|设备|矿卡|挖机/.test(c) && !/油品|油种|编号|ID/i.test(c)) || "";

  const autoDetectIdColumn = (cols: string[]): string =>
    cols.find((c) => /编号|ID/i.test(c)) || "";

  const autoDetectOilColumn = (cols: string[]): string =>
    cols.find((c) => /油品|油种/.test(c)) || "";

  const autoDetectDualColumns = (cols: string[]) => {
    const truckCol = cols.find((c) => /矿卡.*名称|矿卡名称/.test(c)) || "";
    const excavCol = cols.find((c) => /挖机.*名称|挖机名称/.test(c)) || "";
    return { truckCol, excavCol };
  };

  // --- File operations ---

  const browseFile = async () => {
    const selected = await open({
      multiple: false,
      filters: [{ name: "Excel", extensions: ["xlsx", "xls"] }],
    });
    if (selected) {
      setFilePath(selected as string);
      resetData();
      loadSheets(selected as string);
    }
  };

  const resetData = () => {
    setRows([]);
    setColumns([]);
    setAvailableSheets([]);
    setMatchedCount(0);
    setUnmatchedCount(0);
    setSort(null);
    setPage(0);
    setNameToggle({ enabled: false, column: "" });
    setIdToggle({ enabled: false, column: "" });
    setOilToggle({ enabled: false, column: "" });
    setHasDualColumns(false);
    setDualTruckCol("");
    setDualExcavatorCol("");
  };

  const loadSheets = async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await bridge.call<{ sheets: string[] }>("list_excel_sheets", { path });
      setAvailableSheets(res.sheets || []);
      if (res.sheets?.length) {
        setSheetName(res.sheets[0]);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const loadSheet = async () => {
    if (!filePath || !sheetName) return;
    setLoading(true);
    setError(null);
    try {
      const res = await bridge.call<{ columns: string[]; rows: Record<string, unknown>[] }>(
        "read_excel_sheet",
        { path: filePath, sheet: sheetName }
      );
      const cols = res.columns || [];
      const rowData = res.rows || [];
      setColumns(cols);
      setRows(rowData);
      setMatchedCount(0);
      setUnmatchedCount(0);
      setSort(null);
      setPage(0);

      // Auto-detect columns
      const detectedName = autoDetectNameColumn(cols);
      const detectedId = autoDetectIdColumn(cols);
      const detectedOil = autoDetectOilColumn(cols);
      const { truckCol, excavCol } = autoDetectDualColumns(cols);

      setNameToggle({
        enabled: !!detectedName,
        column: detectedName,
      });
      setIdToggle({
        enabled: !!detectedId && !detectedName,
        column: detectedId,
      });
      setOilToggle({
        enabled: !!detectedOil,
        column: detectedOil,
      });

      if (truckCol && excavCol) {
        setHasDualColumns(true);
        setDualTruckCol(truckCol);
        setDualExcavatorCol(excavCol);
        // Enable name toggle for dual mode
        if (!detectedName) {
          setNameToggle({ enabled: true, column: truckCol });
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  // --- Matching ---

  const handleMatch = async () => {
    if (!rows.length) return;
    if (!nameToggle.enabled && !idToggle.enabled && !oilToggle.enabled) {
      setError("请至少启用一种匹配方式");
      return;
    }
    setMatching(true);
    setError(null);
    try {
      if (hasDualColumns && dualTruckCol && dualExcavatorCol) {
        // Dual-column matching: run two separate matches
        const truckRes = await bridge.call<{
          matched: number; unmatched: number; rows: Record<string, unknown>[];
        }>("ledger_match_preview", {
          rows,
          name_column: dualTruckCol,
          oil_column: oilToggle.enabled ? oilToggle.column : null,
          mode: "name",
          result_suffix: "矿卡",
        });
        const excavRes = await bridge.call<{
          matched: number; unmatched: number; rows: Record<string, unknown>[];
        }>("ledger_match_preview", {
          rows: truckRes.rows,
          name_column: dualExcavatorCol,
          oil_column: oilToggle.enabled ? oilToggle.column : null,
          mode: "name",
          result_suffix: "挖机",
        });
        setRows(excavRes.rows || []);
        const totalMatched = (excavRes.rows || []).filter((r) =>
          r["__matched_矿卡"] === true || r["__matched_挖机"] === true
        ).length;
        const totalUnmatched = (excavRes.rows || []).length - totalMatched;
        setMatchedCount(totalMatched);
        setUnmatchedCount(totalUnmatched);
        if (excavRes.rows?.length) {
          setColumns(Object.keys(excavRes.rows[0]));
        }
      } else {
        // Single or combined matching
        const res = await bridge.call<{
          matched: number; unmatched: number; rows: Record<string, unknown>[];
        }>("ledger_match_preview", {
          rows,
          name_column: nameToggle.enabled ? nameToggle.column : null,
          id_column: idToggle.enabled ? idToggle.column : null,
          oil_column: oilToggle.enabled ? oilToggle.column : null,
          mode: nameToggle.enabled ? "name" : "id",
        });
        setRows(res.rows || []);
        setMatchedCount(res.matched || 0);
        setUnmatchedCount(res.unmatched || 0);
        if (res.rows?.length) {
          setColumns(Object.keys(res.rows[0]));
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setMatching(false);
    }
  };

  // --- Clear ---

  const handleClear = () => {
    resetData();
    setShowClearDialog(false);
  };

  // --- Export ---

  const handleExport = async (exportAll: boolean) => {
    setShowExportMenu(false);
    const outputPath = await save({
      filters: [{ name: "Excel", extensions: ["xlsx"] }],
      defaultPath: `${sheetName}_matched.xlsx`,
    });
    if (!outputPath) return;
    const dataToExport = exportAll ? rows : filtered;
    try {
      await bridge.call("export_matched_data", {
        rows: dataToExport,
        columns,
        output_path: outputPath,
      });
    } catch (e) {
      setError(String(e));
    }
  };

  // --- Sorting ---

  const handleSort = (col: string) => {
    setSort((prev) => {
      if (prev?.column === col) {
        if (prev.direction === "asc") return { column: col, direction: "desc" };
        return null; // cycle: asc -> desc -> none
      }
      return { column: col, direction: "asc" };
    });
    setPage(0);
  };

  // --- Filtering + Sorting + Paging ---

  const getMatchStatus = (row: Record<string, unknown>): boolean => {
    if (hasDualColumns) {
      return row["__matched_矿卡"] === true || row["__matched_挖机"] === true;
    }
    return row["__matched"] === true;
  };

  const filtered = viewMode === "all"
    ? rows
    : viewMode === "matched"
      ? rows.filter((r) => getMatchStatus(r))
      : rows.filter((r) => !getMatchStatus(r));

  const sorted = sort
    ? [...filtered].sort((a, b) => {
        const aVal = a[sort.column] ?? "";
        const bVal = b[sort.column] ?? "";
        const cmp = String(aVal).localeCompare(String(bVal), "zh-CN", { numeric: true });
        return sort.direction === "asc" ? cmp : -cmp;
      })
    : filtered;

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paged = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const displayColumns = columns.filter((c) => !c.startsWith("__matched"));

  const anyToggleEnabled = nameToggle.enabled || idToggle.enabled || oilToggle.enabled;

  // Close export menu on outside click
  const handleExportBlur = () => {
    setTimeout(() => setShowExportMenu(false), 150);
  };

  const matchRate = matchedCount + unmatchedCount > 0
    ? ((matchedCount / (matchedCount + unmatchedCount)) * 100).toFixed(1)
    : "0.0";

  const totalRowCount = rows.length;
  const viewCounts = {
    all: totalRowCount,
    matched: matchedCount,
    unmatched: unmatchedCount,
  };

  return (
    <div className="max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-slate-100 text-slate-600">
          <LayersIcon className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-slate-800 leading-tight">台账匹配</h2>
          <p className="text-xs text-slate-500 mt-0.5">将 Excel 数据与设备台账进行模糊匹配</p>
        </div>
      </div>

      {/* ── File Selection Drop Zone ── */}
      <div
        className={`rounded-xl border-2 border-dashed p-6 mb-5 transition-all ${
          dragOver
            ? "border-blue-400 bg-blue-50/30 shadow-sm"
            : filePath
              ? "border-slate-200 bg-white"
              : "border-slate-300 bg-white"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const files = e.dataTransfer.files;
          if (files?.[0]?.name?.match(/\.xlsx?$/i)) {
            const path = (files[0] as unknown as { path?: string }).path || files[0].name;
            setFilePath(path);
            resetData();
            loadSheets(path);
          }
        }}
      >
        {/* Drop zone content when no file */}
        {!filePath && (
          <div
            className="flex flex-col items-center justify-center py-4 cursor-pointer"
            onClick={browseFile}
          >
            <div className={`mb-3 p-3 rounded-full transition-colors ${
              dragOver ? "bg-blue-100 text-blue-500" : "bg-slate-100 text-slate-400"
            }`}>
              <UploadCloudIcon className="w-8 h-8" />
            </div>
            <p className="text-sm font-medium text-slate-600 mb-1">
              拖拽 Excel 文件到此处，或点击浏览
            </p>
            <p className="text-xs text-slate-400">支持 .xlsx / .xls 格式</p>
          </div>
        )}

        {/* File input row when file is selected */}
        {filePath && (
          <div className="flex gap-2 mb-3">
            <div className="relative flex-1">
              <input
                type="text"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                placeholder="选择 Excel 文件"
                className="input pr-20"
              />
              {filePath && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2">
                  <CheckCircleIcon className="w-4 h-4 text-emerald-500" />
                </span>
              )}
            </div>
            <button
              onClick={browseFile}
              className="btn-secondary flex items-center gap-1.5 shrink-0"
            >
              <UploadCloudIcon className="w-4 h-4" />
              浏览
            </button>
            <button
              onClick={() => setShowClearDialog(true)}
              className="btn-danger flex items-center gap-1.5 shrink-0"
            >
              <TrashIcon />
              清空
            </button>
          </div>
        )}

        {/* Sheet selector as styled tabs */}
        {availableSheets.length > 0 && (
          <div className="flex items-center gap-3">
            <ColumnsIcon className="w-4 h-4 text-slate-400 shrink-0" />
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5 overflow-x-auto thin-scrollbar">
              {availableSheets.map((s) => (
                <button
                  key={s}
                  onClick={() => setSheetName(s)}
                  className={`text-xs px-3 py-1.5 rounded-md whitespace-nowrap transition-all ${
                    sheetName === s
                      ? "bg-white text-slate-800 shadow-sm font-medium"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
            <button
              onClick={loadSheet}
              disabled={loading}
              className="btn-primary flex items-center gap-1.5 shrink-0 ml-auto"
            >
              {loading ? (
                <>
                  <LoaderIcon className="w-4 h-4 animate-spin" />
                  加载中
                </>
              ) : (
                "加载"
              )}
            </button>
          </div>
        )}
      </div>

      {/* ── Match Configuration ── */}
      {columns.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <SearchIcon className="w-4 h-4 text-slate-400" />
            匹配配置
          </h3>

          {/* Three toggle switches in a row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-5">
            {/* Name match */}
            <div className={`rounded-lg border p-4 transition-all ${
              nameToggle.enabled
                ? "border-emerald-300 bg-emerald-50/30"
                : "border-slate-200 bg-slate-50/50"
            }`}>
              <div className="mb-3">
                <StyledToggle
                  checked={nameToggle.enabled}
                  onChange={(v) => setNameToggle((p) => ({ ...p, enabled: v }))}
                  label="设备名称匹配"
                  icon={<TagIcon className="w-4 h-4" />}
                />
              </div>
              <select
                value={nameToggle.column}
                onChange={(e) => setNameToggle((p) => ({ ...p, column: e.target.value }))}
                disabled={!nameToggle.enabled}
                className="input text-xs disabled:opacity-40 disabled:bg-slate-50 disabled:cursor-not-allowed"
              >
                <option value="">选择列</option>
                {columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* ID match */}
            <div className={`rounded-lg border p-4 transition-all ${
              idToggle.enabled
                ? "border-emerald-300 bg-emerald-50/30"
                : "border-slate-200 bg-slate-50/50"
            }`}>
              <div className="mb-3">
                <StyledToggle
                  checked={idToggle.enabled}
                  onChange={(v) => setIdToggle((p) => ({ ...p, enabled: v }))}
                  label="设备编号匹配"
                  icon={<HashIcon className="w-4 h-4" />}
                />
              </div>
              <select
                value={idToggle.column}
                onChange={(e) => setIdToggle((p) => ({ ...p, column: e.target.value }))}
                disabled={!idToggle.enabled}
                className="input text-xs disabled:opacity-40 disabled:bg-slate-50 disabled:cursor-not-allowed"
              >
                <option value="">选择列</option>
                {columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Oil match */}
            <div className={`rounded-lg border p-4 transition-all ${
              oilToggle.enabled
                ? "border-emerald-300 bg-emerald-50/30"
                : "border-slate-200 bg-slate-50/50"
            }`}>
              <div className="mb-3">
                <StyledToggle
                  checked={oilToggle.enabled}
                  onChange={(v) => setOilToggle((p) => ({ ...p, enabled: v }))}
                  label="油品匹配"
                  icon={<DropletIcon className="w-4 h-4" />}
                />
              </div>
              <select
                value={oilToggle.column}
                onChange={(e) => setOilToggle((p) => ({ ...p, column: e.target.value }))}
                disabled={!oilToggle.enabled}
                className="input text-xs disabled:opacity-40 disabled:bg-slate-50 disabled:cursor-not-allowed"
              >
                <option value="">选择列</option>
                {columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Dual-column detection */}
          {hasDualColumns && (
            <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50/40 p-4">
              <div className="flex items-center gap-2 mb-2">
                <InfoIcon className="w-4 h-4 text-amber-600" />
                <span className="text-xs font-semibold text-amber-700">双列生产模式已检测</span>
                <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse-subtle" />
              </div>
              <div className="flex gap-4 text-xs text-slate-600">
                <span>矿卡列: <code className="font-mono text-slate-800 bg-amber-100/60 px-1.5 py-0.5 rounded">{dualTruckCol}</code></span>
                <span>挖机列: <code className="font-mono text-slate-800 bg-amber-100/60 px-1.5 py-0.5 rounded">{dualExcavatorCol}</code></span>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                匹配结果将生成 "标准设备名称（矿卡）" 和 "标准设备名称（挖机）" 两列
              </p>
            </div>
          )}

          {/* Match button + Stats bar */}
          <div className="flex items-center gap-4 flex-wrap">
            <button
              onClick={handleMatch}
              disabled={!anyToggleEnabled || matching}
              className={`btn-primary flex items-center gap-2 ${
                !anyToggleEnabled || matching ? "" : "bg-emerald-600 hover:bg-emerald-700"
              }`}
            >
              {matching ? (
                <>
                  <LoaderIcon className="w-4 h-4 animate-spin" />
                  匹配中
                </>
              ) : (
                <>
                  <PlayIcon className="w-4 h-4" />
                  开始匹配
                </>
              )}
            </button>

            {/* Stats cards */}
            {matchedCount + unmatchedCount > 0 && (
              <div className="flex items-center gap-3 ml-auto flex-wrap">
                {/* Total */}
                <div className="flex items-center gap-2.5 bg-slate-50 border border-slate-200 rounded-lg px-4 py-3">
                  <LayersIcon className="w-4 h-4 text-slate-400" />
                  <div>
                    <span className="text-xs text-slate-500 block">全部</span>
                    <span className="text-base font-bold text-slate-800 tabular-nums">{matchedCount + unmatchedCount}</span>
                  </div>
                </div>

                {/* Matched */}
                <div className="flex items-center gap-2.5 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3">
                  <PercentageRing percent={parseFloat(matchRate)} size={36} />
                  <div>
                    <span className="text-xs text-emerald-600 block">已匹配</span>
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-base font-bold text-emerald-800 tabular-nums">{matchedCount}</span>
                      <span className="text-xs text-emerald-500 tabular-nums">{matchRate}%</span>
                    </div>
                  </div>
                </div>

                {/* Unmatched */}
                <div className="flex items-center gap-2.5 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
                  <AlertCircleIcon className="w-4 h-4 text-amber-500" />
                  <div>
                    <span className="text-xs text-amber-600 block">未匹配</span>
                    <span className="text-base font-bold text-amber-800 tabular-nums">{unmatchedCount}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── View Mode Toggle + Toolbar ── */}
      {rows.length > 0 && (
        <div className="flex items-center justify-between mb-4">
          {/* Segmented control */}
          <div className="inline-flex bg-slate-100 rounded-lg p-0.5">
            {([
              { id: "all" as ViewMode, label: "全部", count: viewCounts.all },
              { id: "matched" as ViewMode, label: "已匹配", count: viewCounts.matched },
              { id: "unmatched" as ViewMode, label: "未匹配", count: viewCounts.unmatched },
            ]).map((v) => (
              <button
                key={v.id}
                onClick={() => { setViewMode(v.id); setPage(0); }}
                className={`text-xs px-4 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
                  viewMode === v.id
                    ? "bg-white text-slate-800 shadow-sm font-medium"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {v.label}
                <span className={`inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full text-[10px] font-semibold tabular-nums ${
                  viewMode === v.id
                    ? "bg-slate-800 text-white"
                    : "bg-slate-200 text-slate-500"
                }`}>
                  {v.count}
                </span>
              </button>
            ))}
          </div>

          <div className="flex gap-2">
            {/* Export dropdown */}
            <div className="relative" ref={exportRef} onBlur={handleExportBlur}>
              <button
                onClick={() => setShowExportMenu((p) => !p)}
                className="btn-primary flex items-center gap-2"
              >
                <DownloadIcon />
                导出 Excel
                <ChevronDownIcon className="w-3.5 h-3.5 opacity-60" />
              </button>
              {showExportMenu && (
                <div className="absolute right-0 mt-1.5 w-52 bg-white border border-slate-200 rounded-xl shadow-lg z-20 py-1.5 animate-fade-in">
                  <button
                    onMouseDown={() => handleExport(false)}
                    className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2 transition-colors"
                  >
                    <LayersIcon className="w-4 h-4 text-slate-400" />
                    导出当前视图
                    <span className="ml-auto text-xs text-slate-400 tabular-nums">{sorted.length}</span>
                  </button>
                  <div className="mx-3 border-t border-slate-100 my-0.5" />
                  <button
                    onMouseDown={() => handleExport(true)}
                    className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2 transition-colors"
                  >
                    <DownloadIcon className="w-4 h-4 text-slate-400" />
                    导出全部
                    <span className="ml-auto text-xs text-slate-400 tabular-nums">{rows.length}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Error Banner ── */}
      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-start gap-2.5">
          <AlertCircleIcon className="w-4 h-4 mt-0.5 shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      {/* ── Data Table ── */}
      {rows.length > 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          {/* Horizontal scroll container with edge shadows */}
          <div className="overflow-x-auto max-h-[500px] overflow-y-auto relative">
            {/* Left shadow hint */}
            <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-4 bg-gradient-to-r from-slate-100/60 to-transparent z-10 opacity-0 [div[data-scrolled-left]>&]:opacity-100" />
            {/* Right shadow hint */}
            <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-4 bg-gradient-to-l from-slate-100/60 to-transparent z-10" />

            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50/95 backdrop-blur-sm z-10">
                <tr className="border-b-2 border-slate-200">
                  {displayColumns.map((col) => (
                    <th
                      key={col}
                      onClick={() => handleSort(col)}
                      className="text-left px-3 py-2.5 text-xs font-semibold text-slate-500 whitespace-nowrap cursor-pointer select-none hover:bg-slate-100 transition-colors uppercase tracking-wider"
                    >
                      <span className="inline-flex items-center gap-1">
                        {col}
                        {sort?.column === col ? (
                          sort.direction === "asc" ? (
                            <ArrowUpIcon className="w-3 h-3 text-emerald-600" />
                          ) : (
                            <ArrowDownIcon className="w-3 h-3 text-emerald-600" />
                          )
                        ) : (
                          <ChevronsUpDownIcon className="w-3 h-3 text-slate-300" />
                        )}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paged.map((row, i) => {
                  const matched = getMatchStatus(row);
                  const isUnmatched = !matched && (
                    row["__matched"] === false || (hasDualColumns && row["__matched_矿卡"] === false && row["__matched_挖机"] === false)
                  );
                  return (
                    <tr
                      key={i}
                      className={`border-b border-slate-50 transition-colors ${
                        matched
                          ? "bg-emerald-50/30 border-l-2 border-l-emerald-400 hover:bg-emerald-50/60"
                          : isUnmatched
                            ? "bg-amber-50/30 border-l-2 border-l-amber-400 hover:bg-amber-50/60"
                            : "hover:bg-slate-50/60"
                      }`}
                    >
                      {displayColumns.map((col) => {
                        const val = row[col];
                        const isNumeric = typeof val === "number";
                        return (
                          <td
                            key={col}
                            className={`px-3 py-1.5 whitespace-nowrap text-sm text-slate-700 ${
                              isNumeric ? "font-mono tabular-nums" : ""
                            }`}
                          >
                            {val != null ? String(val) : <span className="text-slate-300">-</span>}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-slate-100 bg-slate-50/50">
            <span className="text-xs text-slate-400 tabular-nums">共 {sorted.length} 条</span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md hover:bg-slate-200 disabled:text-slate-300 disabled:hover:bg-transparent transition-colors"
              >
                <ChevronLeftIcon className="w-3.5 h-3.5" />
                上一页
              </button>
              <span className="text-xs text-slate-400 tabular-nums font-medium px-1">
                {page + 1} / {totalPages || 1}
              </span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md hover:bg-slate-200 disabled:text-slate-300 disabled:hover:bg-transparent transition-colors"
              >
                下一页
                <ChevronRightIcon className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      ) : (
        !loading && (
          <div className="bg-white rounded-xl border-2 border-dashed border-slate-200 p-16 text-center">
            <div className="flex justify-center mb-4">
              <div className="p-4 rounded-full bg-slate-50 text-slate-300">
                <FolderOpenIcon className="w-12 h-12" />
              </div>
            </div>
            <p className="text-sm text-slate-500 font-medium mb-1">暂无数据</p>
            <p className="text-xs text-slate-400">请选择 Excel 文件并加载 Sheet，然后配置匹配参数</p>
            <p className="text-xs text-slate-300 mt-1">支持拖拽文件到上方区域</p>
          </div>
        )
      )}

      {/* ── Loading Overlay ── */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <LoaderIcon className="w-8 h-8 text-slate-400 animate-spin" />
            <span className="text-sm text-slate-500">加载中...</span>
          </div>
        </div>
      )}

      {/* ── Clear Confirmation Dialog ── */}
      {showClearDialog && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 animate-fade-in" onClick={() => setShowClearDialog(false)}>
          <div className="bg-white rounded-xl shadow-2xl p-6 w-80 animate-fade-in" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2.5 mb-3">
              <div className="p-1.5 rounded-lg bg-red-50">
                <TrashIcon className="w-4 h-4 text-red-500" />
              </div>
              <h4 className="text-sm font-semibold text-slate-800">确认清空</h4>
            </div>
            <p className="text-xs text-slate-500 mb-5 leading-relaxed">
              清空后将移除所有已加载的数据和匹配结果，此操作不可撤销。
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowClearDialog(false)}
                className="btn-secondary text-xs"
              >
                取消
              </button>
              <button
                onClick={handleClear}
                className="text-xs px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium transition-colors"
              >
                确认清空
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
