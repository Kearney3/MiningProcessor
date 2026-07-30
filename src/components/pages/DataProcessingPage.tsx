import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { ChevronDownIcon, PlayIcon, FolderIcon, FileIcon, PlusIcon, TrashIcon, CheckCircleIcon, XCircleIcon, AlertTriangleIcon, FuelIcon, ProductionIcon, ElectricalIcon, WorktimeIcon, MergeIcon, MaintenanceIcon } from "../../lib/icons";
import { PathInput, StyledToggle, ChipToggle } from "../../lib/ui-components";
import { inputClass, btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { useLastDirectory } from "../../hooks/useLastDirectory";
import { AnomalyPanel, type AnomalyConfig, DEFAULT_ANOMALY_CONFIG } from "../AnomalyPanel";

const currentYear = new Date().getFullYear();
const yearOptions = Array.from({ length: 61 }, (_, i) => currentYear - 30 + i);
const monthOptions = Array.from({ length: 12 }, (_, i) => i + 1);

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

/** Dual browse buttons for file or folder */
function PathInputDual({
  value,
  onChange,
  placeholder,
  defaultPath,
  onFileSelected,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const browseFile = async () => {
    const selected = await open({
      directory: false,
      multiple: false,
      defaultPath,
      filters: [{ name: "Excel", extensions: ["xlsx", "xls"] }],
    });
    if (selected) {
      const p = selected as string;
      onChange(p);
      onFileSelected?.(p);
    }
  };

  const browseFolder = async () => {
    const selected = await open({
      directory: true,
      multiple: false,
      defaultPath,
    });
    if (selected) {
      const p = selected as string;
      onChange(p);
      onFileSelected?.(p);
    }
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
      </button>
      <button onClick={browseFolder} className={btnSecondaryClass} title="选择文件夹">
        <FolderIcon />
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
  useEquipmentLedger,
  useOilLedger,
  skipHiddenRows,
  skipHiddenCols,
  anomaly,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  anomaly: AnomalyConfig;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { notify } = useToast();
  const [path, setPath] = useState("");
  const [year, setYear] = useState(String(currentYear));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterZeroEngineHours, setFilterZeroEngineHours] = useState(false);
  const [filterZeroWorkHours, setFilterZeroWorkHours] = useState(false);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const params: Record<string, unknown> = {
        path,
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        filter_zero_engine_hours: filterZeroEngineHours,
        filter_zero_work_hours: filterZeroWorkHours,
        anomaly_enabled: anomaly.enabled,
        anomaly_report: anomaly.report,
        anomaly_mode: anomaly.mode,
      };
      if (year) params.year = parseInt(year);
      const res = await bridge.call<{ output_file?: string }>(
        "process_fuel",
        params,
      );
      const msg = res.output_file ? `输出: ${res.output_file}` : "处理完成";
      setResult(msg);
      notify(`油耗处理完成`, "success");
    } catch (e) {
      setError(String(e));
      notify(`油耗处理失败: ${e}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="油耗处理" icon={<FuelIcon />}>
      <PathInput value={path} onChange={setPath} placeholder="选择 Excel 文件" defaultPath={defaultPath} onFileSelected={onFileSelected} />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <StyledSelect
          value={year}
          onChange={setYear}
          placeholder="年份（可选）"
          options={yearOptions.map((y) => ({ label: `${y}年`, value: String(y) }))}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroEngineHours} onChange={(e) => setFilterZeroEngineHours(e.target.checked)} className="rounded border-slate-300" />
          过滤零小时数
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroWorkHours} onChange={(e) => setFilterZeroWorkHours(e.target.checked)} className="rounded border-slate-300" />
          过滤零运行小时数
        </label>
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
  useEquipmentLedger,
  useOilLedger,
  skipHiddenRows,
  skipHiddenCols,
  anomaly,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  anomaly: AnomalyConfig;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { notify } = useToast();
  const [path, setPath] = useState("");
  const [autoDetect, setAutoDetect] = useState(true);
  const [rawStart, setRawStart] = useState("6");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<{
    total_files: number;
    success_files: number;
    failed_files: number;
    warnings: string[];
  } | null>(null);
  const [filterZeroHoursMeter, setFilterZeroHoursMeter] = useState(false);
  const [filterZeroKmMeter, setFilterZeroKmMeter] = useState(false);
  const [filterZeroRunHours, setFilterZeroRunHours] = useState(false);
  const [filterZeroRunKm, setFilterZeroRunKm] = useState(false);

  const handleAutoDetectChange = (v: boolean) => {
    setAutoDetect(v);
    if (v) setRawStart("6");
  };

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setSummary(null);
    try {
      const res = await bridge.call<{
        output_file?: string;
        summary?: { total_files: number; success_files: number; failed_files: number; warnings: string[] };
      }>("process_production", {
        path,
        raw_start: autoDetect ? -1 : parseInt(rawStart),
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        filter_zero_hours_meter: filterZeroHoursMeter,
        filter_zero_km_meter: filterZeroKmMeter,
        filter_zero_run_hours: filterZeroRunHours,
        filter_zero_run_km: filterZeroRunKm,
        anomaly_enabled: anomaly.enabled,
        anomaly_report: anomaly.report,
        anomaly_mode: anomaly.mode,
      });
      if (res.summary) {
        setSummary(res.summary);
      }
      setResult("处理完成");
      notify("生产数据处理完成", "success");
    } catch (e) {
      setError(String(e));
      notify(`生产数据处理失败: ${e}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="生产数据" icon={<ProductionIcon />}>
      <PathInputDual
        value={path}
        onChange={setPath}
        placeholder="选择 Excel 文件或文件夹"
        defaultPath={defaultPath}
        onFileSelected={onFileSelected}
      />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <StyledToggle
          checked={autoDetect}
          onChange={handleAutoDetectChange}
          label="自动识别表头"
        />
      </div>
      {!autoDetect && (
        <div className="mt-2 space-y-1">
          <label className="text-xs text-slate-500">表头起始行</label>
          <input
            type="number"
            value={rawStart}
            onChange={(e) => setRawStart(e.target.value)}
            placeholder="复合表头所在行号"
            className={inputClass}
          />
          <p className="text-xs text-slate-400">复合表头（矿车+矿石类型）所在的行号，默认6</p>
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroHoursMeter} onChange={(e) => setFilterZeroHoursMeter(e.target.checked)} className="rounded border-slate-300" />
          过滤零小时仪表
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroKmMeter} onChange={(e) => setFilterZeroKmMeter(e.target.checked)} className="rounded border-slate-300" />
          过滤零公里仪表
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroRunHours} onChange={(e) => setFilterZeroRunHours(e.target.checked)} className="rounded border-slate-300" />
          过滤零运行小时数
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroRunKm} onChange={(e) => setFilterZeroRunKm(e.target.checked)} className="rounded border-slate-300" />
          过滤零运行里程
        </label>
      </div>
      <ProcessButton
        loading={loading}
        onClick={handleProcess}
        disabled={path === ""}
      />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
      {summary && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-3 text-xs text-slate-600">
            <span>共 {summary.total_files} 个文件，成功 {summary.success_files}，失败 {summary.failed_files}</span>
          </div>
          {summary.warnings.length > 0 && summary.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 rounded-md px-2.5 py-1.5">
              <AlertTriangleIcon />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </ModuleCard>
  );
}

// ═══════════════════════════════════════
// Electrical consumption
// ═══════════════════════════════════════
function ElectricalCard({
  bridge,
  useEquipmentLedger,
  useOilLedger,
  skipHiddenRows,
  skipHiddenCols,
  anomaly,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  anomaly: AnomalyConfig;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { notify } = useToast();
  const [path, setPath] = useState("");
  const [year, setYear] = useState(String(currentYear));
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
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        anomaly_enabled: anomaly.enabled,
        anomaly_report: anomaly.report,
        anomaly_mode: anomaly.mode,
      };
      if (year) params.year = parseInt(year);
      await bridge.call("process_electrical", params);
      setResult("处理完成");
      notify("电力消耗处理完成", "success");
    } catch (e) {
      setError(String(e));
      notify(`电力消耗处理失败: ${e}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="电力消耗" icon={<ElectricalIcon />}>
      <PathInput value={path} onChange={setPath} placeholder="选择 Excel 文件" defaultPath={defaultPath} onFileSelected={onFileSelected} />
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
  useEquipmentLedger,
  useOilLedger,
  skipHiddenRows,
  skipHiddenCols,
  anomaly,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  anomaly: AnomalyConfig;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { notify } = useToast();
  const [path, setPath] = useState("");
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState(String(new Date().getMonth() + 1));
  const [useHeaderMapping, setUseHeaderMapping] = useState(false);
  const [headerMode, setHeaderMode] = useState("position");
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
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        anomaly_enabled: anomaly.enabled,
        anomaly_report: anomaly.report,
        anomaly_mode: anomaly.mode,
      };
      if (useHeaderMapping) {
        params.header_mode = headerMode;
      }
      await bridge.call("process_worktime", params);
      setResult("处理完成");
      notify("工时处理完成", "success");
    } catch (e) {
      setError(String(e));
      notify(`工时处理失败: ${e}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="工时处理" icon={<WorktimeIcon />}>
      <PathInputDual value={path} onChange={setPath} placeholder="选择 Excel 文件或文件夹" defaultPath={defaultPath} onFileSelected={onFileSelected} />
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
  useEquipmentLedger,
  useOilLedger,
  skipHiddenRows,
  skipHiddenCols,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { notify } = useToast();
  const [folderPath, setFolderPath] = useState("");
  const [keyword, setKeyword] = useState("");
  const [stripTime, setStripTime] = useState(false);
  const [tolerantHeader, setTolerantHeader] = useState(false);
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
        tolerant_header: tolerantHeader,
        sort_configs: sortConfigs
          .filter((s) => s.column.trim() !== "")
          .map((s) => ({ column: s.column.trim(), ascending: s.ascending })),
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
      });
      const msg = res.output_file ? `输出: ${res.output_file}` : "合并完成";
      setResult(msg);
      notify("文件合并完成", "success");
    } catch (e) {
      setError(String(e));
      notify(`文件合并失败: ${e}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="文件合并" icon={<MergeIcon />}>
      <PathInput value={folderPath} onChange={setFolderPath} placeholder="选择文件夹" directory defaultPath={defaultPath} onFileSelected={onFileSelected} />
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
      <label className="mt-1 flex items-center gap-1.5 text-xs text-slate-600">
        <input
          type="checkbox"
          checked={tolerantHeader}
          onChange={(e) => setTolerantHeader(e.target.checked)}
          className="rounded border-slate-300"
        />
        兼容表头
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
// Maintenance record processing
// ═══════════════════════════════════════
function MaintenanceCard({
  bridge,
  useEquipmentLedger,
  skipHiddenRows,
  skipHiddenCols,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { notify } = useToast();
  const [path, setPath] = useState("");
  const [splitByYear, setSplitByYear] = useState(false);
  const [detailsOnly, setDetailsOnly] = useState(false);
  const [useMlFallback, setUseMlFallback] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await bridge.call<{ output_file?: string; output_files?: string[] }>("process_maintenance", {
        path,
        use_equipment_ledger: useEquipmentLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        split_by_year: splitByYear,
        details_only: detailsOnly,
        use_ml_fallback: useMlFallback,
      });
      const msg = res.output_files
        ? `输出: ${res.output_files.length} 个文件`
        : res.output_file ? `输出: ${res.output_file}` : "处理完成";
      setResult(msg);
      notify("维修记录处理完成", "success");
    } catch (e) {
      setError(String(e));
      notify(`维修记录处理失败: ${e}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title="维修记录处理" icon={<MaintenanceIcon />}>
      <PathInputDual value={path} onChange={setPath} placeholder="选择出勤统计表文件或文件夹" defaultPath={defaultPath} onFileSelected={onFileSelected} />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <StyledToggle checked={splitByYear} onChange={setSplitByYear} label="按年份拆分输出" />
      </div>
      <div className="mt-2">
        <StyledToggle checked={detailsOnly} onChange={setDetailsOnly} label="仅导出明细" />
      </div>
      <div className="mt-2">
        <StyledToggle
          checked={useMlFallback}
          onChange={setUseMlFallback}
          label="启用机器学习辅助识别"
        />
        <p className="mt-1 pl-[42px] text-xs leading-5 text-slate-500">
          仅对规则仍判为“其他/待确认”的记录进行高置信度回填，不覆盖规则结果
        </p>
      </div>
      <ProcessButton loading={loading} onClick={handleProcess} disabled={path === ""} />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
    </ModuleCard>
  );
}

// ═══════════════════════════════════════
// Data processing page
// ═══════════════════════════════════════
export function DataProcessingPage({ bridge }: { bridge: BridgeProp }) {
  const [useEquipmentLedger, setUseEquipmentLedger] = useState(false);
  const [useOilLedger, setUseOilLedger] = useState(false);
  const [skipHiddenRows, setSkipHiddenRows] = useState(false);
  const [skipHiddenCols, setSkipHiddenCols] = useState(false);
  const [anomaly, setAnomaly] = useState<AnomalyConfig>(DEFAULT_ANOMALY_CONFIG);
  const { initialDir, saveDir } = useLastDirectory(bridge);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">数据处理</h2>
          <p className="text-sm text-slate-500">选择模块处理矿山数据</p>
        </div>
        <div className="flex items-center gap-4">
          <StyledToggle
            checked={useEquipmentLedger}
            onChange={setUseEquipmentLedger}
            label="设备台账匹配"
          />
          <StyledToggle
            checked={useOilLedger}
            onChange={setUseOilLedger}
            label="油品台账匹配"
          />
          <StyledToggle
            checked={skipHiddenRows}
            onChange={setSkipHiddenRows}
            label="跳过隐藏行"
          />
          <StyledToggle
            checked={skipHiddenCols}
            onChange={setSkipHiddenCols}
            label="跳过隐藏列"
          />
        </div>
      </div>

      <AnomalyPanel
        config={anomaly}
        onChange={setAnomaly}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <FuelCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} anomaly={anomaly} defaultPath={initialDir} onFileSelected={saveDir} />
        <ProductionCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} anomaly={anomaly} defaultPath={initialDir} onFileSelected={saveDir} />
        <ElectricalCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} anomaly={anomaly} defaultPath={initialDir} onFileSelected={saveDir} />
        <WorktimeCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} anomaly={anomaly} defaultPath={initialDir} onFileSelected={saveDir} />
        <MergeCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} defaultPath={initialDir} onFileSelected={saveDir} />
        <MaintenanceCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} defaultPath={initialDir} onFileSelected={saveDir} />
      </div>
    </div>
  );
}
