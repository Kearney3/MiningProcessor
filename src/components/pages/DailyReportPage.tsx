import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { DatePicker } from "../DatePicker";
import { Collapsible, PathInput, StyledToggle as Toggle } from "../../lib/ui-components";
import { btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { useLastDirectory } from "../../hooks/useLastDirectory";
import { localYesterdayString } from "../../lib/dateUtils";
import { FileScanPanel } from "../FileScanPanel";
import { ElectricalIcon, FuelIcon, ProductionIcon, QuestionIcon, WorktimeIcon } from "../../lib/icons";
import type { ScanResult } from "../../lib/types";

function joinPath(directory: string, filename: string): string {
  const trimmed = directory.replace(/[\\/]+$/, "");
  const separator = directory.includes("\\") && !directory.includes("/") ? "\\" : "/";
  return `${trimmed || separator}${trimmed ? separator : ""}${filename}`;
}

export function DailyReportPage({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const { t } = useTranslation();
  const { initialDir } = useLastDirectory(bridge, "daily_report_input_dir");
  const [sourceDir, setSourceDir] = useState("");
  const [start, setStart] = useState(localYesterdayString());
  const [end, setEnd] = useState(localYesterdayString());
  const [useEquipment, setUseEquipment] = useState(true);
  const [useModel, setUseModel] = useState(false);
  const [includeRawEquipmentName, setIncludeRawEquipmentName] = useState(true);
  const [includeRawEquipmentCode, setIncludeRawEquipmentCode] = useState(true);
  const [includeRawCompanyName, setIncludeRawCompanyName] = useState(true);
  const [includeDetailSheets, setIncludeDetailSheets] = useState(false);
  const [skipHiddenRows, setSkipHiddenRows] = useState(true);
  const [skipHiddenCols, setSkipHiddenCols] = useState(false);
  const [filterZeroEngineHours, setFilterZeroEngineHours] = useState(true);
  const [filterZeroWorkHours, setFilterZeroWorkHours] = useState(false);
  const [filterZeroHoursMeter, setFilterZeroHoursMeter] = useState(true);
  const [filterZeroKmMeter, setFilterZeroKmMeter] = useState(false);
  const [filterZeroRunHours, setFilterZeroRunHours] = useState(false);
  const [filterZeroRunKm, setFilterZeroRunKm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);

  useEffect(() => {
    if (initialDir && !sourceDir) setSourceDir(initialDir);
  }, [initialDir, sourceDir]);

  const setEquipmentLedger = (enabled: boolean) => {
    setUseEquipment(enabled);
    if (!enabled) setUseModel(false);
  };

  const clearScan = () => {
    setScanResult(null);
    setSelectedPaths([]);
  };

  const handleScan = async (): Promise<ScanResult | null> => {
    const directory = sourceDir.trim();
    if (!directory) {
      notify(t("pages:DailyReportPage.selectDailyReportDataDirectory"), "error");
      return null;
    }
    setScanning(true);
    clearScan();
    try {
      const result = await bridge.call<ScanResult>("daily_report_scan", { source_dir: directory });
      if (!result.files && !result.matched) return null;
      setScanResult(result);
      const paths = result.files?.length
        ? result.files.filter((file) => file.recognized && file.selected).map((file) => file.path)
        : Object.values(result.matched ?? {}).flat();
      setSelectedPaths([...new Set(paths)]);
      return result;
    } catch (error) {
      notify(String(error), "error");
      return null;
    } finally {
      setScanning(false);
    }
  };

  const dailyTypeLabel = (type: string) => {
    const key: Record<string, string> = {
      fuel: "fuelData",
      electrical: "electricalData",
      production: "productionData",
      worktime: "worktimeData",
    };
    return t(`pages:DataSyncPage.ui.${key[type] ?? type}`);
  };

  const dailyTypeIcon = (type: string) => {
    const icons: Record<string, ReactNode> = {
      fuel: <FuelIcon />,
      electrical: <ElectricalIcon />,
      production: <ProductionIcon />,
      worktime: <WorktimeIcon />,
    };
    return icons[type] ?? <QuestionIcon />;
  };

  const exportReport = async () => {
    if (!sourceDir) return notify(t("pages:DailyReportPage.selectDailyReportDataDirectory"), "error");
    if (start > end) return notify(t("pages:DailyReportPage.endDateCannotBeEarlierThanStartDate"), "error");
    if (useModel && !useEquipment) return notify(t("pages:DailyReportPage.modelLedgermatchingmatchingequipmentLedgermatching"), "error");
    if (!scanResult) {
      const scanned = await handleScan();
      // 兼容旧版桥接；正式桥接返回扫描结果后停在此处，交给用户确认。
      if (scanned) return;
    }
    if (scanResult && selectedPaths.length === 0) {
      return notify(t("pages:DailyReportPage.noSelectedFiles"), "error");
    }
    bridge.call("save_last_directory", { key: "daily_report_input_dir", path: sourceDir }).catch(() => {});
    const filename = t("pages:DailyReportPage.dailyReportXlsx", { start, end });
    const output = joinPath(sourceDir, filename);
    setLoading(true);
    try {
      const result = await bridge.call<{
        output_file: string;
        rows: number;
        warnings: Record<string, unknown>[];
        detail_sheets?: string[];
      }>("daily_report_export", {
        source_dir: sourceDir,
        output_path: output,
        date_start: start,
        date_end: end,
        use_equipment_ledger: useEquipment,
        use_model_ledger: useModel,
        config: {
          include_raw_equipment_name: includeRawEquipmentName,
          include_raw_equipment_code: includeRawEquipmentCode,
          include_raw_company_name: includeRawCompanyName,
        },
        include_detail_sheets: includeDetailSheets,
        selected_files: scanResult ? selectedPaths : undefined,
        preprocess_options: {
          skip_hidden_rows: skipHiddenRows,
          skip_hidden_cols: skipHiddenCols,
          filter_zero_engine_hours: filterZeroEngineHours,
          filter_zero_work_hours: filterZeroWorkHours,
          filter_zero_hours_meter: filterZeroHoursMeter,
          filter_zero_km_meter: filterZeroKmMeter,
          filter_zero_run_hours: filterZeroRunHours,
          filter_zero_run_km: filterZeroRunKm,
        },
      });
      const detailMessage = result.detail_sheets?.length
        ? t("pages:DailyReportPage.itemItems", { count: result.detail_sheets.length })
        : "";
      notify(t("pages:DailyReportPage.dailyReportsavedDailyReportDailyReportItems", { rows: result.rows, warnCount: result.warnings.length, detailMessage }), result.warnings.length ? "info" : "success");
    } catch (error) {
      notify(t("pages:DailyReportPage.dailyReportExportFailed") + String(error), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">{t("pages:DailyReportPage.dailyReport")}</h2>
        <p className="text-sm text-slate-500">{t("pages:DailyReportPage.summarizeAndExportDailyReport")}</p>
      </div>
      <section className="bg-white rounded-lg border border-slate-200 p-4 space-y-5">
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">{t("pages:DailyReportPage.dataDirectory")}</label>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <PathInput
                value={sourceDir}
                onChange={(value) => { setSourceDir(value); clearScan(); }}
                onFileSelected={(path) => {
                  clearScan();
                  bridge.call("save_last_directory", { key: "daily_report_input_dir", path }).catch(() => {});
                }}
                directory
                defaultPath={initialDir || undefined}
                placeholder={t("pages:DailyReportPage.selectDataDirectory")}
              />
            </div>
            <button
              type="button"
              onClick={handleScan}
              disabled={!sourceDir || scanning || loading}
              className={`${btnSecondaryClass} ${(!sourceDir || scanning || loading) ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              {scanning ? t("pages:DailyReportPage.scanning") : t("pages:DailyReportPage.scanFiles")}
            </button>
          </div>
          <FileScanPanel
            result={scanResult}
            selectedPaths={new Set(selectedPaths)}
            onToggle={(path, selected) => {
              setSelectedPaths((previous) => selected
                ? [...new Set([...previous, path])]
                : previous.filter((item) => item !== path));
            }}
            onToggleAll={(selected) => {
              if (!scanResult) return;
              const recognized = scanResult.files?.length
                ? scanResult.files.filter((file) => file.recognized && file.types.length > 0).map((file) => file.path)
                : [...new Set(Object.values(scanResult.matched ?? {}).flat())];
              setSelectedPaths(selected ? recognized : []);
            }}
            typeLabel={dailyTypeLabel}
            typeIcon={dailyTypeIcon}
            description={t("pages:DailyReportPage.fileSelectionHint")}
          />
        </div>

        <div className="border-t border-slate-100 pt-4">
          <label className="text-xs font-medium text-slate-500 mb-2 block">{t("pages:DailyReportPage.dateRange")}</label>
          <div className="flex flex-wrap items-end gap-3">
            <DatePicker label={t("pages:DailyReportPage.startDate")} value={start} onChange={setStart} className="w-44" />
            <DatePicker label={t("pages:DailyReportPage.endDate")} value={end} onChange={setEnd} className="w-44" />
            <button
              type="button"
              onClick={() => { setStart(localYesterdayString()); setEnd(localYesterdayString()); }}
              className={btnSecondaryClass}
            >{t("pages:DailyReportPage.yesterday")}</button>
            <button
              type="button"
              onClick={() => { setStart(""); setEnd(""); }}
              className={btnSecondaryClass}
            >{t("pages:DailyReportPage.clear")}</button>
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:DailyReportPage.ledgerMatch")}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <Toggle checked={useEquipment} onChange={setEquipmentLedger} label={t("pages:DailyReportPage.equipmentLedgerMatch")} />
            <Toggle checked={useModel} onChange={setUseModel} label={t("pages:DailyReportPage.modelLedgerMatch")} disabled={!useEquipment} />
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:DailyReportPage.outputOptions")}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <Toggle checked={includeRawEquipmentName} onChange={setIncludeRawEquipmentName} label={t("pages:DailyReportPage.outputOriginalEquipmentNames")} />
            <Toggle checked={includeRawEquipmentCode} onChange={setIncludeRawEquipmentCode} label={t("pages:DailyReportPage.outputOriginalEquipmentIds")} />
            <Toggle checked={includeRawCompanyName} onChange={setIncludeRawCompanyName} label={t("pages:DailyReportPage.outputOriginalCompanyNames")} />
            <Toggle checked={includeDetailSheets} onChange={setIncludeDetailSheets} label={t("pages:DailyReportPage.outputDetailTables")} />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            {t("pages:DailyReportPage.ui.detailSheetHint")}
          </p>
        </div>

        <div className="border-t border-slate-100 pt-4 flex justify-start">
          <button className={btnPrimaryClass} disabled={loading} onClick={exportReport}>
            {loading ? t("pages:DailyReportPage.exporting") : t("pages:DailyReportPage.exportDailyReport")}
          </button>
        </div>
      </section>

      <Collapsible title={t("pages:DailyReportPage.processingOptions")} defaultOpen={false}>
        <div className="space-y-4 pt-3">
          <div>
            <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:DailyReportPage.excelOptions")}</p>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <Toggle checked={skipHiddenRows} onChange={setSkipHiddenRows} label={t("pages:DailyReportPage.skipHiddenRows")} />
              <Toggle checked={skipHiddenCols} onChange={setSkipHiddenCols} label={t("pages:DailyReportPage.skipHiddenColumns")} />
            </div>
          </div>
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:DailyReportPage.dataFilters")}</p>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-400 mb-2">{t("pages:DailyReportPage.fuelProcessing")}</p>
                <div className="flex flex-wrap gap-x-6 gap-y-2">
                  <Toggle checked={filterZeroEngineHours} onChange={setFilterZeroEngineHours} label={t("pages:DailyReportPage.filterZeroEngineHours")} />
                  <Toggle checked={filterZeroWorkHours} onChange={setFilterZeroWorkHours} label={t("pages:DailyReportPage.filterZeroOperatingHours")} />
                </div>
              </div>
              <div className="border-t border-slate-100 pt-3">
                <p className="text-xs text-slate-400 mb-2">{t("pages:DailyReportPage.runtimeData")}</p>
                <div className="flex flex-wrap gap-x-6 gap-y-2">
                  <Toggle checked={filterZeroHoursMeter} onChange={setFilterZeroHoursMeter} label={t("pages:DailyReportPage.filterZeroHoursMeter")} />
                  <Toggle checked={filterZeroKmMeter} onChange={setFilterZeroKmMeter} label={t("pages:DailyReportPage.filterZeroKilometerMeter")} />
                  <Toggle checked={filterZeroRunHours} onChange={setFilterZeroRunHours} label={t("pages:DailyReportPage.filterZeroOperatingHours")} />
                  <Toggle checked={filterZeroRunKm} onChange={setFilterZeroRunKm} label={t("pages:DailyReportPage.filterZeroOperatingDistance")} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </Collapsible>
    </div>
  );
}
