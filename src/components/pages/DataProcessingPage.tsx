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

/** Chevron down icon for selects */
const ChevronDownIcon = () => (
  <svg className="w-3.5 h-3.5 text-slate-400 pointer-events-none" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
  </svg>
);

/** Play icon for process buttons */
const PlayIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
  </svg>
);

const FolderIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
    <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
  </svg>
);

const FileIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
  </svg>
);

const PlusIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
  </svg>
);

const TrashIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
  </svg>
);

/** Check icon for success badges */
const CheckCircleIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
  </svg>
);

/** X icon for error badges */
const XCircleIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
  </svg>
);

/** Inline SVG module icons */
const FuelSvgIcon = () => (
  <svg className="w-5 h-5 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 22V6a2 2 0 012-2h6a2 2 0 012 2v16" />
    <path d="M13 10h2a2 2 0 012 2v2a2 2 0 002 2h0a2 2 0 002-2V9.83a2 2 0 00-.59-1.42L18 6" />
    <path d="M3 22h10" />
    <path d="M7 10V6" />
    <path d="M11 10V6" />
  </svg>
);

const ProductionSvgIcon = () => (
  <svg className="w-5 h-5 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="18" rx="1" />
    <rect x="14" y="8" width="7" height="13" rx="1" />
    <path d="M6 7h1" />
    <path d="M6 11h1" />
    <path d="M6 15h1" />
    <path d="M17 12h1" />
    <path d="M17 16h1" />
  </svg>
);

const ElectricalSvgIcon = () => (
  <svg className="w-5 h-5 text-yellow-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
  </svg>
);

const WorktimeSvgIcon = () => (
  <svg className="w-5 h-5 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

const MergeSvgIcon = () => (
  <svg className="w-5 h-5 text-purple-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="8" height="4" rx="1" />
    <rect x="2" y="13" width="8" height="4" rx="1" />
    <rect x="14" y="10" width="8" height="4" rx="1" />
    <path d="M10 9h2l2 2" />
    <path d="M10 17h2l2-2" />
  </svg>
);

/** Per-module accent border colors — subtle top accent instead of thick left border */
const accentMap: Record<string, string> = {
  fuel: "border-t-2 border-t-amber-400",
  production: "border-t-2 border-t-emerald-400",
  electrical: "border-t-2 border-t-yellow-400",
  worktime: "border-t-2 border-t-blue-400",
  merge: "border-t-2 border-t-purple-400",
};

function ModuleCard({
  title,
  icon,
  accent,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  accent: keyof typeof accentMap;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`bg-white rounded-xl border border-slate-200 ${accentMap[accent]} p-5 hover:shadow-md transition-shadow`}
    >
      <div className="flex items-center gap-2.5 mb-4">
        {icon}
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
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
        className={`input ${value === "" ? "border-amber-300 bg-amber-50/30" : ""}`}
      />
      <button
        onClick={browse}
        className="shrink-0 flex items-center gap-1 text-sm bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-2 rounded-lg transition-colors"
      >
        {directory ? <FolderIcon /> : <FileIcon />}
        浏览
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
        className={`input ${value === "" ? "border-amber-300 bg-amber-50/30" : ""}`}
      />
      <button
        onClick={browseFile}
        className="shrink-0 flex items-center gap-1 text-sm bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-2 rounded-lg transition-colors"
        title="选择文件"
      >
        <FileIcon />
        选文件
      </button>
      <button
        onClick={browseFolder}
        className="shrink-0 flex items-center gap-1 text-sm bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-2 rounded-lg transition-colors"
        title="选择文件夹"
      >
        <FolderIcon />
        选文件夹
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
        className="input appearance-none pr-8"
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
      <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
        <ChevronDownIcon />
      </div>
    </div>
  );
}

/** Styled toggle switch */
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
    <label className="flex items-center gap-2.5 cursor-pointer select-none group">
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-10 items-center rounded-full transition-colors ${
          checked ? "bg-emerald-500" : "bg-slate-200"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
            checked ? "translate-x-5" : "translate-x-1"
          }`}
        />
      </button>
      <span className="text-sm font-medium text-slate-700 group-hover:text-slate-900 transition-colors">
        {label}
      </span>
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
    <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden">
      {options.map((o, i) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`text-xs px-3 py-1.5 transition-colors ${
            value === o.value
              ? "bg-cyan-500 text-white"
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
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
      请先选择输入路径
    </div>
  );
}

/** Result success badge */
function SuccessBadge({ message }: { message: string }) {
  return (
    <div className="mt-3 flex items-center gap-2 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 animate-fade-in">
      <CheckCircleIcon />
      {message}
    </div>
  );
}

/** Result error badge */
function ErrorBadge({ message }: { message: string }) {
  return (
    <div className="mt-3 flex items-center gap-2 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 animate-fade-in">
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
  color = "cyan",
}: {
  loading: boolean;
  onClick: () => void;
  disabled?: boolean;
  color?: string;
}) {
  const colorClasses: Record<string, string> = {
    cyan: "bg-cyan-600 hover:bg-cyan-700",
    emerald: "bg-emerald-600 hover:bg-emerald-700",
    amber: "bg-amber-600 hover:bg-amber-700",
    blue: "bg-blue-600 hover:bg-blue-700",
    purple: "bg-purple-600 hover:bg-purple-700",
  };

  return (
    <button
      disabled={loading || disabled}
      onClick={onClick}
      className={`btn-primary mt-3 w-full flex items-center justify-center gap-2 ${
        loading || disabled
          ? "!bg-slate-100 !text-slate-400 cursor-not-allowed"
          : `${colorClasses[color] || colorClasses.cyan} text-white`
      }`}
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
    <ModuleCard title="油耗处理" icon={<FuelSvgIcon />} accent="fuel">
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
      <ProcessButton loading={loading} onClick={handleProcess} disabled={path === ""} color="amber" />
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
    <ModuleCard title="生产数据" icon={<ProductionSvgIcon />} accent="production">
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
          className="input"
        />
      </div>
      <ProcessButton
        loading={loading}
        onClick={handleProcess}
        disabled={path === ""}
        color="emerald"
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
    <ModuleCard title="电力消耗" icon={<ElectricalSvgIcon />} accent="electrical">
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
        color="amber"
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
    <ModuleCard title="工时处理" icon={<WorktimeSvgIcon />} accent="worktime">
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
            <p className="text-[11px] text-slate-400 leading-relaxed">
              映射规则可在「用户配置 → 工作效率表头映射配置」中编辑
            </p>
          </div>
        )}
      </div>
      <ProcessButton
        loading={loading}
        onClick={handleProcess}
        disabled={path === ""}
        color="blue"
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
    <ModuleCard title="文件合并" icon={<MergeSvgIcon />} accent="merge">
      <PathInput value={folderPath} onChange={setFolderPath} placeholder="选择文件夹" directory />
      {folderPath === "" && <PathWarning />}
      <div className="mt-2">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="文件名关键字"
          className="input"
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
            className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-700 transition-colors"
          >
            <PlusIcon />
            添加排序规则
          </button>
        </div>
        {sortConfigs.length > 0 && (
          <div className="space-y-2">
            {sortConfigs.map((sc, idx) => (
              <div
                key={sc.id}
                className={`flex items-center gap-2 rounded-lg px-2 py-1.5 ${
                  idx % 2 === 0 ? "bg-slate-50" : "bg-white"
                }`}
              >
                <input
                  type="text"
                  value={sc.column}
                  onChange={(e) =>
                    updateSortRow(sc.id, { column: e.target.value })
                  }
                  placeholder="列名"
                  className="input flex-1 text-xs !px-2.5 !py-1.5"
                />
                <select
                  value={sc.ascending ? "asc" : "desc"}
                  onChange={(e) =>
                    updateSortRow(sc.id, { ascending: e.target.value === "asc" })
                  }
                  className="input text-xs !px-2.5 !py-1.5 appearance-none pr-7"
                >
                  <option value="asc">升序</option>
                  <option value="desc">降序</option>
                </select>
                <button
                  onClick={() => removeSortRow(sc.id)}
                  className="shrink-0 p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="删除"
                >
                  <TrashIcon />
                </button>
              </div>
            ))}
          </div>
        )}
        {sortConfigs.length === 0 && (
          <p className="text-[11px] text-slate-400">暂无排序规则，数据按原始顺序合并</p>
        )}
      </div>

      <ProcessButton
        loading={loading}
        onClick={handleProcess}
        disabled={folderPath === "" || keyword === ""}
        color="purple"
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
          <h2 className="text-xl font-semibold text-slate-800">数据处理</h2>
          <p className="text-sm text-slate-500 mt-0.5">选择模块处理矿山数据</p>
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
