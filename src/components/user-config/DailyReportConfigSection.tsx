import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { CheckIcon, SettingsIcon } from "../../lib/icons";
import { SectionCard, ActionButtons, KeywordChipInput, StatusMessage } from "./_shared";

const FORMULA_KEYS = ["延迟时间", "待机时间", "设备可动率", "设备可动利用率", "设备利用率"] as const;
type FormulaKey = typeof FORMULA_KEYS[number];

type MaterialStatistics = Record<string, string[]>;
type DailyReportConfig = {
  material_statistics: MaterialStatistics;
  formulas: Record<string, string>;
};

const DEFAULT_CONFIG: DailyReportConfig = {
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
  const { t } = useTranslation();
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [config, setConfig] = useState<DailyReportConfig>(cloneDefault());
  const [formulaErrors, setFormulaErrors] = useState<Record<string, string>>({});

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
      setStatus({ msg: t("userConfig:DailyReportConfigSection.failedToLoadDailyReportSettings", { error: String(error) }), kind: "error" });
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
    setFormulaErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const validateFormulas = async (showToast = true): Promise<boolean> => {
    setValidating(true);
    try {
      const validation = await bridge.call<{ valid: boolean; errors: Record<string, string> }>("validate_daily_report_config", { config });
      const errors = validation.errors ?? {};
      setFormulaErrors(errors);
      if (!validation.valid) {
        const message = Object.entries(errors)
          .map(([key, value]) => t("userConfig:DailyReportConfigSection.validationError", { key, value }))
          .join("\n");
        setStatus({ msg: message, kind: "error" });
        if (showToast) notify(t("userConfig:DailyReportConfigSection.dailyReportFormulaValidationFailed"), "error");
        return false;
      }
      setStatus({ msg: t("userConfig:DailyReportConfigSection.formulaValidationPassed"), kind: "success" });
      if (showToast) notify(t("userConfig:DailyReportConfigSection.formulaValidationPassed"), "success");
      return true;
    } catch (error) {
      setStatus({
        msg: t("userConfig:DailyReportConfigSection.saveError", { error: String(error) }),
        kind: "error",
      });
      if (showToast) notify(t("userConfig:DailyReportConfigSection.saveError", { error: String(error) }), "error");
      return false;
    } finally {
      setValidating(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setStatus({ msg: "", kind: "info" });
    try {
      if (!(await validateFormulas(false))) {
        notify(t("userConfig:DailyReportConfigSection.dailyReportFormulaValidationFailed"), "error");
        return;
      }
      await bridge.call("save_daily_report_config", { config });
      setStatus({ msg: t("userConfig:DailyReportConfigSection.dailyReportExportSettingsSaved"), kind: "success" });
      notify(t("userConfig:DailyReportConfigSection.dailyReportExportSettingsSaved"), "success");
    } catch (error) {
      setStatus({
        msg: t("userConfig:DailyReportConfigSection.saveError", { error: String(error) }),
        kind: "error",
      });
      notify(t("userConfig:DailyReportConfigSection.failedToSaveDailyReportSettings", { error: String(error) }), "error");
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setConfig(cloneDefault());
    setFormulaErrors({});
    setStatus({ msg: t("userConfig:DailyReportConfigSection.defaultValuesRestoredClickSaveToApply"), kind: "info" });
  };

  return (
    <SectionCard
      title={t("userConfig:DailyReportConfigSection.dailyReportExportSettings")}
      subtitle={t("userConfig:DailyReportConfigSection.theDailyReportPageSelectsOnlyTheDateAndDataSourceMaintainReportingDefinitionsHer")}
      icon={<SettingsIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      <div className="space-y-4">
        <div>
          <p className="text-xs text-slate-500 mb-1">{t("userConfig:DailyReportConfigSection.materialStatisticsConfiguration")}</p>
          <p className="text-xs text-slate-400 mb-3">{t("userConfig:DailyReportConfigSection.materialTypesRequireNoConfigurationAllSourceMaterialsAreExpandedAutomaticallySta")}</p>
          <div className="border border-slate-200 rounded-lg divide-y divide-slate-100">
            {Object.entries(config.material_statistics).map(([target, keywords]) => (
              <div key={target} className="px-3 py-3 grid grid-cols-[7rem_1fr] gap-3 items-start">
                <span className="text-xs font-medium text-slate-600 pt-1.5">{target}</span>
                <KeywordChipInput
                  label=""
                  items={keywords}
                  placeholder={t("userConfig:DailyReportConfigSection.enterAKeywordAndPressEnterToAdd")}
                  onChange={(items) => updateMaterial(target, items)}
                />
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs text-slate-500 mb-1">{t("userConfig:DailyReportConfigSection.delayIdleTimeAndUtilizationFormulas")}</p>
          <p className="text-xs text-slate-400 mb-3">{t("userConfig:DailyReportConfigSection.validateFormulaSyntaxAndFieldNamesWhenSavingVerifyFieldsAgainstActualWorktimeHea")}</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {FORMULA_KEYS.map((key) => (
              <label key={key} className="text-xs text-slate-500">
                {key}
                <input
                  className={`input mt-1 w-full ${formulaErrors[key] ? "border-red-300" : ""}`}
                  value={config.formulas[key] ?? ""}
                  onChange={(e) => updateFormula(key, e.target.value)}
                  aria-label={t("userConfig:DailyReportConfigSection.formula", { key })}
                  aria-invalid={Boolean(formulaErrors[key])}
                />
                {formulaErrors[key] && (
                  <span role="alert" className="mt-1 block text-xs text-red-600">
                    {formulaErrors[key]}
                  </span>
                )}
              </label>
            ))}
          </div>
        </div>
      </div>
      <ActionButtons
        saving={saving}
        disableSave={validating}
        onSave={save}
        onReload={reload}
        onReset={reset}
        onExtra={() => { void validateFormulas(); }}
        extraIcon={<CheckIcon />}
        extraDisabled={saving || validating}
        extraLabel={validating
          ? t("userConfig:DailyReportConfigSection.validatingFormula")
          : t("userConfig:DailyReportConfigSection.validateFormula")}
      />
      <StatusMessage message={status.msg} kind={status.kind} />
    </SectionCard>
  );
}
