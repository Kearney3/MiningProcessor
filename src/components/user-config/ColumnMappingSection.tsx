import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { ColumnsIcon } from "../../lib/icons";
import { SectionCard } from "./_shared";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SKIP = "__SKIP__";

const getDataTypeLabel = (t: (k: string) => string, dt: string): string => {
  const labels: Record<string, string> = {
    work_efficiency: t("userConfig:ColumnMappingSection.工时数据_8c32"),
    fuel_consumption: t("userConfig:ColumnMappingSection.油耗数据_0971"),
    electricity_consumption: t("userConfig:ColumnMappingSection.电力消耗_79c4"),
    equipment_operation: t("userConfig:ColumnMappingSection.设备运行_9a39"),
    production_record: t("userConfig:ColumnMappingSection.生产记录_436f"),
  };
  return labels[dt] || dt;
};

// 每个数据类型可选的 MineBase 目标字段
const TARGET_FIELDS: Record<string, string[]> = {
  work_efficiency: [
    "equipmentName", "equipmentCode", "company", "plannedMinutes", "plannedHours",
    "parkShift", "transfer", "auxiliaryWork", "waitingLoad", "blasting",
    "mealBreak", "refueling", "plannedMaintenance", "unplannedFault", "standby",
    "weatherSnow", "weatherDust", "fillWater", "totalProductionMinutes",
    "powerIssuePlanned", "powerIssueUnplanned", "totalProductionHours", "remark",
  ],
  fuel_consumption: ["date", "shiftType", "equipmentName", "equipmentCode", "fuelName", "consumption"],
  electricity_consumption: ["date", "shiftType", "equipmentName", "equipmentCode", "consumption"],
  equipment_operation: [
    "date", "shiftType", "equipmentName", "company", "engineHoursStart",
    "engineHoursEnd", "runningHours", "milemeterStart", "milemeterEnd", "mileage", "tripCount",
  ],
  production_record: ["date", "shiftType", "truckName", "excavatorName", "materialTypeName", "tripCount", "production"],
};

// ---------------------------------------------------------------------------
// Column Mapping Section
// ---------------------------------------------------------------------------

export function ColumnMappingSection({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [mapping, setMapping] = useState<Record<string, Record<string, string>>>({});
  const [activeType, setActiveType] = useState("fuel_consumption");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadMapping = useCallback(async () => {
    setLoading(true);
    try {
      const res = await bridge.call<Record<string, Record<string, string>>>("get_minebase_column_mapping");
      setMapping(res || {});
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [bridge.call]);

  useEffect(() => { if (expanded) loadMapping(); }, [expanded, loadMapping]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await bridge.call("save_minebase_column_mapping", { mapping });
      setSuccess(t("userConfig:ColumnMappingSection.列映射已保存_de4d"));
      notify(t("userConfig:ColumnMappingSection.列映射已保存_de4d"), "success");
      setTimeout(() => setSuccess(null), 2000);
    } catch (e) {
      setError(String(e));
      notify(t("userConfig:ColumnMappingSection.保存失败:$_e5b7", { error: String(e) }), "error");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!confirm(t("userConfig:ColumnMappingSection.确定要重置列映射为默认配置吗？_a4e0"))) return;
    try {
      await bridge.call("reset_minebase_column_mapping");
      await loadMapping();
      setSuccess(t("userConfig:ColumnMappingSection.已重置为默认配置_0fd4"));
      notify(t("userConfig:ColumnMappingSection.已重置为默认配置_0fd4"), "success");
      setTimeout(() => setSuccess(null), 2000);
    } catch (e) {
      setError(String(e));
      notify(t("userConfig:ColumnMappingSection.重置失败:$_c7e3", { error: String(e) }), "error");
    }
  };

  const updateTarget = (dataType: string, source: string, target: string) => {
    setMapping((prev) => ({
      ...prev,
      [dataType]: { ...prev[dataType], [source]: target },
    }));
  };

  const toggleSkip = (dataType: string, source: string) => {
    setMapping((prev) => {
      const current = prev[dataType]?.[source];
      return {
        ...prev,
        [dataType]: {
          ...prev[dataType],
          [source]: current === SKIP ? (TARGET_FIELDS[dataType]?.[0] || "") : SKIP,
        },
      };
    });
  };

  const removeRow = (dataType: string, source: string) => {
    setMapping((prev) => {
      const next = { ...prev[dataType] };
      delete next[source];
      return { ...prev, [dataType]: next };
    });
  };

  const addRow = (dataType: string) => {
    const source = prompt(t("userConfig:ColumnMappingSection.输入源列名（中文列名）：_aaa7"));
    if (!source?.trim()) return;
    setMapping((prev) => ({
      ...prev,
      [dataType]: {
        ...prev[dataType],
        [source.trim()]: TARGET_FIELDS[dataType]?.[0] || "",
      },
    }));
  };

  const dataTypes = Object.keys(mapping);
  const currentEntries = Object.entries(mapping[activeType] || {});
  const fields = TARGET_FIELDS[activeType] || [];

  return (
    <SectionCard
      title={t("userConfig:ColumnMappingSection.列映射配置_50e5")}
      subtitle={t("userConfig:ColumnMappingSection.配置MiningProcess_f3d4")}
      icon={<ColumnsIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      {loading ? (
        <div className="flex items-center justify-center py-8 text-slate-400 text-sm">{t("userConfig:ColumnMappingSection.加载中..._26b5")}</div>
      ) : (
        <div className="space-y-4">
          {/* 数据类型选项卡 */}
          <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5 overflow-x-auto">
            {dataTypes.map((dt) => (
              <button
                key={dt}
                onClick={() => setActiveType(dt)}
                className={`shrink-0 px-3 py-1.5 text-xs rounded-md transition-colors whitespace-nowrap ${
                  activeType === dt
                    ? "bg-white shadow-sm text-slate-800 font-medium"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {getDataTypeLabel(t, dt)}
              </button>
            ))}
          </div>

          {/* 映射表格 */}
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50">
                  <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 w-8">#</th>
                  <th className="text-left px-3 py-2 text-xs font-medium text-slate-500">{t("userConfig:ColumnMappingSection.源列名_15d3")}</th>
                  <th className="text-left px-3 py-2 text-xs font-medium text-slate-500">{t("userConfig:ColumnMappingSection.目标字段_f278")}</th>
                  <th className="text-center px-3 py-2 text-xs font-medium text-slate-500 w-16">{t("userConfig:ColumnMappingSection.排除_93bd")}</th>
                  <th className="w-10 px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {currentEntries.map(([source, target], i) => {
                  const isExcluded = target === SKIP;
                  return (
                    <tr key={source} className={`border-t border-slate-100 ${isExcluded ? "opacity-50" : ""}`}>
                      <td className="px-3 py-1.5 text-xs text-slate-400">{i + 1}</td>
                      <td className="px-3 py-1.5 text-sm text-slate-700">{source}</td>
                      <td className="px-3 py-1.5">
                        <select
                          value={isExcluded ? "" : target}
                          onChange={(e) => updateTarget(activeType, source, e.target.value)}
                          disabled={isExcluded}
                          className="w-full text-xs border border-slate-200 rounded px-2 py-1 bg-white disabled:bg-slate-50 disabled:text-slate-400"
                        >
                          <option value="">{t("userConfig:ColumnMappingSection.--选择目标字段--_ba06")}</option>
                          {fields.map((f) => (
                            <option key={f} value={f}>{f}</option>
                          ))}
                        </select>
                      </td>
                      <td className="text-center px-3 py-1.5">
                        <input
                          type="checkbox"
                          checked={isExcluded}
                          onChange={() => toggleSkip(activeType, source)}
                          className="rounded border-slate-300"
                        />
                      </td>
                      <td className="px-3 py-1.5">
                        <button
                          onClick={() => removeRow(activeType, source)}
                          className="text-slate-400 hover:text-red-500 transition-colors"
                          title={t("userConfig:ColumnMappingSection.删除_2f4a")}
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {currentEntries.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-xs text-slate-400">
                      暂无映射配置
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* 添加行按钮 */}
          <button
            onClick={() => addRow(activeType)}
            className="text-xs text-blue-600 hover:text-blue-700 transition-colors"
          >
            + {t("userConfig:ColumnMappingSection.addMappingRow")}
          </button>

          {/* 操作按钮 */}
          <div className="flex items-center gap-2 pt-2 border-t border-slate-100">
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-xs bg-slate-900 hover:bg-slate-800 text-white px-3 py-1.5 rounded-md font-medium transition-colors disabled:opacity-50"
            >
              {saving ? t("userConfig:ColumnMappingSection.保存中..._2a33") : t("userConfig:ColumnMappingSection.保存映射_ee41")}
            </button>
            <button
              onClick={handleReset}
              className="text-xs text-red-600 hover:text-red-700 px-3 py-1.5 rounded-md transition-colors"
            >
              {t("userConfig:ColumnMappingSection.restoreDefault")}
            </button>
            {success && <span className="text-xs text-emerald-600">{success}</span>}
            {error && <span className="text-xs text-red-600">{error}</span>}
          </div>
        </div>
      )}
    </SectionCard>
  );
}
