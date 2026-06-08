import { useState, useEffect, useCallback } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

export interface LedgerPageConfig {
  /** Page title, e.g. "设备台账" */
  title: string;
  /** Page icon: JSX element (SVG) rendered next to the title */
  icon?: React.ReactNode;
  /** Standard column names for the ledger, e.g. ["设备名称", ...] */
  standardColumns: string[];
  /** Bridge method to load rows */
  loadDataMethod: string;
  /** Bridge method to import from Excel with column mapping */
  importMethod: string;
  /** Bridge method to export a blank template */
  exportTemplateMethod: string;
  /** Bridge method to set as default */
  setDefaultMethod: string;
  /** Bridge method to cancel default */
  cancelDefaultMethod: string;
  /** Bridge method to clear all data */
  clearMethod: string;
  /** Bridge method to load file columns for mapping */
  loadFileColumnsMethod: string;
  /** Empty-state message when no rows exist */
  emptyMessage: string;
}

interface LedgerRow {
  [key: string]: unknown;
}

interface SortState {
  column: string;
  direction: "asc" | "desc";
}

// ---------------------------------------------------------------------------
// SVG Icons (16x16)
// ---------------------------------------------------------------------------

const IconImport = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
  </svg>
);

const IconExport = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
  </svg>
);

const IconStar = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
  </svg>
);

const IconStarFilled = () => (
  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
  </svg>
);

const IconTrash = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);

const IconRefresh = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);

const IconSearch = () => (
  <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
  </svg>
);

const IconChevronUp = () => (
  <svg className="w-3 h-2" viewBox="0 0 12 8" fill="currentColor">
    <path d="M6 0l6 8H0z" />
  </svg>
);

const IconChevronDown = () => (
  <svg className="w-3 h-2" viewBox="0 0 12 8" fill="currentColor">
    <path d="M6 8L0 0h12z" />
  </svg>
);

const IconChevronLeft = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
  </svg>
);

const IconChevronRight = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
  </svg>
);

const IconClose = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const IconArrowRight = () => (
  <svg className="w-4 h-4 text-slate-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
  </svg>
);

const IconTable = () => (
  <svg className="w-5 h-5 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
  </svg>
);

// ---------------------------------------------------------------------------
// Column Mapping Modal
// ---------------------------------------------------------------------------

function ColumnMappingModal({
  open: isOpen,
  fileColumns,
  standardColumns,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  fileColumns: string[];
  standardColumns: string[];
  onConfirm: (mapping: Record<string, string>) => void;
  onCancel: () => void;
}) {
  const [mapping, setMapping] = useState<Record<string, string>>({});

  // Auto-detect: if a file column matches a standard column name, pre-fill
  useEffect(() => {
    if (!isOpen) return;
    const auto: Record<string, string> = {};
    for (const std of standardColumns) {
      if (fileColumns.includes(std)) {
        auto[std] = std;
      }
    }
    setMapping(auto);
  }, [isOpen, fileColumns, standardColumns]);

  if (!isOpen) return null;

  const usedFileCols = new Set(Object.values(mapping).filter(Boolean));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-lg border border-slate-200 w-full max-w-lg mx-4 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7" />
            </svg>
            列映射
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            将文件中的列映射到台账标准列
          </p>
        </div>

        <div className="px-5 py-3 max-h-80 overflow-y-auto space-y-2.5">
          {standardColumns.map((stdCol) => (
            <div key={stdCol} className="flex items-center gap-3">
              <span className="w-32 text-sm text-slate-700 font-medium truncate" title={stdCol}>
                {stdCol}
              </span>
              <IconArrowRight />
              <select
                value={mapping[stdCol] || ""}
                onChange={(e) =>
                  setMapping((prev) => ({ ...prev, [stdCol]: e.target.value }))
                }
                className="input flex-1"
              >
                <option value="">-- 跳过 --</option>
                {fileColumns.map((fc) => (
                  <option key={fc} value={fc} disabled={usedFileCols.has(fc) && mapping[stdCol] !== fc}>
                    {fc}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>

        <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="btn-secondary text-sm px-4 py-1.5"
          >
            取消
          </button>
          <button
            onClick={() => {
              // Strip empty mappings
              const clean: Record<string, string> = {};
              for (const [k, v] of Object.entries(mapping)) {
                if (v) clean[k] = v;
              }
              onConfirm(clean);
            }}
            className="btn-primary text-sm px-4 py-1.5"
          >
            确认导入
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confirm Dialog
// ---------------------------------------------------------------------------

function ConfirmDialog({
  open: isOpen,
  title,
  message,
  confirmLabel = "确认",
  danger = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-lg border border-slate-200 w-full max-w-sm mx-4 overflow-hidden">
        <div className="px-5 py-5">
          <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
          <p className="text-sm text-slate-500 mt-2">{message}</p>
        </div>
        <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="btn-secondary text-sm px-4 py-1.5"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className={`${danger ? "btn-danger" : "btn-primary"} text-sm px-4 py-1.5`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function LedgerPage({ bridge, config }: { bridge: BridgeProp; config: LedgerPageConfig }) {
  const [rows, setRows] = useState<LedgerRow[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [searchTerm, setSearchTerm] = useState("");
  const [sort, setSort] = useState<SortState | null>(null);
  const [isDefault, setIsDefault] = useState(false);

  // Modal state
  const [showMapping, setShowMapping] = useState(false);
  const [pendingFileColumns, setPendingFileColumns] = useState<string[]>([]);
  const [pendingFilePath, setPendingFilePath] = useState("");
  const [showClearDialog, setShowClearDialog] = useState(false);
  const [showSetDefaultDialog, setShowSetDefaultDialog] = useState(false);
  const [showCancelDefaultDialog, setShowCancelDefaultDialog] = useState(false);
  const [importing, setImporting] = useState(false);

  const PAGE_SIZE = 20;

  // ---- Data loading ----

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await bridge.call<{ rows: LedgerRow[]; columns: string[]; is_default?: boolean }>(
        config.loadDataMethod,
        { from_cache: true }
      );
      const allRows = res.rows || [];
      const allColumns = res.columns || [];
      // 只展示标准列映射的表头，过滤掉原始文件中的无关列
      const standardSet = new Set(config.standardColumns);
      const filteredColumns = allColumns.filter((c) => standardSet.has(c));
      // 如果标准列中有后端新增的但不在 columns 里的，也补上
      for (const sc of config.standardColumns) {
        if (!filteredColumns.includes(sc)) filteredColumns.push(sc);
      }
      setRows(allRows);
      setColumns(filteredColumns);
      setIsDefault(!!res.is_default);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [bridge, config.loadDataMethod, config.standardColumns]);

  useEffect(() => { loadData(); }, [loadData]);

  // ---- Sorting ----

  const handleSort = (col: string) => {
    setSort((prev) => {
      if (prev?.column !== col) return { column: col, direction: "asc" };
      if (prev.direction === "asc") return { column: col, direction: "desc" };
      return null; // third click clears sort
    });
    setPage(0);
  };

  // ---- Filtering + sorting pipeline ----

  let displayRows = searchTerm
    ? rows.filter((r) =>
        Object.values(r).some((v) =>
          String(v ?? "").toLowerCase().includes(searchTerm.toLowerCase())
        )
      )
    : rows;

  if (sort) {
    const { column, direction } = sort;
    const dir = direction === "asc" ? 1 : -1;
    displayRows = [...displayRows].sort((a, b) => {
      const va = a[column];
      const vb = b[column];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      // Try numeric compare
      const na = Number(va);
      const nb = Number(vb);
      if (!isNaN(na) && !isNaN(nb)) return (na - nb) * dir;
      return String(va).localeCompare(String(vb), "zh-CN") * dir;
    });
  }

  const totalPages = Math.max(1, Math.ceil(displayRows.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const paged = displayRows.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  // ---- Actions ----

  const handleImport = async () => {
    try {
      const filePath = await open({
        multiple: false,
        filters: [{ name: "Excel", extensions: ["xlsx", "xls"] }],
      });
      if (!filePath) return;
      const path = typeof filePath === "string" ? filePath : filePath;

      // Ask backend for file columns
      const res = await bridge.call<{ columns: string[] }>(
        config.loadFileColumnsMethod,
        { file_path: path }
      );
      setPendingFileColumns(res.columns || []);
      setPendingFilePath(path);
      setShowMapping(true);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleMappingConfirm = async (mapping: Record<string, string>) => {
    setShowMapping(false);
    setImporting(true);
    setError(null);
    try {
      await bridge.call(config.importMethod, {
        file_path: pendingFilePath,
        column_mapping: mapping,
      });
      await loadData();
    } catch (e) {
      setError(String(e));
    } finally {
      setImporting(false);
      setPendingFilePath("");
      setPendingFileColumns([]);
    }
  };

  const handleExportTemplate = async () => {
    try {
      const filePath = await save({
        filters: [{ name: "Excel", extensions: ["xlsx"] }],
        defaultPath: `${config.title}模板.xlsx`,
      });
      if (!filePath) return;
      await bridge.call(config.exportTemplateMethod, { output_path: filePath });
    } catch (e) {
      setError(String(e));
    }
  };

  const handleSetDefault = async () => {
    setShowSetDefaultDialog(false);
    try {
      await bridge.call(config.setDefaultMethod);
      setIsDefault(true);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleCancelDefault = async () => {
    setShowCancelDefaultDialog(false);
    try {
      await bridge.call(config.cancelDefaultMethod);
      setIsDefault(false);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleClear = async () => {
    setShowClearDialog(false);
    try {
      await bridge.call(config.clearMethod);
      setRows([]);
      setColumns([]);
    } catch (e) {
      setError(String(e));
    }
  };

  // ---- Loading state ----

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400 gap-3">
        <svg className="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <span className="text-sm">加载中...</span>
      </div>
    );
  }

  // ---- Render ----

  return (
    <div className="flex flex-col h-full">
      {/* Title + Toolbar */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          {config.icon && (
            <span className="text-slate-500">{config.icon}</span>
          )}
          <h2 className="text-base font-semibold text-slate-800">{config.title}</h2>
          {isDefault && (
            <span className="text-xs bg-slate-100 text-slate-600 border border-slate-200 px-2 py-0.5 rounded-md inline-flex items-center gap-1">
              <IconStarFilled /> 默认
            </span>
          )}
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2">
              <IconSearch />
            </span>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setPage(0); }}
              placeholder="搜索..."
              className="input text-sm pl-8 pr-3 py-1.5 w-44 border-slate-300"
            />
            {searchTerm && (
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                {displayRows.length}
              </span>
            )}
          </div>

          <div className="w-px h-5 bg-slate-200 mx-0.5" />

          {/* Import */}
          <button
            onClick={handleImport}
            disabled={importing}
            className="btn-secondary"
            title="导入台账"
          >
            <IconImport />
            <span className="hidden sm:inline">导入</span>
          </button>

          {/* Export template */}
          <button
            onClick={handleExportTemplate}
            className="btn-secondary"
            title="导出模板"
          >
            <IconExport />
            <span className="hidden sm:inline">导出模板</span>
          </button>

          <div className="w-px h-5 bg-slate-200 mx-0.5" />

          {/* Set / Cancel default */}
          {isDefault ? (
            <button
              onClick={() => setShowCancelDefaultDialog(true)}
              className="btn-secondary"
              title="取消默认"
            >
              <IconStarFilled />
              <span className="hidden sm:inline">取消默认</span>
            </button>
          ) : (
            <button
              onClick={() => setShowSetDefaultDialog(true)}
              className="btn-secondary"
              title="设为默认"
            >
              <IconStar />
              <span className="hidden sm:inline">设为默认</span>
            </button>
          )}

          {/* Clear */}
          <button
            onClick={() => setShowClearDialog(true)}
            className="btn-danger"
            title="清空台账"
          >
            <IconTrash />
            <span className="hidden sm:inline">清空</span>
          </button>

          {/* Refresh */}
          <button
            onClick={loadData}
            className="btn-secondary"
            title="刷新"
          >
            <IconRefresh />
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-4 py-3 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {error}
          </span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
            <IconClose />
          </button>
        </div>
      )}

      {/* Empty state */}
      {rows.length === 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 p-16 text-center">
          <IconTable />
          <p className="text-slate-400 text-sm mt-4 mb-1">暂无数据</p>
          <p className="text-slate-400 text-xs mb-6">{config.emptyMessage}</p>
          <button
            onClick={handleImport}
            className="btn-primary inline-flex items-center gap-2 text-sm px-5 py-2"
          >
            <IconImport />
            导入台账
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden flex-1 flex flex-col min-h-0">
          <div className="overflow-auto flex-1">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10">
                <tr className="bg-slate-50">
                  {columns.map((col) => {
                    const active = sort?.column === col;
                    return (
                      <th
                        key={col}
                        onClick={() => handleSort(col)}
                        className={`text-left px-3 py-2 text-xs font-medium uppercase tracking-wider whitespace-nowrap cursor-pointer select-none transition-colors ${
                          active
                            ? "text-slate-700 bg-slate-100"
                            : "text-slate-500 hover:bg-slate-100"
                        }`}
                      >
                        <span className="inline-flex items-center gap-1.5">
                          {col}
                          <span className={`inline-flex flex-col -space-y-0.5 ${active ? "text-slate-600" : "text-slate-300"}`}>
                            <span className={active && sort?.direction === "asc" ? "text-slate-600" : "opacity-40"}>
                              <IconChevronUp />
                            </span>
                            <span className={active && sort?.direction === "desc" ? "text-slate-600" : "opacity-40"}>
                              <IconChevronDown />
                            </span>
                          </span>
                        </span>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {paged.map((row, i) => (
                  <tr
                    key={i}
                    className="h-9 border-b border-slate-100 transition-colors hover:bg-slate-50"
                  >
                    {columns.map((col) => (
                      <td key={col} className="px-3 text-slate-700 whitespace-nowrap text-sm">
                        {row[col] != null ? String(row[col]) : ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100 shrink-0">
            <span className="text-xs text-slate-500">
              {searchTerm ? `${displayRows.length} / ${rows.length} 条` : `共 ${rows.length} 条`}
              {sort && (
                <span className="ml-2 text-slate-400">
                  {sort.column} {sort.direction === "asc" ? "升序" : "降序"}
                </span>
              )}
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={safePage === 0}
                onClick={() => setPage((p) => p - 1)}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                <IconChevronLeft />
                上一页
              </button>
              <span className="text-xs text-slate-500 min-w-[4rem] text-center">
                {safePage + 1} / {totalPages}
              </span>
              <button
                disabled={safePage >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                下一页
                <IconChevronRight />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Column Mapping Modal */}
      <ColumnMappingModal
        open={showMapping}
        fileColumns={pendingFileColumns}
        standardColumns={config.standardColumns}
        onConfirm={handleMappingConfirm}
        onCancel={() => { setShowMapping(false); setPendingFilePath(""); setPendingFileColumns([]); }}
      />

      {/* Confirm dialogs */}
      <ConfirmDialog
        open={showClearDialog}
        title="清空台账"
        message={`确定要清空所有${config.title}数据吗？此操作不可撤销。`}
        confirmLabel="清空"
        danger
        onConfirm={handleClear}
        onCancel={() => setShowClearDialog(false)}
      />
      <ConfirmDialog
        open={showSetDefaultDialog}
        title="设为默认"
        message={`将当前${config.title}设为默认，后续处理将自动使用此台账。`}
        onConfirm={handleSetDefault}
        onCancel={() => setShowSetDefaultDialog(false)}
      />
      <ConfirmDialog
        open={showCancelDefaultDialog}
        title="取消默认"
        message={`取消当前${config.title}的默认状态。`}
        onConfirm={handleCancelDefault}
        onCancel={() => setShowCancelDefaultDialog(false)}
      />

      {/* Import overlay */}
      {importing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-lg border border-slate-200 px-8 py-6 flex items-center gap-3">
            <svg className="w-6 h-6 animate-spin text-slate-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm text-slate-600">正在导入...</span>
          </div>
        </div>
      )}
    </div>
  );
}
