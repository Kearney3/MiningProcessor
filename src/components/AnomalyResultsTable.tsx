import type { AnomalyRecord } from "../lib/types";
import { AlertTriangleIcon } from "../lib/icons";

const columns: { key: keyof AnomalyRecord; label: string; className?: string }[] = [
  { key: "数据类型", label: "数据类型", className: "px-4" },
  { key: "行号", label: "行号" },
  { key: "日期", label: "日期" },
  { key: "班次", label: "班次" },
  { key: "设备名称", label: "设备名称" },
  { key: "设备编号", label: "设备编号" },
  { key: "异常列", label: "异常列" },
  { key: "异常值", label: "异常值" },
  { key: "检测方法", label: "检测方法" },
  { key: "说明", label: "说明", className: "pr-4" },
];

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "（空）";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

export function AnomalyResultsTable({ records }: { records: AnomalyRecord[] }) {
  if (records.length === 0) return null;

  return (
    <div className="bg-white rounded-lg border border-amber-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-amber-100 bg-amber-50 flex items-center justify-between">
        <h3 className="text-sm font-medium text-amber-700 flex items-center gap-2">
          <AlertTriangleIcon />
          异常值明细
          <span className="text-xs text-amber-500">共 {records.length} 条</span>
        </h3>
        <span className="text-xs text-amber-600">滚动查看全部记录</span>
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
}
