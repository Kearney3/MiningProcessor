import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import {
  DatabaseIcon,
  EyeIcon,
  EyeOffIcon,
  PlusIcon,
  TrashIcon,
} from "../../lib/icons";
import { SectionCard, ActionButtons, StatusMessage } from "./_shared";

type ConnectionMode = "api" | "database";

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

interface MineBaseProfile {
  id: string;
  name: string;
  mode: ConnectionMode;
  api: MineBaseApiConfig;
  database: MineBaseDbConfig;
}

interface MineBaseConfig {
  active_profile_id: string;
  profiles: MineBaseProfile[];
}

const MASKED_PASSWORD = "********";
const KEYRING_SENTINEL = "__keyring__";

function createProfile(id: string, name = "新连接"): MineBaseProfile {
  return {
    id,
    name,
    mode: "api",
    api: { url: "http://localhost:3000", username: "", password: "" },
    database: {
      host: "localhost",
      port: 5432,
      database: "minebase",
      user: "postgres",
      password: "",
    },
  };
}

function createDefaultConfig(): MineBaseConfig {
  const profile = createProfile("local-api", "本地 MineBase");
  return { active_profile_id: profile.id, profiles: [profile] };
}

let profileSequence = 0;

function createNewProfile(): MineBaseProfile {
  profileSequence += 1;
  return createProfile(`profile-${Date.now()}-${profileSequence}`);
}

function normalizeConfig(raw: MineBaseConfig | null | undefined): MineBaseConfig {
  const rawProfiles = Array.isArray(raw?.profiles) && raw.profiles.length > 0
    ? raw.profiles
    : createDefaultConfig().profiles;

  const usedIds = new Set<string>();
  const profiles = rawProfiles.map((rawProfile, index) => {
    const idBase = String(rawProfile?.id || `profile-${index + 1}`);
    let id = idBase;
    let suffix = 2;
    while (usedIds.has(id)) id = `${idBase}-${suffix++}`;
    usedIds.add(id);

    const rawApi = rawProfile?.api ?? {};
    const rawDatabase = rawProfile?.database ?? {};
    const apiPassword = String(rawApi.password ?? "");
    const databasePassword = String(rawDatabase.password ?? "");
    return {
      id,
      name: String(rawProfile?.name || `连接 ${index + 1}`),
      mode: rawProfile?.mode === "database" ? "database" : "api",
      api: {
        url: String(rawApi.url ?? ""),
        username: String(rawApi.username ?? ""),
        password: apiPassword ? MASKED_PASSWORD : "",
      },
      database: {
        host: String(rawDatabase.host ?? "localhost"),
        port: Number.isFinite(Number(rawDatabase.port)) ? Number(rawDatabase.port) : 5432,
        database: String(rawDatabase.database ?? "minebase"),
        user: String(rawDatabase.user ?? "postgres"),
        password: databasePassword ? MASKED_PASSWORD : "",
      },
    } satisfies MineBaseProfile;
  });

  const activeId = raw?.active_profile_id && usedIds.has(raw.active_profile_id)
    ? raw.active_profile_id
    : profiles[0].id;
  return { active_profile_id: activeId, profiles };
}

export function MineBaseSection({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ msg: string; ok: boolean } | null>(null);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [config, setConfig] = useState<MineBaseConfig>(createDefaultConfig);
  const [showPassword, setShowPassword] = useState(false);

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<MineBaseConfig>("get_config", { key: "minebase" });
      setConfig(normalizeConfig(raw));
      setStatus({ msg: "", kind: "info" });
      setTestResult(null);
      setShowPassword(false);
    } catch {
      setConfig(createDefaultConfig());
      setStatus({ msg: "", kind: "info" });
    }
  }, [bridge.call]);

  useEffect(() => { reload(); }, [reload]);

  const selectedProfile = config.profiles.find(
    (profile) => profile.id === config.active_profile_id,
  ) ?? config.profiles[0];

  const updateSelectedProfile = (update: (profile: MineBaseProfile) => MineBaseProfile) => {
    setConfig((previous) => ({
      ...previous,
      profiles: previous.profiles.map((profile) => (
        profile.id === previous.active_profile_id ? update(profile) : profile
      )),
    }));
    setTestResult(null);
  };

  const updateApi = (field: keyof MineBaseApiConfig, value: string) => {
    updateSelectedProfile((profile) => ({
      ...profile,
      api: { ...profile.api, [field]: value },
    }));
  };

  const updateDatabase = (field: keyof MineBaseDbConfig, value: string | number) => {
    updateSelectedProfile((profile) => ({
      ...profile,
      database: { ...profile.database, [field]: value },
    }));
  };

  const selectProfile = (id: string) => {
    setConfig((previous) => ({ ...previous, active_profile_id: id }));
    setTestResult(null);
    setShowPassword(false);
  };

  const addProfile = () => {
    const profile = createNewProfile();
    setConfig((previous) => ({
      active_profile_id: profile.id,
      profiles: [...previous.profiles, profile],
    }));
    setTestResult(null);
    setStatus({ msg: t("userConfig:MineBaseSection.newProfileAdded"), kind: "info" });
  };

  const removeSelectedProfile = () => {
    if (config.profiles.length <= 1) {
      setStatus({ msg: t("userConfig:MineBaseSection.keepOneProfile"), kind: "error" });
      return;
    }
    const remaining = config.profiles.filter((profile) => profile.id !== config.active_profile_id);
    setConfig({
      active_profile_id: remaining[0].id,
      profiles: remaining,
    });
    setTestResult(null);
    setStatus({ msg: t("userConfig:MineBaseSection.profileRemoved"), kind: "info" });
  };

  const validatePort = (port: number): string | null => {
    if (!Number.isInteger(port) || port < 0 || port > 65535) {
      return t("userConfig:MineBaseSection.item065535Item");
    }
    return null;
  };

  const validateProfile = (profile: MineBaseProfile): string | null => {
    if (!profile.name.trim()) return t("userConfig:MineBaseSection.profileNameRequired");
    if (profile.mode === "api") {
      if (!profile.api.url.trim()) return t("userConfig:MineBaseSection.apiUrlRequired");
      if (!profile.api.username.trim()) return t("userConfig:MineBaseSection.usernameRequired");
      return null;
    }
    const portError = validatePort(profile.database.port);
    if (portError) return portError;
    if (!profile.database.host.trim()) return t("userConfig:MineBaseSection.databaseHostRequired");
    if (!profile.database.database.trim()) return t("userConfig:MineBaseSection.databaseNameRequired");
    if (!profile.database.user.trim()) return t("userConfig:MineBaseSection.databaseUserRequired");
    return null;
  };

  const validateConfig = (): string | null => {
    for (const profile of config.profiles) {
      const error = validateProfile(profile);
      if (error) return `${profile.name || t("userConfig:MineBaseSection.unnamedProfile")}: ${error}`;
    }
    return null;
  };

  const resolvePassword = (password: string) => (
    password === MASKED_PASSWORD ? KEYRING_SENTINEL : password
  );

  const save = async () => {
    const validationError = validateConfig();
    if (validationError) {
      setStatus({ msg: validationError, kind: "error" });
      return;
    }

    setSaving(true);
    try {
      const toSave: MineBaseConfig = {
        ...config,
        profiles: config.profiles.map((profile) => ({
          ...profile,
          api: { ...profile.api, password: resolvePassword(profile.api.password) },
          database: { ...profile.database, password: resolvePassword(profile.database.password) },
        })),
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
    setConfig(createDefaultConfig());
    setStatus({ msg: t("userConfig:MineBaseSection.defaultConfigurationRestoredClickSaveToApply"), kind: "info" });
    setTestResult(null);
    setShowPassword(false);
  };

  const testConnection = async () => {
    if (!selectedProfile) return;
    const validationError = validateProfile(selectedProfile);
    if (validationError) {
      setTestResult({ msg: validationError, ok: false });
      return;
    }

    setTesting(true);
    setTestResult(null);
    try {
      const password = selectedProfile.mode === "api"
        ? resolvePassword(selectedProfile.api.password)
        : resolvePassword(selectedProfile.database.password);
      const params = selectedProfile.mode === "api"
        ? {
            profile_id: selectedProfile.id,
            mode: "api",
            url: selectedProfile.api.url,
            username: selectedProfile.api.username,
            password,
          }
        : {
            profile_id: selectedProfile.id,
            mode: "database",
            host: selectedProfile.database.host,
            port: selectedProfile.database.port,
            database: selectedProfile.database.database,
            user: selectedProfile.database.user,
            password,
          };
      const result = await bridge.call<{ success: boolean; message: string }>("test_minebase_connection", params);
      setTestResult({ msg: result.message, ok: result.success });
    } catch (e) {
      setTestResult({ msg: t("userConfig:MineBaseSection.testError", { error: String(e) }), ok: false });
    } finally {
      setTesting(false);
    }
  };

  const updateMode = (mode: ConnectionMode) => {
    updateSelectedProfile((profile) => ({ ...profile, mode }));
  };

  return (
    <SectionCard
      title={t("userConfig:MineBaseSection.minebaseConfigurationconfiguration")}
      subtitle={t("userConfig:MineBaseSection.configurationMinebaseDatabaseconfiguration")}
      icon={<DatabaseIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      <div className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label className="text-xs font-medium text-slate-500 mb-1 block" htmlFor="minebase-profile">
              {t("userConfig:MineBaseSection.savedProfiles")}
            </label>
            <select
              id="minebase-profile"
              value={selectedProfile?.id ?? ""}
              onChange={(event) => selectProfile(event.target.value)}
              className="input w-full"
            >
              {config.profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name} · {profile.mode === "api"
                    ? (profile.api.url || t("userConfig:MineBaseSection.noAddress"))
                    : (profile.database.host || t("userConfig:MineBaseSection.noAddress"))}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={addProfile}
            className="inline-flex items-center justify-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 px-3 py-2 rounded-md border border-blue-200 hover:bg-blue-50 transition-colors"
          >
            <PlusIcon />
            {t("userConfig:MineBaseSection.addProfile")}
          </button>
          <button
            type="button"
            onClick={removeSelectedProfile}
            disabled={config.profiles.length <= 1}
            className={`inline-flex items-center justify-center gap-1.5 text-xs font-medium text-red-600 hover:text-red-700 px-3 py-2 rounded-md border border-red-200 hover:bg-red-50 transition-colors ${config.profiles.length <= 1 ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            <TrashIcon />
            {t("userConfig:MineBaseSection.removeProfile")}
          </button>
        </div>

        <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-500">
          {t("userConfig:MineBaseSection.profileHint", { count: config.profiles.length })}
        </div>

        {selectedProfile && (
          <div className="rounded-lg border border-slate-200 p-3 sm:p-4 space-y-4">
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
              <div>
                <label className="text-xs font-medium text-slate-500 mb-1 block" htmlFor="minebase-profile-name">
                  {t("userConfig:MineBaseSection.profileName")}
                </label>
                <input
                  id="minebase-profile-name"
                  type="text"
                  value={selectedProfile.name}
                  onChange={(event) => updateSelectedProfile((profile) => ({ ...profile, name: event.target.value }))}
                  className="input w-full"
                  placeholder={t("userConfig:MineBaseSection.profileNamePlaceholder")}
                />
              </div>
              <div>
                <span className="text-xs font-medium text-slate-500 mb-1 block">{t("userConfig:MineBaseSection.syncMode")}</span>
                <div className="flex rounded-md border border-slate-200 overflow-hidden">
                  <button
                    type="button"
                    onClick={() => updateMode("api")}
                    className={`text-xs px-3 py-2 transition-colors ${selectedProfile.mode === "api" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
                  >
                    {t("userConfig:MineBaseSection.ui.apiMode")}
                  </button>
                  <button
                    type="button"
                    onClick={() => updateMode("database")}
                    className={`text-xs px-3 py-2 transition-colors ${selectedProfile.mode === "database" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
                  >
                    {t("userConfig:MineBaseSection.ui.databaseMode")}
                  </button>
                </div>
              </div>
            </div>

            {selectedProfile.mode === "api" ? (
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-slate-500 mb-1 block" htmlFor="minebase-api-url">
                    {t("userConfig:MineBaseSection.apiUrl")}
                  </label>
                  <input
                    id="minebase-api-url"
                    type="url"
                    value={selectedProfile.api.url}
                    onChange={(event) => updateApi("url", event.target.value)}
                    placeholder="http://localhost:3000"
                    className="input w-full"
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block" htmlFor="minebase-api-username">
                      {t("userConfig:MineBaseSection.username")}
                    </label>
                    <input
                      id="minebase-api-username"
                      type="text"
                      value={selectedProfile.api.username}
                      onChange={(event) => updateApi("username", event.target.value)}
                      className="input w-full"
                      autoComplete="username"
                    />
                  </div>
                  <PasswordField
                    id="minebase-api-password"
                    value={selectedProfile.api.password}
                    onChange={(value) => updateApi("password", value)}
                    show={showPassword}
                    onToggle={() => setShowPassword((value) => !value)}
                    label={t("userConfig:MineBaseSection.password")}
                    showLabel={t("userConfig:MineBaseSection.show")}
                    hideLabel={t("userConfig:MineBaseSection.hidden")}
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_120px]">
                  <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block" htmlFor="minebase-db-host">
                      {t("userConfig:MineBaseSection.databaseHost")}
                    </label>
                    <input
                      id="minebase-db-host"
                      type="text"
                      value={selectedProfile.database.host}
                      onChange={(event) => updateDatabase("host", event.target.value)}
                      placeholder="localhost"
                      className="input w-full"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block" htmlFor="minebase-db-port">
                      {t("userConfig:MineBaseSection.port")}
                    </label>
                    <input
                      id="minebase-db-port"
                      type="number"
                      min={0}
                      max={65535}
                      value={selectedProfile.database.port}
                      onChange={(event) => updateDatabase("port", Number(event.target.value))}
                      className={`input w-full ${validatePort(selectedProfile.database.port) ? "border-red-300" : ""}`}
                    />
                    {validatePort(selectedProfile.database.port) && (
                      <p className="text-xs text-red-500 mt-0.5">{validatePort(selectedProfile.database.port)}</p>
                    )}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-500 mb-1 block" htmlFor="minebase-db-name">
                    {t("userConfig:MineBaseSection.databaseName")}
                  </label>
                  <input
                    id="minebase-db-name"
                    type="text"
                    value={selectedProfile.database.database}
                    onChange={(event) => updateDatabase("database", event.target.value)}
                    placeholder="minebase"
                    className="input w-full"
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block" htmlFor="minebase-db-username">
                      {t("userConfig:MineBaseSection.username")}
                    </label>
                    <input
                      id="minebase-db-username"
                      type="text"
                      value={selectedProfile.database.user}
                      onChange={(event) => updateDatabase("user", event.target.value)}
                      className="input w-full"
                      autoComplete="username"
                    />
                  </div>
                  <PasswordField
                    id="minebase-db-password"
                    value={selectedProfile.database.password}
                    onChange={(value) => updateDatabase("password", value)}
                    show={showPassword}
                    onToggle={() => setShowPassword((value) => !value)}
                    label={t("userConfig:MineBaseSection.password")}
                    showLabel={t("userConfig:MineBaseSection.show")}
                    hideLabel={t("userConfig:MineBaseSection.hidden")}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={testConnection}
            disabled={testing || !selectedProfile}
            className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors ${testing ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            {testing ? t("userConfig:MineBaseSection.testing") : t("userConfig:MineBaseSection.testConnection")}
          </button>
          {testResult && (
            <span className={`text-xs ${testResult.ok ? "text-emerald-600" : "text-red-600"}`} role="status">
              {testResult.msg}
            </span>
          )}
        </div>

        <ActionButtons saving={saving} onSave={save} onReload={reload} onReset={resetToDefault} />
        <StatusMessage message={status.msg} kind={status.kind} />
      </div>
    </SectionCard>
  );
}

function PasswordField({
  id,
  value,
  onChange,
  show,
  onToggle,
  label,
  showLabel,
  hideLabel,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  show: boolean;
  onToggle: () => void;
  label: string;
  showLabel: string;
  hideLabel: string;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-slate-500 mb-1 block" htmlFor={id}>{label}</label>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="input w-full pr-10"
          autoComplete="current-password"
        />
        <button
          type="button"
          onClick={onToggle}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          title={show ? hideLabel : showLabel}
          aria-label={show ? hideLabel : showLabel}
        >
          {show ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
    </div>
  );
}
