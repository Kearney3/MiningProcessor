import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import type { SyncResult } from "../../lib/types";

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

const ALL_TYPES = [
  { id: "fuel", label: "油耗数据", icon: "⛽", color: "amber" },
  { id: "production", label: "生产数据", icon: "🏭", color: "blue" },
  { id: "electrical", label: "电力消耗", icon: "⚡", color: "yellow" },
  { id: "work_efficiency", label: "工时数据", icon: "⏱️", color: "violet" },
  { id: "operation", label: "设备运行", icon: "🔧", color: "slate" },
] as const;

const COLOR_MAP: Record<string, { border: string; bg: string; bgActive: string; ring: string; text: string }> = {
  amber: { border: "border-amber-300", bg: "bg-amber-50", bgActive: "bg-amber-100", ring: "ring-amber-200", text: "text-amber-700" },
  blue: { border: "border-blue-300", bg: "bg-blue-50", bgActive: "bg-blue-100", ring: "ring-blue-200", text: "text-blue-700" },
  yellow: { border: "border-yellow-300", bg: "bg-yellow-50", bgActive: "bg-yellow-100", ring: "ring-yellow-200", text: "text-yellow-700" },
  violet: { border: "border-violet-300", bg: "bg-violet-50", bgActive: "bg-violet-100", ring: "ring-violet-200", text: "text-violet-700" },
  slate: { border: "border-slate-300", bg: "bg-slate-50", bgActive: "bg-slate-100", ring: "ring-slate-200", text: "text-slate-700" },
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
    <div className="max-w-3xl mx-auto">
      <h2 className="text-lg font-semibold text-slate-800 mb-4">数据同步</h2>

      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 space-y-5">
        {/* 路径 */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">数据目录</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={inputDir}
              onChange={(e) => setInputDir(e.target.value)}
              placeholder="选择包含已处理数据的文件夹"
              className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-500"
            />
            <button
              onClick={browse}
              className="shrink-0 text-sm bg-slate-100 hover:bg-slate-200 text-slate-600 px-4 py-2 rounded-lg transition-colors"
            >
              浏览
            </button>
          </div>
        </div>

        {/* 同步模式 — pill buttons */}
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1.5 block">同步模式</label>
          <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden">
            {([
              { value: "api" as const, label: "API 模式", icon: "🌐", desc: "HTTP 推送" },
              { value: "database" as const, label: "数据库模式", icon: "🗄️", desc: "直连写入" },
            ]).map((m, i) => (
              <button
                key={m.value}
                onClick={() => setMode(m.value)}
                className={`flex items-center gap-2 px-5 py-2.5 text-sm transition-colors ${
                  i === 1 ? "border-l border-slate-200" : ""
                } ${
                  mode === m.value
                    ? "bg-cyan-600 text-white"
                    : "bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                <span>{m.icon}</span>
                <div className="text-left">
                  <div className="font-medium leading-tight">{m.label}</div>
                  <div className={`text-xs leading-tight ${mode === m.value ? "text-cyan-100" : "text-slate-400"}`}>
                    {m.desc}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* 数据类型 — styled cards with select-all */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-medium text-slate-500">数据类型</label>
            <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleSelectAll}
                className="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500/30"
              />
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
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg border text-left transition-all ${
                    active
                      ? `${c.border} ${c.bgActive} ring-1 ${c.ring}`
                      : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <span className="text-base leading-none">{t.icon}</span>
                  <span className={`text-sm font-medium ${active ? c.text : "text-slate-600"}`}>
                    {t.label}
                  </span>
                  {active && (
                    <svg className={`ml-auto w-4 h-4 ${c.text}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* 试运行 — toggle with explanation */}
        <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
          <label className="relative inline-flex items-center cursor-pointer shrink-0 mt-0.5">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-slate-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-cyan-500/30 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-600"></div>
          </label>
          <div>
            <div className="text-sm font-medium text-slate-700">试运行</div>
            <div className="text-xs text-slate-400 mt-0.5">仅预览同步内容，不实际推送到 MineBase</div>
          </div>
        </div>
      </div>

      <button
        onClick={handleSync}
        disabled={!inputDir || loading || dataTypes.length === 0}
        className={`text-sm font-medium px-6 py-2.5 rounded-lg transition-colors ${
          !inputDir || loading || dataTypes.length === 0
            ? "bg-slate-100 text-slate-400 cursor-not-allowed"
            : "bg-cyan-600 hover:bg-cyan-700 text-white shadow-sm"
        }`}
      >
        {loading ? "同步中..." : "开始同步"}
      </button>

      {/* 结果 */}
      {result && (
        <div className="mt-4 bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
            <h3 className="text-sm font-semibold text-slate-700">同步结果</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="px-5 py-2.5 font-medium">数据类型</th>
                <th className="py-2.5 text-right font-medium">成功</th>
                <th className="py-2.5 text-right font-medium">跳过</th>
                <th className="py-2.5 pr-5 text-right font-medium">失败</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.results).map(([type, stats]) => {
                const hasFailure = stats.failed > 0;
                return (
                  <tr key={type} className="border-t border-slate-100">
                    <td className="px-5 py-2.5 text-slate-700 font-medium">
                      {TYPE_LABEL_MAP[type] ?? type}
                    </td>
                    <td className="py-2.5 text-right">
                      <span className="inline-flex items-center gap-1 text-green-600">
                        {stats.success > 0 && (
                          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500"></span>
                        )}
                        {stats.success}
                      </span>
                    </td>
                    <td className="py-2.5 text-right text-slate-400">{stats.skipped}</td>
                    <td className="py-2.5 pr-5 text-right">
                      <span className={`inline-flex items-center gap-1 ${hasFailure ? "text-red-600" : "text-slate-400"}`}>
                        {hasFailure && (
                          <span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500"></span>
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
        <div className="mt-4 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-4 py-3">
          <span className="shrink-0 mt-0.5">✕</span>
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
