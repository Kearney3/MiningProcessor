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

  const _getSortIcon = (col: string): string => {
    if (sort?.column !== col) return "";
    return sort.direction === "asc" ? " ▲" : " ▼";
  };
  void _getSortIcon;

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

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-800 mb-4">台账匹配</h2>

      {/* File selection with drag-drop hint */}
      <div
        className={`bg-white rounded-xl border-2 border-dashed p-5 mb-4 transition-colors ${
          dragOver
            ? "border-cyan-400 bg-cyan-50/30"
            : filePath
              ? "border-slate-200"
              : "border-slate-300"
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
        <div className="flex gap-2 mb-3">
          <div className="relative flex-1">
            <input
              type="text"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder={dragOver ? "释放文件以加载" : "选择 Excel 文件"}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 pr-9 focus:outline-none focus:ring-2 focus:ring-cyan-500/30"
            />
            {!filePath && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none">
                拖拽至此
              </span>
            )}
          </div>
          <button
            onClick={browseFile}
            className="shrink-0 text-sm bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-2 rounded-lg transition-colors"
          >
            浏览
          </button>
          {filePath && (
            <button
              onClick={() => setShowClearDialog(true)}
              className="shrink-0 text-sm bg-red-50 hover:bg-red-100 text-red-600 px-3 py-2 rounded-lg transition-colors"
            >
              清空
            </button>
          )}
        </div>

        {availableSheets.length > 0 && (
          <div className="flex items-center gap-3">
            <label className="text-xs text-slate-500">Sheet:</label>
            <select
              value={sheetName}
              onChange={(e) => setSheetName(e.target.value)}
              className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-cyan-500/30"
            >
              {availableSheets.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button
              onClick={loadSheet}
              disabled={loading}
              className="text-sm bg-slate-600 hover:bg-slate-700 text-white px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? "加载中..." : "加载"}
            </button>
          </div>
        )}
      </div>

      {/* Match configuration with independent toggles */}
      {columns.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">匹配配置</h3>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            {/* Name match toggle */}
            <div className={`rounded-lg border p-3 transition-colors ${nameToggle.enabled ? "border-cyan-300 bg-cyan-50/20" : "border-slate-200"}`}>
              <label className="flex items-center gap-2 mb-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={nameToggle.enabled}
                  onChange={(e) => setNameToggle((p) => ({ ...p, enabled: e.target.checked }))}
                  className="rounded border-slate-300 text-cyan-600"
                />
                <span className="text-xs font-medium text-slate-700">设备名称匹配</span>
              </label>
              <select
                value={nameToggle.column}
                onChange={(e) => setNameToggle((p) => ({ ...p, column: e.target.value }))}
                disabled={!nameToggle.enabled}
                className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 disabled:opacity-40 disabled:bg-slate-50"
              >
                <option value="">选择列</option>
                {columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* ID match toggle */}
            <div className={`rounded-lg border p-3 transition-colors ${idToggle.enabled ? "border-cyan-300 bg-cyan-50/20" : "border-slate-200"}`}>
              <label className="flex items-center gap-2 mb-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={idToggle.enabled}
                  onChange={(e) => setIdToggle((p) => ({ ...p, enabled: e.target.checked }))}
                  className="rounded border-slate-300 text-cyan-600"
                />
                <span className="text-xs font-medium text-slate-700">设备编号匹配</span>
              </label>
              <select
                value={idToggle.column}
                onChange={(e) => setIdToggle((p) => ({ ...p, column: e.target.value }))}
                disabled={!idToggle.enabled}
                className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 disabled:opacity-40 disabled:bg-slate-50"
              >
                <option value="">选择列</option>
                {columns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Oil match toggle */}
            <div className={`rounded-lg border p-3 transition-colors ${oilToggle.enabled ? "border-cyan-300 bg-cyan-50/20" : "border-slate-200"}`}>
              <label className="flex items-center gap-2 mb-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={oilToggle.enabled}
                  onChange={(e) => setOilToggle((p) => ({ ...p, enabled: e.target.checked }))}
                  className="rounded border-slate-300 text-cyan-600"
                />
                <span className="text-xs font-medium text-slate-700">油品匹配</span>
              </label>
              <select
                value={oilToggle.column}
                onChange={(e) => setOilToggle((p) => ({ ...p, column: e.target.value }))}
                disabled={!oilToggle.enabled}
                className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 disabled:opacity-40 disabled:bg-slate-50"
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
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50/40 p-3">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium text-amber-700">双列生产模式已检测</span>
                <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              </div>
              <div className="flex gap-3 text-xs text-slate-600">
                <span>矿卡列: <strong className="text-slate-800">{dualTruckCol}</strong></span>
                <span>挖机列: <strong className="text-slate-800">{dualExcavatorCol}</strong></span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                匹配结果将生成 "标准设备名称（矿卡）" 和 "标准设备名称（挖机）" 两列
              </p>
            </div>
          )}

          {/* Match button */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleMatch}
              disabled={!anyToggleEnabled || matching}
              className={`text-sm font-medium px-5 py-2 rounded-lg transition-colors ${
                !anyToggleEnabled || matching
                  ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                  : "bg-cyan-600 hover:bg-cyan-700 text-white"
              }`}
            >
              {matching ? "匹配中..." : "开始匹配"}
            </button>

            {/* Stats cards */}
            {matchedCount + unmatchedCount > 0 && (
              <div className="flex items-center gap-3 ml-auto">
                <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-1.5">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-xs text-green-700 font-medium">已匹配</span>
                  <span className="text-sm font-bold text-green-800">{matchedCount}</span>
                </div>
                <div className="flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-lg px-3 py-1.5">
                  <span className="w-2 h-2 rounded-full bg-orange-500" />
                  <span className="text-xs text-orange-700 font-medium">未匹配</span>
                  <span className="text-sm font-bold text-orange-800">{unmatchedCount}</span>
                </div>
                <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
                  <span className="text-xs text-slate-500 font-medium">匹配率</span>
                  <span className="text-sm font-bold text-slate-800">
                    {((matchedCount / (matchedCount + unmatchedCount)) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* View mode tabs + toolbar */}
      {rows.length > 0 && (
        <div className="flex items-center justify-between mb-3">
          <div className="flex gap-1">
            {([
              { id: "all" as ViewMode, label: "全部", count: rows.length },
              { id: "matched" as ViewMode, label: "已匹配", count: matchedCount },
              { id: "unmatched" as ViewMode, label: "未匹配", count: unmatchedCount },
            ]).map((v) => (
              <button
                key={v.id}
                onClick={() => { setViewMode(v.id); setPage(0); }}
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                  viewMode === v.id
                    ? "bg-cyan-600 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {v.label} ({v.count})
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            {/* Export dropdown */}
            <div className="relative" ref={exportRef} onBlur={handleExportBlur}>
              <button
                onClick={() => setShowExportMenu((p) => !p)}
                className="text-sm bg-green-600 hover:bg-green-700 text-white px-4 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors"
              >
                导出 Excel
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showExportMenu && (
                <div className="absolute right-0 mt-1 w-48 bg-white border border-slate-200 rounded-lg shadow-lg z-20 py-1">
                  <button
                    onMouseDown={() => handleExport(false)}
                    className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    导出当前视图 ({sorted.length} 条)
                  </button>
                  <button
                    onMouseDown={() => handleExport(true)}
                    className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    导出全部 ({rows.length} 条)
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {/* Data table */}
      {rows.length > 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50 z-10">
                <tr className="border-b-2 border-slate-200">
                  {displayColumns.map((col) => (
                    <th
                      key={col}
                      onClick={() => handleSort(col)}
                      className="text-left px-3 py-2.5 text-xs font-medium text-slate-500 whitespace-nowrap cursor-pointer select-none hover:bg-slate-100 transition-colors"
                    >
                      <span className="inline-flex items-center gap-1">
                        {col}
                        {sort?.column === col ? (
                          <span className="text-cyan-600">
                            {sort.direction === "asc" ? "▲" : "▼"}
                          </span>
                        ) : (
                          <span className="text-slate-300 text-[10px]">▴▾</span>
                        )}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paged.map((row, i) => {
                  const matched = hasDualColumns
                    ? row["__matched_矿卡"] === true || row["__matched_挖机"] === true
                    : row["__matched"] === true;
                  return (
                    <tr
                      key={i}
                      className={`border-b border-slate-50 transition-colors ${
                        matched
                          ? "bg-green-50/40 hover:bg-green-50"
                          : row["__matched"] === false || (hasDualColumns && !matched)
                            ? "bg-orange-50/40 hover:bg-orange-50"
                            : "hover:bg-slate-50"
                      }`}
                    >
                      {displayColumns.map((col) => (
                        <td key={col} className="px-3 py-1.5 text-slate-600 whitespace-nowrap text-xs">
                          {row[col] != null ? String(row[col]) : ""}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-2 border-t border-slate-100 bg-slate-50/50">
            <span className="text-xs text-slate-400">共 {sorted.length} 条</span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="text-xs px-2.5 py-1 rounded-md hover:bg-slate-200 disabled:text-slate-300 disabled:hover:bg-transparent transition-colors"
              >
                上一页
              </button>
              <span className="text-xs text-slate-400 tabular-nums">{page + 1} / {totalPages || 1}</span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="text-xs px-2.5 py-1 rounded-md hover:bg-slate-200 disabled:text-slate-300 disabled:hover:bg-transparent transition-colors"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      ) : (
        !loading && (
          <div className="bg-white rounded-xl border-2 border-dashed border-slate-200 p-12 text-center">
            <div className="text-slate-300 text-3xl mb-3">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-sm text-slate-400">请选择 Excel 文件并加载 Sheet，然后配置匹配参数</p>
            <p className="text-xs text-slate-300 mt-1">支持拖拽文件到上方区域</p>
          </div>
        )
      )}

      {/* Clear confirmation dialog */}
      {showClearDialog && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowClearDialog(false)}>
          <div className="bg-white rounded-xl shadow-xl p-6 w-80" onClick={(e) => e.stopPropagation()}>
            <h4 className="text-sm font-semibold text-slate-800 mb-2">确认清空</h4>
            <p className="text-xs text-slate-500 mb-4">
              清空后将移除所有已加载的数据和匹配结果，此操作不可撤销。
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowClearDialog(false)}
                className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleClear}
                className="text-xs px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white transition-colors"
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
