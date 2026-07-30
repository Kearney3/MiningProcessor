import { useState, useEffect, useCallback } from "react";
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
      setStatus({ msg: "LLM 配置已保存", kind: "success" });
      notify("LLM 配置已保存", "success");
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: `保存失败: ${String(e)}`, kind: "error" });
      notify(`保存失败: ${e}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setConfig({ ...DEFAULT_LLM_CONFIG });
    setModels([]);
    setApiKeySaved(false);
    setFetchResult(null);
    setStatus({ msg: "已恢复默认配置（需点击保存生效）", kind: "info" });
  };

  const fetchModels = async () => {
    setFetchingModels(true);
    setFetchResult(null);
    try {
      const apiKey = apiKeySaved && config.api_key === MASKED ? "" : config.api_key;
      const res = await bridge.call<{ success: boolean; message: string; models: string[] }>(
        "test_llm_connection",
        { url: config.url, api_key: apiKey, format: config.format },
      );
      if (res.success && Array.isArray(res.models)) {
        setModels(res.models);
        setFetchResult({ msg: res.message || `获取到 ${res.models.length} 个模型`, ok: true });
      } else {
        setFetchResult({ msg: res.message || "获取模型失败", ok: false });
      }
    } catch (e) {
      setFetchResult({ msg: `请求异常: ${String(e)}`, ok: false });
    } finally {
      setFetchingModels(false);
    }
  };

  const verifyConnection = async () => {
    if (!config.url.trim()) {
      setVerifyResult({ msg: "请先填写接口 URL", ok: false });
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
            msg: `连接成功，但所选模型「${selectedModel}」不在可用列表中（共 ${res.models.length} 个模型）`,
            ok: false,
          });
        } else {
          const modelInfo = selectedModel ? `，模型「${selectedModel}」可用` : "";
          setVerifyResult({
            msg: `✓ 连接成功（${res.models.length} 个模型可用${modelInfo}）`,
            ok: true,
          });
        }
      } else {
        setVerifyResult({ msg: `✗ 连接失败: ${res.error}`, ok: false });
      }
    } catch (e) {
      setVerifyResult({ msg: `请求异常: ${String(e)}`, ok: false });
    } finally {
      setVerifying(false);
    }
  };

  const passwordType = showPassword ? "text" : "password";

  return (
    <SectionCard
      title="LLM 标注配置"
      subtitle="配置大模型接口用于维修记录智能标注"
      icon={<LLMIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      <div className="space-y-3">
        {/* Format dropdown */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">接口格式</label>
          <select
            value={config.format}
            onChange={(e) => updateField("format", e.target.value as LLMConfig["format"])}
            className="input w-full"
          >
            <option value="openai">OpenAI 兼容</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </div>

        {/* URL */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">接口 URL</label>
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
              title={showPassword ? "隐藏" : "显示"}
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
        </div>

        {/* Model dropdown + fetch button */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">模型</label>
          <div className="flex gap-2">
            <select
              value={config.model}
              onChange={(e) => updateField("model", e.target.value)}
              className="input flex-1"
            >
              <option value="">-- 请选择模型 --</option>
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            <button
              onClick={fetchModels}
              disabled={fetchingModels}
              className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors shrink-0 ${
                fetchingModels ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              {fetchingModels ? "获取中..." : "获取模型"}
            </button>
            <button
              onClick={verifyConnection}
              disabled={verifying}
              className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors shrink-0 ${
                verifying ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              {verifying ? "验证中..." : "验证连接"}
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
