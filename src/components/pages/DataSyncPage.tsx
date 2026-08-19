import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { open, save } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import type { BridgeProp, SyncResult, SyncWarning } from "../../lib/types";
import { useToast } from "../Toast";
import {
  FolderIcon, FuelIcon, ProductionIcon, ElectricalIcon, WorktimeIcon,
  OperationIcon, GlobeIcon, DatabaseIcon, CheckIcon, MinusIcon,
  CheckCircleIcon, XCircleIcon, AlertTriangleIcon, DownloadIcon, PlayIcon,
} from "../../lib/icons";
import { ChipToggle } from "../../lib/ui-components";
import { inputClass, btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { DatePicker } from "../DatePicker";
import { AnomalyPanel, type AnomalyConfig, DEFAULT_ANOMALY_CONFIG } from "../AnomalyPanel";
import { localToday, localTodayString, localYesterdayString } from "../../lib/dateUtils";

// ═══════════════════════════════════════
// Constants
// ═══════════════════════════════════════

const ALL_TYPES = [
  { id: "fuel", labelKey: "fuelData", icon: <FuelIcon /> },
  { id: "production", labelKey: "productionData", icon: <ProductionIcon /> },
  { id: "electrical", labelKey: "electricalData", icon: <ElectricalIcon /> },
  { id: "work_efficiency", labelKey: "worktimeData", icon: <WorktimeIcon /> },
  { id: "operation", labelKey: "operationData", icon: <OperationIcon /> },
] as const;

// ═══════════════════════════════════════
// Data type checkbox component
// ═══════════════════════════════════════

function DataTypeCheckbox({
  label,
  icon,
  checked,
  onChange,
}: {
  label: string;
  icon: React.ReactNode;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer select-none py-1.5">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="rounded border-slate-300"
      />
      <span className="text-slate-500">{icon}</span>
      <span className="text-sm text-slate-700">{label}</span>
    </label>
  );
}

// ═══════════════════════════════════════
// Main page component
// ═══════════════════════════════════════

export function DataSyncPage({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const { t } = useTranslation();
  const typeLabel = (id: string) => t(`pages:DataSyncPage.ui.${ALL_TYPES.find((type) => type.id === id)?.labelKey ?? id}`);
  const [inputDir, setInputDir] = useState("");
  const [mode, setMode] = useState<"api" | "database">("api");
  const [conflictPolicy, setConflictPolicy] = useState<"SKIP" | "UPDATE" | "REJECT">("SKIP");
  const [dataTypes, setDataTypes] = useState<string[]>(ALL_TYPES.map((type) => type.id));
  const [dryRun, setDryRun] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 处理参数
  const currentDate = localToday();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth() + 1;
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState(String(currentMonth));
  const [headerRow, setHeaderRow] = useState("");

  // 日期范围
  const [dateStart, setDateStart] = useState(localYesterdayString());
  const [dateEnd, setDateEnd] = useState(localYesterdayString());
  const [applyHeaderMapping, setApplyHeaderMapping] = useState(true);
  const [headerMode, setHeaderMode] = useState("position");
  const [useEquipmentLedger, setUseEquipmentLedger] = useState(false);
  const [useOilLedger, setUseOilLedger] = useState(true);
  const [skipHiddenRows, setSkipHiddenRows] = useState(true);
  const [skipHiddenCols, setSkipHiddenCols] = useState(false);
  const [anomaly, setAnomaly] = useState<AnomalyConfig>(DEFAULT_ANOMALY_CONFIG);

  // 过滤开关
  const [filterZeroEngineHours, setFilterZeroEngineHours] = useState(true);
  const [filterZeroWorkHours, setFilterZeroWorkHours] = useState(false);
  const [filterZeroHoursMeter, setFilterZeroHoursMeter] = useState(true);
  const [filterZeroKmMeter, setFilterZeroKmMeter] = useState(false);
  const [filterZeroRunHours, setFilterZeroRunHours] = useState(false);
  const [filterZeroRunKm, setFilterZeroRunKm] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // 启动时从配置加载上次目录，不存在则清空
  useEffect(() => {
    bridge.call<{ path: string }>("get_last_directory", { key: "sync_last_input_dir" })
      .then((res) => {
        const saved = res.path;
        if (!saved) return;
        return bridge.call<{ exists: boolean }>("check_directory_exists", { path: saved })
          .then((r) => {
            if (r.exists) {
              setInputDir(saved);
            } else {
              bridge.call("save_last_directory", { key: "sync_last_input_dir", path: "" }).catch(() => {});
            }
          });
      })
      .catch(() => {});
  }, [bridge]);

  const allSelected = ALL_TYPES.length === dataTypes.length;
  const someSelected = dataTypes.length > 0 && !allSelected;

  const toggleSelectAll = () => {
    if (allSelected) {
      setDataTypes([]);
    } else {
      setDataTypes(ALL_TYPES.map((type) => type.id));
    }
  };

  const handleSync = async () => {
    const syncDir = inputDir.trim();
    if (!syncDir) {
      setError(t("pages:DataSyncPage.selectTheFolderContainingProcessedData"));
      notify(t("pages:DataSyncPage.selectTheFolderContainingProcessedData"), "error");
      return;
    }
    bridge.call("save_last_directory", { key: "sync_last_input_dir", path: syncDir }).catch(() => {});
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await bridge.call<SyncResult>("sync_minebase", {
        input_dir: syncDir,
        mode,
        conflict_policy: conflictPolicy,
        data_types: dataTypes,
        dry_run: dryRun,
        year: year ? Number(year) : undefined,
        month: month ? Number(month) : undefined,
        date_start: dateStart || undefined,
        date_end: dateEnd || undefined,
        apply_header_mapping: applyHeaderMapping,
        header_mode: applyHeaderMapping ? headerMode : undefined,
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        skip_hidden_rows: skipHiddenRows,
        skip_hidden_cols: skipHiddenCols,
        filter_zero_engine_hours: filterZeroEngineHours,
        filter_zero_work_hours: filterZeroWorkHours,
        filter_zero_hours_meter: filterZeroHoursMeter,
        filter_zero_km_meter: filterZeroKmMeter,
        filter_zero_run_hours: filterZeroRunHours,
        filter_zero_run_km: filterZeroRunKm,
        anomaly_enabled: anomaly.enabled,
        anomaly_report: anomaly.report,
        anomaly_mode: anomaly.mode,
      });
      setResult(res);
      const total = Object.values(res.results).reduce(
        (acc, r) => ({ success: acc.success + r.success, skipped: acc.skipped + r.skipped, failed: acc.failed + r.failed }),
        { success: 0, skipped: 0, failed: 0 },
      );
      if (total.failed > 0) {
        notify(t("pages:DataSyncPage.syncCompletedSucceededSkipFailed", { success: total.success, skipped: total.skipped, failed: total.failed }), "error");
      } else {
        notify(t("pages:DataSyncPage.syncCompletedSucceededSkip", { success: total.success, skipped: total.skipped }), "success");
      }
    } catch (e) {
      setError(String(e));
      notify(t("pages:DataSyncPage.syncFailed", { error: e }), "error");
    } finally {
      setLoading(false);
    }
  };

  const browse = async () => {
    const selected = await open({ directory: true, multiple: false });
    if (selected) {
      const dir = selected as string;
      setInputDir(dir);
      bridge.call("save_last_directory", { key: "sync_last_input_dir", path: dir }).catch(() => {});
    }
  };

  return (
    <div className="w-full space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">{t("pages:DataSyncPage.dataSync")}</h2>
        <p className="text-sm text-slate-500">{t("pages:DataSyncPage.dataprocessingdatadataSyncdataMinebase")}</p>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-5">
        {/* Path */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">{t("pages:DataSyncPage.dataDirectory")}</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={inputDir}
              onChange={(e) => setInputDir(e.target.value)}
              placeholder={t("pages:DataSyncPage.selectTheFolderContainingProcessedData")}
              className={`${inputClass} flex-1`}
            />
            <button onClick={browse} className={btnSecondaryClass} title={t("pages:DataSyncPage.selectFolder")}>
              <FolderIcon />
            </button>
          </div>
        </div>

        {/* Sync mode — restrained segmented control */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">{t("pages:DataSyncPage.syncMode")}</label>
          <div className="inline-flex rounded-md bg-slate-100 p-0.5 gap-0.5">
            {([
              { value: "api" as const, label: t("pages:DataSyncPage.apiMode"), desc: t("pages:DataSyncPage.httpPush"), icon: <GlobeIcon /> },
              { value: "database" as const, label: t("pages:DataSyncPage.databaseMode"), desc: t("pages:DataSyncPage.directDatabaseWrite"), icon: <DatabaseIcon /> },
            ]).map((m) => (
              <button
                key={m.value}
                onClick={() => setMode(m.value)}
                className={`flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-all ${
                  mode === m.value
                    ? "bg-white shadow-sm text-slate-800 font-medium"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                <span className={mode === m.value ? "text-slate-600" : "text-slate-400"}>{m.icon}</span>
                <span className="leading-tight">{m.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Conflict policy — segmented control */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">{t("pages:DataSyncPage.conflictPolicy")}</label>
          <div className="inline-flex rounded-md bg-slate-100 p-0.5 gap-0.5">
            {([
              { value: "SKIP" as const, label: t("pages:DataSyncPage.skipDuplicates") },
              { value: "UPDATE" as const, label: t("pages:DataSyncPage.overwriteExisting") },
              { value: "REJECT" as const, label: t("pages:DataSyncPage.rejectAll") },
            ]).map((p) => (
              <button
                key={p.value}
                onClick={() => setConflictPolicy(p.value)}
                className={`px-4 py-2 text-sm rounded-md transition-all ${
                  conflictPolicy === p.value
                    ? "bg-white shadow-sm text-slate-800 font-medium"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {conflictPolicy === "SKIP" && t("pages:DataSyncPage.skipDuplicateRecordsAndKeepExistingData")}
            {conflictPolicy === "UPDATE" && t("pages:DataSyncPage.overwriteExistingDataWhenDuplicateRecordsAreFound")}
            {conflictPolicy === "REJECT" && t("pages:DataSyncPage.rejectTheEntireBatchWhenDuplicateRecordsAreFound")}
          </p>
        </div>

        {/* Data type checkboxes */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-medium text-slate-500">{t("pages:DataSyncPage.dataType")}</label>
            <span className="flex items-center gap-2 text-sm text-slate-500 select-none">
              <button
                type="button"
                role="checkbox"
                aria-checked={allSelected ? "true" : someSelected ? "mixed" : "false"}
                onClick={toggleSelectAll}
                className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                  allSelected
                    ? "bg-slate-900 border-slate-900"
                    : someSelected
                      ? "bg-white border-slate-400"
                      : "bg-white border-slate-300 hover:border-slate-400"
                }`}
              >
                {allSelected && <CheckIcon className="w-3 h-3 text-white" />}
                {someSelected && <MinusIcon />}
              </button>
              {t("pages:DataSyncPage.ui.selectAll")}
            </span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {ALL_TYPES.map((type) => (
              <DataTypeCheckbox
                key={type.id}
                label={t(`pages:DataSyncPage.ui.${type.labelKey}`)}
                icon={type.icon}
                checked={dataTypes.includes(type.id)}
                onChange={(checked) => {
                  if (checked) {
                    setDataTypes((prev) => [...prev, type.id]);
                  } else {
                    setDataTypes((prev) => prev.filter((id) => id !== type.id));
                  }
                }}
              />
            ))}
          </div>
        </div>

        {/* Dry run toggle */}
        <div className="flex items-start gap-3">
          <button
            role="switch"
            aria-checked={dryRun}
            onClick={() => setDryRun(!dryRun)}
            className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors shrink-0 mt-0.5 ${
              dryRun ? "bg-blue-600" : "bg-slate-200"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                dryRun ? "translate-x-4" : "translate-x-0.5"
              }`}
            />
          </button>
          <div>
            <div className="text-sm text-slate-700">{t("pages:DataSyncPage.dryRun")}</div>
            <div className="text-xs text-slate-400 mt-0.5">{t("pages:DataSyncPage.previewOnlyDoNotPushToMinebase")}</div>
          </div>
        </div>

        {/* Processing params — year / month / header row */}
        <div className="border-t border-slate-100 pt-4">
          <label className="text-xs font-medium text-slate-500 mb-2 block">{t("pages:DataSyncPage.processingParameters")}</label>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">{t("pages:DataSyncPage.year")}</label>
              <select
                value={year}
                onChange={(e) => setYear(e.target.value)}
                className={`${inputClass} w-full h-9`}
              >
                {Array.from({ length: 61 }, (_, i) => currentYear - 30 + i).map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">{t("pages:DataSyncPage.month")}</label>
              <select
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                className={`${inputClass} w-full h-9`}
              >
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <option key={m} value={m}>{t("pages:DataProcessingPage.month", { m })}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">{t("pages:DataSyncPage.headerStartRow")}</label>
              <input
                type="number"
                value={headerRow}
                onChange={(e) => setHeaderRow(e.target.value)}
                placeholder={t("pages:DataSyncPage.autoDetect")}
                min="1"
                className={`${inputClass} w-full h-9`}
              />
            </div>
          </div>
        </div>

        {/* Date range filter */}
        <div className="border-t border-slate-100 pt-4">
          <label className="text-xs font-medium text-slate-500 mb-2 block">{t("pages:DataSyncPage.dateRangeFilter")}</label>
          <div className="flex items-end gap-3">
            <DatePicker
              label={t("pages:DataSyncPage.startDate")}
              value={dateStart}
              onChange={setDateStart}
              className="flex-1"
            />
            <DatePicker
              label={t("pages:DataSyncPage.endDate")}
              value={dateEnd}
              onChange={setDateEnd}
              className="flex-1"
            />
            <button
              type="button"
              onClick={() => { setDateStart(localYesterdayString()); setDateEnd(localYesterdayString()); }}
              className={btnSecondaryClass}
            >
              {t("pages:DataSyncPage.ui.yesterday")}
            </button>
            <button
              type="button"
              onClick={() => { setDateStart(""); setDateEnd(""); }}
              className={btnSecondaryClass}
            >
              {t("pages:DataSyncPage.ui.clear")}
            </button>
          </div>
        </div>

        {/* Sync options */}
        <div className="border-t border-slate-100 pt-4 space-y-3">
          <div>
            <p className="text-xs text-slate-400 mb-2">{t("pages:DataSyncPage.headerMapping")}</p>
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <button
                role="switch"
                aria-checked={applyHeaderMapping}
                onClick={() => setApplyHeaderMapping(!applyHeaderMapping)}
                className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
                  applyHeaderMapping ? "bg-blue-600" : "bg-slate-200"
                }`}
              >
                <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                  applyHeaderMapping ? "translate-x-4" : "translate-x-0.5"
                }`} />
              </button>
              <span className="text-sm text-slate-700">{t("pages:DataSyncPage.applyWorktimeHeaderMapping")}</span>
            </label>
            {applyHeaderMapping && (
              <div className="flex items-center gap-2 pl-10 mt-1.5">
                <span className="text-xs text-slate-500">{t("pages:DataSyncPage.mappingMode")}</span>
                <ChipToggle
                  value={headerMode}
                  onChange={setHeaderMode}
                  options={[
                    { label: t("pages:DataSyncPage.byPosition"), value: "position" },
                    { label: t("pages:DataSyncPage.byColumnName"), value: "name" },
                  ]}
                />
              </div>
            )}
          </div>
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs text-slate-400 mb-2">{t("pages:DataSyncPage.ledgerMatch")}</p>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <button
                  role="switch"
                  aria-checked={useEquipmentLedger}
                  onClick={() => setUseEquipmentLedger(!useEquipmentLedger)}
                  className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
                    useEquipmentLedger ? "bg-blue-600" : "bg-slate-200"
                  }`}
                >
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                    useEquipmentLedger ? "translate-x-4" : "translate-x-0.5"
                  }`} />
                </button>
                <span className="text-sm text-slate-700">{t("pages:DataSyncPage.equipmentLedgerMatch")}</span>
              </label>
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <button
                  role="switch"
                  aria-checked={useOilLedger}
                  onClick={() => setUseOilLedger(!useOilLedger)}
                  className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
                    useOilLedger ? "bg-blue-600" : "bg-slate-200"
                  }`}
                >
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                    useOilLedger ? "translate-x-4" : "translate-x-0.5"
                  }`} />
                </button>
                <span className="text-sm text-slate-700">{t("pages:DataSyncPage.oilLedgerMatch")}</span>
              </label>
            </div>
          </div>
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs text-slate-400 mb-2">{t("pages:DataSyncPage.excelOptions")}</p>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <button
                  role="switch"
                  aria-checked={skipHiddenRows}
                  onClick={() => setSkipHiddenRows(!skipHiddenRows)}
                  className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
                    skipHiddenRows ? "bg-blue-600" : "bg-slate-200"
                  }`}
                >
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                    skipHiddenRows ? "translate-x-4" : "translate-x-0.5"
                  }`} />
                </button>
                <span className="text-sm text-slate-700">{t("pages:DataSyncPage.skipHiddenRows")}</span>
              </label>
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <button
                  role="switch"
                  aria-checked={skipHiddenCols}
                  onClick={() => setSkipHiddenCols(!skipHiddenCols)}
                  className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
                    skipHiddenCols ? "bg-blue-600" : "bg-slate-200"
                  }`}
                >
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                    skipHiddenCols ? "translate-x-4" : "translate-x-0.5"
                  }`} />
                </button>
                <span className="text-sm text-slate-700">{t("pages:DataSyncPage.skipHiddenColumns")}</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced options — collapsible */}
      <div className="bg-white rounded-lg border border-slate-200">
        <button
          type="button"
          onClick={() => setAdvancedOpen(!advancedOpen)}
          className="w-full flex items-center justify-between px-4 py-3 text-xs font-medium text-slate-500 hover:bg-slate-50 transition-colors"
        >
          <span>{t("pages:DataSyncPage.advancedOptions")}</span>
          <svg
            className={`w-3.5 h-3.5 transition-transform ${advancedOpen ? "rotate-90" : ""}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
        {advancedOpen && (
          <div className="px-4 pb-4 space-y-4 border-t border-slate-100">
            {/* Anomaly detection */}
            <div className="pt-3">
              <AnomalyPanel config={anomaly} onChange={setAnomaly} embedded />
            </div>

            {/* Data filters */}
            <div className="border-t border-slate-100 pt-3">
              <p className="text-xs font-medium text-slate-500 mb-3">{t("pages:DataSyncPage.dataFilters")}</p>
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-slate-400 mb-2">{t("pages:DataSyncPage.fuelProcessing")}</p>
                  <div className="flex flex-wrap gap-x-6 gap-y-2">
                    {[
                      { checked: filterZeroEngineHours, onChange: setFilterZeroEngineHours, label: t("pages:DataSyncPage.filterZeroEngineHours") },
                      { checked: filterZeroWorkHours, onChange: setFilterZeroWorkHours, label: t("pages:DataSyncPage.filterZeroOperatingHours") },
                    ].map((item) => (
                      <label key={item.label} className="flex items-center gap-2.5 cursor-pointer select-none">
                        <button
                          role="switch"
                          aria-checked={item.checked}
                          onClick={() => item.onChange(!item.checked)}
                          className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
                            item.checked ? "bg-blue-600" : "bg-slate-200"
                          }`}
                        >
                          <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                            item.checked ? "translate-x-4" : "translate-x-0.5"
                          }`} />
                        </button>
                        <span className="text-sm text-slate-700">{item.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div className="border-t border-slate-100 pt-3">
                  <p className="text-xs text-slate-400 mb-2">{t("pages:DataSyncPage.productionData")}</p>
                  <div className="flex flex-wrap gap-x-6 gap-y-2">
                    {[
                      { checked: filterZeroHoursMeter, onChange: setFilterZeroHoursMeter, label: t("pages:DataSyncPage.filterZeroHoursMeter") },
                      { checked: filterZeroKmMeter, onChange: setFilterZeroKmMeter, label: t("pages:DataSyncPage.filterZeroKilometerMeter") },
                      { checked: filterZeroRunHours, onChange: setFilterZeroRunHours, label: t("pages:DataSyncPage.filterZeroOperatingHours") },
                      { checked: filterZeroRunKm, onChange: setFilterZeroRunKm, label: t("pages:DataSyncPage.filterZeroOperatingDistance") },
                    ].map((item) => (
                      <label key={item.label} className="flex items-center gap-2.5 cursor-pointer select-none">
                        <button
                          role="switch"
                          aria-checked={item.checked}
                          onClick={() => item.onChange(!item.checked)}
                          className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
                            item.checked ? "bg-blue-600" : "bg-slate-200"
                          }`}
                        >
                          <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                            item.checked ? "translate-x-4" : "translate-x-0.5"
                          }`} />
                        </button>
                        <span className="text-sm text-slate-700">{item.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={handleSync}
          disabled={!inputDir || loading || dataTypes.length === 0}
          className={`${btnPrimaryClass} flex items-center gap-2`}
        >
          {!loading && <PlayIcon />}
          {loading ? t("pages:DataSyncPage.syncing") : t("pages:DataSyncPage.startSync")}
        </button>
      </div>

      {/* Result / Error */}
      {result && (() => {
        const totals = Object.values(result.results).reduce(
          (acc, r) => ({
            success: acc.success + r.success,
            skipped: acc.skipped + r.skipped,
            failed: acc.failed + r.failed,
            warnings: acc.warnings + (r.warnings?.length ?? 0),
          }),
          { success: 0, skipped: 0, failed: 0, warnings: 0 },
        );
        const hasError = totals.failed > 0;
        return (
          <div className={`flex items-center gap-2 text-xs rounded-md px-2.5 py-1.5 ${
            hasError ? "text-red-700 bg-red-50" : "text-emerald-700 bg-emerald-50"
          }`}>
            {hasError ? <XCircleIcon /> : <CheckCircleIcon />}
            <span>{t("pages:DataSyncPage.success")} {totals.success}</span>
            {totals.skipped > 0 && <span>· {t("pages:DataSyncPage.skipped")} {totals.skipped}</span>}
            {totals.failed > 0 && <span>· {t("pages:DataSyncPage.failure")} {totals.failed}</span>}
            {totals.warnings > 0 && <span>· {t("pages:DataSyncPage.ui.anomalies")} {totals.warnings}</span>}
          </div>
        );
      })()}

      {/* Result table — zebra-striped with status badges */}
      {result && (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
            <h3 className="text-sm font-medium text-slate-700 flex items-center gap-2">
              <CheckCircleIcon />
              {t("pages:DataSyncPage.ui.syncResult")}
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left">
                <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider">{t("pages:DataSyncPage.dataType")}</th>
                <th className="py-2 text-xs font-medium text-slate-500 uppercase tracking-wider text-right">{t("pages:DataSyncPage.success")}</th>
                <th className="py-2 text-xs font-medium text-slate-500 uppercase tracking-wider text-right">{t("pages:DataSyncPage.skipped")}</th>
                <th className="py-2 pr-4 text-xs font-medium text-slate-500 uppercase tracking-wider text-right">{t("pages:DataSyncPage.failure")}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.results).map(([type, stats], idx) => {
                const hasFailure = stats.failed > 0;
                return (
                  <tr key={type} className={`h-9 border-b border-slate-100 hover:bg-slate-50 ${idx % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                    <td className="px-4 py-2 text-sm text-slate-700">
                      {typeLabel(type)}
                    </td>
                    <td className="py-2 text-right">
                      <span className="text-xs rounded-md px-2.5 py-1 text-emerald-700 bg-emerald-50">
                        {stats.success}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      <span className="text-xs text-slate-400">{stats.skipped}</span>
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {hasFailure ? (
                        <span className="text-xs rounded-md px-2.5 py-1 text-red-700 bg-red-50">
                          {stats.failed}
                        </span>
                      ) : (
                        <span className="text-xs rounded-md px-2.5 py-1 text-slate-700 bg-slate-50">
                          {stats.failed}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Dry run preview file card */}
      {result?.dry_run_file && (
        <div className="bg-white rounded-lg border border-cyan-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-cyan-100 bg-cyan-50 flex items-center justify-between">
            <h3 className="text-sm font-medium text-cyan-700 flex items-center gap-2">
              <CheckCircleIcon />
              {t("pages:DataSyncPage.ui.previewFileReady")}
            </h3>
            <button
              type="button"
              onClick={() => openPath(result.dry_run_file!)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-cyan-700 bg-cyan-100 hover:bg-cyan-200 rounded-md transition-colors"
              title={t("pages:DataSyncPage.openPreviewFile")}
            >
              <DownloadIcon />
              {t("pages:DataSyncPage.ui.openFile")}
            </button>
          </div>
          <div className="px-4 py-3">
            <p className="text-xs text-slate-500 font-mono break-all">{result.dry_run_file}</p>
            <p className="text-xs text-slate-400 mt-2">{t("pages:DataSyncPage.eachDataTypeIsSavedInASeparateSheetSoAllRecordsCanBeReviewedBeforeSyncing")}</p>
          </div>
        </div>
      )}

      {/* Warnings table */}
      {result && (() => {
        const allWarnings: { type: string; label: string; w: SyncWarning }[] = [];
        for (const [type, stats] of Object.entries(result.results)) {
          for (const w of stats.warnings ?? []) {
            allWarnings.push({ type, label: typeLabel(type), w });
          }
        }
        if (allWarnings.length === 0) return null;

        const handleExportWarnings = async () => {
          try {
            const today = localTodayString();
            const savePath = await save({
              defaultPath: t("pages:DataSyncPage.anomalyDetailsXlsx", { today }),
              filters: [{ name: "Excel", extensions: ["xlsx"] }],
            });
            if (!savePath) return;

            const rawWarnings = allWarnings.map((item) => ({
              data_type: item.type,
              row: item.w.row,
              field: item.w.field,
              value: item.w.value,
              message: item.w.message,
            }));
            const res = await bridge.call<{ output_file: string }>("export_sync_warnings", {
              warnings: rawWarnings,
              output_path: savePath,
            });
            notify(t("pages:DataSyncPage.anomalyRowsExportedTo", { path: res.output_file }), "success");
          } catch (e) {
            notify(t("pages:DataSyncPage.exportFailed", { error: e }), "error");
          }
        };

        return (
          <div className="bg-white rounded-lg border border-amber-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-amber-100 bg-amber-50 flex items-center justify-between">
              <h3 className="text-sm font-medium text-amber-700 flex items-center gap-2">
                <AlertTriangleIcon />
                {t("pages:DataSyncPage.anomalies")}
                <span className="text-xs text-amber-500">{t("pages:DataSyncPage.total", { count: allWarnings.length })}</span>
              </h3>
              <button
                type="button"
                onClick={handleExportWarnings}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-amber-700 bg-amber-100 hover:bg-amber-200 rounded-md transition-colors"
                title={t("pages:DataSyncPage.exportanomalyfileExcelFile")}
              >
                <DownloadIcon />
                {t("pages:DataSyncPage.ui.exportExcel")}
              </button>
            </div>
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0">
                  <tr className="bg-amber-50 text-left">
                    <th className="px-4 py-2 text-xs font-medium text-amber-600 uppercase tracking-wider">{t("pages:DataSyncPage.dataType")}</th>
                    <th className="py-2 text-xs font-medium text-amber-600 uppercase tracking-wider">{t("pages:DataSyncPage.row")}</th>
                    <th className="py-2 text-xs font-medium text-amber-600 uppercase tracking-wider">{t("pages:DataSyncPage.field")}</th>
                    <th className="py-2 text-xs font-medium text-amber-600 uppercase tracking-wider">{t("pages:DataSyncPage.originalValue")}</th>
                    <th className="py-2 pr-4 text-xs font-medium text-amber-600 uppercase tracking-wider">{t("pages:DataSyncPage.issue")}</th>
                  </tr>
                </thead>
                <tbody>
                  {allWarnings.map((item, idx) => (
                    <tr key={idx} className={`h-9 border-b border-slate-100 hover:bg-amber-50/50 ${idx % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                      <td className="px-4 py-2 text-sm text-slate-700">{item.label}</td>
                      <td className="py-2 text-sm text-slate-500">{item.w.row}</td>
                      <td className="py-2 text-sm text-slate-700">{item.w.field}</td>
                      <td className="py-2 text-sm text-red-600 font-mono">{item.w.value || t("pages:DataSyncPage.empty")}</td>
                      <td className="py-2 pr-4 text-sm text-slate-500">{item.w.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}

      {error && (
        <div className="flex items-start gap-2 text-xs text-red-700 bg-red-50 rounded-md px-2.5 py-1.5">
          <XCircleIcon />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
