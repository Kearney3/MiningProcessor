import { useEffect, useState } from "react";

export interface AnomalyConfig {
  enabled: boolean;
  report: boolean;
  mode: "flag" | "filter" | "handle";
}

export const DEFAULT_ANOMALY_CONFIG: AnomalyConfig = {
  enabled: false,
  report: false,
  mode: "flag",
};

const MODE_OPTIONS = [
  { label: "标记异常值", value: "flag" as const, desc: "标记但不删除" },
  { label: "过滤异常值", value: "filter" as const, desc: "移除异常行" },
  { label: "处理异常值", value: "handle" as const, desc: "按配置替换默认值" },
];

// 逐列检测开关的默认列配置（与 func/anomaly/rules.py 保持一致）
const TYPE_COLUMNS: Record<string, { label: string; columns: string[] }> = {
  fuel: { label: "油耗", columns: ["油品消耗"] },
  fuel_engine: { label: "发动机", columns: ["发动机小时数开始", "发动机小时数结束", "运行小时数"] },
  production_running: { label: "运行", columns: ["运行里程", "运行小时数", "趟次"] },
  production: { label: "生产", columns: ["趟次", "产量"] },
  electrical: { label: "电力", columns: ["电力消耗"] },
  worktime: { label: "工时", columns: ["__all_numeric__"] },
};

export type ColumnToggles = Record<string, boolean>;

export function buildDefaultColumnToggles(): ColumnToggles {
  const toggles: ColumnToggles = {};
  for (const [dtype, cfg] of Object.entries(TYPE_COLUMNS)) {
    for (const col of cfg.columns) {
      toggles[`${dtype}:${col}`] = true;
    }
  }
  return toggles;
}

function mergeColumnToggles(
  defaults: ColumnToggles,
  overrides?: Record<string, Record<string, { enabled?: boolean }>>,
): ColumnToggles {
  if (!overrides) return { ...defaults };
  const result = { ...defaults };
  for (const key of Object.keys(defaults)) {
    const [dtype, col] = key.split(":");
    const dtypeCfg = overrides[dtype];
    if (dtypeCfg && col in dtypeCfg && typeof dtypeCfg[col] === "object") {
      const colEnabled = dtypeCfg[col].enabled;
      if (typeof colEnabled === "boolean") {
        result[key] = colEnabled;
      }
    }
  }
  return result;
}

export function AnomalyPanel({
  config,
  onChange,
  columnToggles,
  onColumnTogglesChange,
  savedThresholds,
  savedStatisticalColumns,
}: {
  config: AnomalyConfig;
  onChange: (c: AnomalyConfig) => void;
  columnToggles: ColumnToggles;
  onColumnTogglesChange: (t: ColumnToggles) => void;
  savedThresholds?: Record<string, Record<string, { enabled?: boolean }>>;
  savedStatisticalColumns?: Record<string, Record<string, { enabled?: boolean }>>;
}) {
  const [initialized, setInitialized] = useState(false);

  // 首次挂载时从保存的配置初始化列开关默认值
  useEffect(() => {
    if (initialized) return;
    setInitialized(true);
    const defaults = buildDefaultColumnToggles();
    const fromThresholds = mergeColumnToggles(defaults, savedThresholds);
    const fromStat = mergeColumnToggles(fromThresholds, savedStatisticalColumns);
    const changed = Object.keys(defaults).some((k) => defaults[k] !== fromStat[k]);
    if (changed) {
      onColumnTogglesChange(fromStat);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
      <label className="flex items-center gap-2.5 cursor-pointer select-none">
        <button
          role="switch"
          aria-checked={config.enabled}
          onClick={() => onChange({ ...config, enabled: !config.enabled })}
          className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
            config.enabled ? "bg-blue-600" : "bg-slate-200"
          }`}
        >
          <span
            className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
              config.enabled ? "translate-x-4" : "translate-x-0.5"
            }`}
          />
        </button>
        <span className="text-sm text-slate-700">启用异常值检测</span>
      </label>
      {config.enabled && (
        <div className="ml-6 space-y-2">
          <label className="flex items-center gap-2.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={config.report}
              onChange={(e) => onChange({ ...config, report: e.target.checked })}
              className="rounded border-slate-300"
            />
            <span className="text-sm text-slate-700">输出异常报告</span>
          </label>
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <span>处理方式：</span>
            <div className="inline-flex rounded-md border border-slate-200 overflow-hidden">
              {MODE_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  onClick={() => onChange({ ...config, mode: o.value })}
                  title={o.desc}
                  className={`text-xs px-3 py-1.5 transition-colors ${
                    config.mode === o.value
                      ? "bg-slate-900 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          {/* 逐列检测开关 */}
          <div className="space-y-2 pt-1 border-t border-slate-200 mt-2">
            <span className="text-xs font-medium text-slate-500">逐列检测开关</span>
            {Object.entries(TYPE_COLUMNS).map(([dtype, cfg]) => (
              <div key={dtype} className="flex items-start gap-2">
                <span className="text-xs text-slate-500 w-12 shrink-0 pt-0.5">{cfg.label}:</span>
                <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                  {cfg.columns.map((col) => {
                    const key = `${dtype}:${col}`;
                    const label = col === "__all_numeric__" ? "全部数值列" : col;
                    return (
                      <label key={key} className="flex items-center gap-1 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={columnToggles[key] ?? true}
                          onChange={(e) =>
                            onColumnTogglesChange({ ...columnToggles, [key]: e.target.checked })
                          }
                          className="rounded border-slate-300 h-3 w-3"
                        />
                        <span className="text-xs text-slate-600">{label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
