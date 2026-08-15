import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { open, save } from "@tauri-apps/plugin-dialog";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { useLastDirectory } from "../../hooks/useLastDirectory";
import {
  ImportIcon, ExportIcon, StarIcon, StarFilledIcon,
  TrashIcon, RefreshIcon, SearchIcon, ChevronUpIcon,
  ChevronDownSmallIcon, ChevronLeftIcon, ChevronRightIcon,
  CloseIcon, ArrowRightIcon, TableIcon,
} from "../../lib/icons";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface LedgerPageConfig {
  /** Page title, e.g. "设备台账" */
  title: string;
  /** Page icon: JSX element (SVG) rendered next to the title */
  icon?: React.ReactNode;
  /** Standard column names for the ledger, e.g. ["设备名称", ...] */
  standardColumns: string[];
  /** Stable Chinese business title used for exported filenames. */
  businessTitle?: string;
  /** Stable Chinese business filename used for template exports. */
  businessTemplateFilename?: string;
  /** Bridge method to load rows */
  loadDataMethod: string;
  /** Bridge method to import from Excel with column mapping */
  importMethod: string;
  /** Bridge method to export a blank template */
  exportTemplateMethod: string;
  /** Bridge method to export current data as Excel */
  exportDataMethod?: string;
  /** Data type parameter for export (e.g. "oil", "equipment") */
  exportDataType?: string;
  /** Bridge method to set as default */
  setDefaultMethod: string;
  /** Bridge method to cancel default */
  cancelDefaultMethod: string;
  /** Bridge method to clear all data */
  clearMethod: string;
  /** Bridge method to load file columns for mapping */
  loadFileColumnsMethod: string;
  /** Bridge method to list Excel sheets */
  listSheetsMethod: string;
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
// Sheet Selection Modal
// ---------------------------------------------------------------------------

function SheetSelectionModal({
  open: isOpen,
  sheets,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  sheets: string[];
  onConfirm: (sheet: string) => void;
  onCancel: () => void;
}) {
  const [selected, setSelected] = useState(sheets[0] || "");
  const { t } = useTranslation();

  useEffect(() => {
    if (isOpen && sheets.length > 0) {
      setSelected(sheets[0]);
    }
  }, [isOpen, sheets]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-lg border border-slate-200 w-full max-w-sm mx-4 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <TableIcon />
            {t("pages:LedgerPage.ui.selectSheet")}
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {t("pages:LedgerPage.ui.selectSheetHint")}
          </p>
        </div>

        <div className="px-5 py-3 max-h-60 overflow-y-auto space-y-1">
          {sheets.map((sheet) => (
            <label
              key={sheet}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-md cursor-pointer transition-colors ${
                selected === sheet
                  ? "bg-blue-50 border border-blue-200"
                  : "hover:bg-slate-50 border border-transparent"
              }`}
            >
              <input
                type="radio"
                name="sheet-select"
                value={sheet}
                checked={selected === sheet}
                onChange={() => setSelected(sheet)}
                className="accent-blue-600"
              />
              <span className="text-sm text-slate-700">{sheet}</span>
            </label>
          ))}
        </div>

        <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="btn-secondary text-sm px-4 py-1.5"
          >
            {t("pages:LedgerPage.ui.cancel")}
          </button>
          <button
            onClick={() => onConfirm(selected)}
            className="btn-primary text-sm px-4 py-1.5"
          >
            {t("pages:LedgerPage.ui.next")}
          </button>
        </div>
      </div>
    </div>
  );
}

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
  const { t } = useTranslation();
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
            {t("pages:LedgerPage.ui.columnMapping")}
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {t("pages:LedgerPage.ui.columnMappingHint")}
          </p>
        </div>

        <div className="px-5 py-3 max-h-80 overflow-y-auto space-y-2.5">
          {standardColumns.map((stdCol) => (
            <div key={stdCol} className="flex items-center gap-3">
              <span className="w-32 text-sm text-slate-700 font-medium truncate" title={stdCol}>
                {stdCol}
              </span>
              <ArrowRightIcon />
              <select
                value={mapping[stdCol] || ""}
                onChange={(e) =>
                  setMapping((prev) => ({ ...prev, [stdCol]: e.target.value }))
                }
                className="input flex-1"
              >
                <option value="">{t("pages:LedgerPage.skip")}</option>
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
            {t("pages:LedgerPage.ui.cancel")}
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
            {t("pages:LedgerPage.ui.confirmImport")}
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
  confirmLabel,
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
  const { t } = useTranslation();
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
            {t("pages:LedgerPage.ui.cancel")}
          </button>
          <button
            onClick={onConfirm}
            className={`${danger ? "btn-danger" : "btn-primary"} text-sm px-4 py-1.5`}
          >
            {confirmLabel ?? t("pages:LedgerPage.ui.confirm")}
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
  const { notify } = useToast();
  const { t } = useTranslation();
  const { initialDir, saveDir } = useLastDirectory(bridge);
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
  const [pendingSheets, setPendingSheets] = useState<string[]>([]);
  const [showSheetSelection, setShowSheetSelection] = useState(false);
  const [pendingSheetName, setPendingSheetName] = useState<string>("");
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
        defaultPath: initialDir || undefined,
        filters: [{ name: "Excel", extensions: ["xlsx", "xls"] }],
      });
      if (!filePath) return;
      const path = typeof filePath === "string" ? filePath : filePath;
      setPendingFilePath(path);
      saveDir(path);

      // Get sheets list
      const sheetsRes = await bridge.call<{ sheets: string[] }>(
        config.listSheetsMethod,
        { path }
      );
      const sheets = sheetsRes.sheets || [];

      if (sheets.length <= 1) {
        // Single sheet: skip selection, go directly to column mapping
        const sheetName = sheets[0] || "";
        setPendingSheetName(sheetName);
        await loadColumnsForSheet(path, sheetName);
      } else {
        // Multiple sheets: show sheet selection
        setPendingSheets(sheets);
        setShowSheetSelection(true);
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const loadColumnsForSheet = async (path: string, sheetName: string) => {
    try {
      const res = await bridge.call<{ columns: string[]; sheets: string[] }>(
        config.loadFileColumnsMethod,
        { file_path: path, sheet_name: sheetName }
      );
      setPendingFileColumns(res.columns || []);
      setShowMapping(true);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleSheetConfirm = (sheetName: string) => {
    setShowSheetSelection(false);
    setPendingSheetName(sheetName);
    loadColumnsForSheet(pendingFilePath, sheetName);
  };

  const handleMappingConfirm = async (mapping: Record<string, string>) => {
    setShowMapping(false);
    setImporting(true);
    setError(null);
    try {
      await bridge.call(config.importMethod, {
        file_path: pendingFilePath,
        column_mapping: mapping,
        sheet_name: pendingSheetName || undefined,
      });
      await loadData();
      notify(t("pages:LedgerPage.importedSuccessfully"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:LedgerPage.importFailed", { error: String(e) }), "error");
    } finally {
      setImporting(false);
      setPendingFilePath("");
      setPendingFileColumns([]);
      setPendingSheetName("");
    }
  };

  const handleExportTemplate = async () => {
    try {
      const filePath = await save({
        filters: [{ name: "Excel", extensions: ["xlsx"] }],
        defaultPath: config.businessTemplateFilename
          ?? t("pages:LedgerPage.templateFilename", { title: config.title }),
      });
      if (!filePath) return;
      await bridge.call(config.exportTemplateMethod, { output_path: filePath });
      notify(t("pages:LedgerPage.templateExported"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:LedgerPage.templateExportFailed", { error: String(e) }), "error");
    }
  };

  const handleExportData = async () => {
    if (!config.exportDataMethod || rows.length === 0) return;
    try {
      const filePath = await save({
        filters: [{ name: "Excel", extensions: ["xlsx"] }],
        defaultPath: `${config.businessTitle ?? config.title}.xlsx`,
      });
      if (!filePath) return;
      await bridge.call(config.exportDataMethod, {
        data_type: config.exportDataType,
        output_path: filePath,
      });
      notify(t("pages:LedgerPage.ledgerExported"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:LedgerPage.ledgerExportFailed", { error: String(e) }), "error");
    }
  };

  const handleSetDefault = async () => {
    setShowSetDefaultDialog(false);
    try {
      await bridge.call(config.setDefaultMethod);
      setIsDefault(true);
      notify(t("pages:LedgerPage.setAsDefaultSetAsDefault"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:LedgerPage.setAsDefaultfailed", { error: String(e) }), "error");
    }
  };

  const handleCancelDefault = async () => {
    setShowCancelDefaultDialog(false);
    try {
      await bridge.call(config.cancelDefaultMethod);
      setIsDefault(false);
      notify(t("pages:LedgerPage.defaultCleared"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:LedgerPage.clearDefaultfailed", { error: String(e) }), "error");
    }
  };

  const handleClear = async () => {
    setShowClearDialog(false);
    try {
      await bridge.call(config.clearMethod);
      setRows([]);
      setColumns([]);
      notify(t("pages:LedgerPage.ledgerCleared"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:LedgerPage.clearFailed", { error: String(e) }), "error");
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
        <span className="text-sm">{t("pages:LedgerPage.text")}</span>
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
              <StarFilledIcon /> {t("pages:LedgerPage.ui.default")}
            </span>
          )}
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none">
              <SearchIcon />
            </span>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setPage(0); }}
              placeholder={t("pages:LedgerPage.textVariant")}
              className="input text-sm w-44 border-slate-300"
              style={{ paddingLeft: "2.25rem", paddingRight: "0.75rem" }}
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
            title={t("pages:LedgerPage.importLedger")}
          >
            <ImportIcon />
            <span className="hidden sm:inline">{t("pages:LedgerPage.ui.import")}</span>
          </button>

          {/* Export template */}
          <button
            onClick={handleExportTemplate}
            className="btn-secondary"
            title={t("pages:LedgerPage.exportTemplate")}
          >
            <ExportIcon />
            <span className="hidden sm:inline">{t("pages:LedgerPage.exportTemplate")}</span>
          </button>

          {/* Export data */}
          {config.exportDataMethod && rows.length > 0 && (
            <button
              onClick={handleExportData}
              className="btn-secondary"
              title={t("pages:LedgerPage.exportLedger")}
            >
              <ExportIcon />
              <span className="hidden sm:inline">{t("pages:LedgerPage.exportLedger")}</span>
            </button>
          )}

          <div className="w-px h-5 bg-slate-200 mx-0.5" />

          {/* Set / Cancel default */}
          {isDefault ? (
            <button
              onClick={() => setShowCancelDefaultDialog(true)}
              className="btn-secondary"
              title={t("pages:LedgerPage.clearDefault")}
            >
              <StarFilledIcon />
              <span className="hidden sm:inline">{t("pages:LedgerPage.clearDefault")}</span>
            </button>
          ) : (
            <button
              onClick={() => setShowSetDefaultDialog(true)}
              className="btn-secondary"
              title={t("pages:LedgerPage.setAsDefaultVariant")}
            >
              <StarIcon />
              <span className="hidden sm:inline">{t("pages:LedgerPage.setAsDefaultVariant")}</span>
            </button>
          )}

          {/* Clear */}
          <button
            onClick={() => setShowClearDialog(true)}
            className="btn-danger"
            title={t("pages:LedgerPage.clearLedger")}
          >
            <TrashIcon />
            <span className="hidden sm:inline">{t("pages:LedgerPage.ui.clear")}</span>
          </button>

          {/* Refresh */}
          <button
            onClick={loadData}
            className="btn-secondary"
            title={t("pages:LedgerPage.ui.refresh")}
          >
            <RefreshIcon />
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
            <CloseIcon />
          </button>
        </div>
      )}

      {/* Empty state */}
      {rows.length === 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 p-16 text-center">
          <TableIcon />
          <p className="text-slate-400 text-sm mt-4 mb-1">{t("pages:LedgerPage.noData")}</p>
          <p className="text-slate-400 text-xs mb-6">{config.emptyMessage}</p>
          <button
            onClick={handleImport}
            className="btn-primary inline-flex items-center gap-2 text-sm px-5 py-2"
          >
            <ImportIcon />
            {t("pages:LedgerPage.importLedger")}
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
                              <ChevronUpIcon />
                            </span>
                            <span className={active && sort?.direction === "desc" ? "text-slate-600" : "opacity-40"}>
                              <ChevronDownSmallIcon />
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
              {searchTerm ? t("pages:LedgerPage.items", { shown: displayRows.length, total: rows.length }) : t("pages:LedgerPage.totalItems", { total: rows.length })}
              {sort && (
                <span className="ml-2 text-slate-400">
                  {sort.column} {sort.direction === "asc" ? t("pages:LedgerPage.asc") : t("pages:LedgerPage.desc")}
                </span>
              )}
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={safePage === 0}
                onClick={() => setPage((p) => p - 1)}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                <ChevronLeftIcon />
                {t("pages:LedgerPage.ui.previousPage")}
              </button>
              <span className="text-xs text-slate-500 min-w-[4rem] text-center">
                {safePage + 1} / {totalPages}
              </span>
              <button
                disabled={safePage >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                {t("pages:LedgerPage.ui.nextPage")}
                <ChevronRightIcon />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sheet Selection Modal */}
      <SheetSelectionModal
        open={showSheetSelection}
        sheets={pendingSheets}
        onConfirm={handleSheetConfirm}
        onCancel={() => { setShowSheetSelection(false); setPendingFilePath(""); setPendingSheets([]); }}
      />

      {/* Column Mapping Modal */}
      <ColumnMappingModal
        open={showMapping}
        fileColumns={pendingFileColumns}
        standardColumns={config.standardColumns}
        onConfirm={handleMappingConfirm}
        onCancel={() => { setShowMapping(false); setPendingFilePath(""); setPendingFileColumns([]); setPendingSheetName(""); }}
      />

      {/* Confirm dialogs */}
      <ConfirmDialog
        open={showClearDialog}
        title={t("pages:LedgerPage.clearLedger")}
        message={t("pages:LedgerPage.datacleardataDatadataThisActionCannotBeUndone", { title: config.title })}
        confirmLabel={t("pages:LedgerPage.ui.clear")}
        danger
        onConfirm={handleClear}
        onCancel={() => setShowClearDialog(false)}
      />
      <ConfirmDialog
        open={showSetDefaultDialog}
        title={t("pages:LedgerPage.setAsDefaultVariant")}
        message={t("pages:LedgerPage.defaultDefaultdefaultDefaultprocessingdefaultledger", { title: config.title })}
        onConfirm={handleSetDefault}
        onCancel={() => setShowSetDefaultDialog(false)}
      />
      <ConfirmDialog
        open={showCancelDefaultDialog}
        title={t("pages:LedgerPage.clearDefault")}
        message={t("pages:LedgerPage.defaultDefaultdefaultdefault", { title: config.title })}
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
            <span className="text-sm text-slate-600">{t("pages:LedgerPage.textVariant2")}</span>
          </div>
        </div>
      )}
    </div>
  );
}
