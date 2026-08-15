import { useState, useEffect, useCallback } from "react";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { TuneIcon, CloseIcon } from "../../lib/icons";
import { SectionCard, ActionButtons, StatusMessage } from "./_shared";
import { useTranslation } from "react-i18next";

// ---------------------------------------------------------------------------
// Types & Constants
// ---------------------------------------------------------------------------

interface ThresholdRow {
  column: string;
  min: string;
  max: string;
  default: string;
}

interface AnomalyConfig {
  enabled: boolean;
  generate_report: boolean;
  flag_anomalies: boolean;
  filter_anomalies: boolean;
  handle_anomalies: boolean;
  use_threshold: boolean;
  use_sigma: boolean;
  use_percentile: boolean;
  sigma_n: number;
  percentile_low: number;
  percentile_high: number;
  thresholds: Record<string, Record<string, { min?: number; max?: number; enabled?: boolean }>>;
  statistical_columns: Record<string, Record<string, { enabled?: boolean }>>;
  handling_rules: Record<string, Record<string, { strategy: string; default?: number }>>;
}

const getDataTypeOptions = (t: (k: string) => string): { key: string; label: string }[] => [
  { key: "fuel", label: t("userConfig:AnomalyConfigSection.fuelConsumptionVariant") },
  { key: "fuel_engine", label: t("userConfig:AnomalyConfigSection.engine") },
  { key: "production_running", label: t("userConfig:AnomalyConfigSection.runtimeData") },
  { key: "production", label: t("userConfig:AnomalyConfigSection.productionData") },
  { key: "electrical", label: t("userConfig:AnomalyConfigSection.electricalConsumption") },
  { key: "worktime", label: t("userConfig:AnomalyConfigSection.worktimeData") },
  { key: "tire", label: t("userConfig:AnomalyConfigSection.tireData") },
];

const ALL_NUMERIC = "__all_numeric__";

// ---------------------------------------------------------------------------
// Anomaly Config Section
// ---------------------------------------------------------------------------

export function AnomalyConfigSection({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const DATA_TYPE_OPTIONS = getDataTypeOptions(t);
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });

  // 检测方法开关
  const [useThreshold, setUseThreshold] = useState(true);
  const [useSigma, setUseSigma] = useState(false);
  const [usePercentile, setUsePercentile] = useState(false);

  // 统计参数
  const [sigmaN, setSigmaN] = useState("3.0");
  const [pctLow, setPctLow] = useState("1.0");
  const [pctHigh, setPctHigh] = useState("99.0");

  // 当前选中数据类型 & 各类型的阈值行
  const [activeType, setActiveType] = useState("fuel");
  const [thresholdRows, setThresholdRows] = useState<Record<string, ThresholdRow[]>>({});

  // 逐列检测开关（持久化到用户配置）
  type ColumnToggles = Record<string, boolean>;
  const COLUMN_DEFS: Record<string, string[]> = {
    fuel: ["油品消耗"],
    fuel_engine: ["发动机小时数开始", "发动机小时数结束", "运行小时数"],
    production_running: ["运行里程", "运行小时数", "趟次"],
    production: ["趟次", "产量"],
    electrical: ["电力消耗"],
    worktime: ["__all_numeric__"],
    tire: ["寿命（时间）", "寿命（里程）"],
  };
  const [columnToggles, setColumnToggles] = useState<ColumnToggles>(() => {
    const t: ColumnToggles = {};
    for (const [dtype, cols] of Object.entries(COLUMN_DEFS)) {
      for (const col of cols) t[`${dtype}:${col}`] = true;
    }
    return t;
  });

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<AnomalyConfig>("get_anomaly_config", {});
      if (raw && typeof raw === "object") {
        setUseThreshold(raw.use_threshold ?? true);
        setUseSigma(raw.use_sigma ?? false);
        setUsePercentile(raw.use_percentile ?? false);
        setSigmaN(String(raw.sigma_n ?? 3.0));
        setPctLow(String(raw.percentile_low ?? 1.0));
        setPctHigh(String(raw.percentile_high ?? 99.0));

        // 构建每类型的行
        const rows: Record<string, ThresholdRow[]> = {};
        const handling = raw.handling_rules || {};
        for (const { key } of DATA_TYPE_OPTIONS) {
          const dtThresholds = raw.thresholds?.[key] || {};
          const dtHandling = handling[key] || {};
          rows[key] = Object.entries(dtThresholds).map(([col, bounds]) => {
            const rule = dtHandling[col];
            return {
              column: col,
              min: bounds.min !== undefined ? String(bounds.min) : "",
              max: bounds.max !== undefined ? String(bounds.max) : "",
              default: rule?.strategy === "default_value" && rule.default !== undefined ? String(rule.default) : "",
            };
          });
          if (rows[key].length === 0) rows[key] = [];
        }
        setThresholdRows(rows);

        // 加载逐列检测开关
        const t: ColumnToggles = {};
        const thresholdsData = raw.thresholds || {};
        const statData = raw.statistical_columns || {};
        for (const dtype of DATA_TYPE_OPTIONS.map((o) => o.key)) {
          const tCfg = thresholdsData[dtype] || {};
          const sCfg = statData[dtype] || {};
          for (const col of COLUMN_DEFS[dtype] || []) {
            const tVal = tCfg[col]?.enabled ?? true;
            const sVal = sCfg[col]?.enabled ?? true;
            t[`${dtype}:${col}`] = tVal && sVal;
          }
        }
        // 只有当值有变化时才更新
        const changed = Object.keys(t).some((k) => t[k] !== (columnToggles[k] ?? true));
        if (changed) setColumnToggles(t);
      }
      setStatus({ msg: "", kind: "info" });
    } catch {
      // 静默失败，使用默认值
    }
  }, [bridge.call]);

  useEffect(() => { reload(); }, [reload]);

  const updateRow = (type: string, idx: number, field: keyof ThresholdRow, value: string) => {
    setThresholdRows((prev) => ({
      ...prev,
      [type]: (prev[type] || []).map((r, i) => (i === idx ? { ...r, [field]: value } : r)),
    }));
  };

  const addRow = () => {
    setThresholdRows((prev) => ({
      ...prev,
      [activeType]: [...(prev[activeType] || []), { column: "", min: "", max: "", default: "" }],
    }));
  };

  const removeRow = (type: string, idx: number) => {
    setThresholdRows((prev) => ({
      ...prev,
      [type]: (prev[type] || []).filter((_, i) => i !== idx),
    }));
  };

  const save = async () => {
    setSaving(true);
    try {
      // 收集阈值 + 处理规则
      const thresholds: Record<string, Record<string, { min?: number; max?: number; enabled?: boolean }>> = {};
      const handling_rules: Record<string, Record<string, { strategy: string; default?: number }>> = {};

      for (const { key } of DATA_TYPE_OPTIONS) {
        const rows = thresholdRows[key] || [];
        const dtThresholds: Record<string, { min?: number; max?: number; enabled?: boolean }> = {};
        const dtHandling: Record<string, { strategy: string; default?: number }> = {};

        for (const row of rows) {
          const col = row.column.trim();
          if (!col) continue;

          const bounds: { min?: number; max?: number } = {};
          if (row.min.trim()) {
            const v = parseFloat(row.min);
            if (!isNaN(v)) bounds.min = v;
          }
          if (row.max.trim()) {
            const v = parseFloat(row.max);
            if (!isNaN(v)) bounds.max = v;
          }
          if (Object.keys(bounds).length > 0) dtThresholds[col] = bounds;

          if (row.default.trim()) {
            const v = parseFloat(row.default);
            dtHandling[col] = { strategy: "default_value", default: isNaN(v) ? 0 : v };
          }
        }
        if (Object.keys(dtThresholds).length > 0) thresholds[key] = dtThresholds;
        if (Object.keys(dtHandling).length > 0) handling_rules[key] = dtHandling;
      }

      const parseOr = (s: string, fallback: number) => {
        const v = parseFloat(s);
        return isNaN(v) ? fallback : v;
      };

      // 合并逐列检测开关到 thresholds 和 statistical_columns
      const thresholdsOut = { ...thresholds };
      const statColsOut: Record<string, Record<string, { enabled: boolean }>> = {};
      for (const [dtype, cols] of Object.entries(COLUMN_DEFS)) {
        for (const col of cols) {
          const val = columnToggles[`${dtype}:${col}`] ?? true;
          // thresholds 中标记 enabled
          if (thresholdsOut[dtype]?.[col]) {
            thresholdsOut[dtype] = { ...thresholdsOut[dtype], [col]: { ...thresholdsOut[dtype][col], enabled: val } };
          } else if (!val) {
            if (!thresholdsOut[dtype]) thresholdsOut[dtype] = {};
            thresholdsOut[dtype][col] = { enabled: val };
          }
          // statistical_columns 中标记 enabled
          if (!statColsOut[dtype]) statColsOut[dtype] = {};
          statColsOut[dtype][col] = { enabled: val };
        }
      }

      const updates = {
        use_threshold: useThreshold,
        use_sigma: useSigma,
        use_percentile: usePercentile,
        sigma_n: parseOr(sigmaN, 3.0),
        percentile_low: parseOr(pctLow, 1.0),
        percentile_high: parseOr(pctHigh, 99.0),
        thresholds: thresholdsOut,
        statistical_columns: statColsOut,
        handling_rules,
      };

      await bridge.call("save_anomaly_config", { updates });
      setStatus({ msg: t("userConfig:AnomalyConfigSection.anomalyDetectionConfigurationsaved"), kind: "success" });
      notify(t("userConfig:AnomalyConfigSection.anomalyDetectionConfigurationsaved"), "success");
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: t("userConfig:AnomalyConfigSection.saveFailed", { error: String(e) }), kind: "error" });
      notify(t("userConfig:AnomalyConfigSection.saveFailed", { error: String(e) }), "error");
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = async () => {
    if (!confirm(t("userConfig:AnomalyConfigSection.restoreDefaultAnomalyDetectionConfiguration"))) return;
    try {
      await bridge.call("save_anomaly_config", { config: {} });
      await reload();
      setStatus({ msg: t("userConfig:AnomalyConfigSection.defaultConfigurationRestored"), kind: "info" });
      notify(t("userConfig:AnomalyConfigSection.anomalyDetectionDefaultsRestored"), "success");
    } catch (e) {
      setStatus({ msg: t("userConfig:AnomalyConfigSection.restoreFailed", { error: String(e) }), kind: "error" });
    }
  };

  const currentRows = thresholdRows[activeType] || [];
  const currentColumns = COLUMN_DEFS[activeType] || [];

  return (
    <SectionCard
      title={t("userConfig:AnomalyConfigSection.anomalyDetectionConfiguration")}
      subtitle={t("userConfig:AnomalyConfigSection.configureDetectionThresholdsForEachDataTypeMultipliersAndPercentileRanges")}
      icon={<TuneIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      {/* 说明文字 */}
      <p className="text-xs text-slate-500 mb-3">
        {t("userConfig:AnomalyConfigSection.ui.detectionHint", { sentinel: ALL_NUMERIC })}
      </p>

      {/* 检测方法开关 */}
      <div className="flex items-center gap-5 mb-3">
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={useThreshold} onChange={(e) => setUseThreshold(e.target.checked)} className="w-4 h-4 rounded border-slate-300" />
          {t("userConfig:AnomalyConfigSection.absoluteThreshold")}
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={useSigma} onChange={(e) => setUseSigma(e.target.checked)} className="w-4 h-4 rounded border-slate-300" />
          {t("userConfig:AnomalyConfigSection.sigmaDetection")}
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={usePercentile} onChange={(e) => setUsePercentile(e.target.checked)} className="w-4 h-4 rounded border-slate-300" />
          {t("userConfig:AnomalyConfigSection.percentileDetection")}
        </label>
      </div>

      <div className="border-t border-slate-100 pt-3 mb-3" />

      {/* 统计参数 */}
      <p className="text-xs font-medium text-slate-500 mb-2">{t("userConfig:AnomalyConfigSection.statistics")}</p>
      <div className="flex gap-3 mb-3">
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("userConfig:AnomalyConfigSection.multiplier")}</label>
          <input type="text" value={sigmaN} onChange={(e) => setSigmaN(e.target.value)} placeholder="3.0" className="input w-28" />
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("userConfig:AnomalyConfigSection.percentileLowerBound")}</label>
          <input type="text" value={pctLow} onChange={(e) => setPctLow(e.target.value)} placeholder="1.0" className="input w-28" />
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("userConfig:AnomalyConfigSection.percentileUpperBound")}</label>
          <input type="text" value={pctHigh} onChange={(e) => setPctHigh(e.target.value)} placeholder="99.0" className="input w-28" />
        </div>
      </div>

      <div className="border-t border-slate-100 pt-3 mb-3" />

      {/* 阈值配置 */}
      <p className="text-xs font-medium text-slate-500 mb-2">{t("userConfig:AnomalyConfigSection.thresholdConfiguration")}</p>

      {/* 数据类型选项卡 */}
      <div
        role="tablist"
        aria-label={t("userConfig:AnomalyConfigSection.anomalyDataType")}
        className="flex gap-1 bg-slate-100 rounded-lg p-0.5 overflow-x-auto mb-3"
      >
        {DATA_TYPE_OPTIONS.map(({ key, label }) => (
          <button
            key={key}
            role="tab"
            aria-selected={activeType === key}
            onClick={() => setActiveType(key)}
            className={`shrink-0 px-3 py-1.5 text-xs rounded-md transition-colors whitespace-nowrap ${
              activeType === key
                ? "bg-white shadow-sm text-slate-800 font-medium"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 当前数据类型的逐列检测开关 */}
      <div className="flex flex-wrap items-start gap-x-5 gap-y-2 border-b border-slate-100 pb-3 mb-3 px-0.5">
        <div className="shrink-0">
          <p className="text-xs font-medium text-slate-500">{t("userConfig:AnomalyConfigSection.perColumnDetection")}</p>
          <p className="text-xs text-slate-400">{t("userConfig:AnomalyConfigSection.whenDisabledSkipAllDetectionMethodsForThisColumn")}</p>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 pt-0.5">
          {currentColumns.map((col) => {
            const key = `${activeType}:${col}`;
            const label = col === ALL_NUMERIC ? t("userConfig:AnomalyConfigSection.allNumericColumns") : col;
            return (
              <label key={key} className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={columnToggles[key] ?? true}
                  onChange={(e) => setColumnToggles({ ...columnToggles, [key]: e.target.checked })}
                  className="w-3.5 h-3.5 rounded border-slate-300"
                />
                <span className="text-xs text-slate-600">{label}</span>
              </label>
            );
          })}
        </div>
      </div>

      {/* 表头 */}
      <div className="grid grid-cols-[1fr_100px_100px_100px_32px] gap-2 mb-1.5 px-0.5">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{t("userConfig:AnomalyConfigSection.columnColumn")}</span>
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{t("userConfig:AnomalyConfigSection.minimum")}</span>
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{t("userConfig:AnomalyConfigSection.maximum")}</span>
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider" title={t("userConfig:AnomalyConfigSection.replacementValueForAnomalyHandling")}>{t("userConfig:AnomalyConfigSection.defaultValue")}</span>
        <span />
      </div>

      {/* 阈值行 */}
      <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
        {currentRows.map((row, idx) => (
          <div key={idx} className="grid grid-cols-[1fr_100px_100px_100px_32px] gap-2 items-center">
            <input
              type="text"
              value={row.column}
              onChange={(e) => updateRow(activeType, idx, "column", e.target.value)}
              placeholder={t("userConfig:AnomalyConfigSection.columnNameOrAllNumeric", { sentinel: ALL_NUMERIC })}
              className="input w-full"
            />
            <input
              type="text"
              value={row.min}
              onChange={(e) => updateRow(activeType, idx, "min", e.target.value)}
              placeholder={t("userConfig:AnomalyConfigSection.noLowerLimit")}
              className="input w-full"
            />
            <input
              type="text"
              value={row.max}
              onChange={(e) => updateRow(activeType, idx, "max", e.target.value)}
              placeholder={t("userConfig:AnomalyConfigSection.noUpperLimit")}
              className="input w-full"
            />
            <input
              type="text"
              value={row.default}
              onChange={(e) => updateRow(activeType, idx, "default", e.target.value)}
              placeholder="0"
              title={t("userConfig:AnomalyConfigSection.useThisValueWhenHandlingAnomalies")}
              className="input w-full"
            />
            <button
              onClick={() => removeRow(activeType, idx)}
              className="w-8 h-8 flex items-center justify-center rounded-md text-red-700 hover:text-red-800 hover:bg-red-50 transition-colors"
              title={t("userConfig:AnomalyConfigSection.deleteThisRow")}
            >
              <CloseIcon />
            </button>
          </div>
        ))}
        {currentRows.length === 0 && (
          <div className="text-center py-4 text-xs text-slate-400">{t("userConfig:AnomalyConfigSection.noThresholdRules")}</div>
        )}
      </div>

      <ActionButtons
        saving={saving}
        onSave={save}
        onReload={reload}
        onReset={resetToDefault}
        onExtra={addRow}
        extraLabel={t("userConfig:AnomalyConfigSection.addThreshold")}
      />
      <StatusMessage message={status.msg} kind={status.kind} />
    </SectionCard>
  );
}
