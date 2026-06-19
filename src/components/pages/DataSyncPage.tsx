import { useState, useEffect } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import type { BridgeProp, SyncResult } from "../../lib/types";
import { useToast } from "../Toast";
import { FolderIcon } from "../../lib/icons";
import { inputClass, btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { DatePicker } from "../DatePicker";

// ═══════════════════════════════════════
// Date helpers
// ═══════════════════════════════════════

function yesterdayISO(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

// ═══════════════════════════════════════
// Lucide-style SVG Icons (16x16, stroke-width 2)
// ═══════════════════════════════════════

const FuelIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);

const ProductionIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const ElectricalIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);

const WorktimeIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

const OperationIcon = () => (
  <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" />
  </svg>
);

const GlobeIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
  </svg>
);

const DatabaseIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </svg>
);

const CheckIcon = ({ className = "w-3 h-3" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const MinusIcon = () => (
  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const CheckCircleIcon = () => (
  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);

const XCircleIcon = () => (
  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />
  </svg>
);

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

// ═══════════════════════════════════════
// Main page component
// ═══════════════════════════════════════

const STORAGE_KEY = "sync_last_input_dir";

export function DataSyncPage({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const [inputDir, setInputDir] = useState(() => localStorage.getItem(STORAGE_KEY) || "");
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
  const [useLedger, setUseLedger] = useState(true);

  // 启动时验证上次目录是否存在，不存在则清空
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    bridge.call<{ exists: boolean }>("check_directory_exists", { path: saved })
      .then((res) => {
        if (!res.exists) {
          setInputDir("");
          localStorage.removeItem(STORAGE_KEY);
        }
      })
      .catch(() => {
        setInputDir("");
        localStorage.removeItem(STORAGE_KEY);
      });
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
        use_ledger: useLedger,
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
      localStorage.setItem(STORAGE_KEY, dir);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-5">
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
            <button onClick={browse} className={btnSecondaryClass}>
              <FolderIcon />
              浏览
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
          <div className="space-y-0.5">
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
                className={`${inputClass} w-full`}
              >
                {Array.from({ length: 5 }, (_, i) => currentYear - 2 + i).map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">月份</label>
              <select
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                className={`${inputClass} w-full`}
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
                className={`${inputClass} w-full`}
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

        {/* Sync options — header mapping & ledger */}
        <div className="border-t border-slate-100 pt-4 space-y-3">
          <div className="flex items-start gap-3">
            <button
              role="switch"
              aria-checked={applyHeaderMapping}
              onClick={() => setApplyHeaderMapping(!applyHeaderMapping)}
              className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors shrink-0 mt-0.5 ${
                applyHeaderMapping ? "bg-blue-600" : "bg-slate-200"
              }`}
            >
              <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                applyHeaderMapping ? "translate-x-4" : "translate-x-0.5"
              }`} />
            </button>
            <div>
              <div className="text-sm text-slate-700">应用工时表头映射</div>
              <div className="text-xs text-slate-400 mt-0.5">对工作效率表应用列名映射配置</div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <button
              role="switch"
              aria-checked={useLedger}
              onClick={() => setUseLedger(!useLedger)}
              className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors shrink-0 mt-0.5 ${
                useLedger ? "bg-blue-600" : "bg-slate-200"
              }`}
            >
              <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                useLedger ? "translate-x-4" : "translate-x-0.5"
              }`} />
            </button>
            <div>
              <div className="text-sm text-slate-700">应用台账匹配</div>
              <div className="text-xs text-slate-400 mt-0.5">使用设备台账标准化设备名称</div>
            </div>
          </div>
        </div>
      </div>

      <button
        onClick={handleSync}
        disabled={!inputDir || loading || dataTypes.length === 0}
        className={btnPrimaryClass}
      >
        {loading && (
          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {loading ? "同步中..." : "开始同步"}
      </button>

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

      {error && (
        <div className="flex items-start gap-2 text-xs text-red-700 bg-red-50 rounded-md px-2.5 py-1.5">
          <XCircleIcon />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
