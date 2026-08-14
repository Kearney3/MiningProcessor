import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { DatePicker } from "../DatePicker";
import { Collapsible, PathInput, StyledToggle as Toggle } from "../../lib/ui-components";
import { btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { useLastDirectory } from "../../hooks/useLastDirectory";
import { localYesterdayString } from "../../lib/dateUtils";

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
  const [skipHiddenRows, setSkipHiddenRows] = useState(false);
  const [skipHiddenCols, setSkipHiddenCols] = useState(false);
  const [filterZeroEngineHours, setFilterZeroEngineHours] = useState(false);
  const [filterZeroWorkHours, setFilterZeroWorkHours] = useState(false);
  const [filterZeroHoursMeter, setFilterZeroHoursMeter] = useState(false);
  const [filterZeroKmMeter, setFilterZeroKmMeter] = useState(false);
  const [filterZeroRunHours, setFilterZeroRunHours] = useState(false);
  const [filterZeroRunKm, setFilterZeroRunKm] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialDir && !sourceDir) setSourceDir(initialDir);
  }, [initialDir, sourceDir]);

  const setEquipmentLedger = (enabled: boolean) => {
    setUseEquipment(enabled);
    if (!enabled) setUseModel(false);
  };

  const exportReport = async () => {
    if (!sourceDir) return notify(t("pages:DailyReportPage.请选择日报数据目录_2d46"), "error");
    if (start > end) return notify(t("pages:DailyReportPage.结束日期不能早于起始日期_b190"), "error");
    if (useModel && !useEquipment) return notify(t("pages:DailyReportPage.型号台账匹配需要同时开启设备台_00e5"), "error");
    const filename = t("pages:DailyReportPage.每日报表_$_$.xlsx_7ed0", { start, end });
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
        ? t("pages:DailyReportPage.，分项表$个_7734", { count: result.detail_sheets.length })
        : "";
      notify(t("pages:DailyReportPage.日报已保存：$行，警告$条$_11dc", { rows: result.rows, warnCount: result.warnings.length, detailMessage }), result.warnings.length ? "info" : "success");
    } catch (error) {
      notify(t("pages:DailyReportPage.日报导出失败：_ba00") + String(error), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">{t("pages:DailyReportPage.每日报表_732e")}</h2>
        <p className="text-sm text-slate-500">{t("pages:DailyReportPage.汇总并导出日报_43ba")}</p>
      </div>
      <section className="bg-white rounded-lg border border-slate-200 p-4 space-y-5">
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">{t("pages:DailyReportPage.数据目录_0d50")}</label>
          <PathInput
            value={sourceDir}
            onChange={setSourceDir}
            onFileSelected={(path) => {
              bridge.call("save_last_directory", { key: "daily_report_input_dir", path }).catch(() => {});
            }}
            directory
            defaultPath={initialDir || undefined}
            placeholder={t("pages:DailyReportPage.选择数据目录_e9dd")}
          />
        </div>

        <div className="border-t border-slate-100 pt-4">
          <label className="text-xs font-medium text-slate-500 mb-2 block">{t("pages:DailyReportPage.日期范围_7866")}</label>
          <div className="flex flex-wrap items-end gap-3">
            <DatePicker label={t("pages:DailyReportPage.起始日期_2343")} value={start} onChange={setStart} className="w-44" />
            <DatePicker label={t("pages:DailyReportPage.结束日期_1d46")} value={end} onChange={setEnd} className="w-44" />
            <button
              type="button"
              onClick={() => { setStart(localYesterdayString()); setEnd(localYesterdayString()); }}
              className={btnSecondaryClass}
            >{t("pages:DailyReportPage.昨日_23c9")}</button>
            <button
              type="button"
              onClick={() => { setStart(""); setEnd(""); }}
              className={btnSecondaryClass}
            >{t("pages:DailyReportPage.清除_4403")}</button>
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:DailyReportPage.台账匹配_9897")}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <Toggle checked={useEquipment} onChange={setEquipmentLedger} label={t("pages:DailyReportPage.设备台账匹配_5a23")} />
            <Toggle checked={useModel} onChange={setUseModel} label={t("pages:DailyReportPage.型号台账匹配_135c")} disabled={!useEquipment} />
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:DailyReportPage.输出选项_dc62")}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <Toggle checked={includeRawEquipmentName} onChange={setIncludeRawEquipmentName} label={t("pages:DailyReportPage.输出原始设备名称_7f2b")} />
            <Toggle checked={includeRawEquipmentCode} onChange={setIncludeRawEquipmentCode} label={t("pages:DailyReportPage.输出原始设备编号_5dfd")} />
            <Toggle checked={includeRawCompanyName} onChange={setIncludeRawCompanyName} label={t("pages:DailyReportPage.输出原始公司名称_fc62")} />
            <Toggle checked={includeDetailSheets} onChange={setIncludeDetailSheets} label={t("pages:DailyReportPage.输出分项表格_e5fb")} />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            {t("pages:DailyReportPage.ui.detailSheetHint")}
          </p>
        </div>

        <div className="border-t border-slate-100 pt-4 flex justify-start">
          <button className={btnPrimaryClass} disabled={loading} onClick={exportReport}>
            {loading ? t("pages:DailyReportPage.导出中…_86f9") : t("pages:DailyReportPage.导出每日报表_34bc")}
          </button>
        </div>
      </section>

      <Collapsible title={t("pages:DailyReportPage.处理选项_6ad1")} defaultOpen={false}>
        <div className="space-y-4 pt-3">
          <div>
            <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:DailyReportPage.Excel选项_104b")}</p>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <Toggle checked={skipHiddenRows} onChange={setSkipHiddenRows} label={t("pages:DailyReportPage.跳过隐藏行_bc25")} />
              <Toggle checked={skipHiddenCols} onChange={setSkipHiddenCols} label={t("pages:DailyReportPage.跳过隐藏列_3ed3")} />
            </div>
          </div>
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs font-medium text-slate-500 mb-2">{t("pages:DailyReportPage.数据过滤_8626")}</p>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-400 mb-2">{t("pages:DailyReportPage.油耗处理_1a41")}</p>
                <div className="flex flex-wrap gap-x-6 gap-y-2">
                  <Toggle checked={filterZeroEngineHours} onChange={setFilterZeroEngineHours} label={t("pages:DailyReportPage.过滤零小时数_549f")} />
                  <Toggle checked={filterZeroWorkHours} onChange={setFilterZeroWorkHours} label={t("pages:DailyReportPage.过滤零运行小时数_eaf1")} />
                </div>
              </div>
              <div className="border-t border-slate-100 pt-3">
                <p className="text-xs text-slate-400 mb-2">{t("pages:DailyReportPage.运行数据_6644")}</p>
                <div className="flex flex-wrap gap-x-6 gap-y-2">
                  <Toggle checked={filterZeroHoursMeter} onChange={setFilterZeroHoursMeter} label={t("pages:DailyReportPage.过滤零小时仪表_99e8")} />
                  <Toggle checked={filterZeroKmMeter} onChange={setFilterZeroKmMeter} label={t("pages:DailyReportPage.过滤零公里仪表_2e3c")} />
                  <Toggle checked={filterZeroRunHours} onChange={setFilterZeroRunHours} label={t("pages:DailyReportPage.过滤零运行小时数_eaf1")} />
                  <Toggle checked={filterZeroRunKm} onChange={setFilterZeroRunKm} label={t("pages:DailyReportPage.过滤零运行里程_d55d")} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </Collapsible>
    </div>
  );
}
