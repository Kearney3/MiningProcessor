import { useState, useRef } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { inputClass, btnPrimaryClass, btnSecondaryClass } from "../../lib/ui-classes";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "all" | "matched" | "unmatched";

interface MatchToggle {
  enabled: boolean;
  column: string;
}

interface SortState {
  column: string;
  direction: "asc" | "desc";
}

// ---------------------------------------------------------------------------
// SVG Icons (Lucide-style, no emoji)
// ---------------------------------------------------------------------------

const IconUploadCloud = () => (
  <svg className="w-6 h-6 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
    <path d="M12 12v9" />
    <path d="m16 16-4-4-4 4" />
  </svg>
);

const IconTag = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z" />
    <circle cx="7.5" cy="7.5" r=".5" fill="currentColor" />
  </svg>
);

const IconHash = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <line x1="4" x2="20" y1="9" y2="9" />
    <line x1="4" x2="20" y1="15" y2="15" />
    <line x1="10" x2="8" y1="3" y2="21" />
    <line x1="16" x2="14" y1="3" y2="21" />
  </svg>
);

const IconDroplet = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z" />
  </svg>
);

const IconSearch = () => (
  <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </svg>
);

const IconLayers = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z" />
    <path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65" />
    <path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65" />
  </svg>
);

const IconPlay = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <polygon points="6 3 20 12 6 21 6 3" />
  </svg>
);

const IconDownload = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" x2="12" y1="15" y2="3" />
  </svg>
);

const IconTrash = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18" />
    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
  </svg>
);

const IconColumns = () => (
  <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
    <line x1="12" x2="12" y1="3" y2="21" />
  </svg>
);

const IconChevronDown = () => (
  <svg className="w-3.5 h-3.5 opacity-60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="m6 9 6 6 6-6" />
  </svg>
);

const IconChevronLeft = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="m15 18-6-6 6-6" />
  </svg>
);

const IconChevronRight = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="m9 18 6-6-6-6" />
  </svg>
);

const IconArrowUp = () => (
  <svg className="w-3 h-3 text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="m5 12 7-7 7 7" />
    <path d="M12 19V5" />
  </svg>
);

const IconArrowDown = () => (
  <svg className="w-3 h-3 text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5v14" />
    <path d="m19 12-7 7-7-7" />
  </svg>
);

const IconChevronsUpDown = () => (
  <svg className="w-3 h-3 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="m7 15 5 5 5-5" />
    <path d="m7 9 5-5 5 5" />
  </svg>
);

const IconLoader = () => (
  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);

const IconAlertCircle = () => (
  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" x2="12" y1="8" y2="12" />
    <line x1="12" x2="12.01" y1="16" y2="16" />
  </svg>
);

const IconInfo = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <path d="M12 16v-4" />
    <path d="M12 8h.01" />
  </svg>
);

const IconTable = () => (
  <svg className="w-8 h-8 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
  </svg>
);

// ---------------------------------------------------------------------------
// Toggle Switch (w-8 h-5, restrained style — no color flash)
// ---------------------------------------------------------------------------

function ToggleSwitch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
        checked ? "bg-slate-900" : "bg-slate-200"
      }`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
          checked ? "translate-x-[14px]" : "translate-x-[3px]"
        }`}
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function LedgerMatchPage({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
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
      notify(`匹配完成: ${matchedCount} 匹配, ${unmatchedCount} 未匹配`, "success");
    } catch (e) {
      setError(String(e));
      notify(`匹配失败: ${e}`, "error");
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
      notify("导出成功", "success");
    } catch (e) {
      setError(String(e));
      notify(`导出失败: ${e}`, "error");
    }
  };

  // --- Sorting ---

  const handleSort = (col: string) => {
    setSort((prev) => {
      if (prev?.column === col) {
        if (prev.direction === "asc") return { column: col, direction: "desc" };
        return null;
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

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full">
      {/* Title */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-slate-500"><IconLayers /></span>
        <h2 className="text-base font-semibold text-slate-800">台账匹配</h2>
        <span className="text-xs text-slate-400 ml-1">将 Excel 数据与设备台账进行模糊匹配</span>
      </div>

      {/* ── File Selection Drop Zone ── */}
      <div
        className={`rounded-lg border-2 border-dashed p-6 mb-4 transition-colors ${
          dragOver
            ? "border-blue-400 bg-blue-50/50"
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
        {!filePath && (
          <div
            className="flex flex-col items-center justify-center py-2 cursor-pointer"
            onClick={browseFile}
          >
            <IconUploadCloud />
            <p className="text-sm text-slate-500 mt-2">
              拖拽 Excel 文件到此处，或点击浏览
            </p>
            <p className="text-xs text-slate-400 mt-0.5">支持 .xlsx / .xls 格式</p>
          </div>
        )}

        {filePath && (
          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="选择 Excel 文件"
              className={`${inputClass} flex-1`}
            />
            <button onClick={browseFile} className={btnSecondaryClass}>
              浏览
            </button>
            <button
              onClick={() => setShowClearDialog(true)}
              className="flex items-center gap-1.5 text-red-600 text-sm px-3 py-1.5 rounded-md hover:bg-red-50 transition-colors"
            >
              <IconTrash />
              清空
            </button>
          </div>
        )}

        {/* Sheet selector tabs */}
        {availableSheets.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="shrink-0"><IconColumns /></span>
            <div className="flex gap-1 overflow-x-auto">
              {availableSheets.map((s) => (
                <button
                  key={s}
                  onClick={() => setSheetName(s)}
                  className={`text-xs px-3 py-1.5 rounded-md whitespace-nowrap transition-colors ${
                    sheetName === s
                      ? "bg-white border border-slate-200 shadow-sm text-slate-800 font-medium"
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
              className={`${btnPrimaryClass} ml-auto shrink-0`}
            >
              {loading ? <><IconLoader /> 加载中</> : "加载"}
            </button>
          </div>
        )}
      </div>

      {/* ── Match Configuration ── */}
      {columns.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-4 mb-4">
          <h3 className="text-sm font-medium text-slate-700 mb-3 flex items-center gap-2">
            <span className="text-slate-400"><IconSearch /></span>
            匹配配置
          </h3>

          {/* Three independent toggles in a flex row */}
          <div className="flex flex-wrap gap-x-8 gap-y-3 mb-4">
            {/* Name match */}
            <div className="flex items-center gap-3">
              <ToggleSwitch
                checked={nameToggle.enabled}
                onChange={(v) => setNameToggle((p) => ({ ...p, enabled: v }))}
              />
              <span className={`text-sm ${nameToggle.enabled ? "text-slate-800 font-medium" : "text-slate-500"}`}>
                <span className="inline-flex items-center gap-1"><IconTag /> 设备名称</span>
              </span>
              <select
                value={nameToggle.column}
                onChange={(e) => setNameToggle((p) => ({ ...p, column: e.target.value }))}
                disabled={!nameToggle.enabled}
                className={`${inputClass} text-xs disabled:opacity-40 disabled:cursor-not-allowed w-40`}
              >
                <option value="">选择列</option>
                {columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* ID match */}
            <div className="flex items-center gap-3">
              <ToggleSwitch
                checked={idToggle.enabled}
                onChange={(v) => setIdToggle((p) => ({ ...p, enabled: v }))}
              />
              <span className={`text-sm ${idToggle.enabled ? "text-slate-800 font-medium" : "text-slate-500"}`}>
                <span className="inline-flex items-center gap-1"><IconHash /> 设备编号</span>
              </span>
              <select
                value={idToggle.column}
                onChange={(e) => setIdToggle((p) => ({ ...p, column: e.target.value }))}
                disabled={!idToggle.enabled}
                className={`${inputClass} text-xs disabled:opacity-40 disabled:cursor-not-allowed w-40`}
              >
                <option value="">选择列</option>
                {columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Oil match */}
            <div className="flex items-center gap-3">
              <ToggleSwitch
                checked={oilToggle.enabled}
                onChange={(v) => setOilToggle((p) => ({ ...p, enabled: v }))}
              />
              <span className={`text-sm ${oilToggle.enabled ? "text-slate-800 font-medium" : "text-slate-500"}`}>
                <span className="inline-flex items-center gap-1"><IconDroplet /> 油品</span>
              </span>
              <select
                value={oilToggle.column}
                onChange={(e) => setOilToggle((p) => ({ ...p, column: e.target.value }))}
                disabled={!oilToggle.enabled}
                className={`${inputClass} text-xs disabled:opacity-40 disabled:cursor-not-allowed w-40`}
              >
                <option value="">选择列</option>
                {columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Dual-column detection notice */}
          {hasDualColumns && (
            <div className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-slate-400"><IconInfo /></span>
                <span className="text-xs font-medium text-slate-600">双列生产模式已检测</span>
              </div>
              <div className="flex gap-4 text-xs text-slate-500">
                <span>矿卡列: <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-xs">{dualTruckCol}</code></span>
                <span>挖机列: <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-xs">{dualExcavatorCol}</code></span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                匹配结果将生成 "标准设备名称（矿卡）" 和 "标准设备名称（挖机）" 两列
              </p>
            </div>
          )}

          {/* Match button + inline stats */}
          <div className="flex items-center gap-4 flex-wrap">
            <button
              onClick={handleMatch}
              disabled={!anyToggleEnabled || matching}
              className={btnPrimaryClass}
            >
              {matching ? <><IconLoader /> 匹配中</> : <><IconPlay /> 开始匹配</>}
            </button>

            {/* Inline stats — simple text, no card widgets */}
            {matchedCount + unmatchedCount > 0 && (
              <div className="flex items-center gap-4 text-sm text-slate-600 ml-auto">
                <span className="tabular-nums">全部: <strong className="text-slate-800">{matchedCount + unmatchedCount}</strong></span>
                <span className="text-slate-300">|</span>
                <span className="tabular-nums">已匹配: <strong className="text-slate-800">{matchedCount}</strong> ({matchRate}%)</span>
                <span className="text-slate-300">|</span>
                <span className="tabular-nums">未匹配: <strong className="text-slate-800">{unmatchedCount}</strong></span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── View Mode Toggle + Toolbar ── */}
      {rows.length > 0 && (
        <div className="flex items-center justify-between mb-3">
          {/* Segmented control */}
          <div className="inline-flex bg-slate-100 rounded-md p-0.5">
            {([
              { id: "all" as ViewMode, label: "全部", count: viewCounts.all },
              { id: "matched" as ViewMode, label: "已匹配", count: viewCounts.matched },
              { id: "unmatched" as ViewMode, label: "未匹配", count: viewCounts.unmatched },
            ]).map((v) => (
              <button
                key={v.id}
                onClick={() => { setViewMode(v.id); setPage(0); }}
                className={`text-xs px-3 py-1.5 rounded-[5px] transition-all flex items-center gap-1 ${
                  viewMode === v.id
                    ? "bg-white shadow-sm text-slate-800 font-medium"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {v.label}
                <span className="text-[10px] ml-0.5 tabular-nums opacity-60">{v.count}</span>
              </button>
            ))}
          </div>

          <div className="flex gap-2">
            {/* Export dropdown */}
            <div className="relative" ref={exportRef} onBlur={handleExportBlur}>
              <button
                onClick={() => setShowExportMenu((p) => !p)}
                className={btnSecondaryClass}
              >
                <IconDownload />
                导出 Excel
                <IconChevronDown />
              </button>
              {showExportMenu && (
                <div className="absolute right-0 mt-1.5 w-48 bg-white border border-slate-200 rounded-md z-20 py-1">
                  <button
                    onMouseDown={() => handleExport(false)}
                    className="w-full text-left px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 flex items-center justify-between transition-colors"
                  >
                    导出当前视图
                    <span className="text-xs text-slate-400 tabular-nums">{sorted.length}</span>
                  </button>
                  <div className="mx-2 border-t border-slate-100 my-0.5" />
                  <button
                    onMouseDown={() => handleExport(true)}
                    className="w-full text-left px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 flex items-center justify-between transition-colors"
                  >
                    导出全部
                    <span className="text-xs text-slate-400 tabular-nums">{rows.length}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Error Banner ── */}
      {error && (
        <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-4 py-2.5 flex items-center gap-2">
          <span className="text-red-500"><IconAlertCircle /></span>
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600 text-xs">dismiss</button>
        </div>
      )}

      {/* ── Data Table ── */}
      {rows.length > 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden flex-1 flex flex-col min-h-0">
          <div className="overflow-auto flex-1">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50 z-10">
                <tr className="border-b border-slate-200">
                  {displayColumns.map((col) => (
                    <th
                      key={col}
                      onClick={() => handleSort(col)}
                      className="text-left px-3 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider whitespace-nowrap cursor-pointer select-none hover:bg-slate-100 transition-colors"
                    >
                      <span className="inline-flex items-center gap-1">
                        {col}
                        {sort?.column === col ? (
                          sort.direction === "asc" ? <IconArrowUp /> : <IconArrowDown />
                        ) : (
                          <IconChevronsUpDown />
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
                      className={`h-9 border-b border-slate-100 transition-colors ${
                        matched
                          ? "bg-emerald-50/40 hover:bg-emerald-50/70"
                          : isUnmatched
                            ? "bg-amber-50/40 hover:bg-amber-50/70"
                            : "hover:bg-slate-50"
                      }`}
                    >
                      {displayColumns.map((col) => {
                        const val = row[col];
                        const isNumeric = typeof val === "number";
                        return (
                          <td
                            key={col}
                            className={`px-3 text-sm text-slate-700 whitespace-nowrap ${
                              isNumeric ? "tabular-nums" : ""
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
          <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100 shrink-0">
            <span className="text-xs text-slate-500">共 {sorted.length} 条</span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                <IconChevronLeft />
                上一页
              </button>
              <span className="text-xs text-slate-500 min-w-[4rem] text-center tabular-nums">
                {page + 1} / {totalPages || 1}
              </span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                下一页
                <IconChevronRight />
              </button>
            </div>
          </div>
        </div>
      ) : (
        !loading && (
          <div className="bg-white rounded-lg border border-slate-200 p-16 text-center">
            <span className="flex justify-center mb-4 text-slate-300"><IconTable /></span>
            <p className="text-sm text-slate-500 mb-1">暂无数据</p>
            <p className="text-xs text-slate-400">请选择 Excel 文件并加载 Sheet，然后配置匹配参数</p>
          </div>
        )
      )}

      {/* ── Loading Overlay ── */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <svg className="w-8 h-8 animate-spin text-slate-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm text-slate-500">加载中...</span>
          </div>
        </div>
      )}

      {/* ── Clear Confirmation Dialog ── */}
      {showClearDialog && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowClearDialog(false)}>
          <div className="bg-white rounded-lg border border-slate-200 w-full max-w-sm mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-5">
              <h3 className="text-sm font-semibold text-slate-800">确认清空</h3>
              <p className="text-sm text-slate-500 mt-2">
                清空后将移除所有已加载的数据和匹配结果，此操作不可撤销。
              </p>
            </div>
            <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
              <button
                onClick={() => setShowClearDialog(false)}
                className={btnSecondaryClass}
              >
                取消
              </button>
              <button
                onClick={handleClear}
                className="text-sm px-4 py-1.5 rounded-md bg-red-600 hover:bg-red-700 text-white font-medium transition-colors"
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
