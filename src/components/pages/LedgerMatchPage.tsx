import { useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { open, save } from "@tauri-apps/plugin-dialog";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { inputClass, btnPrimaryClass, btnSecondaryClass } from "../../lib/ui-classes";
import { useLastDirectory } from "../../hooks/useLastDirectory";
import {
  FileIcon, UploadCloudIcon, TagIcon, HashIcon, DropletIcon,
  SearchIcon, LayersIcon, PlayIcon, DownloadIcon, TrashIcon,
  ColumnsIcon, ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon,
  ArrowUpIcon, ArrowDownIcon, ChevronsUpDownIcon, LoaderIcon,
  AlertCircleIcon, InfoIcon, TableIcon, CheckCircleIcon,
} from "../../lib/icons";
import { ToggleSwitch } from "../../lib/ui-components";

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

interface SheetConfig {
  nameToggle: MatchToggle;
  idToggle: MatchToggle;
  oilToggle: MatchToggle;
  hasDualColumns: boolean;
  dualTruckCol: string;
  dualExcavatorCol: string;
}

interface SheetData {
  columns: string[];
  rows: Record<string, unknown>[];
}

interface SheetState {
  raw: SheetData;           // original imported data
  matched: SheetData | null; // after matching (null = not yet matched)
  config: SheetConfig;
  matchedCount: number;
  unmatchedCount: number;
}

const EMPTY_CONFIG: SheetConfig = {
  nameToggle: { enabled: false, column: "" },
  idToggle: { enabled: false, column: "" },
  oilToggle: { enabled: false, column: "" },
  hasDualColumns: false,
  dualTruckCol: "",
  dualExcavatorCol: "",
};

// ---------------------------------------------------------------------------
// Auto-detection helpers
// ---------------------------------------------------------------------------

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

function buildAutoConfig(columns: string[]): SheetConfig {
  const detectedName = autoDetectNameColumn(columns);
  const detectedId = autoDetectIdColumn(columns);
  const detectedOil = autoDetectOilColumn(columns);
  const { truckCol, excavCol } = autoDetectDualColumns(columns);

  const hasDual = !!(truckCol && excavCol);

  return {
    nameToggle: {
      enabled: hasDual ? true : !!detectedName,
      column: hasDual ? truckCol : detectedName,
    },
    idToggle: {
      enabled: !!detectedId && !detectedName && !hasDual,
      column: detectedId,
    },
    oilToggle: {
      enabled: !!detectedOil,
      column: detectedOil,
    },
    hasDualColumns: hasDual,
    dualTruckCol: truckCol,
    dualExcavatorCol: excavCol,
  };
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function LedgerMatchPage({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const { t } = useTranslation();
  const { initialDir, saveDir } = useLastDirectory(bridge);
  const [filePath, setFilePath] = useState("");
  const [sheetName, setSheetName] = useState("");
  const [availableSheets, setAvailableSheets] = useState<string[]>([]);
  const [sheetStates, setSheetStates] = useState<Record<string, SheetState>>({});
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [loading, setLoading] = useState(false);
  const [matching, setMatching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<SortState | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [showClearDialog, setShowClearDialog] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [dateOnly, setDateOnly] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);
  const PAGE_SIZE = 20;

  // Derived state for current sheet
  const currentState = sheetStates[sheetName] || null;
  const currentConfig = currentState?.config ?? EMPTY_CONFIG;

  // Display data: matched result if available, otherwise raw
  const displayData: SheetData = currentState?.matched ?? currentState?.raw ?? { columns: [], rows: [] };
  const columns = displayData.columns;
  const rows = displayData.rows;
  const matchedCount = currentState?.matchedCount ?? 0;
  const unmatchedCount = currentState?.unmatchedCount ?? 0;

  // --- Save current sheet's config back to sheetStates ---
  const saveCurrentConfig = useCallback((config: SheetConfig) => {
    if (!sheetName) return;
    setSheetStates((prev) => {
      const existing = prev[sheetName];
      if (!existing) return prev;
      return { ...prev, [sheetName]: { ...existing, config } };
    });
  }, [sheetName]);

  // --- Toggle handlers (update both local UI + persist to sheetStates) ---
  const updateNameToggle = (patch: Partial<MatchToggle>) => {
    const next = { ...currentConfig.nameToggle, ...patch };
    const config = { ...currentConfig, nameToggle: next };
    saveCurrentConfig(config);
  };
  const updateIdToggle = (patch: Partial<MatchToggle>) => {
    const next = { ...currentConfig.idToggle, ...patch };
    const config = { ...currentConfig, idToggle: next };
    saveCurrentConfig(config);
  };
  const updateOilToggle = (patch: Partial<MatchToggle>) => {
    const next = { ...currentConfig.oilToggle, ...patch };
    const config = { ...currentConfig, oilToggle: next };
    saveCurrentConfig(config);
  };

  // --- File operations ---

  const browseFile = async () => {
    const selected = await open({
      multiple: false,
      defaultPath: initialDir || undefined,
      filters: [{ name: "Excel", extensions: ["xlsx", "xls"] }],
    });
    if (selected) {
      const p = selected as string;
      setFilePath(p);
      saveDir(p);
      resetData();
      loadSheets(p);
    }
  };

  const resetData = () => {
    setSheetStates({});
    setAvailableSheets([]);
    setSheetName("");
    setViewMode("all");
    setSort(null);
    setPage(0);
    setDateOnly(false);
  };

  const loadSheets = async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await bridge.call<{ sheets: string[] }>("list_excel_sheets", { path });
      setAvailableSheets(res.sheets || []);
      if (res.sheets?.length) {
        // Auto-load first sheet
        await loadSheetData(path, res.sheets[0]);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const loadSheetData = async (path: string, sheet: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await bridge.call<{ columns: string[]; rows: Record<string, unknown>[]; total: number; truncated: boolean }>(
        "read_excel_sheet",
        { path, sheet }
      );
      const cols = res.columns || [];
      const rowData = res.rows || [];
      const autoConfig = buildAutoConfig(cols);

      setSheetStates((prev) => ({
        ...prev,
        [sheet]: {
          raw: { columns: cols, rows: rowData },
          matched: null,
          config: autoConfig,
          matchedCount: 0,
          unmatchedCount: 0,
        },
      }));
      setSheetName(sheet);
      setViewMode("all");
      setSort(null);
      setPage(0);

      if (res.truncated) {
        notify(t("pages:LedgerMatchPage.sheetTruncated", { sheet, total: res.total }), "info");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  // --- Sheet switching ---
  const handleSheetSwitch = async (newSheet: string) => {
    if (newSheet === sheetName) return;

    // If we already have state for this sheet, just switch
    if (sheetStates[newSheet]) {
      setSheetName(newSheet);
      setViewMode("all");
      setSort(null);
      setPage(0);
      return;
    }

    // Otherwise load from file
    await loadSheetData(filePath, newSheet);
  };

  // --- Matching ---

  const handleMatch = async () => {
    if (!rows.length || !currentState) return;
    const cfg = currentConfig;
    if (!cfg.nameToggle.enabled && !cfg.idToggle.enabled && !cfg.oilToggle.enabled) {
      setError(t("pages:LedgerMatchPage.请至少启用一种匹配方式_3c4c"));
      return;
    }
    setMatching(true);
    setError(null);
    try {
      let finalRows: Record<string, unknown>[] = [];
      let finalCols: string[] = [];
      let totalMatched = 0;
      let totalUnmatched = 0;

      const sourceRows = currentState.raw.rows;

      if (cfg.hasDualColumns && cfg.dualTruckCol && cfg.dualExcavatorCol) {
        const truckRes = await bridge.call<{
          matched: number; unmatched: number; rows: Record<string, unknown>[]; columns: string[];
        }>("ledger_match_preview", {
          rows: sourceRows,
          name_column: cfg.dualTruckCol,
          oil_column: cfg.oilToggle.enabled ? cfg.oilToggle.column : null,
          mode: "name",
          result_suffix: "矿卡",
        });
        const excavRes = await bridge.call<{
          matched: number; unmatched: number; rows: Record<string, unknown>[]; columns: string[];
        }>("ledger_match_preview", {
          rows: truckRes.rows,
          name_column: cfg.dualExcavatorCol,
          oil_column: cfg.oilToggle.enabled ? cfg.oilToggle.column : null,
          mode: "name",
          result_suffix: "挖机",
        });
        finalCols = excavRes.columns || (excavRes.rows?.length ? Object.keys(excavRes.rows[0]) : []);
        // Normalize rows: rebuild each row object with keys in column order
        finalRows = (excavRes.rows || []).map((row) => {
          const ordered: Record<string, unknown> = {};
          for (const c of finalCols) ordered[c] = row[c];
          return ordered;
        });
        totalMatched = finalRows.filter((r) =>
          r["__matched_矿卡"] === true || r["__matched_挖机"] === true
        ).length;
        totalUnmatched = finalRows.length - totalMatched;
      } else {
        const res = await bridge.call<{
          matched: number; unmatched: number; rows: Record<string, unknown>[]; columns: string[];
        }>("ledger_match_preview", {
          rows: sourceRows,
          name_column: cfg.nameToggle.enabled ? cfg.nameToggle.column : null,
          id_column: cfg.idToggle.enabled ? cfg.idToggle.column : null,
          oil_column: cfg.oilToggle.enabled ? cfg.oilToggle.column : null,
          mode: cfg.nameToggle.enabled ? "name" : "id",
        });
        finalCols = res.columns || (res.rows?.length ? Object.keys(res.rows[0]) : []);
        // Normalize rows: rebuild each row object with keys in column order
        finalRows = (res.rows || []).map((row) => {
          const ordered: Record<string, unknown> = {};
          for (const c of finalCols) ordered[c] = row[c];
          return ordered;
        });
        totalMatched = res.matched || 0;
        totalUnmatched = res.unmatched || 0;
      }

      // Update sheet state with matched results
      setSheetStates((prev) => {
        const existing = prev[sheetName];
        if (!existing) return prev;
        return {
          ...prev,
          [sheetName]: {
            ...existing,
            matched: { columns: finalCols, rows: finalRows },
            matchedCount: totalMatched,
            unmatchedCount: totalUnmatched,
          },
        };
      });

      notify(t("pages:LedgerMatchPage.匹配完成:$匹配,$未匹配_0748", { matched: totalMatched, unmatched: totalUnmatched }), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:LedgerMatchPage.匹配失败:$_775d", { error: String(e) }), "error");
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

  const handleExport = async (mode: "current-view" | "current-all" | "all-sheets") => {
    setShowExportMenu(false);
    const outputPath = await save({
      filters: [{ name: "Excel", extensions: ["xlsx"] }],
      defaultPath: mode === "all-sheets" ? "匹配结果.xlsx" : `${sheetName}_匹配结果.xlsx`,
    });
    if (!outputPath) return;

    if (mode === "all-sheets") {
      // Export all matched sheets as separate tabs
      const matchedSheets: Record<string, SheetData> = {};
      for (const [name, state] of Object.entries(sheetStates)) {
        if (state.matched) {
          matchedSheets[name] = state.matched;
        }
      }
      const sheetKeys = Object.keys(matchedSheets);
      if (sheetKeys.length === 0) {
        notify(t("pages:LedgerMatchPage.没有已匹配的Sheet可导出_3aab"), "info");
        return;
      }
      try {
        await bridge.call("export_matched_data", {
          sheets: matchedSheets,
          output_path: outputPath,
          date_only: dateOnly,
        });
        notify(t("pages:LedgerMatchPage.导出成功（$个Sheet）_cbb8", { count: sheetKeys.length }), "success");
      } catch (e) {
        setError(String(e));
        notify(t("pages:LedgerMatchPage.导出失败:$_d4b1", { error: String(e) }), "error");
      }
    } else {
      // Export current sheet
      const data = currentState?.matched ?? currentState?.raw;
      if (!data) {
        notify(t("pages:LedgerMatchPage.没有数据可导出_fc30"), "info");
        return;
      }
      const rowsToExport = mode === "current-view" ? filtered : data.rows;
      try {
        await bridge.call("export_matched_data", {
          rows: rowsToExport,
          columns: data.columns,
          output_path: outputPath,
          date_only: dateOnly,
        });
        notify(t("pages:LedgerMatchPage.导出成功_105c"), "success");
      } catch (e) {
        setError(String(e));
        notify(t("pages:LedgerMatchPage.导出失败:$_d4b1", { error: String(e) }), "error");
      }
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
    if (currentConfig.hasDualColumns) {
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

  const anyToggleEnabled = currentConfig.nameToggle.enabled || currentConfig.idToggle.enabled || currentConfig.oilToggle.enabled;

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

  // Count sheets with matched results
  const matchedSheetCount = Object.values(sheetStates).filter((s) => s.matched).length;

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full">
      {/* Title */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-slate-500"><LayersIcon /></span>
        <h2 className="text-base font-semibold text-slate-800">{t("pages:LedgerMatchPage.台账匹配_9897")}</h2>
        <span className="text-xs text-slate-400 ml-1">{t("pages:LedgerMatchPage.将Excel数据与设备台账进行_2631")}</span>
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
            <UploadCloudIcon />
            <p className="text-sm text-slate-500 mt-2">
              {t("pages:LedgerMatchPage.ui.dropFile")}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">{t("pages:LedgerMatchPage.支持.xlsx/.xls格式_10a3")}</p>
          </div>
        )}

        {filePath && (
          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder={t("pages:LedgerMatchPage.ui.selectExcelFile")}
              className={`${inputClass} flex-1`}
            />
            <button onClick={browseFile} className={btnSecondaryClass} title={t("pages:LedgerMatchPage.ui.selectFile")}>
              <FileIcon />
            </button>
            <button
              onClick={() => setShowClearDialog(true)}
              className="flex items-center gap-1.5 text-red-600 text-sm px-3 py-1.5 rounded-md hover:bg-red-50 transition-colors"
            >
              <TrashIcon />
              {t("pages:LedgerMatchPage.ui.clear")}
            </button>
          </div>
        )}

        {/* Sheet selector tabs */}
        {availableSheets.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="shrink-0"><ColumnsIcon /></span>
            <div className="flex gap-1 overflow-x-auto">
              {availableSheets.map((s) => {
                const hasState = !!sheetStates[s];
                const isMatched = !!sheetStates[s]?.matched;
                return (
                  <button
                    key={s}
                    onClick={() => handleSheetSwitch(s)}
                    className={`text-xs px-3 py-1.5 rounded-md whitespace-nowrap transition-colors flex items-center gap-1 ${
                      sheetName === s
                        ? "bg-white border border-slate-200 shadow-sm text-slate-800 font-medium"
                        : isMatched
                          ? "text-emerald-600 hover:text-emerald-700 bg-emerald-50"
                          : hasState
                            ? "text-slate-600 hover:text-slate-700"
                            : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {isMatched && <CheckCircleIcon />}
                    {s}
                  </button>
                );
              })}
            </div>
            {matchedSheetCount > 0 && (
              <span className="text-xs text-emerald-600 ml-2 shrink-0">
                {matchedSheetCount}/{availableSheets.length} {t("pages:LedgerMatchPage.ui.matched")}
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── Match Configuration ── */}
      {columns.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-4 mb-4">
          <h3 className="text-sm font-medium text-slate-700 mb-3 flex items-center gap-2">
            <span className="text-slate-400"><SearchIcon /></span>
            {t("pages:LedgerMatchPage.ui.matchConfig")}
            {sheetName && (
              <span className="text-xs text-slate-400 font-normal">— {sheetName}</span>
            )}
          </h3>

          {/* Three independent toggles in a flex row */}
          <div className="flex flex-wrap gap-x-8 gap-y-3 mb-4">
            {/* Name match */}
            <div className="flex items-center gap-3">
              <ToggleSwitch
                checked={currentConfig.nameToggle.enabled}
                onChange={(v) => updateNameToggle({ enabled: v })}
              />
              <span className={`text-sm ${currentConfig.nameToggle.enabled ? "text-slate-800 font-medium" : "text-slate-500"}`}>
                <span className="inline-flex items-center gap-1"><TagIcon /> {t("pages:LedgerMatchPage.设备名称_9f69")}</span>
              </span>
              <select
                value={currentConfig.nameToggle.column}
                onChange={(e) => updateNameToggle({ column: e.target.value })}
                disabled={!currentConfig.nameToggle.enabled}
                className={`${inputClass} text-xs disabled:opacity-40 disabled:cursor-not-allowed w-40`}
              >
                <option value="">{t("pages:LedgerMatchPage.ui.selectColumn")}</option>
                {currentState?.raw.columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* ID match */}
            <div className="flex items-center gap-3">
              <ToggleSwitch
                checked={currentConfig.idToggle.enabled}
                onChange={(v) => updateIdToggle({ enabled: v })}
              />
              <span className={`text-sm ${currentConfig.idToggle.enabled ? "text-slate-800 font-medium" : "text-slate-500"}`}>
                <span className="inline-flex items-center gap-1"><HashIcon /> {t("pages:LedgerMatchPage.设备编号_cf05")}</span>
              </span>
              <select
                value={currentConfig.idToggle.column}
                onChange={(e) => updateIdToggle({ column: e.target.value })}
                disabled={!currentConfig.idToggle.enabled}
                className={`${inputClass} text-xs disabled:opacity-40 disabled:cursor-not-allowed w-40`}
              >
                <option value="">{t("pages:LedgerMatchPage.ui.selectColumn")}</option>
                {currentState?.raw.columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Oil match */}
            <div className="flex items-center gap-3">
              <ToggleSwitch
                checked={currentConfig.oilToggle.enabled}
                onChange={(v) => updateOilToggle({ enabled: v })}
              />
              <span className={`text-sm ${currentConfig.oilToggle.enabled ? "text-slate-800 font-medium" : "text-slate-500"}`}>
                <span className="inline-flex items-center gap-1"><DropletIcon /> {t("pages:LedgerMatchPage.ui.oil")}</span>
              </span>
              <select
                value={currentConfig.oilToggle.column}
                onChange={(e) => updateOilToggle({ column: e.target.value })}
                disabled={!currentConfig.oilToggle.enabled}
                className={`${inputClass} text-xs disabled:opacity-40 disabled:cursor-not-allowed w-40`}
              >
                <option value="">{t("pages:LedgerMatchPage.ui.selectColumn")}</option>
                {currentState?.raw.columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Dual-column detection notice */}
          {currentConfig.hasDualColumns && (
            <div className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-slate-400"><InfoIcon /></span>
                <span className="text-xs font-medium text-slate-600">{t("pages:LedgerMatchPage.双列生产模式已检测_95f9")}</span>
              </div>
              <div className="flex gap-4 text-xs text-slate-500">
                <span>{t("pages:LedgerMatchPage.矿卡列:_0c28")} <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-xs">{currentConfig.dualTruckCol}</code></span>
                <span>{t("pages:LedgerMatchPage.挖机列:_9d71")} <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-xs">{currentConfig.dualExcavatorCol}</code></span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                {t("pages:LedgerMatchPage.ui.dualColumnHint")}
              </p>
            </div>
          )}

          {/* Export options */}
          <div className="flex items-center gap-6 mb-4 pt-3 border-t border-slate-100">
            <div className="flex items-center gap-2">
              <ToggleSwitch
                checked={dateOnly}
                onChange={setDateOnly}
              />
              <span className={`text-sm ${dateOnly ? "text-slate-800 font-medium" : "text-slate-500"}`}>
                {t("pages:LedgerMatchPage.ui.dateFormat")}
              </span>
            </div>
            {matchedSheetCount > 1 && (
              <span className="text-xs text-emerald-600">
                {t("pages:LedgerMatchPage.ui.matchedSheets", { count: matchedSheetCount })}
              </span>
            )}
          </div>

          {/* Match button + inline stats */}
          <div className="flex items-center gap-4 flex-wrap">
            <button
              onClick={handleMatch}
              disabled={!anyToggleEnabled || matching}
              className={btnPrimaryClass}
            >
              {matching ? <><LoaderIcon /> {t("pages:LedgerMatchPage.匹配中_0c25")}</> : <><PlayIcon /> {t("pages:LedgerMatchPage.开始匹配_44b2")}</>}
            </button>

            {/* Inline stats — simple text, no card widgets */}
            {matchedCount + unmatchedCount > 0 && (
              <div className="flex items-center gap-4 text-sm text-slate-600 ml-auto">
                <span className="tabular-nums">{t("pages:LedgerMatchPage.全部:_3cf9")} <strong className="text-slate-800">{matchedCount + unmatchedCount}</strong></span>
                <span className="text-slate-300">|</span>
                <span className="tabular-nums">{t("pages:LedgerMatchPage.已匹配:_143f")} <strong className="text-slate-800">{matchedCount}</strong> ({matchRate}%)</span>
                <span className="text-slate-300">|</span>
                <span className="tabular-nums">{t("pages:LedgerMatchPage.未匹配:_2951")} <strong className="text-slate-800">{unmatchedCount}</strong></span>
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
              { id: "all" as ViewMode, label: t("pages:LedgerMatchPage.ui.all"), count: viewCounts.all },
              { id: "matched" as ViewMode, label: t("pages:LedgerMatchPage.ui.matched"), count: viewCounts.matched },
              { id: "unmatched" as ViewMode, label: t("pages:LedgerMatchPage.ui.unmatched"), count: viewCounts.unmatched },
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
                <DownloadIcon />
                {t("pages:LedgerMatchPage.ui.exportExcel")}
                <ChevronDownIcon />
              </button>
              {showExportMenu && (
                <div className="absolute right-0 mt-1.5 w-56 bg-white border border-slate-200 rounded-md z-20 py-1">
                  <div className="px-3 py-1 text-[10px] font-medium text-slate-400 uppercase tracking-wider">
                    {t("pages:LedgerMatchPage.ui.currentSheet")}: {sheetName}
                  </div>
                  <button
                    onMouseDown={() => handleExport("current-view")}
                    className="w-full text-left px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 flex items-center justify-between transition-colors"
                  >
                    {t("pages:LedgerMatchPage.ui.exportCurrentView")}
                    <span className="text-xs text-slate-400 tabular-nums">{t("pages:LedgerMatchPage.ui.rowCount", { count: sorted.length })}</span>
                  </button>
                  <button
                    onMouseDown={() => handleExport("current-all")}
                    className="w-full text-left px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 flex items-center justify-between transition-colors"
                  >
                    {t("pages:LedgerMatchPage.ui.exportSheetAll")}
                    <span className="text-xs text-slate-400 tabular-nums">{t("pages:LedgerMatchPage.ui.rowCount", { count: displayData.rows.length })}</span>
                  </button>
                  {matchedSheetCount > 1 && (
                    <>
                      <div className="mx-2 border-t border-slate-100 my-1" />
                      <button
                        onMouseDown={() => handleExport("all-sheets")}
                        className="w-full text-left px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 flex items-center justify-between transition-colors"
                      >
                        {t("pages:LedgerMatchPage.ui.exportAllMatched")}
                        <span className="text-xs text-emerald-600 tabular-nums">{t("pages:LedgerMatchPage.ui.sheetCount", { count: matchedSheetCount })}</span>
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Error Banner ── */}
      {error && (
        <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-4 py-2.5 flex items-center gap-2">
          <span className="text-red-500"><AlertCircleIcon /></span>
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
                          sort.direction === "asc" ? <ArrowUpIcon /> : <ArrowDownIcon />
                        ) : (
                          <ChevronsUpDownIcon />
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
                    row["__matched"] === false || (currentConfig.hasDualColumns && row["__matched_矿卡"] === false && row["__matched_挖机"] === false)
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
            <span className="text-xs text-slate-500">{t("pages:LedgerMatchPage.ui.totalRows", { count: sorted.length })}</span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                <ChevronLeftIcon />
                {t("pages:LedgerMatchPage.ui.previousPage")}
              </button>
              <span className="text-xs text-slate-500 min-w-[4rem] text-center tabular-nums">
                {page + 1} / {totalPages || 1}
              </span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                {t("pages:LedgerMatchPage.ui.nextPage")}
                <ChevronRightIcon />
              </button>
            </div>
          </div>
        </div>
      ) : (
        !loading && (
          <div className="bg-white rounded-lg border border-slate-200 p-16 text-center">
            <span className="flex justify-center mb-4 text-slate-300"><TableIcon /></span>
            <p className="text-sm text-slate-500 mb-1">{t("pages:LedgerMatchPage.暂无数据_21ef")}</p>
            <p className="text-xs text-slate-400">{t("pages:LedgerMatchPage.请选择Excel文件并加载Sh_4410")}</p>
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
            <span className="text-sm text-slate-500">{t("pages:LedgerMatchPage.加载中..._26b5")}</span>
          </div>
        </div>
      )}

      {/* ── Clear Confirmation Dialog ── */}
      {showClearDialog && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowClearDialog(false)}>
          <div className="bg-white rounded-lg border border-slate-200 w-full max-w-sm mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-5">
              <h3 className="text-sm font-semibold text-slate-800">{t("pages:LedgerMatchPage.确认清空_8452")}</h3>
              <p className="text-sm text-slate-500 mt-2">
                {t("pages:LedgerMatchPage.ui.clearWarning")}
              </p>
            </div>
            <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
              <button
                onClick={() => setShowClearDialog(false)}
                className={btnSecondaryClass}
              >
                {t("pages:LedgerMatchPage.ui.cancel")}
              </button>
              <button
                onClick={handleClear}
                className="text-sm px-4 py-1.5 rounded-md bg-red-600 hover:bg-red-700 text-white font-medium transition-colors"
              >
                {t("pages:LedgerMatchPage.确认清空_8452")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
