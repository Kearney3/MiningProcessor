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

export function AnomalyPanel({
  config,
  onChange,
}: {
  config: AnomalyConfig;
  onChange: (c: AnomalyConfig) => void;
}) {
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
        </div>
      )}
    </div>
  );
}
