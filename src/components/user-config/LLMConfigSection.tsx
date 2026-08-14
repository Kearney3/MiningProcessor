import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import {
  LLMIcon, EyeIcon, EyeOffIcon,
} from "../../lib/icons";
import { SectionCard, ActionButtons, StatusMessage } from "./_shared";

// ---------------------------------------------------------------------------
// Types & Defaults
// ---------------------------------------------------------------------------

interface LLMConfig {
  format: "openai" | "anthropic";
  url: string;
  api_key: string;
  model: string;
}

const DEFAULT_LLM_CONFIG: LLMConfig = {
  format: "openai",
  url: "",
  api_key: "",
  model: "",
};

// ---------------------------------------------------------------------------
// LLM Config Section
// ---------------------------------------------------------------------------

export function LLMConfigSection({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [config, setConfig] = useState<LLMConfig>({ ...DEFAULT_LLM_CONFIG });
  const [showPassword, setShowPassword] = useState(false);
  const [apiKeySaved, setApiKeySaved] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [fetchResult, setFetchResult] = useState<{ msg: string; ok: boolean } | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{ msg: string; ok: boolean } | null>(null);

  const MASKED = "***";

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<LLMConfig>("get_llm_config", {});
      if (raw && typeof raw === "object") {
        const key = raw.api_key ?? "";
        const hasKey = !!key;
        setApiKeySaved(hasKey);
        setConfig({
          format: raw.format ?? "openai",
          url: raw.url ?? "",
          api_key: hasKey ? MASKED : "",
          model: raw.model ?? "",
        });
        if (raw.model) {
          setModels([raw.model]);
        }
      } else {
        setConfig({ ...DEFAULT_LLM_CONFIG });
        setModels([]);
        setApiKeySaved(false);
      }
      setStatus({ msg: "", kind: "info" });
    } catch {
      setConfig({ ...DEFAULT_LLM_CONFIG });
      setModels([]);
      setApiKeySaved(false);
    }
  }, [bridge.call]);

  useEffect(() => { reload(); }, [reload]);

  const updateField = <K extends keyof LLMConfig>(field: K, value: LLMConfig[K]) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  const save = async () => {
    setSaving(true);
    try {
      const apiKey = apiKeySaved && config.api_key === MASKED ? "" : config.api_key;
      await bridge.call("update_llm_config", {
        url: config.url,
        api_key: apiKey,
        model: config.model,
        format: config.format,
      });
      setStatus({ msg: t("userConfig:LLMConfigSection.LLM配置已保存_0e52"), kind: "success" });
      notify(t("userConfig:LLMConfigSection.LLM配置已保存_0e52"), "success");
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: t("userConfig:LLMConfigSection.保存失败:$_2655", { error: String(e) }), kind: "error" });
      notify(t("userConfig:LLMConfigSection.保存失败:$_e5b7", { error: String(e) }), "error");
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setConfig({ ...DEFAULT_LLM_CONFIG });
    setModels([]);
    setApiKeySaved(false);
    setFetchResult(null);
    setStatus({ msg: t("userConfig:LLMConfigSection.已恢复默认配置（需点击保存生效_c62f"), kind: "info" });
  };

  const fetchModels = async () => {
    setFetchingModels(true);
    setFetchResult(null);
    try {
      const apiKey = apiKeySaved && config.api_key === MASKED ? "" : config.api_key;
      const res = await bridge.call<{ success: boolean; error: string; models: string[] }>(
        "test_llm_connection",
        { url: config.url, api_key: apiKey, format: config.format },
      );
      if (res.success && Array.isArray(res.models)) {
        setModels(res.models);
        if (res.models.length > 0) {
          setFetchResult({ msg: t("userConfig:LLMConfigSection.获取到$个模型_f769", { count: res.models.length }), ok: true });
        } else {
          setFetchResult({ msg: res.error || t("userConfig:LLMConfigSection.未返回模型，请手动输入模型名称_4683"), ok: true });
        }
      } else {
        setFetchResult({ msg: res.error || t("userConfig:LLMConfigSection.获取模型失败_803c"), ok: false });
      }
    } catch (e) {
      setFetchResult({ msg: t("userConfig:LLMConfigSection.请求异常:$_e019", { error: String(e) }), ok: false });
    } finally {
      setFetchingModels(false);
    }
  };

  const verifyConnection = async () => {
    if (!config.url.trim()) {
      setVerifyResult({ msg: t("userConfig:LLMConfigSection.请先填写接口URL_fd01"), ok: false });
      return;
    }
    setVerifying(true);
    setVerifyResult(null);
    try {
      const apiKey = apiKeySaved && config.api_key === MASKED ? "" : config.api_key;
      const res = await bridge.call<{ success: boolean; models: string[]; error: string }>(
        "test_llm_connection",
        { url: config.url, api_key: apiKey, format: config.format },
      );
      if (res.success) {
        const selectedModel = config.model.trim();
        if (selectedModel && !res.models.includes(selectedModel)) {
          setVerifyResult({
            msg: t("userConfig:LLMConfigSection.连接成功，但所选模型「$」不在_452e", { model: selectedModel, count: res.models.length }),
            ok: false,
          });
        } else {
          const modelInfo = selectedModel ? t("userConfig:LLMConfigSection.，模型「$」可用_5068", { model: selectedModel }) : "";
          setVerifyResult({
            msg: t("userConfig:LLMConfigSection.✓连接成功（$个模型可用$）_8b01", { count: res.models.length, modelInfo }),
            ok: true,
          });
        }
      } else {
        setVerifyResult({ msg: t("userConfig:LLMConfigSection.✗连接失败:$_f00c", { error: res.error }), ok: false });
      }
    } catch (e) {
      setVerifyResult({ msg: t("userConfig:LLMConfigSection.请求异常:$_e019", { error: String(e) }), ok: false });
    } finally {
      setVerifying(false);
    }
  };

  const passwordType = showPassword ? "text" : "password";

  return (
    <SectionCard
      title={t("userConfig:LLMConfigSection.LLM标注配置_4aee")}
      subtitle={t("userConfig:LLMConfigSection.配置大模型接口用于维修记录智能_8504")}
      icon={<LLMIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      <div className="space-y-3">
        {/* Format dropdown */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:LLMConfigSection.接口格式_3471")}</label>
          <select
            value={config.format}
            onChange={(e) => updateField("format", e.target.value as LLMConfig["format"])}
            className="input w-full"
          >
            <option value="openai">{t("userConfig:LLMConfigSection.OpenAI兼容_a2fb")}</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </div>

        {/* URL */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:LLMConfigSection.接口URL_71a3")}</label>
          <input
            type="text"
            value={config.url}
            onChange={(e) => updateField("url", e.target.value)}
            placeholder="https://api.openai.com/v1"
            className="input w-full"
          />
        </div>

        {/* API Key with show/hide */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">API Key</label>
          <div className="relative">
            <input
              type={passwordType}
              value={config.api_key}
              onChange={(e) => {
                updateField("api_key", e.target.value);
                if (apiKeySaved) setApiKeySaved(false);
              }}
              placeholder="sk-..."
              className="input w-full pr-10"
              autoComplete="new-password"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              title={showPassword ? t("userConfig:LLMConfigSection.隐藏_dce5") : t("userConfig:LLMConfigSection.显示_4d77")}
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
        </div>

        {/* Model dropdown + fetch button */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:LLMConfigSection.模型_8000")}</label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                list="llm-model-list"
                value={config.model}
                onChange={(e) => updateField("model", e.target.value)}
                placeholder={t("userConfig:LLMConfigSection.选择或输入模型名称_d8d7")}
                className="input w-full"
              />
              <datalist id="llm-model-list">
                {models.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
            <button
              onClick={fetchModels}
              disabled={fetchingModels}
              className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors shrink-0 ${
                fetchingModels ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              {fetchingModels ? t("userConfig:LLMConfigSection.获取中..._4a8d") : t("userConfig:LLMConfigSection.获取模型_9259")}
            </button>
            <button
              onClick={verifyConnection}
              disabled={verifying}
              className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors shrink-0 ${
                verifying ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              {verifying ? t("userConfig:LLMConfigSection.验证中..._fd31") : t("userConfig:LLMConfigSection.验证连接_c476")}
            </button>
          </div>
          {fetchResult && (
            <span className={`text-xs mt-1 block ${fetchResult.ok ? "text-emerald-600" : "text-red-600"}`}>
              {fetchResult.msg}
            </span>
          )}
          {verifyResult && (
            <span className={`text-xs mt-1 block ${verifyResult.ok ? "text-emerald-600" : "text-amber-600"}`}>
              {verifyResult.msg}
            </span>
          )}
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
