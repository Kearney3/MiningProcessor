import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

// ═══════════════════════════════════════
// Shared helpers & small components
// ═══════════════════════════════════════

const currentYear = new Date().getFullYear();
const yearOptions = Array.from({ length: 11 }, (_, i) => currentYear - 5 + i);
const monthOptions = Array.from({ length: 12 }, (_, i) => i + 1);

/** Chevron down icon for selects — Lucide style, 16x16 */
const ChevronDownIcon = () => (
  <svg className="w-4 h-4 text-slate-400 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 9l6 6 6-6" />
  </svg>
);

/** Play icon for process buttons */
const PlayIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

const FolderIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
  </svg>
);

const FileIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

const PlusIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const TrashIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
  </svg>
);

/** Check icon for success badges */
const CheckCircleIcon = () => (
  <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);

/** X icon for error badges */
const XCircleIcon = () => (
  <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />
  </svg>
);

/** Warning icon */
const AlertTriangleIcon = () => (
  <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

// ═══════════════════════════════════════
// Lucide-style module icons (16x16)
// ═══════════════════════════════════════

/** Zap icon — fuel */
const FuelIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);

/** Bar-chart-2 icon — production */
const ProductionIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

/** Bolt icon — electrical */
const ElectricalIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);

/** Clock icon — worktime */
const WorktimeIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

/** Layers icon — merge */
const MergeIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" />
    <polyline points="2 12 12 17 22 12" />
  </svg>
);

// ═══════════════════════════════════════
// Design-system component tokens
// ═══════════════════════════════════════

const inputClass = "border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-colors";
const btnSecondaryClass = "shrink-0 flex items-center gap-1.5 text-sm border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-md transition-colors";
const btnPrimaryClass = "flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 text-white rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed";

function ModuleCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-sm font-medium text-slate-700">{title}</h3>
      </div>
      {children}
    </div>
  );
}

/** File / folder selection input */
function PathInput({
  value,
  onChange,
  placeholder,
  directory = false,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  directory?: boolean;
}) {
  const browse = async () => {
    const selected = await open({
      directory,
      multiple: false,
      filters: directory
        ? undefined
        : [{ name: "Excel", extensions: ["xlsx", "xls"] }],
    });
    if (selected) onChange(selected as string);
  };

  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`${inputClass} flex-1 ${value === "" ? "border-amber-300 bg-amber-50/30" : ""}`}
      />
      <button onClick={browse} className={btnSecondaryClass}>
        {directory ? <FolderIcon /> : <FileIcon />}
        <span>浏览</span>
      </button>
    </div>
  );
}

/** Dual browse buttons for file or folder */
function PathInputDual({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const browseFile = async () => {
    const selected = await open({
      directory: false,
      multiple: false,
      filters: [{ name: "Excel", extensions: ["xlsx", "xls"] }],
    });
    if (selected) onChange(selected as string);
  };

  const browseFolder = async () => {
    const selected = await open({ directory: true, multiple: false });
    if (selected) onChange(selected as string);
  };

  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`${inputClass} flex-1 ${value === "" ? "border-amber-300 bg-amber-50/30" : ""}`}
      />
      <button onClick={browseFile} className={btnSecondaryClass} title="选择文件">
        <FileIcon />
        <span>选文件</span>
      </button>
      <button onClick={browseFolder} className={btnSecondaryClass} title="选择文件夹">
        <FolderIcon />
        <span>选文件夹</span>
      </button>
    </div>
  );
}

/** Generic select dropdown with chevron icon */
function StyledSelect({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string }[];
  placeholder?: string;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${inputClass} appearance-none pr-8 w-full`}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none">
        <ChevronDownIcon />
      </div>
    </div>
  );
}

/** Styled toggle switch — restrained design */
function StyledToggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer select-none">
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
          checked ? "bg-blue-600" : "bg-slate-200"
        }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
            checked ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>
      <span className="text-sm text-slate-700">{label}</span>
    </label>
  );
}

/** Chip-style toggle with two options */
function ChipToggle({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string }[];
}) {
  return (
    <div className="inline-flex rounded-md border border-slate-200 overflow-hidden">
      {options.map((o, i) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`text-xs px-3 py-1.5 transition-colors ${
            value === o.value
              ? "bg-slate-900 text-white"
              : "bg-white text-slate-600 hover:bg-slate-50"
          } ${i > 0 ? "border-l border-slate-200" : ""}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Inline validation warning */
function PathWarning() {
  return (
    <div className="mt-1.5 flex items-center gap-1 text-xs text-amber-600">
      <AlertTriangleIcon />
      请先选择输入路径
    </div>
  );
}

/** Result success badge */
function SuccessBadge({ message }: { message: string }) {
  return (
    <div className="mt-3 flex items-center gap-2 text-xs rounded-md px-2.5 py-1.5 text-emerald-700 bg-emerald-50">
      <CheckCircleIcon />
      {message}
    </div>
  );
}

/** Result error badge */
function ErrorBadge({ message }: { message: string }) {
  return (
    <div className="mt-3 flex items-center gap-2 text-xs rounded-md px-2.5 py-1.5 text-red-700 bg-red-50">
      <XCircleIcon />
      {message}
    </div>
  );
}

/** Processing button with icon */
function ProcessButton({
  loading,
  onClick,
  disabled,
}: {
  loading: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      disabled={loading || disabled}
      onClick={onClick}
      className={`${btnPrimaryClass} mt-3 w-full`}
    >
      {!loading && <PlayIcon />}
      {loading ? (
        <>
          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          处理中...
        </>
      ) : (
        "开始处理"
      )}
    </button>
  );
}

// ═══════════════════════════════════════
// Sort config row type
// ═══════════════════════════════════════
interface SortConfig {
  id: number;
  column: string;
  ascending: boolean;
}

// ═══════════════════════════════════════
// Fuel processing
// ═══════════════════════════════════════
function FuelCard({
  bridge,
  useLedger,
}: {
  bridge: BridgeProp;
  useLedger: boolean;
}) {
  const [path, setPath] = useState("");
  const [year, setYear] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const params: Record<string, unknown> = { path, use_ledger: useLedger };
      if (year) params.year = parseInt(year);
      const res = await bridge.call<{ output_file?: string }>(
        "process_fuel",
        params,
      );
      setResult(res.output_file ? `输出: ${res.output_file}` : "处理完成");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="油耗处理" icon={<FuelIcon />}>
      <PathInput value={path} onChange={setPath} placeholder="选择 Excel 文件" />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <StyledSelect
          value={year}
          onChange={setYear}
          placeholder="年份（可选）"
          options={yearOptions.map((y) => ({ label: `${y}年`, value: String(y) }))}
        />
      </div>
      <ProcessButton loading={loading} onClick={handleProcess} disabled={path === ""} />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
    </ModuleCard>
  );
}

// ═══════════════════════════════════════
// Production data
// ═══════════════════════════════════════
function ProductionCard({
  bridge,
  useLedger,
}: {
  bridge: BridgeProp;
  useLedger: boolean;
}) {
  const [path, setPath] = useState("");
  const [rawStart, setRawStart] = useState("-1");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      await bridge.call("process_production", {
        path,
        raw_start: parseInt(rawStart),
        use_ledger: useLedger,
      });
      setResult("处理完成");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="生产数据" icon={<ProductionIcon />}>
      <PathInputDual
        value={path}
        onChange={setPath}
        placeholder="选择文件或文件夹"
      />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <input
          type="number"
          value={rawStart}
          onChange={(e) => setRawStart(e.target.value)}
          placeholder="表头起始行（-1=自动检测）"
          className={inputClass}
        />
      </div>
      <ProcessButton
        loading={loading}
        onClick={handleProcess}
        disabled={path === ""}
      />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
    </ModuleCard>
  );
}

// ═══════════════════════════════════════
// Electrical consumption
// ═══════════════════════════════════════
function ElectricalCard({
  bridge,
  useLedger,
}: {
  bridge: BridgeProp;
  useLedger: boolean;
}) {
  const [path, setPath] = useState("");
  const [year, setYear] = useState("");
  const [addShift, setAddShift] = useState(false);
  const [defaultShift, setDefaultShift] = useState("Day");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const params: Record<string, unknown> = {
        path,
        add_shift_column: addShift,
        default_shift: defaultShift,
        use_ledger: useLedger,
      };
      if (year) params.year = parseInt(year);
      await bridge.call("process_electrical", params);
      setResult("处理完成");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="电力消耗" icon={<ElectricalIcon />}>
      <PathInput value={path} onChange={setPath} placeholder="选择 Excel 文件" />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <StyledSelect
          value={year}
          onChange={setYear}
          placeholder="年份（可选）"
          options={yearOptions.map((y) => ({ label: `${y}年`, value: String(y) }))}
        />
      </div>
      <div className="mt-2 space-y-2">
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={addShift}
            onChange={(e) => setAddShift(e.target.checked)}
            className="rounded border-slate-300"
          />
          班次列
        </label>
        {addShift && (
          <div className="flex items-center gap-2 pl-5">
            <span className="text-xs text-slate-500">默认班次</span>
            <StyledSelect
              value={defaultShift}
              onChange={setDefaultShift}
              options={[
                { label: "Day", value: "Day" },
                { label: "Night", value: "Night" },
              ]}
            />
          </div>
        )}
      </div>
      <ProcessButton
        loading={loading}
        onClick={handleProcess}
        disabled={path === ""}
      />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
    </ModuleCard>
  );
}

// ═══════════════════════════════════════
// Worktime processing
// ═══════════════════════════════════════
function WorktimeCard({
  bridge,
  useLedger,
}: {
  bridge: BridgeProp;
  useLedger: boolean;
}) {
  const [path, setPath] = useState("");
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState(String(new Date().getMonth() + 1));
  const [useHeaderMapping, setUseHeaderMapping] = useState(false);
  const [headerMode, setHeaderMode] = useState("position");
  const [fuzzyMatch, setFuzzyMatch] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const params: Record<string, unknown> = {
        path,
        year: parseInt(year),
        month: parseInt(month),
        use_header_mapping: useHeaderMapping,
        use_ledger: useLedger,
      };
      if (useHeaderMapping) {
        params.header_mode = headerMode;
        params.fuzzy_match = fuzzyMatch;
      }
      await bridge.call("process_worktime", params);
      setResult("处理完成");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="工时处理" icon={<WorktimeIcon />}>
      <PathInput value={path} onChange={setPath} placeholder="选择 Excel 文件或文件夹" directory />
      {path === "" && <PathWarning />}
      <div className="mt-2 grid grid-cols-2 gap-2">
        <StyledSelect
          value={year}
          onChange={setYear}
          options={yearOptions.map((y) => ({ label: `${y}年`, value: String(y) }))}
        />
        <StyledSelect
          value={month}
          onChange={setMonth}
          options={monthOptions.map((m) => ({ label: `${m}月`, value: String(m) }))}
        />
      </div>
      <div className="mt-2 space-y-2">
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={useHeaderMapping}
            onChange={(e) => setUseHeaderMapping(e.target.checked)}
            className="rounded border-slate-300"
          />
          应用表头映射
        </label>
        {useHeaderMapping && (
          <div className="space-y-2 pl-5">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">映射模式</span>
              <ChipToggle
                value={headerMode}
                onChange={setHeaderMode}
                options={[
                  { label: "位置映射", value: "position" },
                  { label: "名称映射", value: "name" },
                ]}
              />
            </div>
            <label className="flex items-center gap-1.5 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={fuzzyMatch}
                onChange={(e) => setFuzzyMatch(e.target.checked)}
                className="rounded border-slate-300"
              />
              启用模糊匹配
            </label>
            <p className="text-xs text-slate-400 leading-relaxed">
              映射规则可在「用户配置 → 工作效率表头映射配置」中编辑
            </p>
          </div>
        )}
      </div>
      <ProcessButton
        loading={loading}
        onClick={handleProcess}
        disabled={path === ""}
      />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
    </ModuleCard>
  );
}

// ═══════════════════════════════════════
// Merge processing
// ═══════════════════════════════════════
function MergeCard({
  bridge,
  useLedger,
}: {
  bridge: BridgeProp;
  useLedger: boolean;
}) {
  const [folderPath, setFolderPath] = useState("");
  const [keyword, setKeyword] = useState("");
  const [stripTime, setStripTime] = useState(false);
  const [sortConfigs, setSortConfigs] = useState<SortConfig[]>([]);
  const [nextId, setNextId] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const addSortRow = () => {
    setSortConfigs((prev) => [...prev, { id: nextId, column: "", ascending: true }]);
    setNextId((n) => n + 1);
  };

  const removeSortRow = (id: number) => {
    setSortConfigs((prev) => prev.filter((r) => r.id !== id));
  };

  const updateSortRow = (id: number, field: Partial<SortConfig>) => {
    setSortConfigs((prev) =>
      prev.map((r) => (r.id === id ? { ...r, ...field } : r)),
    );
  };

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await bridge.call<{ output_file?: string }>("process_merge", {
        folder_path: folderPath,
        keyword,
        strip_time: stripTime,
        sort_configs: sortConfigs
          .filter((s) => s.column.trim() !== "")
          .map((s) => ({ column: s.column.trim(), ascending: s.ascending })),
        use_ledger: useLedger,
      });
      setResult(res.output_file ? `输出: ${res.output_file}` : "合并完成");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="文件合并" icon={<MergeIcon />}>
      <PathInput value={folderPath} onChange={setFolderPath} placeholder="选择文件夹" directory />
      {folderPath === "" && <PathWarning />}
      <div className="mt-2">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="文件名关键字"
          className={inputClass}
        />
      </div>
      <label className="mt-2 flex items-center gap-1.5 text-xs text-slate-600">
        <input
          type="checkbox"
          checked={stripTime}
          onChange={(e) => setStripTime(e.target.checked)}
          className="rounded border-slate-300"
        />
        去除时间部分
      </label>

      {/* Sort configuration */}
      <div className="mt-3 border-t border-slate-100 pt-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-slate-600">排序规则</span>
          <button
            onClick={addSortRow}
            className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-800 transition-colors"
          >
            <PlusIcon />
            添加排序规则
          </button>
        </div>
        {sortConfigs.length > 0 && (
          <div className="space-y-1.5">
            {sortConfigs.map((sc) => (
              <div
                key={sc.id}
                className="flex items-center gap-2 border border-slate-200 rounded-md px-2 h-9"
              >
                <input
                  type="text"
                  value={sc.column}
                  onChange={(e) =>
                    updateSortRow(sc.id, { column: e.target.value })
                  }
                  placeholder="列名"
                  className="flex-1 text-xs outline-none bg-transparent"
                />
                <select
                  value={sc.ascending ? "asc" : "desc"}
                  onChange={(e) =>
                    updateSortRow(sc.id, { ascending: e.target.value === "asc" })
                  }
                  className="text-xs border-0 bg-transparent outline-none text-slate-600 appearance-none pr-4"
                >
                  <option value="asc">升序</option>
                  <option value="desc">降序</option>
                </select>
                <button
                  onClick={() => removeSortRow(sc.id)}
                  className="shrink-0 p-1 text-slate-400 hover:text-red-600 transition-colors"
                  title="删除"
                >
                  <TrashIcon />
                </button>
              </div>
            ))}
          </div>
        )}
        {sortConfigs.length === 0 && (
          <p className="text-xs text-slate-400">暂无排序规则，数据按原始顺序合并</p>
        )}
      </div>

      <ProcessButton
        loading={loading}
        onClick={handleProcess}
        disabled={folderPath === "" || keyword === ""}
      />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
    </ModuleCard>
  );
}

// ═══════════════════════════════════════
// Data processing page
// ═══════════════════════════════════════
export function DataProcessingPage({ bridge }: { bridge: BridgeProp }) {
  const [useLedger, setUseLedger] = useState(false);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">数据处理</h2>
          <p className="text-sm text-slate-500">选择模块处理矿山数据</p>
        </div>
        <StyledToggle
          checked={useLedger}
          onChange={setUseLedger}
          label="启用台账匹配（设备+油品）"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <FuelCard bridge={bridge} useLedger={useLedger} />
        <ProductionCard bridge={bridge} useLedger={useLedger} />
        <ElectricalCard bridge={bridge} useLedger={useLedger} />
        <WorktimeCard bridge={bridge} useLedger={useLedger} />
        <MergeCard bridge={bridge} useLedger={useLedger} />
      </div>
    </div>
  );
}
