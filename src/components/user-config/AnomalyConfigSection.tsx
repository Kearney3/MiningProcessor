import { useState, useEffect, useCallback } from "react";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { TuneIcon, CloseIcon } from "../../lib/icons";
import { SectionCard, ActionButtons, StatusMessage } from "./_shared";

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

const DATA_TYPE_OPTIONS: { key: string; label: string }[] = [
  { key: "fuel", label: "油耗" },
  { key: "fuel_engine", label: "发动机" },
  { key: "production_running", label: "运行数据" },
  { key: "production", label: "生产数据" },
  { key: "electrical", label: "电力消耗" },
  { key: "worktime", label: "工时数据" },
];

const ALL_NUMERIC = "__all_numeric__";

// ---------------------------------------------------------------------------
// Anomaly Config Section
// ---------------------------------------------------------------------------

export function AnomalyConfigSection({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });

  // 检测方法开关
  const [useThreshold, setUseThreshold] = useState(true);
  const [useSigma, setUseSigma] = useState(true);
  const [usePercentile, setUsePercentile] = useState(true);

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
        setUseSigma(raw.use_sigma ?? true);
        setUsePercentile(raw.use_percentile ?? true);
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
      setStatus({ msg: "异常值检测配置已保存", kind: "success" });
      notify("异常值检测配置已保存", "success");
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: `保存失败: ${String(e)}`, kind: "error" });
      notify(`保存失败: ${e}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = async () => {
    if (!confirm("确定要恢复异常值检测默认配置吗？")) return;
    try {
      await bridge.call("save_anomaly_config", { config: {} });
      await reload();
      setStatus({ msg: "已恢复默认配置", kind: "info" });
      notify("已恢复异常值检测默认配置", "success");
    } catch (e) {
      setStatus({ msg: `恢复失败: ${String(e)}`, kind: "error" });
    }
  };

  const currentRows = thresholdRows[activeType] || [];
  const currentColumns = COLUMN_DEFS[activeType] || [];

  return (
    <SectionCard
      title="异常值检测配置"
      subtitle="配置各数据类型的检测阈值、σ 倍数和百分位范围"
      icon={<TuneIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      {/* 说明文字 */}
      <p className="text-xs text-slate-500 mb-3">
        检测方法：选择启用的检测策略，关闭的策略不会应用。
        阈值规则对指定列名设置 min/max 范围；使用 <code className="text-xs bg-slate-100 px-1 rounded">{ALL_NUMERIC}</code> 可对所有数值列统一检测。
        默认值列仅在启用「处理异常值」模式时生效。
      </p>

      {/* 检测方法开关 */}
      <div className="flex items-center gap-5 mb-3">
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={useThreshold} onChange={(e) => setUseThreshold(e.target.checked)} className="w-4 h-4 rounded border-slate-300" />
          绝对阈值检测
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={useSigma} onChange={(e) => setUseSigma(e.target.checked)} className="w-4 h-4 rounded border-slate-300" />
          σ 异常检测
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={usePercentile} onChange={(e) => setUsePercentile(e.target.checked)} className="w-4 h-4 rounded border-slate-300" />
          百分位检测
        </label>
      </div>

      <div className="border-t border-slate-100 pt-3 mb-3" />

      {/* 统计参数 */}
      <p className="text-xs font-medium text-slate-500 mb-2">统计参数</p>
      <div className="flex gap-3 mb-3">
        <div>
          <label className="text-xs text-slate-500 mb-1 block">σ 倍数</label>
          <input type="text" value={sigmaN} onChange={(e) => setSigmaN(e.target.value)} placeholder="3.0" className="input w-28" />
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">百分位下限</label>
          <input type="text" value={pctLow} onChange={(e) => setPctLow(e.target.value)} placeholder="1.0" className="input w-28" />
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">百分位上限</label>
          <input type="text" value={pctHigh} onChange={(e) => setPctHigh(e.target.value)} placeholder="99.0" className="input w-28" />
        </div>
      </div>

      <div className="border-t border-slate-100 pt-3 mb-3" />

      {/* 阈值配置 */}
      <p className="text-xs font-medium text-slate-500 mb-2">阈值配置</p>

      {/* 数据类型选项卡 */}
      <div
        role="tablist"
        aria-label="异常值数据类型"
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
          <p className="text-xs font-medium text-slate-500">逐列检测</p>
          <p className="text-xs text-slate-400">关闭后跳过该列的全部检测方法</p>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 pt-0.5">
          {currentColumns.map((col) => {
            const key = `${activeType}:${col}`;
            const label = col === ALL_NUMERIC ? "全部数值列" : col;
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
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">列名 / 标记</span>
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">最小值</span>
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">最大值</span>
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider" title="处理异常值时的替换值">默认值</span>
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
              placeholder={`列名或 ${ALL_NUMERIC}`}
              className="input w-full"
            />
            <input
              type="text"
              value={row.min}
              onChange={(e) => updateRow(activeType, idx, "min", e.target.value)}
              placeholder="无下限"
              className="input w-full"
            />
            <input
              type="text"
              value={row.max}
              onChange={(e) => updateRow(activeType, idx, "max", e.target.value)}
              placeholder="无上限"
              className="input w-full"
            />
            <input
              type="text"
              value={row.default}
              onChange={(e) => updateRow(activeType, idx, "default", e.target.value)}
              placeholder="0"
              title="选择「处理异常值」时替换为此值"
              className="input w-full"
            />
            <button
              onClick={() => removeRow(activeType, idx)}
              className="w-8 h-8 flex items-center justify-center rounded-md text-slate-600 hover:text-red-500 hover:bg-red-50 transition-colors"
              title="删除此行"
            >
              <CloseIcon />
            </button>
          </div>
        ))}
        {currentRows.length === 0 && (
          <div className="text-center py-4 text-xs text-slate-400">暂无阈值配置</div>
        )}
      </div>

      <ActionButtons
        saving={saving}
        onSave={save}
        onReload={reload}
        onReset={resetToDefault}
        onExtra={addRow}
        extraLabel="添加阈值"
      />
      <StatusMessage message={status.msg} kind={status.kind} />
    </SectionCard>
  );
}
