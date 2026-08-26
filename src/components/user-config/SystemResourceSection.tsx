import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { SettingsIcon } from "../../lib/icons";
import { SectionCard, ActionButtons, StatusMessage } from "./_shared";

interface SystemResourceConfig {
  cpu_cores: number;
  available_cpu_cores: number;
  default_cpu_cores: number;
}

const DEFAULT_SYSTEM_RESOURCE_CONFIG: SystemResourceConfig = {
  cpu_cores: 1,
  available_cpu_cores: 1,
  default_cpu_cores: 1,
};

export function SystemResourceSection({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [config, setConfig] = useState<SystemResourceConfig>({ ...DEFAULT_SYSTEM_RESOURCE_CONFIG });
  const [cpuCores, setCpuCores] = useState("");

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<Partial<SystemResourceConfig>>("get_system_resource_config", {});
      const next = {
        ...DEFAULT_SYSTEM_RESOURCE_CONFIG,
        ...(raw && typeof raw === "object" ? raw : {}),
      };
      setConfig(next);
      setCpuCores(String(next.cpu_cores));
      setStatus({ msg: "", kind: "info" });
    } catch {
      setConfig({ ...DEFAULT_SYSTEM_RESOURCE_CONFIG });
      setCpuCores(String(DEFAULT_SYSTEM_RESOURCE_CONFIG.cpu_cores));
    }
  }, [bridge.call]);

  useEffect(() => { reload(); }, [reload]);

  const save = async () => {
    const value = Number.parseInt(cpuCores.trim(), 10);
    if (!/^\d+$/.test(cpuCores.trim()) || value < 1 || value > config.available_cpu_cores) {
      setStatus({
        msg: t("userConfig:SystemResourceSection.invalidCpuCores", { max: config.available_cpu_cores }),
        kind: "error",
      });
      return;
    }

    setSaving(true);
    try {
      const saved = await bridge.call<Partial<SystemResourceConfig>>("save_system_resource_config", { cpu_cores: value });
      const next = { ...config, ...(saved && typeof saved === "object" ? saved : {}), cpu_cores: value };
      setConfig(next);
      setCpuCores(String(next.cpu_cores));
      setStatus({ msg: t("userConfig:SystemResourceSection.cpuCoresSaved"), kind: "success" });
      notify(t("userConfig:SystemResourceSection.cpuCoresSaved"), "success");
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      const message = t("userConfig:SystemResourceSection.saveFailed", { error: String(e) });
      setStatus({ msg: message, kind: "error" });
      notify(message, "error");
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setCpuCores(String(config.default_cpu_cores));
    setStatus({ msg: t("userConfig:SystemResourceSection.defaultConfigurationRestoredClickSaveToApply"), kind: "info" });
  };

  return (
    <SectionCard
      title={t("userConfig:SystemResourceSection.systemResourceSettings")}
      subtitle={t("userConfig:SystemResourceSection.configureCpuResourcesForDataProcessing")}
      icon={<SettingsIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      <div className="space-y-3">
        <p className="text-xs text-slate-500">
          {t("userConfig:SystemResourceSection.cpuCoresHint")}
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-48">
            <label className="text-xs font-medium text-slate-500 mb-1 block">
              {t("userConfig:SystemResourceSection.cpuCores")}
            </label>
            <input
              type="number"
              min={1}
              max={config.available_cpu_cores}
              step={1}
              value={cpuCores}
              onChange={(e) => setCpuCores(e.target.value)}
              className="input w-full"
            />
          </div>
          <span className="text-xs text-slate-500 pb-2">
            {t("userConfig:SystemResourceSection.availableCpuCores", { available: config.available_cpu_cores })}
          </span>
        </div>
      </div>
      <ActionButtons
        saving={saving}
        onSave={save}
        onReload={reload}
        onReset={resetToDefault}
      />
      <StatusMessage message={status.msg} kind={status.kind} />
    </SectionCard>
  );
}

