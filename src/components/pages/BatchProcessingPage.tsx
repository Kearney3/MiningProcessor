import { useState, useMemo, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { open } from "@tauri-apps/plugin-dialog";
import type { BridgeProp, BatchProgress, ScanResult, BatchSummary, AnomalyRecord } from "../../lib/types";
import { useToast } from "../Toast";
import {
  FolderIcon, SearchIcon, SettingsIcon, CalendarIcon, RulerIcon,
  PlayIcon, CheckIcon, XIcon, StopCircleIcon,
  CheckCircleIcon, XCircleIcon, AlertTriangleIcon,
  FuelIcon, ProductionIcon, ElectricalIcon, WorktimeIcon, MergeIcon,
  QuestionIcon, FilterIcon,
} from "../../lib/icons";
import { ChipToggle, StyledToggle as Toggle, ConfirmDialog, Collapsible, SectionDivider } from "../../lib/ui-components";
import { inputClass, btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { useLastDirectory } from "../../hooks/useLastDirectory";
import { AnomalyPanel, type AnomalyConfig, DEFAULT_ANOMALY_CONFIG } from "../AnomalyPanel";
import { AnomalyResultsTable } from "../AnomalyResultsTable";
import { addLocalDays, formatLocalDate, localToday } from "../../lib/dateUtils";

// ═══════════════════════════════════════
// Types
// ═══════════════════════════════════════

interface BatchBridgeProp extends BridgeProp {
  cancel: () => Promise<void>;
  progress: BatchProgress | null;
  setProgress: (p: BatchProgress | null) => void;
}

type TableMergeMode = "split" | "merge" | "table_merge";
type BaseTableType = "fuel" | "worktime";

// ═══════════════════════════════════════
// Constants
// ═══════════════════════════════════════

const dataTypeConfig: Record<string, { icon: React.ReactNode; labelKey: string }> = {
  油耗:       { icon: <FuelIcon />,         labelKey: "fuel" },
  生产:       { icon: <ProductionIcon />,   labelKey: "production" },
  电力:       { icon: <ElectricalIcon />,   labelKey: "electrical" },
  工时:       { icon: <WorktimeIcon />,     labelKey: "worktime" },
  production: { icon: <ProductionIcon />,   labelKey: "production" },
  fuel:       { icon: <FuelIcon />,         labelKey: "fuel" },
  electrical: { icon: <ElectricalIcon />,   labelKey: "electrical" },
  worktime:   { icon: <WorktimeIcon />,     labelKey: "worktime" },
  merge:      { icon: <MergeIcon />,        labelKey: "merge" },
};

function getTypeConfig(type: string) {
  return dataTypeConfig[type] ?? { icon: <QuestionIcon />, labelKey: "" };
}

function formatToday(): string {
  return formatLocalDate(localToday());
}

function shiftDate(dateStr: string, days: number): string {
  const parts = dateStr.split("-").map(Number);
  const date = new Date(parts[0], parts[1] - 1, parts[2]);
  return formatLocalDate(addLocalDays(date, days));
}

// ═══════════════════════════════════════
// Progress bar — restrained
// ═══════════════════════════════════════

function ProgressBar({ percent, stage, detail }: { percent: number; stage: string; detail: string }) {
  const pct = Math.round(percent * 100);
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-slate-500 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm font-medium text-slate-700">{stage}</span>
        </div>
        <span className="text-xs font-mono text-slate-500">{pct}%</span>
      </div>
      <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-1.5 rounded-full bg-blue-600 transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      {detail && <p className="mt-2 text-xs text-slate-400 truncate">{detail}</p>}
    </div>
  );
}

// ═══════════════════════════════════════
// Main page component
// ═══════════════════════════════════════

export function BatchProcessingPage({ bridge }: { bridge: BatchBridgeProp }) {
  // -- Path & scan --
  const { notify } = useToast();
  const { t } = useTranslation();
  const typeLabel = (type: string) => {
    const config = getTypeConfig(type);
    return config.labelKey ? t(`pages:BatchProcessingPage.ui.type.${config.labelKey}`) : type;
  };
  const { initialDir, saveDir } = useLastDirectory(bridge);
  const [folderPath, setFolderPath] = useState("");
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState(false);

  // -- Processing --
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<BatchSummary | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyRecord[]>([]);

  // -- Confirmation dialog --
  const [showConfirm, setShowConfirm] = useState(false);

  // -- Basic params --
  const [year, setYear] = useState(localToday().getFullYear().toString());
  const [month, setMonth] = useState((localToday().getMonth() + 1).toString());
  const [rawStart, setRawStart] = useState("-1");

  // -- Output mode --
  const [tableMergeMode, setTableMergeMode] = useState<TableMergeMode>("merge");
  const [baseTableType, setBaseTableType] = useState<BaseTableType>("fuel");

  // -- Ledger --
  const [useEquipmentLedger, setUseEquipmentLedger] = useState(false);
  const [useOilLedger, setUseOilLedger] = useState(false);
  const [useModelLedger, setUseModelLedger] = useState(false);
  const [skipHiddenRows, setSkipHiddenRows] = useState(false);
  const [skipHiddenCols, setSkipHiddenCols] = useState(false);
  const [filterZeroEngineHours, setFilterZeroEngineHours] = useState(true);
  const [filterZeroWorkHours, setFilterZeroWorkHours] = useState(false);
  const [filterZeroHoursMeter, setFilterZeroHoursMeter] = useState(true);
  const [filterZeroKmMeter, setFilterZeroKmMeter] = useState(true);
  const [filterZeroRunHours, setFilterZeroRunHours] = useState(false);
  const [filterZeroRunKm, setFilterZeroRunKm] = useState(false);
  const [anomaly, setAnomaly] = useState<AnomalyConfig>(DEFAULT_ANOMALY_CONFIG);

  // -- Date filter --
  const [dateFilterEnabled, setDateFilterEnabled] = useState(false);
  const [filterDate, setFilterDate] = useState(formatToday());

  // -- Header mapping --
  const [useHeaderMapping, setUseHeaderMapping] = useState(false);
  const [headerMode, setHeaderMode] = useState("position");

  // ── Derived ──
  const hasMissing = useMemo(() => scanResult && scanResult.missing.length > 0, [scanResult]);

  // ── Handlers ──
  const browse = async () => {
    const selected = await open({ directory: true, multiple: false, defaultPath: initialDir || undefined });
    if (selected) {
      const dir = selected as string;
      setFolderPath(dir);
      setScanResult(null);
      saveDir(dir);
    }
  };

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setScanResult(null);
    try {
      const params: Record<string, unknown> = { folder_path: folderPath };
      if (dateFilterEnabled && filterDate) {
        params.filter_date = filterDate;
      }
      const res = await bridge.call<ScanResult>("batch_scan", params);
      setScanResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  };

  const doProcess = useCallback(async () => {
    if (!scanResult) return;
    setProcessing(true);
    setError(null);
    setResult(null);
    setSummary(null);
    setAnomalies([]);
    bridge.setProgress(null);
    try {
      const params: Record<string, unknown> = {
        folder_path: folderPath,
        matched: scanResult.matched,
        year: parseInt(year),
        month: parseInt(month),
        raw_start: parseInt(rawStart),
        use_equipment_ledger: useEquipmentLedger,
        use_oil_ledger: useOilLedger,
        use_model_ledger: useModelLedger,
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
      };

      if (tableMergeMode === "merge") {
        params.merge_output = true;
      } else if (tableMergeMode === "table_merge") {
        params.merge_output = false;
        params.table_merge_config = { base_type: baseTableType };
      } else {
        params.merge_output = false;
      }

      if (dateFilterEnabled && filterDate) {
        params.filter_date = filterDate;
      }

      if (useHeaderMapping) {
        params.use_worktime_header_mapping = true;
        params.header_mode = headerMode;
      }

      const res = await bridge.call<{ cancelled?: boolean; summary?: BatchSummary }>("batch_process", params);
      if (res.summary) {
        setSummary(res.summary);
        setAnomalies(res.summary.anomalies ?? []);
      }
      setResult(t("pages:BatchProcessingPage.批量处理完成_7518"));
      notify(t("pages:BatchProcessingPage.批量处理完成_7518"), "success");
    } catch (e) {
      const msg = String(e);
      if (msg.includes("cancel")) {
        setResult(t("pages:BatchProcessingPage.已取消_2111"));
        notify(t("pages:BatchProcessingPage.批量处理已取消_2424"), "info");
      } else {
        setError(msg);
        notify(t("pages:BatchProcessingPage.批量处理失败:$_596c", { msg }), "error");
      }
    } finally {
      setProcessing(false);
      bridge.setProgress(null);
    }
  }, [scanResult, folderPath, year, month, rawStart, useEquipmentLedger, useOilLedger, useModelLedger, skipHiddenRows, skipHiddenCols, filterZeroEngineHours, filterZeroWorkHours, filterZeroHoursMeter, filterZeroKmMeter, filterZeroRunHours, filterZeroRunKm, tableMergeMode, baseTableType, dateFilterEnabled, filterDate, useHeaderMapping, headerMode, bridge]);

  const handleProcess = () => {
    if (hasMissing) {
      setShowConfirm(true);
    } else {
      doProcess();
    }
  };

  const handleCancel = async () => {
    await bridge.cancel();
  };

  // ═══════════════════════════════════════
  // Render
  // ═══════════════════════════════════════

  return (
    <div className="space-y-5">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">{t("pages:BatchProcessingPage.批量处理_ba72")}</h2>
          <p className="text-sm text-slate-500">{t("pages:BatchProcessingPage.扫描文件夹并批量处理多种报表_d8f0")}</p>
        </div>
      </div>

      {/* ════════════════════════════════════
          Section 1: Folder & Scan
          ════════════════════════════════════ */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={folderPath}
            onChange={(e) => { setFolderPath(e.target.value); setScanResult(null); }}
            placeholder={t("pages:BatchProcessingPage.选择包含报表的文件夹_53e9")}
            className={`${inputClass} flex-1 ${folderPath === "" ? "border-amber-300 bg-amber-50/30" : ""}`}
          />
          <button onClick={browse} className={btnSecondaryClass} title={t("pages:BatchProcessingPage.选择文件夹_aaa4")}>
            <FolderIcon />
          </button>
          <button
            onClick={handleScan}
            disabled={!folderPath || scanning}
            className={`shrink-0 flex items-center gap-1.5 text-sm px-3.5 py-1.5 rounded-md font-medium transition-colors ${
              !folderPath || scanning
                ? "bg-slate-100 text-slate-400"
                : "bg-slate-900 hover:bg-slate-800 text-white"
            }`}
          >
            {scanning ? (
              <>
                <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {t("pages:BatchProcessingPage.ui.scanning")}
              </>
            ) : (
              <>
                <SearchIcon />
                {t("pages:BatchProcessingPage.ui.scanFiles")}
              </>
            )}
          </button>
        </div>

        {/* ── Scan results as simple text list ── */}
        {scanResult && (
          <div className="mt-3 space-y-1.5">
            {Object.entries(scanResult.matched).map(([type, files]) => {
              const cfg = getTypeConfig(type);
              return (
                <div key={type} className="flex items-center gap-2 text-sm text-slate-700 py-1">
                  <CheckIcon />
                  <span className="text-slate-500">{cfg.icon}</span>
                  <span className="text-slate-700">{typeLabel(type)}</span>
                  <span className="text-xs text-slate-400">({t("pages:BatchProcessingPage.ui.fileCount", { count: (files as string[]).length })})</span>
                </div>
              );
            })}
            {scanResult.missing.map((type) => (
              <div key={type} className="flex items-center gap-2 text-sm py-1">
                <XIcon />
                <QuestionIcon />
                <span className="text-slate-500">{type}</span>
                <span className="text-xs text-slate-400">{t("pages:BatchProcessingPage.未找到_c465")}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ════════════════════════════════════
          Section 2: Parameters
          ════════════════════════════════════ */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-medium text-slate-700 mb-3 flex items-center gap-2">
          <SettingsIcon />
          {t("pages:BatchProcessingPage.parameterConfig")}
        </h3>

        {/* ── Basic params grid ── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-slate-500 mb-1 block">{t("pages:BatchProcessingPage.年份_8f30")}</label>
            <select
              value={year}
              onChange={(e) => setYear(e.target.value)}
              className={`${inputClass} h-9`}
            >
              {Array.from({ length: 61 }, (_, i) => localToday().getFullYear() - 30 + i).map((y) => (
                <option key={y} value={y}>{t("pages:DataProcessingPage.$年_b668", { y })}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">{t("pages:BatchProcessingPage.月份_8190")}</label>
            <select
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className={`${inputClass} h-9`}
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{t("pages:DataProcessingPage.$月_d5bf", { m })}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">{t("pages:BatchProcessingPage.表头起始行_7c63")}</label>
            <input
              type="number"
              value={rawStart}
              onChange={(e) => setRawStart(e.target.value)}
              className={`${inputClass} h-9`}
            />
          </div>
        </div>

        <div className="mt-3 space-y-3">
          <div>
            <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:BatchProcessingPage.台账匹配_9897")}</p>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              <Toggle checked={useEquipmentLedger} onChange={setUseEquipmentLedger} label={t("pages:BatchProcessingPage.设备台账匹配_5a23")} />
              <Toggle checked={useOilLedger} onChange={setUseOilLedger} label={t("pages:BatchProcessingPage.油品台账匹配_8663")} />
              <Toggle checked={useModelLedger} onChange={setUseModelLedger} label={t("pages:BatchProcessingPage.型号台账匹配_135c")} />
            </div>
          </div>
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:BatchProcessingPage.Excel选项_104b")}</p>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              <Toggle checked={skipHiddenRows} onChange={setSkipHiddenRows} label={t("pages:BatchProcessingPage.跳过隐藏行_bc25")} />
              <Toggle checked={skipHiddenCols} onChange={setSkipHiddenCols} label={t("pages:BatchProcessingPage.跳过隐藏列_3ed3")} />
            </div>
          </div>
        </div>

        <SectionDivider label={t("pages:BatchProcessingPage.输出方式_71ab")} />

        {/* ── Table merge mode ── */}
        <div className="space-y-3">
          <ChipToggle
            value={tableMergeMode}
            onChange={(v) => setTableMergeMode(v as TableMergeMode)}
            options={[
              { label: t("pages:BatchProcessingPage.分表输出_76b1"), value: "split", tip: t("pages:BatchProcessingPage.每个报表类型输出独立文件_6e1c") },
              { label: t("pages:BatchProcessingPage.合并输出_6a20"), value: "merge", tip: t("pages:BatchProcessingPage.所有结果合并为一个文件_bb18") },
              { label: t("pages:BatchProcessingPage.表内合并_2283"), value: "table_merge", tip: t("pages:BatchProcessingPage.以某类表为基准合并数据_38a3") },
            ]}
          />
          {tableMergeMode === "table_merge" && (
            <div className="flex items-center gap-3 pl-1">
              <span className="text-xs text-slate-500">{t("pages:BatchProcessingPage.基准表_a229")}</span>
              <ChipToggle
                value={baseTableType}
                onChange={(v) => setBaseTableType(v as BaseTableType)}
                options={[
                  { label: t("pages:BatchProcessingPage.油耗_75d6"), value: "fuel" },
                  { label: t("pages:BatchProcessingPage.工时_e8c0"), value: "worktime" },
                ]}
              />
            </div>
          )}
        </div>
      </div>

      {/* ════════════════════════════════════
          Section 3: Consolidated advanced options
          ════════════════════════════════════ */}
      <Collapsible
        title={t("pages:BatchProcessingPage.高级选项_1083")}
        icon={<SettingsIcon />}
        summary={
          <span className="mr-1 text-xs font-normal text-slate-500">
            {dateFilterEnabled || useHeaderMapping || anomaly.enabled
              ? t("pages:BatchProcessingPage.$项已启用_ee73", { count: Number(dateFilterEnabled) + Number(useHeaderMapping) + Number(anomaly.enabled) })
              : t("pages:BatchProcessingPage.使用默认设置_af8d")}
          </span>
        }
      >
        <div className="grid grid-cols-1 xl:grid-cols-4 xl:divide-x divide-slate-100">
          {/* ── Date filter ── */}
          <section className="py-4 xl:pr-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
              <span className="text-slate-500"><CalendarIcon /></span>
              {t("pages:BatchProcessingPage.dateFilter")}
            </div>
            <div className="space-y-3">
              <Toggle
                checked={dateFilterEnabled}
                onChange={setDateFilterEnabled}
                label={t("pages:BatchProcessingPage.按日期过滤_e159")}
              />

              {dateFilterEnabled && (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => setFilterDate(shiftDate(filterDate, -1))}
                      className="text-xs px-3 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      {t("pages:BatchProcessingPage.ui.previousDay")}
                    </button>
                    <button
                      onClick={() => setFilterDate(formatToday())}
                      className="text-xs px-3 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      {t("pages:BatchProcessingPage.ui.today")}
                    </button>
                    <button
                      onClick={() => {
                        const el = document.getElementById("batch-filter-date") as HTMLInputElement | null;
                        el?.showPicker?.();
                      }}
                      className="text-xs px-3 py-1.5 rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors flex items-center gap-1"
                    >
                      <CalendarIcon />
                      {t("pages:BatchProcessingPage.ui.chooseDate")}
                    </button>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <label className="text-xs text-slate-500" htmlFor="batch-filter-date">{t("pages:BatchProcessingPage.日期_4ff1")}</label>
                    <input
                      id="batch-filter-date"
                      type="date"
                      value={filterDate}
                      onChange={(e) => setFilterDate(e.target.value)}
                      className={`${inputClass} w-auto`}
                    />
                    <span className="text-xs text-slate-400 font-mono">{filterDate}</span>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* ── Header mapping ── */}
          <section className="border-t border-slate-100 py-4 xl:border-t-0 xl:pl-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
              <span className="text-slate-500"><RulerIcon /></span>
              {t("pages:BatchProcessingPage.headerMapping")}
            </div>
            <div className="space-y-3">
              <Toggle
                checked={useHeaderMapping}
                onChange={setUseHeaderMapping}
                label={t("pages:BatchProcessingPage.启用表头映射_453a")}
              />

              {useHeaderMapping && (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-xs text-slate-500">{t("pages:BatchProcessingPage.映射模式_2ba8")}</span>
                    <ChipToggle
                      value={headerMode}
                      onChange={setHeaderMode}
                      options={[
                        { label: t("pages:BatchProcessingPage.位置映射_51c1"), value: "position" },
                        { label: t("pages:BatchProcessingPage.名称映射_817c"), value: "name" },
                      ]}
                    />
                  </div>
                  
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {t("pages:BatchProcessingPage.ui.headerMappingHint")}
                  </p>
                </div>
              )}
            </div>
          </section>

          {/* ── Anomaly detection ── */}
          <section className="border-t border-slate-100 py-4 xl:border-t-0 xl:pl-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
              <span className="text-amber-600"><AlertTriangleIcon /></span>
              {t("pages:BatchProcessingPage.ui.anomalyDetection")}
            </div>
            <AnomalyPanel
              config={anomaly}
              onChange={setAnomaly}
              embedded
            />
          </section>

          {/* ── Data filters ── */}
          <section className="border-t border-slate-100 py-4 xl:border-t-0 xl:pl-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
              <span className="text-slate-500"><FilterIcon /></span>
              {t("pages:BatchProcessingPage.dataFilter")}
            </div>
            <div className="space-y-3">
              <div>
                <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:BatchProcessingPage.油耗处理_1a41")}</p>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  <Toggle checked={filterZeroEngineHours} onChange={setFilterZeroEngineHours} label={t("pages:BatchProcessingPage.过滤零小时数_549f")} />
                  <Toggle checked={filterZeroWorkHours} onChange={setFilterZeroWorkHours} label={t("pages:BatchProcessingPage.过滤零运行小时数_eaf1")} />
                </div>
              </div>
              <div className="border-t border-slate-100 pt-3">
                <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:BatchProcessingPage.生产数据_9fb6")}</p>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  <Toggle checked={filterZeroHoursMeter} onChange={setFilterZeroHoursMeter} label={t("pages:BatchProcessingPage.过滤零小时仪表_99e8")} />
                  <Toggle checked={filterZeroKmMeter} onChange={setFilterZeroKmMeter} label={t("pages:BatchProcessingPage.过滤零公里仪表_2e3c")} />
                  <Toggle checked={filterZeroRunHours} onChange={setFilterZeroRunHours} label={t("pages:BatchProcessingPage.过滤零运行小时数_eaf1")} />
                  <Toggle checked={filterZeroRunKm} onChange={setFilterZeroRunKm} label={t("pages:BatchProcessingPage.过滤零运行里程_d55d")} />
                </div>
              </div>
            </div>
          </section>
        </div>
      </Collapsible>

      {/* ════════════════════════════════════
          Section 4: Progress
          ════════════════════════════════════ */}
      {processing && bridge.progress && (
        <ProgressBar
          percent={bridge.progress.percent}
          stage={bridge.progress.stage}
          detail={bridge.progress.detail}
        />
      )}

      {/* ════════════════════════════════════
          Section 5: Actions
          ════════════════════════════════════ */}
      <div className="flex gap-3">
        <button
          onClick={handleProcess}
          disabled={!scanResult || processing}
          className={`${btnPrimaryClass} flex items-center gap-2`}
        >
          {!processing && <PlayIcon />}
          {processing ? t("pages:BatchProcessingPage.处理中..._2fb9") : t("pages:BatchProcessingPage.开始批量处理_1a4f")}
        </button>
        {processing && (
          <button
            onClick={handleCancel}
            className="flex items-center gap-1.5 text-sm text-red-600 hover:text-red-700 transition-colors px-3.5 py-1.5"
          >
            <StopCircleIcon />
            {t("pages:BatchProcessingPage.ui.cancel")}
          </button>
        )}
      </div>

      {/* ── Result / Error ── */}
      {result && (
        <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 rounded-md px-2.5 py-1.5">
          <CheckCircleIcon />
          {result}
        </div>
      )}
      {error && (
        <div className="flex items-start gap-2 text-xs text-red-700 bg-red-50 rounded-md px-2.5 py-1.5">
          <XCircleIcon />
          <span>{error}</span>
        </div>
      )}

      {/* ── Batch Summary ── */}
      {summary && (
        <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
          <h3 className="text-sm font-medium text-slate-700">{t("pages:BatchProcessingPage.处理汇总_c45e")}</h3>
          <div className="flex items-center gap-4 text-xs">
            {summary.success_modules.length > 0 && (
              <div className="flex items-center gap-1.5">
                <CheckIcon />
                <span className="text-slate-600">
                  {t("pages:BatchProcessingPage.ui.success")}: {summary.success_modules.join("、")}
                </span>
              </div>
            )}
            {summary.failed_modules.length > 0 && (
              <div className="flex items-center gap-1.5">
                <XIcon />
                <span className="text-slate-600">
                  {t("pages:BatchProcessingPage.ui.failure")}: {summary.failed_modules.join("、")}
                </span>
              </div>
            )}
          </div>
          {summary.warnings.length > 0 && (
            <div className="space-y-1.5">
              {summary.warnings.map((w, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 rounded-md px-2.5 py-1.5"
                >
                  <AlertTriangleIcon />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <AnomalyResultsTable records={anomalies} />

      {/* ════════════════════════════════════
          Confirmation Dialog
          ════════════════════════════════════ */}
      {showConfirm && scanResult && (
        <ConfirmDialog
          title={t("pages:BatchProcessingPage.部分文件缺失_4034")}
          message={t("pages:BatchProcessingPage.扫描发现以下报表类型未找到对应_0aac")}
          details={scanResult.missing}
          confirmLabel={t("pages:BatchProcessingPage.继续处理_a53f")}
          cancelLabel={t("pages:BatchProcessingPage.返回_5f41")}
          onConfirm={() => { setShowConfirm(false); doProcess(); }}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}
