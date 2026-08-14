import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { KeywordsIcon } from "../../lib/icons";
import { SectionCard, ActionButtons, StatusMessage, KeywordChipInput } from "./_shared";

// ---------------------------------------------------------------------------
// Types & Defaults
// ---------------------------------------------------------------------------

interface FileKeywords {
  fuel: string[];
  electrical: string[];
  production: string[];
  worktime: string[];
  maintenance: string[];
}

const DEFAULT_FILE_KEYWORDS: FileKeywords = {
  fuel: ["Fuel report "],
  electrical: ["Цахилгааны хэлтэс"],
  production: ["白班", "夜班"],
  worktime: ["工作效率表"],
  maintenance: ["设备出勤统计表"],
};

// ---------------------------------------------------------------------------
// File Keywords Section
// ---------------------------------------------------------------------------

export function FileKeywordsSection({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [keywords, setKeywords] = useState<FileKeywords>({ ...DEFAULT_FILE_KEYWORDS });

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<Record<string, string[]>>("get_config", { key: "file_keywords" });
      if (raw && typeof raw === "object") {
        setKeywords({
          fuel: raw.fuel ?? DEFAULT_FILE_KEYWORDS.fuel,
          electrical: raw.electrical ?? DEFAULT_FILE_KEYWORDS.electrical,
          production: raw.production ?? DEFAULT_FILE_KEYWORDS.production,
          worktime: raw.worktime ?? DEFAULT_FILE_KEYWORDS.worktime,
          maintenance: raw.maintenance ?? DEFAULT_FILE_KEYWORDS.maintenance,
        });
      } else {
        setKeywords({ ...DEFAULT_FILE_KEYWORDS });
      }
      setStatus({ msg: "", kind: "info" });
    } catch {
      setKeywords({ ...DEFAULT_FILE_KEYWORDS });
    }
  }, [bridge.call]);

  useEffect(() => { reload(); }, [reload]);

  const updateField = (key: keyof FileKeywords, items: string[]) => {
    setKeywords((prev) => ({ ...prev, [key]: items }));
  };

  const save = async () => {
    setSaving(true);
    try {
      await bridge.call("save_config", { data: { file_keywords: keywords }, target: "user" });
      setStatus({ msg: t("userConfig:FileKeywordsSection.文件关键字配置已保存_73b3"), kind: "success" });
      notify(t("userConfig:FileKeywordsSection.文件关键字已保存_6441"), "success");
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: t("userConfig:FileKeywordsSection.保存失败:$_2655", { error: String(e) }), kind: "error" });
      notify(t("userConfig:FileKeywordsSection.保存失败:$_e5b7", { error: String(e) }), "error");
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setKeywords({ ...DEFAULT_FILE_KEYWORDS });
    setStatus({ msg: t("userConfig:FileKeywordsSection.已恢复默认关键字（需点击保存生_699b"), kind: "info" });
  };

  const fields: { key: keyof FileKeywords; label: string; hint: string }[] = [
    { key: "fuel", label: t("userConfig:FileKeywordsSection.油耗关键字_e747"), hint: t("userConfig:FileKeywordsSection.输入后按回车添加_9739") },
    { key: "electrical", label: t("userConfig:FileKeywordsSection.电力关键字_194b"), hint: t("userConfig:FileKeywordsSection.输入后按回车添加_9739") },
    { key: "production", label: t("userConfig:FileKeywordsSection.生产关键字_eb36"), hint: t("userConfig:FileKeywordsSection.输入后按回车添加_9739") },
    { key: "worktime", label: t("userConfig:FileKeywordsSection.工时关键字_c158"), hint: t("userConfig:FileKeywordsSection.输入后按回车添加_9739") },
    { key: "maintenance", label: t("userConfig:FileKeywordsSection.维修关键字_6729"), hint: t("userConfig:FileKeywordsSection.输入后按回车添加_9739") },
  ];

  return (
    <SectionCard
      title={t("userConfig:FileKeywordsSection.文件关键字_d556")}
      subtitle={t("userConfig:FileKeywordsSection.批量处理时用于匹配文件名的关键_02e8")}
      icon={<KeywordsIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      <div className="space-y-3">
        {fields.map(({ key, label, hint }) => (
          <KeywordChipInput
            key={key}
            label={label}
            items={keywords[key]}
            placeholder={hint}
            onChange={(items) => updateField(key, items)}
          />
        ))}
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
