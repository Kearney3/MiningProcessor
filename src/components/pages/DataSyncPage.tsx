import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import type { SyncResult } from "../../lib/types";

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

// ═══════════════════════════════════════
// SVG Icon Components
// ═══════════════════════════════════════

const FuelSvgIcon = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 22V6a2 2 0 012-2h6a2 2 0 012 2v16" />
    <path d="M13 10h2a2 2 0 012 2v2a2 2 0 002 2h0a2 2 0 002-2V9.83a2 2 0 00-.59-1.42L18 6" />
    <path d="M3 22h10" />
    <path d="M7 10V6" />
    <path d="M11 10V6" />
  </svg>
);

const ProductionSvgIcon = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
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
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
  </svg>
);

const WorktimeSvgIcon = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

const OperationSvgIcon = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" />
  </svg>
);

const GlobeSvgIcon = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
  </svg>
);

const DatabaseSvgIcon = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </svg>
);

const FolderSvgIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
    <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
  </svg>
);

const CheckSvgIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
  </svg>
);

const MinusSvgIcon = () => (
  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
  </svg>
);

const CheckCircleSvgIcon = () => (
  <svg className="w-4 h-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
  </svg>
);

const XCircleSvgIcon = () => (
  <svg className="w-4 h-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
  </svg>
);

// ═══════════════════════════════════════
// Constants
// ═══════════════════════════════════════

const ALL_TYPES = [
  { id: "fuel", label: "油耗数据", icon: <FuelSvgIcon />, color: "amber" },
  { id: "production", label: "生产数据", icon: <ProductionSvgIcon />, color: "blue" },
  { id: "electrical", label: "电力消耗", icon: <ElectricalSvgIcon />, color: "yellow" },
  { id: "work_efficiency", label: "工时数据", icon: <WorktimeSvgIcon />, color: "violet" },
  { id: "operation", label: "设备运行", icon: <OperationSvgIcon />, color: "slate" },
] as const;

const COLOR_MAP: Record<string, { border: string; bg: string; bgActive: string; ring: string; text: string; borderActive: string }> = {
  amber:  { border: "border-amber-200", bg: "bg-amber-50", bgActive: "bg-amber-50", ring: "ring-amber-200", text: "text-amber-600", borderActive: "border-amber-500" },
  blue:   { border: "border-blue-200", bg: "bg-blue-50", bgActive: "bg-blue-50", ring: "ring-blue-200", text: "text-blue-600", borderActive: "border-blue-500" },
  yellow: { border: "border-yellow-200", bg: "bg-yellow-50", bgActive: "bg-yellow-50", ring: "ring-yellow-200", text: "text-yellow-600", borderActive: "border-yellow-500" },
  violet: { border: "border-violet-200", bg: "bg-violet-50", bgActive: "bg-violet-50", ring: "ring-violet-200", text: "text-violet-600", borderActive: "border-violet-500" },
  slate:  { border: "border-slate-200", bg: "bg-slate-50", bgActive: "bg-slate-50", ring: "ring-slate-200", text: "text-slate-600", borderActive: "border-slate-500" },
};

const TYPE_LABEL_MAP: Record<string, string> = Object.fromEntries(ALL_TYPES.map((t) => [t.id, t.label]));

export function DataSyncPage({ bridge }: { bridge: BridgeProp }) {
  const [inputDir, setInputDir] = useState("");
  const [mode, setMode] = useState<"api" | "database">("api");
  const [dataTypes, setDataTypes] = useState<string[]>(["fuel", "production", "electrical", "work_efficiency"]);
  const [dryRun, setDryRun] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const allSelected = ALL_TYPES.length === dataTypes.length;
  const someSelected = dataTypes.length > 0 && !allSelected;

  const toggleSelectAll = () => {
    if (allSelected) {
      setDataTypes([]);
    } else {
      setDataTypes(ALL_TYPES.map((t) => t.id));
    }
  };

  const toggleType = (id: string) => {
    setDataTypes((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
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
      });
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const browse = async () => {
    const selected = await open({ directory: true, multiple: false });
    if (selected) setInputDir(selected as string);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-slate-800">数据同步</h2>
        <p className="text-sm text-slate-500 mt-0.5">将处理后的数据同步至 MineBase</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-5">
        {/* Path */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">数据目录</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={inputDir}
              onChange={(e) => setInputDir(e.target.value)}
              placeholder="选择包含已处理数据的文件夹"
              className="input flex-1"
            />
            <button
              onClick={browse}
              className="shrink-0 flex items-center gap-1.5 text-sm bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-2 rounded-lg transition-colors"
            >
              <FolderSvgIcon />
              浏览
            </button>
          </div>
        </div>

        {/* Sync mode -- pill segmented control */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">同步模式</label>
          <div className="inline-flex rounded-lg bg-slate-100 p-1 gap-0.5">
            {([
              { value: "api" as const, label: "API 模式", desc: "HTTP 推送", icon: <GlobeSvgIcon /> },
              { value: "database" as const, label: "数据库模式", desc: "直连写入", icon: <DatabaseSvgIcon /> },
            ]).map((m) => (
              <button
                key={m.value}
                onClick={() => setMode(m.value)}
                className={`flex items-center gap-2.5 px-5 py-2.5 text-sm rounded-md transition-all ${
                  mode === m.value
                    ? "bg-white text-slate-800 shadow-sm font-medium"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                <span className={mode === m.value ? "text-cyan-600" : "text-slate-400"}>{m.icon}</span>
                <div className="text-left">
                  <div className="leading-tight">{m.label}</div>
                  <div className={`text-xs leading-tight ${mode === m.value ? "text-slate-400" : "text-slate-400"}`}>
                    {m.desc}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Data type cards */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-medium text-slate-500">数据类型</label>
            <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
              <button
                type="button"
                role="checkbox"
                aria-checked={allSelected ? "true" : someSelected ? "mixed" : "false"}
                onClick={toggleSelectAll}
                className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                  allSelected
                    ? "bg-cyan-600 border-cyan-600"
                    : someSelected
                      ? "bg-white border-cyan-400"
                      : "bg-white border-slate-300 hover:border-slate-400"
                }`}
              >
                {allSelected && <CheckSvgIcon className="w-3 h-3 text-white" />}
                {someSelected && <MinusSvgIcon />}
              </button>
              全选
            </label>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {ALL_TYPES.map((t) => {
              const active = dataTypes.includes(t.id);
              const c = COLOR_MAP[t.color];
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => toggleType(t.id)}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-all ${
                    active
                      ? `border-2 ${c.borderActive} ${c.bgActive} ring-1 ${c.ring}`
                      : "border border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <span className={`shrink-0 ${active ? c.text : "text-slate-400"}`}>{t.icon}</span>
                  <span className={`text-sm font-medium ${active ? c.text : "text-slate-600"}`}>
                    {t.label}
                  </span>
                  {active && (
                    <span className={`ml-auto ${c.text}`}>
                      <CheckSvgIcon />
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Dry run toggle */}
        <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
          <button
            role="switch"
            aria-checked={dryRun}
            onClick={() => setDryRun(!dryRun)}
            className={`relative inline-flex h-6 w-10 items-center rounded-full transition-colors shrink-0 mt-0.5 ${
              dryRun ? "bg-cyan-600" : "bg-slate-300"
            }`}
          >
            <span
              className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
                dryRun ? "translate-x-5" : "translate-x-1"
              }`}
            />
          </button>
          <div>
            <div className="text-sm font-medium text-slate-700">试运行</div>
            <div className="text-xs text-slate-400 mt-0.5">仅预览同步内容，不实际推送到 MineBase</div>
          </div>
        </div>
      </div>

      <button
        onClick={handleSync}
        disabled={!inputDir || loading || dataTypes.length === 0}
        className={`btn-primary flex items-center gap-2 ${
          !inputDir || loading || dataTypes.length === 0
            ? "!bg-slate-100 !text-slate-400 cursor-not-allowed"
            : "bg-cyan-600 hover:bg-cyan-700 text-white shadow-sm"
        }`}
      >
        {loading && (
          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {loading ? "同步中..." : "开始同步"}
      </button>

      {/* Result table -- zebra-striped with status badges */}
      {result && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden animate-fade-in">
          <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
            <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
              <CheckCircleSvgIcon />
              同步结果
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="table-header text-left">
                <th className="px-5 py-2.5">数据类型</th>
                <th className="py-2.5 text-right">成功</th>
                <th className="py-2.5 text-right">跳过</th>
                <th className="py-2.5 pr-5 text-right">失败</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.results).map(([type, stats], idx) => {
                const hasFailure = stats.failed > 0;
                return (
                  <tr key={type} className={`table-row ${idx % 2 === 0 ? "bg-white" : "bg-slate-50/50"}`}>
                    <td className="px-5 py-2.5 text-slate-700 font-medium">
                      {TYPE_LABEL_MAP[type] ?? type}
                    </td>
                    <td className="py-2.5 text-right">
                      <span className="badge badge-success">
                        {stats.success > 0 && (
                          <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1" />
                        )}
                        {stats.success}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      <span className="text-slate-400">{stats.skipped}</span>
                    </td>
                    <td className="py-2.5 pr-5 text-right">
                      <span className={`badge ${hasFailure ? "badge-error" : "badge-info"}`}>
                        {hasFailure && (
                          <span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500 mr-1" />
                        )}
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
        <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3 animate-fade-in">
          <XCircleSvgIcon />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
