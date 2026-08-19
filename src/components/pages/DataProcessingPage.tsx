import { useState, memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { open } from "@tauri-apps/plugin-dialog";
import type { AnomalyRecord, BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { ChevronDownIcon, PlayIcon, FolderIcon, FileIcon, PlusIcon, TrashIcon, CheckCircleIcon, XCircleIcon, AlertTriangleIcon, FuelIcon, TireIcon, ProductionIcon, ElectricalIcon, WorktimeIcon, MergeIcon, MaintenanceIcon } from "../../lib/icons";
import { PathInput, StyledToggle, ChipToggle } from "../../lib/ui-components";
import { inputClass, btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { useLastDirectory } from "../../hooks/useLastDirectory";
import { AnomalyPanel, type AnomalyConfig, DEFAULT_ANOMALY_CONFIG } from "../AnomalyPanel";
import { AnomalyResultsTable } from "../AnomalyResultsTable";
import { localToday } from "../../lib/dateUtils";

const currentYear = localToday().getFullYear();
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
  const { t } = useTranslation();
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
      <button onClick={browseFile} className={btnSecondaryClass} title={t("pages:DataProcessingPage.selectFile")}>
        <FileIcon />
      </button>
      <button onClick={browseFolder} className={btnSecondaryClass} title={t("pages:DataProcessingPage.selectFolder")}>
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
  const { t } = useTranslation();
  return (
    <div className="mt-1.5 flex items-center gap-1 text-xs text-amber-600">
      <AlertTriangleIcon />
      {t("pages:DataProcessingPage.ui.selectInputPath")}
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
  const { t } = useTranslation();
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
          {t("pages:DataProcessingPage.text")}
        </>
      ) : (
        t("pages:DataProcessingPage.startProcessing")
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
const FuelCard = memo(function FuelCard({
  bridge,
  useEquipmentLedger,
  useOilLedger,
  useModelLedger,
  skipHiddenRows,
  skipHiddenCols,
  anomaly,
  onAnomalies,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  useModelLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  anomaly: AnomalyConfig;
  onAnomalies: (records: AnomalyRecord[]) => void;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [path, setPath] = useState("");
  const [year, setYear] = useState(String(currentYear));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterZeroEngineHours, setFilterZeroEngineHours] = useState(true);
  const [filterZeroWorkHours, setFilterZeroWorkHours] = useState(false);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    onAnomalies([]);
    try {
      const params: Record<string, unknown> = {
        path,
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        use_model_ledger: useModelLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        filter_zero_engine_hours: filterZeroEngineHours,
        filter_zero_work_hours: filterZeroWorkHours,
        anomaly_enabled: anomaly.enabled,
        anomaly_report: anomaly.report,
        anomaly_mode: anomaly.mode,
      };
      if (year) params.year = parseInt(year);
      const res = await bridge.call<{ output_file?: string; anomalies?: AnomalyRecord[] }>(
        "process_fuel",
        params,
      );
      onAnomalies(res.anomalies ?? []);
      const msg = res.output_file ? t("pages:DataProcessingPage.output", { path: res.output_file }) : t("pages:DataProcessingPage.processingCompleted");
      setResult(msg);
      notify(t("pages:DataProcessingPage.fuelProcessingCompleted"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:DataProcessingPage.fuelProcessingFailed", { error: e }), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title={t("pages:DataProcessingPage.fuelProcessing")} icon={<FuelIcon />}>
      <PathInput value={path} onChange={setPath} placeholder={t("pages:DataProcessingPage.selectExcelFile")} defaultPath={defaultPath} onFileSelected={onFileSelected} />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <StyledSelect
          value={year}
          onChange={setYear}
          placeholder={t("pages:DataProcessingPage.yearOptional")}
          options={yearOptions.map((y) => ({ label: t("pages:DataProcessingPage.year", { y }), value: String(y) }))}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroEngineHours} onChange={(e) => setFilterZeroEngineHours(e.target.checked)} className="rounded border-slate-300" />
          {t("pages:DataProcessingPage.filterZeroEngineHours")}
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroWorkHours} onChange={(e) => setFilterZeroWorkHours(e.target.checked)} className="rounded border-slate-300" />
          {t("pages:DataProcessingPage.filterZeroWorkHours")}
        </label>
      </div>
      <ProcessButton loading={loading} onClick={handleProcess} disabled={path === ""} />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
    </ModuleCard>
  );
});

// ═══════════════════════════════════════
// Tire life processing
// ═══════════════════════════════════════
const TireCard = memo(function TireCard({
  bridge,
  useEquipmentLedger,
  useOilLedger,
  useModelLedger,
  skipHiddenRows,
  skipHiddenCols,
  anomaly,
  onAnomalies,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  useModelLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  anomaly: AnomalyConfig;
  onAnomalies: (records: AnomalyRecord[]) => void;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [path, setPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    onAnomalies([]);
    try {
      const res = await bridge.call<{ output_file?: string; anomalies?: AnomalyRecord[] }>(
        "process_tire",
        {
          path,
          use_equipment_ledger: useEquipmentLedger,
          use_oil_ledger: useOilLedger,
          use_model_ledger: useModelLedger,
          skip_hidden_rows: skipHiddenRows,
          skip_hidden_cols: skipHiddenCols,
          anomaly_enabled: anomaly.enabled,
          anomaly_report: anomaly.report,
          anomaly_mode: anomaly.mode,
        },
      );
      onAnomalies(res.anomalies ?? []);
      setResult(
        res.output_file
          ? t("pages:DataProcessingPage.output", { path: res.output_file })
          : t("pages:DataProcessingPage.processingCompleted"),
      );
      notify(t("pages:DataProcessingPage.tireProcessingCompleted"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:DataProcessingPage.tireProcessingFailed", { error: e }), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title={t("pages:DataProcessingPage.tireProcessing")} icon={<TireIcon />}>
      <PathInput
        value={path}
        onChange={setPath}
        placeholder={t("pages:DataProcessingPage.selectTireLifeFile")}
        fileExtensions={["xlsx"]}
        defaultPath={defaultPath}
        onFileSelected={onFileSelected}
      />
      {path === "" && <PathWarning />}
      <ProcessButton loading={loading} onClick={handleProcess} disabled={path === ""} />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
    </ModuleCard>
  );
});

// ═══════════════════════════════════════
// Production data
// ═══════════════════════════════════════
const ProductionCard = memo(function ProductionCard({
  bridge,
  useEquipmentLedger,
  useOilLedger,
  useModelLedger,
  skipHiddenRows,
  skipHiddenCols,
  anomaly,
  onAnomalies,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  useModelLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  anomaly: AnomalyConfig;
  onAnomalies: (records: AnomalyRecord[]) => void;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { t } = useTranslation();
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
  const [filterZeroHoursMeter, setFilterZeroHoursMeter] = useState(true);
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
    onAnomalies([]);
    try {
      const res = await bridge.call<{
        output_file?: string;
        summary?: { total_files: number; success_files: number; failed_files: number; warnings: string[] };
        anomalies?: AnomalyRecord[];
      }>("process_production", {
        path,
        raw_start: autoDetect ? -1 : parseInt(rawStart),
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        use_model_ledger: useModelLedger,
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
      onAnomalies(res.anomalies ?? []);
      setResult(t("pages:DataProcessingPage.processingCompleted"));
      notify(t("pages:DataProcessingPage.productionProcessingCompleted"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:DataProcessingPage.productionProcessingFailed", { error: e }), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title={t("pages:DataProcessingPage.productionData")} icon={<ProductionIcon />}>
      <PathInputDual
        value={path}
        onChange={setPath}
        placeholder={t("pages:DataProcessingPage.selectExcelFileOrFolder")}
        defaultPath={defaultPath}
        onFileSelected={onFileSelected}
      />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <StyledToggle
          checked={autoDetect}
          onChange={handleAutoDetectChange}
          label={t("pages:DataProcessingPage.autoDetectHeader")}
        />
      </div>
      {!autoDetect && (
        <div className="mt-2 space-y-1">
          <label className="text-xs text-slate-500">{t("pages:DataProcessingPage.headerStartRow")}</label>
          <input
            type="number"
            value={rawStart}
            onChange={(e) => setRawStart(e.target.value)}
            placeholder={t("pages:DataProcessingPage.compositeHeaderRow")}
            className={inputClass}
          />
          <p className="text-xs text-slate-400">{t("pages:DataProcessingPage.compositeHeaderRowTruckOreTypeDefault6")}</p>
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroHoursMeter} onChange={(e) => setFilterZeroHoursMeter(e.target.checked)} className="rounded border-slate-300" />
          {t("pages:DataProcessingPage.filterZeroHoursMeter")}
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroKmMeter} onChange={(e) => setFilterZeroKmMeter(e.target.checked)} className="rounded border-slate-300" />
          {t("pages:DataProcessingPage.filterZeroKmMeter")}
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroRunHours} onChange={(e) => setFilterZeroRunHours(e.target.checked)} className="rounded border-slate-300" />
          {t("pages:DataProcessingPage.filterZeroWorkHours")}
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={filterZeroRunKm} onChange={(e) => setFilterZeroRunKm(e.target.checked)} className="rounded border-slate-300" />
          {t("pages:DataProcessingPage.filterZeroRunKm")}
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
            <span>{t("pages:DataProcessingPage.ui.fileSummary", { total: summary.total_files, success: summary.success_files, failed: summary.failed_files })}</span>
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
});

// ═══════════════════════════════════════
// Electrical consumption
// ═══════════════════════════════════════
const ElectricalCard = memo(function ElectricalCard({
  bridge,
  useEquipmentLedger,
  useOilLedger,
  useModelLedger,
  skipHiddenRows,
  skipHiddenCols,
  anomaly,
  onAnomalies,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  useModelLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  anomaly: AnomalyConfig;
  onAnomalies: (records: AnomalyRecord[]) => void;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { t } = useTranslation();
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
    onAnomalies([]);
    try {
      const params: Record<string, unknown> = {
        path,
        add_shift_column: addShift,
        default_shift: defaultShift,
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        use_model_ledger: useModelLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        anomaly_enabled: anomaly.enabled,
        anomaly_report: anomaly.report,
        anomaly_mode: anomaly.mode,
      };
      if (year) params.year = parseInt(year);
      const res = await bridge.call<{ anomalies?: AnomalyRecord[] }>("process_electrical", params);
      onAnomalies(res.anomalies ?? []);
      setResult(t("pages:DataProcessingPage.processingCompleted"));
      notify(t("pages:DataProcessingPage.electricalProcessingCompleted"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:DataProcessingPage.electricalProcessingFailed", { error: e }), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title={t("pages:DataProcessingPage.electricalConsumption")} icon={<ElectricalIcon />}>
      <PathInput value={path} onChange={setPath} placeholder={t("pages:DataProcessingPage.selectExcelFile")} defaultPath={defaultPath} onFileSelected={onFileSelected} />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <StyledSelect
          value={year}
          onChange={setYear}
          placeholder={t("pages:DataProcessingPage.yearOptional")}
          options={yearOptions.map((y) => ({ label: t("pages:DataProcessingPage.year", { y }), value: String(y) }))}
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
          {t("pages:DataProcessingPage.shiftColumn")}
        </label>
        {addShift && (
          <div className="flex items-center gap-2 pl-5">
            <span className="text-xs text-slate-500">{t("pages:DataProcessingPage.defaultShift")}</span>
            <StyledSelect
              value={defaultShift}
              onChange={setDefaultShift}
              options={[
                { label: t("common:dayShift"), value: "Day" },
                { label: t("common:nightShift"), value: "Night" },
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
});

// ═══════════════════════════════════════
// Worktime processing
// ═══════════════════════════════════════
const WorktimeCard = memo(function WorktimeCard({
  bridge,
  useEquipmentLedger,
  useOilLedger,
  useModelLedger,
  skipHiddenRows,
  skipHiddenCols,
  anomaly,
  onAnomalies,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  useModelLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  anomaly: AnomalyConfig;
  onAnomalies: (records: AnomalyRecord[]) => void;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [path, setPath] = useState("");
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState(String(localToday().getMonth() + 1));
  const [useHeaderMapping, setUseHeaderMapping] = useState(false);
  const [headerMode, setHeaderMode] = useState("position");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProcess = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    onAnomalies([]);
    try {
      const params: Record<string, unknown> = {
        path,
        year: parseInt(year),
        month: parseInt(month),
        use_header_mapping: useHeaderMapping,
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        use_model_ledger: useModelLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        anomaly_enabled: anomaly.enabled,
        anomaly_report: anomaly.report,
        anomaly_mode: anomaly.mode,
      };
      if (useHeaderMapping) {
        params.header_mode = headerMode;
      }
      const res = await bridge.call<{ anomalies?: AnomalyRecord[] }>("process_worktime", params);
      onAnomalies(res.anomalies ?? []);
      setResult(t("pages:DataProcessingPage.processingCompleted"));
      notify(t("pages:DataProcessingPage.worktimeProcessingCompleted"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:DataProcessingPage.worktimeProcessingFailed", { error: e }), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title={t("pages:DataProcessingPage.worktimeProcessing")} icon={<WorktimeIcon />}>
      <PathInputDual value={path} onChange={setPath} placeholder={t("pages:DataProcessingPage.selectExcelFileOrFolder")} defaultPath={defaultPath} onFileSelected={onFileSelected} />
      {path === "" && <PathWarning />}
      <div className="mt-2 grid grid-cols-2 gap-2">
        <StyledSelect
          value={year}
          onChange={setYear}
          options={yearOptions.map((y) => ({ label: t("pages:DataProcessingPage.year", { y }), value: String(y) }))}
        />
        <StyledSelect
          value={month}
          onChange={setMonth}
          options={monthOptions.map((m) => ({ label: t("pages:DataProcessingPage.month", { m }), value: String(m) }))}
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
          {t("pages:DataProcessingPage.applyHeaderMapping")}
        </label>
        {useHeaderMapping && (
          <div className="space-y-2 pl-5">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">{t("pages:DataProcessingPage.mappingMode")}</span>
              <ChipToggle
                value={headerMode}
                onChange={setHeaderMode}
                options={[
                  { label: t("pages:DataProcessingPage.positionMapping"), value: "position" },
                  { label: t("pages:DataProcessingPage.nameMapping"), value: "name" },
                ]}
              />
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              {t("pages:DataProcessingPage.ui.headerMappingHint")}
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
});

// ═══════════════════════════════════════
// Merge processing
// ═══════════════════════════════════════
const MergeCard = memo(function MergeCard({
  bridge,
  useEquipmentLedger,
  useOilLedger,
  useModelLedger,
  skipHiddenRows,
  skipHiddenCols,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useOilLedger: boolean;
  useModelLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [folderPath, setFolderPath] = useState("");
  const [keyword, setKeyword] = useState("");
  const [stripTime, setStripTime] = useState(false);
  const [tolerantHeader, setTolerantHeader] = useState(false);
  const [dedup, setDedup] = useState(false);
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
        dedup,
        sort_configs: sortConfigs
          .filter((s) => s.column.trim() !== "")
          .map((s) => ({ column: s.column.trim(), ascending: s.ascending })),
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        use_model_ledger: useModelLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
      });
      const msg = res.output_file ? t("pages:DataProcessingPage.output", { path: res.output_file }) : t("pages:DataProcessingPage.mergeComplete");
      setResult(msg);
      notify(t("pages:DataProcessingPage.fileMergeCompleted"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:DataProcessingPage.fileMergeFailed", { error: e }), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title={t("pages:DataProcessingPage.fileMerge")} icon={<MergeIcon />}>
      <PathInput value={folderPath} onChange={setFolderPath} placeholder={t("pages:DataProcessingPage.selectFolder")} directory defaultPath={defaultPath} onFileSelected={onFileSelected} />
      {folderPath === "" && <PathWarning />}
      <div className="mt-2">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder={t("pages:DataProcessingPage.filenameKeyword")}
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
        {t("pages:DataProcessingPage.stripTimePart")}
      </label>
      <label className="mt-1 flex items-center gap-1.5 text-xs text-slate-600">
        <input
          type="checkbox"
          checked={tolerantHeader}
          onChange={(e) => setTolerantHeader(e.target.checked)}
          className="rounded border-slate-300"
        />
        {t("pages:DataProcessingPage.tolerantHeader")}
      </label>
      <label className="mt-1 flex items-center gap-1.5 text-xs text-slate-600">
        <input
          type="checkbox"
          checked={dedup}
          onChange={(e) => setDedup(e.target.checked)}
          className="rounded border-slate-300"
        />
        {t("pages:DataProcessingPage.removeDuplicates")}
      </label>

      {/* Sort configuration */}
      <div className="mt-3 border-t border-slate-100 pt-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-slate-600">{t("pages:DataProcessingPage.sortRules")}</span>
          <button
            onClick={addSortRow}
            className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-800 transition-colors"
          >
            <PlusIcon />
            {t("pages:DataProcessingPage.ui.addSortRule")}
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
                  placeholder={t("pages:DataProcessingPage.columnName")}
                  className="flex-1 text-xs outline-none bg-transparent"
                />
                <select
                  value={sc.ascending ? "asc" : "desc"}
                  onChange={(e) =>
                    updateSortRow(sc.id, { ascending: e.target.value === "asc" })
                  }
                  className="text-xs border-0 bg-transparent outline-none text-slate-600 appearance-none pr-4"
                >
                  <option value="asc">{t("pages:DataProcessingPage.asc")}</option>
                  <option value="desc">{t("pages:DataProcessingPage.desc")}</option>
                </select>
                <button
                  onClick={() => removeSortRow(sc.id)}
                  className="shrink-0 p-1 text-slate-400 hover:text-red-600 transition-colors"
                  title={t("pages:DataProcessingPage.delete")}
                >
                  <TrashIcon />
                </button>
              </div>
            ))}
          </div>
        )}
        {sortConfigs.length === 0 && (
          <p className="text-xs text-slate-400">{t("pages:DataProcessingPage.noSortRulesMergeDataInOriginalOrder")}</p>
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
});

// ═══════════════════════════════════════
// Maintenance record processing
// ═══════════════════════════════════════
const MaintenanceCard = memo(function MaintenanceCard({
  bridge,
  useEquipmentLedger,
  useModelLedger,
  skipHiddenRows,
  skipHiddenCols,
  defaultPath,
  onFileSelected,
}: {
  bridge: BridgeProp;
  useEquipmentLedger: boolean;
  useModelLedger: boolean;
  skipHiddenRows: boolean;
  skipHiddenCols: boolean;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { t } = useTranslation();
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
        use_model_ledger: useModelLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        split_by_year: splitByYear,
        details_only: detailsOnly,
        use_ml_fallback: useMlFallback,
      });
      const msg = res.output_files
        ? t("pages:DataProcessingPage.outputItemsfile", { count: res.output_files.length })
        : res.output_file ? t("pages:DataProcessingPage.output", { path: res.output_file }) : t("pages:DataProcessingPage.processingCompleted");
      setResult(msg);
      notify(t("pages:DataProcessingPage.maintenanceProcessingCompleted"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:DataProcessingPage.maintenanceProcessingFailed", { error: e }), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModuleCard title={t("pages:DataProcessingPage.maintenanceRecords")} icon={<MaintenanceIcon />}>
      <PathInputDual value={path} onChange={setPath} placeholder={t("pages:DataProcessingPage.selectAttendanceReportFileOrFolder")} defaultPath={defaultPath} onFileSelected={onFileSelected} />
      {path === "" && <PathWarning />}
      <div className="mt-2">
        <StyledToggle checked={splitByYear} onChange={setSplitByYear} label={t("pages:DataProcessingPage.splitByYear")} />
      </div>
      <div className="mt-2">
        <StyledToggle checked={detailsOnly} onChange={setDetailsOnly} label={t("pages:DataProcessingPage.detailsOnly")} />
      </div>
      <div className="mt-2">
        <StyledToggle
          checked={useMlFallback}
          onChange={setUseMlFallback}
          label={t("pages:DataProcessingPage.enableMlAssistedClassification")}
        />
        <p className="mt-1 pl-[42px] text-xs leading-5 text-slate-500">
          {t("pages:DataProcessingPage.ui.mlFallbackHint")}
        </p>
      </div>
      <ProcessButton loading={loading} onClick={handleProcess} disabled={path === ""} />
      {result && <SuccessBadge message={result} />}
      {error && <ErrorBadge message={error} />}
    </ModuleCard>
  );
});

// ═══════════════════════════════════════
// Data processing page
// ═══════════════════════════════════════
export function DataProcessingPage({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();
  const [useEquipmentLedger, setUseEquipmentLedger] = useState(false);
  const [useOilLedger, setUseOilLedger] = useState(false);
  const [useModelLedger, setUseModelLedger] = useState(false);
  const [skipHiddenRows, setSkipHiddenRows] = useState(false);
  const [skipHiddenCols, setSkipHiddenCols] = useState(false);
  const [anomaly, setAnomaly] = useState<AnomalyConfig>(DEFAULT_ANOMALY_CONFIG);
  const [anomalies, setAnomalies] = useState<AnomalyRecord[]>([]);
  const { initialDir, saveDir } = useLastDirectory(bridge);
  const anomalyConfig = useMemo(() => anomaly, [anomaly]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">{t("pages:DataProcessingPage.dataProcessing")}</h2>
          <p className="text-sm text-slate-500">{t("pages:DataProcessingPage.selectAModuleToProcessMiningData")}</p>
        </div>
        <div className="flex items-center gap-4">
          <StyledToggle
            checked={useEquipmentLedger}
            onChange={setUseEquipmentLedger}
            label={t("pages:DataProcessingPage.equipmentLedgerMatch")}
          />
          <StyledToggle
            checked={useOilLedger}
            onChange={setUseOilLedger}
            label={t("pages:DataProcessingPage.oilLedgerMatch")}
          />
          <StyledToggle
            checked={useModelLedger}
            onChange={setUseModelLedger}
            label={t("pages:DataProcessingPage.modelLedgerMatch")}
          />
          <StyledToggle
            checked={skipHiddenRows}
            onChange={setSkipHiddenRows}
            label={t("pages:DataProcessingPage.skipHiddenRows")}
          />
          <StyledToggle
            checked={skipHiddenCols}
            onChange={setSkipHiddenCols}
            label={t("pages:DataProcessingPage.skipHiddenColumns")}
          />
        </div>
      </div>

      <AnomalyPanel
        config={anomaly}
        onChange={setAnomaly}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <FuelCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} useModelLedger={useModelLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} anomaly={anomalyConfig} onAnomalies={setAnomalies} defaultPath={initialDir} onFileSelected={saveDir} />
        <ProductionCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} useModelLedger={useModelLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} anomaly={anomalyConfig} onAnomalies={setAnomalies} defaultPath={initialDir} onFileSelected={saveDir} />
        <ElectricalCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} useModelLedger={useModelLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} anomaly={anomalyConfig} onAnomalies={setAnomalies} defaultPath={initialDir} onFileSelected={saveDir} />
        <WorktimeCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} useModelLedger={useModelLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} anomaly={anomalyConfig} onAnomalies={setAnomalies} defaultPath={initialDir} onFileSelected={saveDir} />
        <MergeCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} useModelLedger={useModelLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} defaultPath={initialDir} onFileSelected={saveDir} />
        <MaintenanceCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useModelLedger={useModelLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} defaultPath={initialDir} onFileSelected={saveDir} />
        <TireCard bridge={bridge} useEquipmentLedger={useEquipmentLedger} useOilLedger={useOilLedger} useModelLedger={useModelLedger} skipHiddenRows={skipHiddenRows} skipHiddenCols={skipHiddenCols} anomaly={anomalyConfig} onAnomalies={setAnomalies} defaultPath={initialDir} onFileSelected={saveDir} />
      </div>

      <AnomalyResultsTable records={anomalies} />
    </div>
  );
}
