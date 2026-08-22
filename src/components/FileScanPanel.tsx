import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ScanResult, ScannedFile } from "../lib/types";
import { CheckIcon, FileIcon, QuestionIcon } from "../lib/icons";

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
  if (!result) return null;

  const files = result.files?.length ? result.files : fallbackFiles(result);
  const recognizedFiles = files.filter((file) => file.recognized && file.types.length > 0);
  const selectedCount = recognizedFiles.filter((file) => selectedPaths.has(file.path)).length;
  const allSelected = recognizedFiles.length > 0 && selectedCount === recognizedFiles.length;

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

      <div className="max-h-72 overflow-y-auto divide-y divide-slate-100">
        {files.length === 0 ? (
          <div className="px-3.5 py-6 text-sm text-slate-500 text-center">{t("pages:FileScanPanel.noExcelFiles")}</div>
        ) : files.map((file) => {
          const recognized = file.recognized && file.types.length > 0;
          const checked = recognized && selectedPaths.has(file.path);
          return (
            <label
              key={file.path}
              className={`flex items-start gap-3 px-3.5 py-2.5 ${recognized ? "cursor-pointer hover:bg-slate-50" : "bg-slate-50/60"}`}
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
                  {recognized ? file.types.map((type) => (
                    <span key={type} className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                      {typeIcon?.(type)}
                      {typeLabel(type)}
                    </span>
                  )) : (
                    <span className="text-xs text-slate-400">{t("pages:FileScanPanel.unrecognized")}</span>
                  )}
                </span>
              </span>
              {recognized && checked && <CheckIcon className="mt-0.5 shrink-0 text-emerald-600" />}
            </label>
          );
        })}
      </div>

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
