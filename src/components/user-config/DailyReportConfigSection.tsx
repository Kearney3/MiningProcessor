import { useCallback, useEffect, useState } from "react";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { SettingsIcon } from "../../lib/icons";
import { SectionCard, ActionButtons, KeywordChipInput, StatusMessage } from "./_shared";

const FORMULA_KEYS = ["延迟时间", "待机时间", "设备可动率", "设备可动利用率", "设备利用率"] as const;
type FormulaKey = typeof FORMULA_KEYS[number];

type MaterialStatistics = Record<string, string[]>;
type DailyReportConfig = {
  include_raw_equipment_name: boolean;
  include_raw_equipment_code: boolean;
  include_raw_company_name: boolean;
  material_statistics: MaterialStatistics;
  formulas: Record<string, string>;
};

const DEFAULT_CONFIG: DailyReportConfig = {
  include_raw_equipment_name: true,
  include_raw_equipment_code: true,
  include_raw_company_name: true,
  material_statistics: {
    焦煤: ["Нү"],
    动力煤: ["oxid"],
    工程作业: ["И.А"],
    土石: ["Хө", "Ш.Х", "Шг.х", "Б.н"],
  },
  formulas: {
    延迟时间: "transfer+auxiliary_work+waiting_load",
    待机时间: "blasting+refueling+standby+weather_snow+weather_dust+fill_water+power_issue_planned+power_issue_unplanned",
    设备可动率: "(planned_minutes-planned_maintenance-unplanned_fault)/planned_minutes",
    设备可动利用率: "(planned_minutes-planned_maintenance-unplanned_fault)>0?(transfer+auxiliary_work+waiting_load+total_production_minutes)/(planned_minutes-planned_maintenance-unplanned_fault):0",
    设备利用率: "(planned_minutes-planned_maintenance-unplanned_fault)>0?(transfer+auxiliary_work+waiting_load+total_production_minutes)/(planned_minutes):0",
  },
};

function cloneDefault(): DailyReportConfig {
  return JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as DailyReportConfig;
}

export function DailyReportConfigSection({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [config, setConfig] = useState<DailyReportConfig>(cloneDefault());

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<Partial<DailyReportConfig>>("get_daily_report_config");
      setConfig({
        ...cloneDefault(),
        ...raw,
        material_statistics: raw?.material_statistics ?? cloneDefault().material_statistics,
        formulas: { ...cloneDefault().formulas, ...(raw?.formulas ?? {}) },
      });
      setStatus({ msg: "", kind: "info" });
    } catch (error) {
      setStatus({ msg: `加载日报设置失败: ${String(error)}`, kind: "error" });
    }
  }, [bridge.call]);

  useEffect(() => { reload(); }, [reload]);

  const updateMaterial = (target: string, keywords: string[]) => {
    setConfig((prev) => ({
      ...prev,
      material_statistics: { ...prev.material_statistics, [target]: keywords },
    }));
  };

  const updateFormula = (key: FormulaKey, value: string) => {
    setConfig((prev) => ({ ...prev, formulas: { ...prev.formulas, [key]: value } }));
  };

  const save = async () => {
    setSaving(true);
    setStatus({ msg: "", kind: "info" });
    try {
      const validation = await bridge.call<{ valid: boolean; errors: Record<string, string> }>("validate_daily_report_config", { config });
      if (!validation.valid) {
        const message = Object.entries(validation.errors).map(([key, value]) => `${key}：${value}`).join("；");
        setStatus({ msg: message, kind: "error" });
        notify("日报公式校验失败", "error");
        return;
      }
      await bridge.call("save_daily_report_config", { config });
      setStatus({ msg: "日报导出设置已保存", kind: "success" });
      notify("日报导出设置已保存", "success");
    } catch (error) {
      setStatus({ msg: `保存失败: ${String(error)}`, kind: "error" });
      notify(`日报设置保存失败: ${String(error)}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setConfig(cloneDefault());
    setStatus({ msg: "已恢复默认值（需点击保存生效）", kind: "info" });
  };

  return (
    <SectionCard
      title="日报导出设置"
      subtitle="日报页只选择日期和数据来源，统计口径在这里统一维护"
      icon={<SettingsIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      <div className="space-y-4">
        <div>
          <p className="text-xs text-slate-500 mb-2">日报设备字段</p>
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-600">
            {[
              ["include_raw_equipment_name", "输出原始设备名称"],
              ["include_raw_equipment_code", "输出原始设备编号"],
              ["include_raw_company_name", "输出原始公司名称"],
            ].map(([key, label]) => (
              <label key={key} className="inline-flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={Boolean(config[key as keyof DailyReportConfig])}
                  onChange={(e) => setConfig((prev) => ({ ...prev, [key]: e.target.checked }))}
                  className="rounded border-slate-300"
                />
                {label}
              </label>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs text-slate-500 mb-1">物料统计配置</p>
          <p className="text-xs text-slate-400 mb-3">物料类型无需配置，会自动展开全部源物料；统计分类按行顺序关键字匹配，每条生产记录只命中一次。</p>
          <div className="border border-slate-200 rounded-lg divide-y divide-slate-100">
            {Object.entries(config.material_statistics).map(([target, keywords]) => (
              <div key={target} className="px-3 py-3 grid grid-cols-[7rem_1fr] gap-3 items-start">
                <span className="text-xs font-medium text-slate-600 pt-1.5">{target}</span>
                <KeywordChipInput
                  label=""
                  items={keywords}
                  placeholder="输入关键字后回车添加"
                  onChange={(items) => updateMaterial(target, items)}
                />
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs text-slate-500 mb-1">延迟、待机与利用率公式</p>
          <p className="text-xs text-slate-400 mb-3">公式变量必须来自已配置的工时表头/列映射；支持四则运算、比较和三元表达式。</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {FORMULA_KEYS.map((key) => (
              <label key={key} className="text-xs text-slate-500">
                {key}
                <input
                  className="input mt-1 w-full"
                  value={config.formulas[key] ?? ""}
                  onChange={(e) => updateFormula(key, e.target.value)}
                  aria-label={`${key}公式`}
                />
              </label>
            ))}
          </div>
        </div>
      </div>
      <ActionButtons saving={saving} onSave={save} onReload={reload} onReset={reset} />
      <StatusMessage message={status.msg} kind={status.kind} />
    </SectionCard>
  );
}
