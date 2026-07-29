import { useState, useEffect } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import type { BridgeProp, SyncResult, SyncWarning } from "../../lib/types";
import { useToast } from "../Toast";
import {
  FolderIcon, FuelIcon, ProductionIcon, ElectricalIcon, WorktimeIcon,
  OperationIcon, GlobeIcon, DatabaseIcon, CheckIcon, MinusIcon,
  CheckCircleIcon, XCircleIcon, AlertTriangleIcon, DownloadIcon, PlayIcon,
} from "../../lib/icons";
import { inputClass, btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { DatePicker } from "../DatePicker";
import { AnomalyPanel, type AnomalyConfig, DEFAULT_ANOMALY_CONFIG } from "../AnomalyPanel";

// ═══════════════════════════════════════
// Date helpers
// ═══════════════════════════════════════

function yesterdayISO(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

// ═══════════════════════════════════════
// Constants
// ═══════════════════════════════════════

const ALL_TYPES = [
  { id: "fuel", label: "油耗数据", icon: <FuelIcon /> },
  { id: "production", label: "生产数据", icon: <ProductionIcon /> },
  { id: "electrical", label: "电力消耗", icon: <ElectricalIcon /> },
  { id: "work_efficiency", label: "工时数据", icon: <WorktimeIcon /> },
  { id: "operation", label: "设备运行", icon: <OperationIcon /> },
] as const;

const TYPE_LABEL_MAP: Record<string, string> = Object.fromEntries(ALL_TYPES.map((t) => [t.id, t.label]));

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

// ═══════════════════════════════════════
// Main page component
// ═══════════════════════════════════════

export function DataSyncPage({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const [inputDir, setInputDir] = useState("");
  const [mode, setMode] = useState<"api" | "database">("api");
  const [dataTypes, setDataTypes] = useState<string[]>(ALL_TYPES.map((t) => t.id));
  const [dryRun, setDryRun] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 处理参数
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState(String(currentMonth));
  const [headerRow, setHeaderRow] = useState("");

  // 日期范围
  const [dateStart, setDateStart] = useState(yesterdayISO());
  const [dateEnd, setDateEnd] = useState(yesterdayISO());
  const [applyHeaderMapping, setApplyHeaderMapping] = useState(true);
  const [headerMode, setHeaderMode] = useState("position");
  const [useEquipmentLedger, setUseEquipmentLedger] = useState(false);
  const [useOilLedger, setUseOilLedger] = useState(true);
  const [skipHiddenRows, setSkipHiddenRows] = useState(true);
  const [skipHiddenCols, setSkipHiddenCols] = useState(false);
  const [anomaly, setAnomaly] = useState<AnomalyConfig>(DEFAULT_ANOMALY_CONFIG);

  // 过滤开关
  const [filterZeroEngineHours, setFilterZeroEngineHours] = useState(false);
  const [filterZeroWorkHours, setFilterZeroWorkHours] = useState(false);
  const [filterZeroHoursMeter, setFilterZeroHoursMeter] = useState(false);
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
      setDataTypes(ALL_TYPES.map((t) => t.id));
    }
  };

  const handleSync = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await bridge.call<SyncResult>("sync_minebase", {
        input_dir: inputDir,
        mode,
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
        notify(`同步完成: 成功=${total.success}, 跳过=${total.skipped}, 失败=${total.failed}`, "error");
      } else {
        notify(`同步完成: 成功=${total.success}, 跳过=${total.skipped}`, "success");
      }
    } catch (e) {
      setError(String(e));
      notify(`同步失败: ${e}`, "error");
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
        <h2 className="text-lg font-semibold text-slate-800">数据同步</h2>
        <p className="text-sm text-slate-500">将处理后的数据同步至 MineBase</p>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-5">
        {/* Path */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">数据目录</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={inputDir}
              onChange={(e) => setInputDir(e.target.value)}
              placeholder="选择包含已处理数据的文件夹"
              className={`${inputClass} flex-1`}
            />
            <button onClick={browse} className={btnSecondaryClass} title="选择文件夹">
              <FolderIcon />
            </button>
          </div>
        </div>

        {/* Sync mode — restrained segmented control */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">同步模式</label>
          <div className="inline-flex rounded-md bg-slate-100 p-0.5 gap-0.5">
            {([
              { value: "api" as const, label: "API 模式", desc: "HTTP 推送", icon: <GlobeIcon /> },
              { value: "database" as const, label: "数据库模式", desc: "直连写入", icon: <DatabaseIcon /> },
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

        {/* Data type checkboxes */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-medium text-slate-500">数据类型</label>
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
              全选
            </span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {ALL_TYPES.map((t) => (
              <DataTypeCheckbox
                key={t.id}
                label={t.label}
                icon={t.icon}
                checked={dataTypes.includes(t.id)}
                onChange={(checked) => {
                  if (checked) {
                    setDataTypes((prev) => [...prev, t.id]);
                  } else {
                    setDataTypes((prev) => prev.filter((id) => id !== t.id));
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
            <div className="text-sm text-slate-700">试运行</div>
            <div className="text-xs text-slate-400 mt-0.5">仅预览同步内容，不实际推送到 MineBase</div>
          </div>
        </div>

        {/* Processing params — year / month / header row */}
        <div className="border-t border-slate-100 pt-4">
          <label className="text-xs font-medium text-slate-500 mb-2 block">处理参数</label>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">年份</label>
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
              <label className="text-xs text-slate-400 mb-1 block">月份</label>
              <select
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                className={`${inputClass} w-full h-9`}
              >
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <option key={m} value={m}>{m}月</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">表头起始行</label>
              <input
                type="number"
                value={headerRow}
                onChange={(e) => setHeaderRow(e.target.value)}
                placeholder="自动检测"
                min="1"
                className={`${inputClass} w-full h-9`}
              />
            </div>
          </div>
        </div>

        {/* Date range filter */}
        <div className="border-t border-slate-100 pt-4">
          <label className="text-xs font-medium text-slate-500 mb-2 block">日期范围过滤</label>
          <div className="flex items-end gap-3">
            <DatePicker
              label="起始日期"
              value={dateStart}
              onChange={setDateStart}
              className="flex-1"
            />
            <DatePicker
              label="结束日期"
              value={dateEnd}
              onChange={setDateEnd}
              className="flex-1"
            />
            <button
              type="button"
              onClick={() => { setDateStart(yesterdayISO()); setDateEnd(yesterdayISO()); }}
              className={btnSecondaryClass}
            >
              昨日
            </button>
            <button
              type="button"
              onClick={() => { setDateStart(""); setDateEnd(""); }}
              className={btnSecondaryClass}
            >
              清除
            </button>
          </div>
        </div>

        {/* Sync options */}
        <div className="border-t border-slate-100 pt-4 space-y-3">
          <div>
            <p className="text-xs text-slate-400 mb-2">表头映射</p>
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
              <span className="text-sm text-slate-700">应用工时表头映射</span>
            </label>
            {applyHeaderMapping && (
              <div className="flex items-center gap-2 pl-10 mt-1.5">
                <span className="text-xs text-slate-500">映射模式</span>
                <ChipToggle
                  value={headerMode}
                  onChange={setHeaderMode}
                  options={[
                    { label: "按位置", value: "position" },
                    { label: "按列名", value: "name" },
                  ]}
                />
              </div>
            )}
          </div>
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs text-slate-400 mb-2">台账匹配</p>
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
                <span className="text-sm text-slate-700">设备台账匹配</span>
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
                <span className="text-sm text-slate-700">油品台账匹配</span>
              </label>
            </div>
          </div>
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs text-slate-400 mb-2">Excel 选项</p>
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
                <span className="text-sm text-slate-700">跳过隐藏行</span>
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
                <span className="text-sm text-slate-700">跳过隐藏列</span>
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
          <span>高级选项</span>
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
              <p className="text-xs font-medium text-slate-500 mb-3">数据过滤</p>
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-slate-400 mb-2">油耗处理</p>
                  <div className="flex flex-wrap gap-x-6 gap-y-2">
                    {[
                      { checked: filterZeroEngineHours, onChange: setFilterZeroEngineHours, label: "过滤零小时数" },
                      { checked: filterZeroWorkHours, onChange: setFilterZeroWorkHours, label: "过滤零运行小时数" },
                    ].map((t) => (
                      <label key={t.label} className="flex items-center gap-2.5 cursor-pointer select-none">
                        <button
                          role="switch"
                          aria-checked={t.checked}
                          onClick={() => t.onChange(!t.checked)}
                          className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
                            t.checked ? "bg-blue-600" : "bg-slate-200"
                          }`}
                        >
                          <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                            t.checked ? "translate-x-4" : "translate-x-0.5"
                          }`} />
                        </button>
                        <span className="text-sm text-slate-700">{t.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div className="border-t border-slate-100 pt-3">
                  <p className="text-xs text-slate-400 mb-2">生产数据</p>
                  <div className="flex flex-wrap gap-x-6 gap-y-2">
                    {[
                      { checked: filterZeroHoursMeter, onChange: setFilterZeroHoursMeter, label: "过滤零小时仪表" },
                      { checked: filterZeroKmMeter, onChange: setFilterZeroKmMeter, label: "过滤零公里仪表" },
                      { checked: filterZeroRunHours, onChange: setFilterZeroRunHours, label: "过滤零运行小时数" },
                      { checked: filterZeroRunKm, onChange: setFilterZeroRunKm, label: "过滤零运行里程" },
                    ].map((t) => (
                      <label key={t.label} className="flex items-center gap-2.5 cursor-pointer select-none">
                        <button
                          role="switch"
                          aria-checked={t.checked}
                          onClick={() => t.onChange(!t.checked)}
                          className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
                            t.checked ? "bg-blue-600" : "bg-slate-200"
                          }`}
                        >
                          <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                            t.checked ? "translate-x-4" : "translate-x-0.5"
                          }`} />
                        </button>
                        <span className="text-sm text-slate-700">{t.label}</span>
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
          {loading ? "同步中..." : "开始同步"}
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
            <span>成功 {totals.success}</span>
            {totals.skipped > 0 && <span>· 跳过 {totals.skipped}</span>}
            {totals.failed > 0 && <span>· 失败 {totals.failed}</span>}
            {totals.warnings > 0 && <span>· 异常 {totals.warnings}</span>}
          </div>
        );
      })()}

      {/* Result table — zebra-striped with status badges */}
      {result && (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
            <h3 className="text-sm font-medium text-slate-700 flex items-center gap-2">
              <CheckCircleIcon />
              同步结果
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left">
                <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider">数据类型</th>
                <th className="py-2 text-xs font-medium text-slate-500 uppercase tracking-wider text-right">成功</th>
                <th className="py-2 text-xs font-medium text-slate-500 uppercase tracking-wider text-right">跳过</th>
                <th className="py-2 pr-4 text-xs font-medium text-slate-500 uppercase tracking-wider text-right">失败</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.results).map(([type, stats], idx) => {
                const hasFailure = stats.failed > 0;
                return (
                  <tr key={type} className={`h-9 border-b border-slate-100 hover:bg-slate-50 ${idx % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                    <td className="px-4 py-2 text-sm text-slate-700">
                      {TYPE_LABEL_MAP[type] ?? type}
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
                      <span className={`text-xs rounded-md px-2.5 py-1 ${hasFailure ? "text-red-700 bg-red-50" : "text-slate-500 bg-slate-50"}`}>
                        {stats.failed}
                      </span>
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
              预览文件已生成
            </h3>
            <button
              type="button"
              onClick={() => openPath(result.dry_run_file!)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-cyan-700 bg-cyan-100 hover:bg-cyan-200 rounded-md transition-colors"
              title="打开预览文件"
            >
              <DownloadIcon />
              打开文件
            </button>
          </div>
          <div className="px-4 py-3">
            <p className="text-xs text-slate-500 font-mono break-all">{result.dry_run_file}</p>
            <p className="text-xs text-slate-400 mt-2">各数据类型分别保存在独立 Sheet 中，可查看即将同步的所有记录。</p>
          </div>
        </div>
      )}

      {/* Warnings table */}
      {result && (() => {
        const allWarnings: { type: string; label: string; w: SyncWarning }[] = [];
        for (const [type, stats] of Object.entries(result.results)) {
          for (const w of stats.warnings ?? []) {
            allWarnings.push({ type, label: TYPE_LABEL_MAP[type] ?? type, w });
          }
        }
        if (allWarnings.length === 0) return null;

        const handleExportWarnings = async () => {
          try {
            const today = new Date().toISOString().slice(0, 10);
            const savePath = await save({
              defaultPath: `异常行明细_${today}.xlsx`,
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
            notify(`异常行已导出至: ${res.output_file}`, "success");
          } catch (e) {
            notify(`导出失败: ${e}`, "error");
          }
        };

        return (
          <div className="bg-white rounded-lg border border-amber-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-amber-100 bg-amber-50 flex items-center justify-between">
              <h3 className="text-sm font-medium text-amber-700 flex items-center gap-2">
                <AlertTriangleIcon />
                异常行
                <span className="text-xs text-amber-500">共 {allWarnings.length} 条</span>
              </h3>
              <button
                type="button"
                onClick={handleExportWarnings}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-amber-700 bg-amber-100 hover:bg-amber-200 rounded-md transition-colors"
                title="导出异常行为 Excel 文件"
              >
                <DownloadIcon />
                导出 Excel
              </button>
            </div>
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0">
                  <tr className="bg-amber-50 text-left">
                    <th className="px-4 py-2 text-xs font-medium text-amber-600 uppercase tracking-wider">数据类型</th>
                    <th className="py-2 text-xs font-medium text-amber-600 uppercase tracking-wider">行号</th>
                    <th className="py-2 text-xs font-medium text-amber-600 uppercase tracking-wider">字段</th>
                    <th className="py-2 text-xs font-medium text-amber-600 uppercase tracking-wider">原始值</th>
                    <th className="py-2 pr-4 text-xs font-medium text-amber-600 uppercase tracking-wider">问题</th>
                  </tr>
                </thead>
                <tbody>
                  {allWarnings.map((item, idx) => (
                    <tr key={idx} className={`h-9 border-b border-slate-100 hover:bg-amber-50/50 ${idx % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                      <td className="px-4 py-2 text-sm text-slate-700">{item.label}</td>
                      <td className="py-2 text-sm text-slate-500">{item.w.row}</td>
                      <td className="py-2 text-sm text-slate-700">{item.w.field}</td>
                      <td className="py-2 text-sm text-red-600 font-mono">{item.w.value || "（空）"}</td>
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
