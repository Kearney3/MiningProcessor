import { useEffect, useState } from "react";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { DatePicker } from "../DatePicker";
import { Collapsible, PathInput, StyledToggle as Toggle } from "../../lib/ui-components";
import { btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { useLastDirectory } from "../../hooks/useLastDirectory";

function yesterdayISO() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

function joinPath(directory: string, filename: string): string {
  const trimmed = directory.replace(/[\\/]+$/, "");
  const separator = directory.includes("\\") && !directory.includes("/") ? "\\" : "/";
  return `${trimmed || separator}${trimmed ? separator : ""}${filename}`;
}

export function DailyReportPage({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const { initialDir } = useLastDirectory(bridge, "daily_report_input_dir");
  const [sourceDir, setSourceDir] = useState("");
  const [start, setStart] = useState(yesterdayISO());
  const [end, setEnd] = useState(yesterdayISO());
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
    if (!sourceDir) return notify("请选择日报数据目录", "error");
    if (start > end) return notify("结束日期不能早于起始日期", "error");
    if (useModel && !useEquipment) return notify("型号台账匹配需要同时开启设备台账匹配", "error");
    const output = joinPath(sourceDir, `每日报表_${start}_${end}.xlsx`);
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
        ? `，分项表 ${result.detail_sheets.length} 个`
        : "";
      notify(`日报已保存：${result.rows} 行，警告 ${result.warnings.length} 条${detailMessage}`, result.warnings.length ? "info" : "success");
    } catch (error) {
      notify("日报导出失败：" + String(error), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">每日报表</h2>
        <p className="text-sm text-slate-500">汇总并导出日报</p>
      </div>
      <section className="bg-white rounded-lg border border-slate-200 p-4 space-y-5">
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">数据目录</label>
          <PathInput
            value={sourceDir}
            onChange={setSourceDir}
            onFileSelected={(path) => {
              bridge.call("save_last_directory", { key: "daily_report_input_dir", path }).catch(() => {});
            }}
            directory
            defaultPath={initialDir || undefined}
            placeholder="选择数据目录"
          />
        </div>

        <div className="border-t border-slate-100 pt-4">
          <label className="text-xs font-medium text-slate-500 mb-2 block">日期范围</label>
          <div className="flex flex-wrap items-end gap-3">
            <DatePicker label="起始日期" value={start} onChange={setStart} className="w-44" />
            <DatePicker label="结束日期" value={end} onChange={setEnd} className="w-44" />
            <button
              type="button"
              onClick={() => { setStart(yesterdayISO()); setEnd(yesterdayISO()); }}
              className={btnSecondaryClass}
            >昨日</button>
            <button
              type="button"
              onClick={() => { setStart(""); setEnd(""); }}
              className={btnSecondaryClass}
            >清除</button>
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <p className="text-xs font-medium text-slate-500 mb-2">台账匹配</p>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <Toggle checked={useEquipment} onChange={setEquipmentLedger} label="设备台账匹配" />
            <Toggle checked={useModel} onChange={setUseModel} label="型号台账匹配" disabled={!useEquipment} />
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <p className="text-xs font-medium text-slate-500 mb-2">输出选项</p>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <Toggle checked={includeRawEquipmentName} onChange={setIncludeRawEquipmentName} label="输出原始设备名称" />
            <Toggle checked={includeRawEquipmentCode} onChange={setIncludeRawEquipmentCode} label="输出原始设备编号" />
            <Toggle checked={includeRawCompanyName} onChange={setIncludeRawCompanyName} label="输出原始公司名称" />
            <Toggle checked={includeDetailSheets} onChange={setIncludeDetailSheets} label="输出分项表格" />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            开启分项表格后，会在日报文件中追加工时、运行、生产、油耗和电耗统计 Sheet。
          </p>
        </div>

        <div className="border-t border-slate-100 pt-4 flex justify-start">
          <button className={btnPrimaryClass} disabled={loading} onClick={exportReport}>
            {loading ? "导出中…" : "导出每日报表"}
          </button>
        </div>
      </section>

      <Collapsible title="处理选项" defaultOpen={false}>
        <div className="space-y-4 pt-3">
          <div>
            <p className="text-xs font-medium text-slate-500 mb-2">Excel 选项</p>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <Toggle checked={skipHiddenRows} onChange={setSkipHiddenRows} label="跳过隐藏行" />
              <Toggle checked={skipHiddenCols} onChange={setSkipHiddenCols} label="跳过隐藏列" />
            </div>
          </div>
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs font-medium text-slate-500 mb-2">数据过滤</p>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-400 mb-2">油耗处理</p>
                <div className="flex flex-wrap gap-x-6 gap-y-2">
                  <Toggle checked={filterZeroEngineHours} onChange={setFilterZeroEngineHours} label="过滤零小时数" />
                  <Toggle checked={filterZeroWorkHours} onChange={setFilterZeroWorkHours} label="过滤零运行小时数" />
                </div>
              </div>
              <div className="border-t border-slate-100 pt-3">
                <p className="text-xs text-slate-400 mb-2">运行数据</p>
                <div className="flex flex-wrap gap-x-6 gap-y-2">
                  <Toggle checked={filterZeroHoursMeter} onChange={setFilterZeroHoursMeter} label="过滤零小时仪表" />
                  <Toggle checked={filterZeroKmMeter} onChange={setFilterZeroKmMeter} label="过滤零公里仪表" />
                  <Toggle checked={filterZeroRunHours} onChange={setFilterZeroRunHours} label="过滤零运行小时数" />
                  <Toggle checked={filterZeroRunKm} onChange={setFilterZeroRunKm} label="过滤零运行里程" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </Collapsible>
    </div>
  );
}
