import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ScanResult, ScannedFile } from "../lib/types";
import { CheckIcon, ChevronLeftIcon, ChevronRightIcon, FileIcon, QuestionIcon } from "../lib/icons";

const PAGE_SIZE = 8;
const ALL_FILTER = "all";
const TYPE_ORDER = ["fuel", "electrical", "production", "operation", "worktime"];

interface FileScanPanelProps {
  result: ScanResult | null;
  selectedPaths: ReadonlySet<string>;
  onToggle: (path: string, selected: boolean) => void;
  onToggleAll: (selected: boolean) => void;
  typeLabel: (type: string) => string;
  typeIcon?: (type: string) => ReactNode;
  title?: string;
  description?: string;
}

function fallbackFiles(result: ScanResult): ScannedFile[] {
  const files = new Map<string, ScannedFile>();
  for (const [type, paths] of Object.entries(result.matched ?? {})) {
    for (const path of paths) {
      const name = path.split(/[\\/]/).pop() || path;
      const current = files.get(path) ?? {
        path,
        name,
        relative_path: name,
        types: [],
        recognized: true,
        selected: true,
      };
      if (!current.types.includes(type)) current.types.push(type);
      files.set(path, current);
    }
  }
  return [...files.values()];
}

function filterTypeKey(type: string): string {
  return type === "work_efficiency" ? "worktime" : type;
}

export function FileScanPanel({
  result,
  selectedPaths,
  onToggle,
  onToggleAll,
  typeLabel,
  typeIcon,
  title,
  description,
}: FileScanPanelProps) {
  const { t } = useTranslation();
  const [activeFilter, setActiveFilter] = useState(ALL_FILTER);
  const [currentPage, setCurrentPage] = useState(1);

  const files = result ? (result.files?.length ? result.files : fallbackFiles(result)) : [];
  const typeFilters = useMemo(() => {
    const counts = new Map<string, number>();
    for (const file of files) {
      if (!file.recognized || file.types.length === 0) continue;
      for (const type of new Set(file.types.map(filterTypeKey))) {
        counts.set(type, (counts.get(type) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .sort(([left], [right]) => {
        const leftIndex = TYPE_ORDER.indexOf(left);
        const rightIndex = TYPE_ORDER.indexOf(right);
        if (leftIndex === -1 && rightIndex === -1) return left.localeCompare(right);
        if (leftIndex === -1) return 1;
        if (rightIndex === -1) return -1;
        return leftIndex - rightIndex;
      })
      .map(([type, count]) => ({ type, count }));
  }, [files]);

  const filteredFiles = useMemo(() => {
    if (activeFilter === ALL_FILTER) return files;
    return files.filter((file) => (
      file.recognized
      && file.types.some((type) => filterTypeKey(type) === activeFilter)
    ));
  }, [activeFilter, files]);
  const pageCount = Math.max(1, Math.ceil(filteredFiles.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, pageCount);
  const visibleFiles = filteredFiles.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const listMessage = files.length === 0
    ? t("pages:FileScanPanel.noExcelFiles")
    : filteredFiles.length === 0
      ? t("pages:FileScanPanel.noMatchingFiles")
      : null;
  const placeholderCount = Math.max(0, PAGE_SIZE - (listMessage ? 1 : visibleFiles.length));

  useEffect(() => {
    setActiveFilter(ALL_FILTER);
    setCurrentPage(1);
  }, [result]);

  useEffect(() => {
    setActiveFilter((current) => (
      current === ALL_FILTER || typeFilters.some(({ type }) => type === current) ? current : ALL_FILTER
    ));
  }, [typeFilters]);

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, pageCount));
  }, [pageCount]);

  if (!result) return null;

  const recognizedFiles = files.filter((file) => file.recognized && file.types.length > 0);
  const selectedCount = recognizedFiles.filter((file) => selectedPaths.has(file.path)).length;
  const allSelected = recognizedFiles.length > 0 && selectedCount === recognizedFiles.length;
  const filterTabs = [
    { type: ALL_FILTER, label: t("pages:FileScanPanel.allTypes"), count: files.length },
    ...typeFilters.map(({ type, count }) => ({ type, label: typeLabel(type), count })),
  ];

  return (
    <section
      className="mt-4 rounded-lg border border-slate-200 overflow-hidden"
      aria-label={title ?? t("pages:FileScanPanel.scanResults")}
    >
      <div className="flex flex-wrap items-center gap-2 px-3.5 py-2.5 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center gap-2 min-w-0">
          <SearchResultIcon />
          <h3 className="text-sm font-medium text-slate-700">
            {title ?? t("pages:FileScanPanel.scanResults")}
          </h3>
          <span className="text-xs text-slate-500">
            {t("pages:FileScanPanel.selectedCount", { selected: selectedCount, total: recognizedFiles.length })}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => onToggleAll(!allSelected)}
            disabled={recognizedFiles.length === 0}
            className="text-xs font-medium text-blue-700 hover:text-blue-800 disabled:text-slate-400 disabled:cursor-not-allowed"
          >
            {allSelected ? t("pages:FileScanPanel.clearAll") : t("pages:FileScanPanel.selectAll")}
          </button>
        </div>
      </div>

      {description && <p className="px-3.5 py-2 text-xs text-slate-500 border-b border-slate-100">{description}</p>}

      <div
        className="flex items-center gap-1 overflow-x-auto border-b border-slate-100 px-3 py-1.5"
        role="tablist"
        aria-label={t("pages:FileScanPanel.filterTabs")}
      >
        {filterTabs.map((tab) => {
          const active = activeFilter === tab.type;
          const icon = tab.type === ALL_FILTER ? null : typeIcon?.(tab.type);
          return (
            <button
              key={tab.type}
              type="button"
              role="tab"
              aria-selected={active}
              aria-label={`${tab.label} (${tab.count})`}
              onClick={() => {
                setActiveFilter(tab.type);
                setCurrentPage(1);
              }}
              className={`inline-flex shrink-0 items-center gap-1 rounded-md px-2.5 py-1 text-xs transition-colors ${
                active
                  ? "bg-blue-50 font-medium text-blue-700"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              }`}
            >
              {icon && (
                <span className="inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center [&>svg]:h-3.5 [&>svg]:w-3.5">
                  {icon}
                </span>
              )}
              <span>{tab.label}</span>
              <span className={active ? "text-blue-600/75" : "text-slate-400"}>{tab.count}</span>
            </button>
          );
        })}
      </div>

      <div className="divide-y divide-slate-100">
        {listMessage ? (
          <div className="flex h-14 items-center justify-center px-3.5 text-sm text-slate-500">{listMessage}</div>
        ) : visibleFiles.map((file) => {
          const recognized = file.recognized && file.types.length > 0;
          const checked = recognized && selectedPaths.has(file.path);
          return (
            <label
              key={file.path}
              className={`flex h-14 items-start gap-3 overflow-hidden px-3.5 py-2.5 ${recognized ? "cursor-pointer hover:bg-slate-50" : "bg-slate-50/60"}`}
            >
              <input
                type="checkbox"
                checked={checked}
                disabled={!recognized}
                onChange={(event) => onToggle(file.path, event.target.checked)}
                className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
                aria-label={file.name}
              />
              <span className={`mt-0.5 ${recognized ? "text-slate-500" : "text-slate-400"}`}>
                {recognized ? <FileIcon /> : <QuestionIcon />}
              </span>
              <span className="min-w-0 flex-1">
                <span className={`block truncate text-sm ${recognized ? "text-slate-700" : "text-slate-500"}`} title={file.path}>
                  {file.name}
                </span>
                <span className="mt-1 flex flex-wrap items-center gap-1.5">
                  {recognized ? file.types.map((type) => {
                    const icon = typeIcon?.(type);
                    return (
                      <span key={type} className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                        {icon && (
                          <span className="inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center [&>svg]:h-3.5 [&>svg]:w-3.5">
                            {icon}
                          </span>
                        )}
                        {typeLabel(type)}
                      </span>
                    );
                  }) : (
                    <span className="text-xs text-slate-400">{t("pages:FileScanPanel.unrecognized")}</span>
                  )}
                </span>
              </span>
              {recognized && checked && (
                <CheckIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
              )}
            </label>
          );
        })}
        {Array.from({ length: placeholderCount }, (_, index) => (
          <div key={`empty-row-${index}`} className="h-14 bg-slate-50/30" aria-hidden="true" />
        ))}
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-3.5 py-2">
          <span className="text-xs text-slate-500">
            {t("pages:FileScanPanel.pageSummary", { current: safePage, total: pageCount, count: filteredFiles.length })}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label={t("pages:FileScanPanel.previousPage")}
              onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
              disabled={safePage === 1}
              className="inline-flex h-6 w-6 items-center justify-center rounded text-slate-500 hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-300"
            >
              <ChevronLeftIcon />
            </button>
            <button
              type="button"
              aria-label={t("pages:FileScanPanel.nextPage")}
              onClick={() => setCurrentPage((page) => Math.min(pageCount, page + 1))}
              disabled={safePage === pageCount}
              className="inline-flex h-6 w-6 items-center justify-center rounded text-slate-500 hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-300"
            >
              <ChevronRightIcon />
            </button>
          </div>
        </div>
      )}

      {result.missing.length > 0 && (
        <div className="flex items-start gap-2 px-3.5 py-2.5 border-t border-amber-100 bg-amber-50 text-xs text-amber-800">
          <QuestionIcon />
          <span>
            {t("pages:FileScanPanel.missingTypes", {
              types: result.missing.map(typeLabel).join("、"),
            })}
          </span>
        </div>
      )}
    </section>
  );
}

function SearchResultIcon() {
  return (
    <span className="relative inline-flex h-4 w-4 items-center justify-center text-slate-500" aria-hidden="true">
      <span className="absolute inset-0 rounded border border-current opacity-60" />
      <span className="absolute bottom-[-2px] right-[-2px] h-1.5 w-1.5 rounded-full bg-blue-600" />
    </span>
  );
}
