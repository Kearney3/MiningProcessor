import { useState, useEffect, useCallback } from "react";

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

interface FileKeywords {
  fuel: string[];
  electrical: string[];
  production: string[];
  worktime: string[];
}

interface HeaderMappingEntry {
  index: number | null;
  original: string;
  new: string;
}

interface HeaderMappingConfig {
  mode: "position" | "name";
  fuzzy: boolean;
  entries: HeaderMappingEntry[];
}

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

const DEFAULT_FILE_KEYWORDS: FileKeywords = {
  fuel: ["Fuel report "],
  electrical: ["Цахилгааны хэлтэс"],
  production: ["白班", "夜班"],
  worktime: ["工作效率表"],
};

const DEFAULT_HEADER_MAPPING: HeaderMappingConfig = {
  mode: "position",
  fuzzy: false,
  entries: [
    { index: 1, original: "", new: "日期" },
    { index: 2, original: "", new: "班次" },
    { index: 3, original: "", new: "序号" },
    { index: 4, original: "", new: "设备名称" },
    { index: 5, original: "", new: "公司" },
    { index: 6, original: "", new: "应运行分钟" },
    { index: 7, original: "", new: "应运行小时数" },
    { index: 8, original: "", new: "停车/换班" },
    { index: 9, original: "", new: "转移" },
    { index: 10, original: "", new: "挖机场地推土/清理墙壁" },
    { index: 11, original: "", new: "等待装货" },
    { index: 12, original: "", new: "爆破" },
    { index: 13, original: "", new: "就餐/休息时间" },
    { index: 14, original: "", new: "柴油" },
    { index: 15, original: "", new: "计划维修/润滑" },
    { index: 16, original: "", new: "未计划/故障" },
    { index: 17, original: "", new: "待命" },
    { index: 18, original: "", new: "因天气：大风暴，雨，雪" },
    { index: 19, original: "", new: "扬尘：洒水车不足" },
    { index: 20, original: "", new: "排队/装水" },
    { index: 21, original: "", new: "总产量生产运行分钟" },
    { index: 22, original: "", new: "因电力原因停车/计划" },
    { index: 23, original: "", new: "因电力原因停车/未计划" },
    { index: 24, original: "", new: "总产量生产运行小时" },
    { index: 25, original: "", new: "注释" },
  ],
};

const DEFAULT_MINEBASE_CONFIG: MineBaseConfig = {
  mode: "api",
  api: { url: "", username: "", password: "" },
  database: { host: "localhost", port: 5432, database: "minebase", user: "postgres", password: "" },
};

/* ------------------------------------------------------------------ */
/*  SVG Icons (16x16)                                                  */
/* ------------------------------------------------------------------ */

const IconKeywords = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
  </svg>
);

const IconTableHeader = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
  </svg>
);

const IconDatabase = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
  </svg>
);

const IconColumns = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7" />
  </svg>
);

const IconSave = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
  </svg>
);

const IconRefresh = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);

const IconRestore = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a5 5 0 015 5v2M3 10l4-4M3 10l4 4" />
  </svg>
);

const IconPlus = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
  </svg>
);

const IconClose = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const IconEye = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
  </svg>
);

const IconEyeOff = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L6.59 6.59m7.532 7.532l3.29 3.29M3 3l18 18" />
  </svg>
);

const IconCheck = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
  </svg>
);

const IconError = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const IconChevronDown = () => (
  <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
  </svg>
);

// ---------------------------------------------------------------------------
// Collapsible Section Card — NO colored left border
// ---------------------------------------------------------------------------

function SectionCard({
  title,
  subtitle,
  icon,
  expanded,
  onToggle,
  children,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <span className="text-slate-500">{icon}</span>
          <div className="text-left">
            <h3 className="text-sm font-medium text-slate-700">{title}</h3>
            <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
          </div>
        </div>
        <span className={`transition-transform ${expanded ? "rotate-180" : ""}`}>
          <IconChevronDown />
        </span>
      </button>
      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3">{children}</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-section action buttons (text-xs)
// ---------------------------------------------------------------------------

function ActionButtons({
  saving,
  onSave,
  onReload,
  onReset,
  onExtra,
  extraLabel,
}: {
  saving: boolean;
  onSave: () => void;
  onReload: () => void;
  onReset: () => void;
  onExtra?: () => void;
  extraLabel?: string;
}) {
  return (
    <div className="flex gap-2 flex-wrap mt-4 pt-3 border-t border-slate-100">
      <button
        onClick={onSave}
        disabled={saving}
        className={`inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700 px-2.5 py-1.5 rounded-md hover:bg-blue-50 transition-colors ${
          saving ? "opacity-50 cursor-not-allowed" : ""
        }`}
      >
        <IconSave />
        {saving ? "保存中..." : "保存"}
      </button>
      <button
        onClick={onReload}
        className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2.5 py-1.5 rounded-md hover:bg-slate-50 transition-colors"
      >
        <IconRefresh />
        重新加载
      </button>
      <button
        onClick={onReset}
        className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-700 px-2.5 py-1.5 rounded-md hover:bg-red-50 transition-colors"
      >
        <IconRestore />
        恢复默认
      </button>
      {onExtra && extraLabel && (
        <button
          onClick={onExtra}
          className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2.5 py-1.5 rounded-md hover:bg-slate-50 transition-colors"
        >
          <IconPlus />
          {extraLabel}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status message
// ---------------------------------------------------------------------------

function StatusMessage({ message, kind }: { message: string; kind: "success" | "error" | "info" }) {
  if (!message) return null;

  const cls =
    kind === "error"
      ? "text-red-700 bg-red-50 border-red-200"
      : kind === "success"
        ? "text-emerald-700 bg-emerald-50 border-emerald-200"
        : "text-slate-600 bg-slate-50 border-slate-200";

  const icon =
    kind === "error" ? <IconError /> : kind === "success" ? <IconCheck /> : null;

  return (
    <div className={`mt-3 text-xs rounded-md px-3 py-2 border flex items-center gap-2 ${cls}`}>
      {icon}
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 1: File Keywords
// ---------------------------------------------------------------------------

function FileKeywordsSection({ bridge }: { bridge: BridgeProp }) {
  const [expanded, setExpanded] = useState(true);
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
        });
      } else {
        setKeywords({ ...DEFAULT_FILE_KEYWORDS });
      }
      setStatus({ msg: "", kind: "info" });
    } catch {
      setKeywords({ ...DEFAULT_FILE_KEYWORDS });
    }
  }, [bridge]);

  useEffect(() => { reload(); }, [reload]);

  const join = (arr: string[]) => arr.join(",");
  const split = (s: string) =>
    s.split(",").map((v) => v.trim()).filter(Boolean);

  const updateField = (key: keyof FileKeywords, text: string) => {
    setKeywords((prev) => ({ ...prev, [key]: split(text) }));
  };

  const save = async () => {
    setSaving(true);
    try {
      await bridge.call("save_config", { data: { file_keywords: keywords }, target: "user" });
      setStatus({ msg: "文件关键字配置已保存", kind: "success" });
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: `保存失败: ${String(e)}`, kind: "error" });
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setKeywords({ ...DEFAULT_FILE_KEYWORDS });
    setStatus({ msg: "已恢复默认关键字（需点击保存生效）", kind: "info" });
  };

  const fields: { key: keyof FileKeywords; label: string; hint: string }[] = [
    { key: "fuel", label: "油耗关键字", hint: "例如: Fuel report, 设备柴油消耗" },
    { key: "electrical", label: "电力关键字", hint: "例如: Electrical, Цахилгааны хэлтэс" },
    { key: "production", label: "生产关键字", hint: "例如: 白班, 夜班" },
    { key: "worktime", label: "工时关键字", hint: "例如: 工作效率表, 工时" },
  ];

  return (
    <SectionCard
      title="文件关键字"
      subtitle="批量处理时用于匹配文件名的关键字，多个关键字用英文逗号分隔"
      icon={<IconKeywords />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      <div className="space-y-3">
        {fields.map(({ key, label, hint }) => (
          <div key={key}>
            <label className="text-xs font-medium text-slate-500 mb-1 block">{label}</label>
            <input
              type="text"
              value={join(keywords[key])}
              onChange={(e) => updateField(key, e.target.value)}
              placeholder={hint}
              className="input w-full"
            />
          </div>
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

// ---------------------------------------------------------------------------
// Section 2: Worktime Header Mapping
// ---------------------------------------------------------------------------

function HeaderMappingSection({ bridge }: { bridge: BridgeProp }) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [mode, setMode] = useState<"position" | "name">("position");
  const [fuzzy, setFuzzy] = useState(false);
  const [entries, setEntries] = useState<HeaderMappingEntry[]>([]);

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<HeaderMappingConfig>("get_config", { key: "worktime_header_mapping" });
      if (raw && typeof raw === "object" && Array.isArray(raw.entries)) {
        setMode(raw.mode ?? "position");
        setFuzzy(raw.fuzzy ?? false);
        setEntries(raw.entries.map((e) => ({ index: e.index ?? null, original: e.original ?? "", new: e.new ?? "" })));
      } else {
        setMode(DEFAULT_HEADER_MAPPING.mode);
        setFuzzy(DEFAULT_HEADER_MAPPING.fuzzy);
        setEntries(DEFAULT_HEADER_MAPPING.entries.map((e) => ({ ...e })));
      }
      setStatus({ msg: "", kind: "info" });
    } catch {
      setMode(DEFAULT_HEADER_MAPPING.mode);
      setFuzzy(DEFAULT_HEADER_MAPPING.fuzzy);
      setEntries(DEFAULT_HEADER_MAPPING.entries.map((e) => ({ ...e })));
    }
  }, [bridge]);

  useEffect(() => { reload(); }, [reload]);

  const validate = (): string | null => {
    const seen: Record<number, number> = {};
    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      if (!e.new.trim()) return `第 ${i + 1} 行：匹配列名不能为空`;
      if (e.index !== null) {
        if (seen[e.index] !== undefined) {
          return `行号 ${e.index} 重复（第 ${seen[e.index]} 行和第 ${i + 1} 行）`;
        }
        seen[e.index] = i + 1;
      }
    }
    return null;
  };

  const save = async () => {
    const err = validate();
    if (err) {
      setStatus({ msg: err, kind: "error" });
      return;
    }
    setSaving(true);
    try {
      const cleanEntries = entries
        .filter((e) => e.index !== null || e.original.trim() || e.new.trim())
        .map((e) => ({ index: e.index, original: e.original.trim(), new: e.new.trim() }));
      await bridge.call("save_config", {
        data: { worktime_header_mapping: { mode, fuzzy, entries: cleanEntries } },
        target: "user",
      });
      setStatus({ msg: `已保存 ${cleanEntries.length} 条表头映射`, kind: "success" });
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: `保存失败: ${String(e)}`, kind: "error" });
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setMode(DEFAULT_HEADER_MAPPING.mode);
    setFuzzy(DEFAULT_HEADER_MAPPING.fuzzy);
    setEntries(DEFAULT_HEADER_MAPPING.entries.map((e) => ({ ...e })));
    setStatus({ msg: "已恢复默认配置（需点击保存生效）", kind: "info" });
  };

  const addRow = () => {
    setEntries((prev) => [...prev, { index: null, original: "", new: "" }]);
  };

  const removeRow = (idx: number) => {
    setEntries((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateEntry = (idx: number, field: keyof HeaderMappingEntry, value: unknown) => {
    setEntries((prev) =>
      prev.map((e, i) => (i === idx ? { ...e, [field]: value } : e))
    );
  };

  return (
    <SectionCard
      title="工时表头映射"
      subtitle="配置工时 Excel 表头的重命名规则"
      icon={<IconTableHeader />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      {/* Mode toggle + fuzzy */}
      <div className="flex items-center gap-5 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-500">映射模式：</span>
          <div className="flex rounded-md border border-slate-200 overflow-hidden">
            <button
              onClick={() => setMode("position")}
              className={`text-xs px-2.5 py-1 transition-colors ${
                mode === "position" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              位置映射
            </button>
            <button
              onClick={() => setMode("name")}
              className={`text-xs px-2.5 py-1 transition-colors ${
                mode === "name" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              名称映射
            </button>
          </div>
        </div>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={fuzzy}
            onChange={(e) => setFuzzy(e.target.checked)}
            className="w-4 h-4 rounded border-slate-300"
          />
          模糊匹配
        </label>
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[60px_1fr_1fr_32px] gap-2 mb-1.5 px-0.5">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">列号</span>
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">原始列名</span>
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">匹配列名</span>
        <span />
      </div>

      {/* Mapping rows */}
      <div className="space-y-1 max-h-80 overflow-y-auto pr-1">
        {entries.map((entry, idx) => (
          <div key={idx} className="grid grid-cols-[60px_1fr_1fr_32px] gap-2 items-center">
            <input
              type="number"
              min={1}
              value={entry.index ?? ""}
              onChange={(e) => {
                const v = e.target.value.trim();
                updateEntry(idx, "index", v ? parseInt(v, 10) : null);
              }}
              placeholder="从1起"
              className="input w-full"
            />
            <input
              type="text"
              value={entry.original}
              onChange={(e) => updateEntry(idx, "original", e.target.value)}
              placeholder="原始列名"
              className="input w-full"
            />
            <input
              type="text"
              value={entry.new}
              onChange={(e) => updateEntry(idx, "new", e.target.value)}
              placeholder="匹配列名"
              className="input w-full"
            />
            <button
              onClick={() => removeRow(idx)}
              className="w-8 h-8 flex items-center justify-center rounded-md text-slate-600 hover:text-red-500 hover:bg-red-50 transition-colors"
              title="删除此行"
            >
              <IconClose />
            </button>
          </div>
        ))}
      </div>

      <ActionButtons
        saving={saving}
        onSave={save}
        onReload={reload}
        onReset={resetToDefault}
        onExtra={addRow}
        extraLabel="添加映射"
      />
      <StatusMessage message={status.msg} kind={status.kind} />
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Section 3: MineBase Connection
// ---------------------------------------------------------------------------

function MineBaseSection({ bridge }: { bridge: BridgeProp }) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [config, setConfig] = useState<MineBaseConfig>({ ...DEFAULT_MINEBASE_CONFIG });
  const [showPassword, setShowPassword] = useState(false);

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<MineBaseConfig>("get_config", { key: "minebase" });
      if (raw && typeof raw === "object") {
        setConfig({
          mode: raw.mode ?? "api",
          api: {
            url: raw.api?.url ?? "",
            username: raw.api?.username ?? "",
            password: raw.api?.password ?? "",
          },
          database: {
            host: raw.database?.host ?? "localhost",
            port: raw.database?.port ?? 5432,
            database: raw.database?.database ?? "minebase",
            user: raw.database?.user ?? "postgres",
            password: raw.database?.password ?? "",
          },
        });
      } else {
        setConfig({ ...DEFAULT_MINEBASE_CONFIG });
      }
      setStatus({ msg: "", kind: "info" });
    } catch {
      setConfig({ ...DEFAULT_MINEBASE_CONFIG });
    }
  }, [bridge]);

  useEffect(() => { reload(); }, [reload]);

  const updateApi = (field: keyof MineBaseApiConfig, value: string) => {
    setConfig((prev) => ({ ...prev, api: { ...prev.api, [field]: value } }));
  };

  const updateDb = (field: keyof MineBaseDbConfig, value: string | number) => {
    setConfig((prev) => ({ ...prev, database: { ...prev.database, [field]: value } }));
  };

  const validatePort = (port: number): string | null => {
    if (port < 0 || port > 65535) return "端口必须在 0-65535 之间";
    return null;
  };

  const save = async () => {
    if (config.mode === "database") {
      const err = validatePort(config.database.port);
      if (err) {
        setStatus({ msg: err, kind: "error" });
        return;
      }
    }
    setSaving(true);
    try {
      await bridge.call("save_config", { data: { minebase: config }, target: "user" });
      setStatus({ msg: "MineBase 连接配置已保存", kind: "success" });
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: `保存失败: ${String(e)}`, kind: "error" });
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setConfig({ ...DEFAULT_MINEBASE_CONFIG });
    setStatus({ msg: "已恢复默认配置（需点击保存生效）", kind: "info" });
  };

  const passwordType = showPassword ? "text" : "password";

  return (
    <SectionCard
      title="MineBase 连接配置"
      subtitle="配置 MineBase 数据库同步的连接参数"
      icon={<IconDatabase />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      {/* Mode toggle */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-medium text-slate-500">同步模式：</span>
        <div className="flex rounded-md border border-slate-200 overflow-hidden">
          <button
            onClick={() => setConfig((p) => ({ ...p, mode: "api" }))}
            className={`text-xs px-2.5 py-1 transition-colors ${
              config.mode === "api" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            API 模式
          </button>
          <button
            onClick={() => setConfig((p) => ({ ...p, mode: "database" }))}
            className={`text-xs px-2.5 py-1 transition-colors ${
              config.mode === "database" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            直连数据库
          </button>
        </div>
      </div>

      {/* API fields */}
      {config.mode === "api" && (
        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1 block">API 地址</label>
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
              <label className="text-xs font-medium text-slate-500 mb-1 block">用户名</label>
              <input
                type="text"
                value={config.api.username}
                onChange={(e) => updateApi("username", e.target.value)}
                className="input w-full"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">密码</label>
              <div className="relative">
                <input
                  type={passwordType}
                  value={config.api.password}
                  onChange={(e) => updateApi("password", e.target.value)}
                  className="input w-full pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  title={showPassword ? "隐藏" : "显示"}
                >
                  {showPassword ? <IconEyeOff /> : <IconEye />}
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
              <label className="text-xs font-medium text-slate-500 mb-1 block">数据库主机</label>
              <input
                type="text"
                value={config.database.host}
                onChange={(e) => updateDb("host", e.target.value)}
                placeholder="localhost"
                className="input w-full"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">端口</label>
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
            <label className="text-xs font-medium text-slate-500 mb-1 block">数据库名</label>
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
              <label className="text-xs font-medium text-slate-500 mb-1 block">用户名</label>
              <input
                type="text"
                value={config.database.user}
                onChange={(e) => updateDb("user", e.target.value)}
                className="input w-full"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">密码</label>
              <div className="relative">
                <input
                  type={passwordType}
                  value={config.database.password}
                  onChange={(e) => updateDb("password", e.target.value)}
                  className="input w-full pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  title={showPassword ? "隐藏" : "显示"}
                >
                  {showPassword ? <IconEyeOff /> : <IconEye />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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

// ---------------------------------------------------------------------------
// Section 4: Column Mapping (placeholder)
// ---------------------------------------------------------------------------

function ColumnMappingSection() {
  const [expanded, setExpanded] = useState(false);

  return (
    <SectionCard
      title="列映射配置"
      subtitle="配置 MiningProcessor 输出列到 MineBase 字段的映射关系"
      icon={<IconColumns />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      <div className="flex flex-col items-center justify-center py-12 text-slate-400 gap-2">
        <svg className="w-10 h-10 text-slate-200" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <p className="text-sm">列映射配置编辑器开发中...</p>
      </div>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function UserConfigPage({ bridge }: { bridge: BridgeProp }) {
  return (
    <div>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-slate-800">用户配置</h2>
        <p className="text-xs text-slate-500 mt-0.5">管理与业务处理无关的个人偏好设置</p>
      </div>

      <div className="space-y-2">
        <MineBaseSection bridge={bridge} />
        <FileKeywordsSection bridge={bridge} />
        <HeaderMappingSection bridge={bridge} />
        <ColumnMappingSection />
      </div>
    </div>
  );
}
