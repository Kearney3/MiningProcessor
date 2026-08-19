import { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { AnomalyRecord } from "../lib/types";
import { AlertTriangleIcon } from "../lib/icons";

const getColumns = (t: (k: string) => string): { key: keyof AnomalyRecord; label: string; className?: string }[] => [
  { key: "数据类型", label: t("components:AnomalyResultsTable.dataType"), className: "px-4" },
  { key: "行号", label: t("components:AnomalyResultsTable.row") },
  { key: "日期", label: t("components:AnomalyResultsTable.date") },
  { key: "班次", label: t("components:AnomalyResultsTable.shift") },
  { key: "设备名称", label: t("components:AnomalyResultsTable.equipment") },
  { key: "设备编号", label: t("components:AnomalyResultsTable.equipmentId") },
  { key: "异常列", label: t("components:AnomalyResultsTable.anomalyColumn") },
  { key: "异常值", label: t("components:AnomalyResultsTable.anomalyValue") },
  { key: "检测方法", label: t("components:AnomalyResultsTable.method") },
  { key: "说明", label: t("components:AnomalyResultsTable.note"), className: "pr-4" },
];

function makeDisplayValue(t: (k: string) => string) {
  return function displayValue(value: unknown): string {
    if (value === null || value === undefined || value === "") return t("components:AnomalyResultsTable.empty");
    if (typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }
    return String(value);
  };
}

export const AnomalyResultsTable = memo(function AnomalyResultsTable({ records }: { records: AnomalyRecord[] }) {
  const { t } = useTranslation();
  const columns = useMemo(() => getColumns(t), [t]);
  const displayValue = useMemo(() => makeDisplayValue(t), [t]);
  if (records.length === 0) return null;

  return (
    <div className="bg-white rounded-lg border border-amber-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-amber-100 bg-amber-50 flex items-center justify-between">
        <h3 className="text-sm font-medium text-amber-700 flex items-center gap-2">
          <AlertTriangleIcon />
          {t("components:AnomalyResultsTable.anomalyDetails")}
          <span className="text-xs text-amber-500">{t("components:AnomalyResultsTable.total", { count: records.length })}</span>
        </h3>
        <span className="text-xs text-amber-600">{t("components:AnomalyResultsTable.scrollToViewAll")}</span>
      </div>
      <div className="max-h-72 overflow-auto">
        <table className="min-w-[980px] w-full text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="bg-amber-50 text-left">
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`${column.className ?? ""} py-2 text-xs font-medium text-amber-600 whitespace-nowrap`}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((record, index) => (
              <tr
                key={`${displayValue(record.数据类型)}-${displayValue(record.行号)}-${displayValue(record.异常列)}-${index}`}
                className={`h-9 border-b border-slate-100 hover:bg-amber-50/50 ${index % 2 === 0 ? "bg-white" : "bg-slate-50"}`}
              >
                {columns.map((column) => {
                  const value = displayValue(record[column.key]);
                  const isAnomalyValue = column.key === "异常值";
                  return (
                    <td
                      key={column.key}
                      className={`${column.className ?? ""} py-2 text-sm whitespace-nowrap ${isAnomalyValue ? "text-red-600 font-mono" : "text-slate-600"}`}
                      title={value}
                    >
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
});
