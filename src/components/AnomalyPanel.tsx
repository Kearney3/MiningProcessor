import { useTranslation } from "react-i18next";

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

const getModeOptions = (t: (k: string) => string) => [
  { label: t("components:AnomalyPanel.flagAnomalies"), value: "flag" as const, desc: t("components:AnomalyPanel.flagWithoutDeleting") },
  { label: t("components:AnomalyPanel.filterAnomalies"), value: "filter" as const, desc: t("components:AnomalyPanel.removeRows") },
  { label: t("components:AnomalyPanel.handleAnomalies"), value: "handle" as const, desc: t("components:AnomalyPanel.replaceWithConfiguredDefaults") },
];

export function AnomalyPanel({
  config,
  onChange,
  embedded = false,
}: {
  config: AnomalyConfig;
  onChange: (c: AnomalyConfig) => void;
  embedded?: boolean;
}) {
  const { t } = useTranslation();
  const MODE_OPTIONS = getModeOptions(t);
  return (
    <div className={embedded ? "space-y-2" : "rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2"}>
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
        <span className="text-sm text-slate-700">{t("components:AnomalyPanel.enableAnomalyDetection")}</span>
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
            <span className="text-sm text-slate-700">{t("components:AnomalyPanel.exportReport")}</span>
          </label>
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <span>{t("components:AnomalyPanel.processingMode")}</span>
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
          <p className="text-xs text-slate-400">
            {t("components:AnomalyPanel.ui.columnRulesHint")}
          </p>
        </div>
      )}
    </div>
  );
}
