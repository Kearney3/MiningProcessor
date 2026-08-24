import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { DatabaseIcon, EyeIcon, EyeOffIcon } from "../../lib/icons";
import { SectionCard, ActionButtons, StatusMessage } from "./_shared";

// ---------------------------------------------------------------------------
// Types & Defaults
// ---------------------------------------------------------------------------

interface MineBaseApiConfig {
  url: string;
  username: string;
  password: string;
}

interface MineBaseDbConfig {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
}

interface MineBaseConfig {
  mode: "api" | "database";
  api: MineBaseApiConfig;
  database: MineBaseDbConfig;
}

const DEFAULT_MINEBASE_CONFIG: MineBaseConfig = {
  mode: "api",
  api: { url: "", username: "", password: "" },
  database: { host: "localhost", port: 5432, database: "minebase", user: "postgres", password: "" },
};

// ---------------------------------------------------------------------------
// MineBase Section
// ---------------------------------------------------------------------------

export function MineBaseSection({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ msg: string; ok: boolean } | null>(null);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [config, setConfig] = useState<MineBaseConfig>({ ...DEFAULT_MINEBASE_CONFIG });
  const [showPassword, setShowPassword] = useState(false);
  const [passSaved, setPassSaved] = useState<{ api: boolean; db: boolean }>({ api: false, db: false });

  const MASKED = "********";
  const KEYRING_SENTINEL = "__keyring__";

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<MineBaseConfig>("get_config", { key: "minebase" });
      if (raw && typeof raw === "object") {
        const apiPass = raw.api?.password ?? "";
        const dbPass = raw.database?.password ?? "";
        setPassSaved({
          api: !!(apiPass && apiPass !== KEYRING_SENTINEL ? apiPass : apiPass === KEYRING_SENTINEL),
          db: !!(dbPass && dbPass !== KEYRING_SENTINEL ? dbPass : dbPass === KEYRING_SENTINEL),
        });
        setConfig({
          mode: raw.mode ?? "api",
          api: {
            url: raw.api?.url ?? "",
            username: raw.api?.username ?? "",
            password: (apiPass && apiPass !== KEYRING_SENTINEL) || apiPass === KEYRING_SENTINEL ? MASKED : "",
          },
          database: {
            host: raw.database?.host ?? "localhost",
            port: raw.database?.port ?? 5432,
            database: raw.database?.database ?? "minebase",
            user: raw.database?.user ?? "postgres",
            password: (dbPass && dbPass !== KEYRING_SENTINEL) || dbPass === KEYRING_SENTINEL ? MASKED : "",
          },
        });
      } else {
        setConfig({ ...DEFAULT_MINEBASE_CONFIG });
      }
      setStatus({ msg: "", kind: "info" });
    } catch {
      setConfig({ ...DEFAULT_MINEBASE_CONFIG });
    }
  }, [bridge.call]);

  useEffect(() => { reload(); }, [reload]);

  const updateApi = (field: keyof MineBaseApiConfig, value: string) => {
    setConfig((prev) => ({ ...prev, api: { ...prev.api, [field]: value } }));
  };

  const updateDb = (field: keyof MineBaseDbConfig, value: string | number) => {
    setConfig((prev) => ({ ...prev, database: { ...prev.database, [field]: value } }));
  };

  const validatePort = (port: number): string | null => {
    if (!Number.isInteger(port) || port < 0 || port > 65535) return t("userConfig:MineBaseSection.item065535Item");
    return null;
  };

  const validateConfig = (): string | null => {
    if (config.mode === "api") {
      if (!config.api.url.trim()) return t("userConfig:MineBaseSection.apiUrlRequired");
      if (!config.api.username.trim()) return t("userConfig:MineBaseSection.usernameRequired");
      return null;
    }
    const portError = validatePort(config.database.port);
    if (portError) return portError;
    if (!config.database.host.trim()) return t("userConfig:MineBaseSection.databaseHostRequired");
    if (!config.database.database.trim()) return t("userConfig:MineBaseSection.databaseNameRequired");
    if (!config.database.user.trim()) return t("userConfig:MineBaseSection.databaseUserRequired");
    return null;
  };

  const save = async () => {
    const validationError = validateConfig();
    if (validationError) {
      setStatus({ msg: validationError, kind: "error" });
      return;
    }
    setSaving(true);
    try {
      const resolvePass = (val: string, saved: boolean) =>
        saved && val === MASKED ? KEYRING_SENTINEL : val;
      const toSave = {
        ...config,
        api: { ...config.api, password: resolvePass(config.api.password, passSaved.api) },
        database: { ...config.database, password: resolvePass(config.database.password, passSaved.db) },
      };
      await bridge.call("save_minebase_config", { config: toSave });
      setStatus({ msg: t("userConfig:MineBaseSection.minebaseConfigurationconfigurationsaved"), kind: "success" });
      notify(t("userConfig:MineBaseSection.minebaseConfigurationSaved"), "success");
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: t("userConfig:MineBaseSection.saveFailed", { error: String(e) }), kind: "error" });
      notify(t("userConfig:MineBaseSection.saveFailed", { error: String(e) }), "error");
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setConfig({ ...DEFAULT_MINEBASE_CONFIG });
    setStatus({ msg: t("userConfig:MineBaseSection.defaultConfigurationRestoredClickSaveToApply"), kind: "info" });
    setTestResult(null);
  };

  const testConnection = async () => {
    const validationError = validateConfig();
    if (validationError) {
      setTestResult({ msg: validationError, ok: false });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const resolvePass = (val: string, saved: boolean) =>
        saved && val === MASKED ? KEYRING_SENTINEL : val;

      const params = config.mode === "api"
        ? { mode: "api", url: config.api.url, username: config.api.username, password: resolvePass(config.api.password, passSaved.api) }
        : { mode: "database", host: config.database.host, port: config.database.port, database: config.database.database, user: config.database.user, password: resolvePass(config.database.password, passSaved.db) };
      const res = await bridge.call<{ success: boolean; message: string }>("test_minebase_connection", params);
      setTestResult({ msg: res.message, ok: res.success });
    } catch (e) {
      setTestResult({ msg: t("userConfig:MineBaseSection.testError", { error: String(e) }), ok: false });
    } finally {
      setTesting(false);
    }
  };

  const passwordType = showPassword ? "text" : "password";

  return (
    <SectionCard
      title={t("userConfig:MineBaseSection.minebaseConfigurationconfiguration")}
      subtitle={t("userConfig:MineBaseSection.configurationMinebaseDatabaseconfiguration")}
      icon={<DatabaseIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      {/* Mode toggle */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-medium text-slate-500">{t("userConfig:MineBaseSection.syncMode")}</span>
        <div className="flex rounded-md border border-slate-200 overflow-hidden">
          <button
            onClick={() => setConfig((p) => ({ ...p, mode: "api" }))}
            className={`text-xs px-2.5 py-1 transition-colors ${
              config.mode === "api" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {t("userConfig:MineBaseSection.ui.apiMode")}
          </button>
          <button
            onClick={() => setConfig((p) => ({ ...p, mode: "database" }))}
            className={`text-xs px-2.5 py-1 transition-colors ${
              config.mode === "database" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {t("userConfig:MineBaseSection.ui.databaseMode")}
          </button>
        </div>
      </div>

      {/* API fields */}
      {config.mode === "api" && (
        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:MineBaseSection.apiUrl")}</label>
            <input
              type="text"
              value={config.api.url}
              onChange={(e) => updateApi("url", e.target.value)}
              placeholder="http://localhost:3000"
              className="input w-full"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:MineBaseSection.username")}</label>
              <input
                type="text"
                value={config.api.username}
                onChange={(e) => updateApi("username", e.target.value)}
                className="input w-full"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:MineBaseSection.password")}</label>
              <div className="relative">
                <input
                  type={passwordType}
                  value={config.api.password}
                  onChange={(e) => updateApi("password", e.target.value)}
                  className="input w-full pr-10"
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  title={showPassword ? t("userConfig:MineBaseSection.hidden") : t("userConfig:MineBaseSection.show")}
                >
                  {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Database fields */}
      {config.mode === "database" && (
        <div className="space-y-3">
          <div className="grid grid-cols-[1fr_120px] gap-3">
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:MineBaseSection.databaseHost")}</label>
              <input
                type="text"
                value={config.database.host}
                onChange={(e) => updateDb("host", e.target.value)}
                placeholder="localhost"
                className="input w-full"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:MineBaseSection.port")}</label>
              <input
                type="number"
                min={0}
                max={65535}
                value={config.database.port}
                onChange={(e) => updateDb("port", parseInt(e.target.value, 10) || 5432)}
                className={`input w-full ${
                  validatePort(config.database.port) ? "border-red-300" : ""
                }`}
              />
              {validatePort(config.database.port) && (
                <p className="text-xs text-red-500 mt-0.5">{validatePort(config.database.port)}</p>
              )}
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:MineBaseSection.databaseName")}</label>
            <input
              type="text"
              value={config.database.database}
              onChange={(e) => updateDb("database", e.target.value)}
              placeholder="minebase"
              className="input w-full"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:MineBaseSection.username")}</label>
              <input
                type="text"
                value={config.database.user}
                onChange={(e) => updateDb("user", e.target.value)}
                className="input w-full"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:MineBaseSection.password")}</label>
              <div className="relative">
                <input
                  type={passwordType}
                  value={config.database.password}
                  onChange={(e) => updateDb("password", e.target.value)}
                  className="input w-full pr-10"
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  title={showPassword ? t("userConfig:MineBaseSection.hidden") : t("userConfig:MineBaseSection.show")}
                >
                  {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Test connection button */}
      <div className="mt-3 flex items-center gap-2">
        <button
          onClick={testConnection}
          disabled={testing}
          className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors ${
            testing ? "opacity-50 cursor-not-allowed" : ""
          }`}
        >
          {testing ? t("userConfig:MineBaseSection.testing") : t("userConfig:MineBaseSection.testConnection")}
        </button>
        {testResult && (
          <span className={`text-xs ${testResult.ok ? "text-emerald-600" : "text-red-600"}`}>
            {testResult.msg}
          </span>
        )}
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
