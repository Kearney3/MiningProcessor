import { useState, useCallback, useEffect } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { invoke } from "@tauri-apps/api/core";
import type { BridgeProp, BatchProgress } from "../../lib/types";
import { useToast } from "../Toast";
import { inputClass, btnSecondaryClass, btnPrimaryClass } from "../../lib/ui-classes";
import { useLastDirectory } from "../../hooks/useLastDirectory";
import {
  ChevronDownIcon, PlayIcon, FileIcon, CheckCircleIcon, XCircleIcon, AlertTriangleIcon,
  ColumnsIcon, FilterIcon, BotIcon,
} from "../../lib/icons";

// ── Shared UI ────────────────────────────────────────────

function PathInput({
  value, onChange, placeholder, defaultPath, onFileSelected,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const browse = async () => {
    const selected = await open({
      directory: false, multiple: false, defaultPath,
      filters: [{ name: "Excel", extensions: ["xlsx", "xls"] }],
    });
    if (selected) {
      const p = selected as string;
      onChange(p);
      onFileSelected?.(p);
    }
  };
  return (
    <div className="flex gap-2">
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`${inputClass} flex-1 ${value === "" ? "border-amber-300 bg-amber-50/30" : ""}`} />
      <button onClick={browse} className={btnSecondaryClass} title="选择文件"><FileIcon /></button>
    </div>
  );
}

function StyledSelect({ value, onChange, options, placeholder }: {
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string }[];
  placeholder?: string;
}) {
  return (
    <div className="relative">
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className={`${inputClass} appearance-none pr-8 w-full`}>
        {placeholder && <option value="" disabled>{placeholder}</option>}
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none"><ChevronDownIcon /></div>
    </div>
  );
}

function StepIndicator({ current, labels }: { current: number; labels: string[] }) {
  return (
    <div className="flex items-center gap-1 mb-6">
      {labels.map((label, i) => {
        const idx = i + 1;
        const done = idx < current;
        const active = idx === current;
        return (
          <div key={idx} className="flex items-center">
            {i > 0 && <div className={`w-8 h-px mx-1 ${done ? "bg-blue-500" : "bg-slate-200"}`} />}
            <div className="flex items-center gap-1.5">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                done ? "bg-blue-500 text-white" : active ? "bg-blue-100 text-blue-700 ring-2 ring-blue-300" : "bg-slate-100 text-slate-400"
              }`}>{done ? "✓" : idx}</div>
              <span className={`text-xs ${active ? "text-blue-700 font-medium" : done ? "text-slate-600" : "text-slate-400"}`}>{label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Auto-detect column mapping ───────────────────────────

const COLUMN_HINTS: Record<string, string[]> = {
  content_column: ["维修内容", "维修描述", "故障描述", "内容", "维修记录"],
  category_column: ["大类", "分类", "故障大类", "系统分类"],
  minor_column: ["小类", "子分类", "故障小类", "详细分类"],
  status_column: ["分类方式", "标注方式", "分类状态", "标注状态", "分类来源"],
};

function autoDetectColumn(columns: string[], field: string): string {
  const hints = COLUMN_HINTS[field] || [];
  for (const hint of hints) {
    if (columns.includes(hint)) return hint;
  }
  return columns[0] || "";
}

// ── Page Component ───────────────────────────────────────

interface PreviewData {
  columns: string[];
  rows: number;
  sample: Record<string, unknown>[];
}

export function LLMLabelingPage({ bridge, progress, setProgress }: {
  bridge: BridgeProp;
  progress: BatchProgress | null;
  setProgress: (p: BatchProgress | null) => void;
}) {
  const { notify } = useToast();
  const { initialDir } = useLastDirectory(bridge);

  // Clear stale progress on mount
  useEffect(() => {
    setProgress(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Step state
  const [step, setStep] = useState(1);

  // Step 1: File & Sheet
  const [filePath, setFilePath] = useState("");
  const [sheets, setSheets] = useState<string[]>([]);
  const [sheetName, setSheetName] = useState("");
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Step 2: Column mapping
  const [contentCol, setContentCol] = useState("维修内容");
  const [categoryCol, setCategoryCol] = useState("大类");
  const [minorCol, setMinorCol] = useState("小类");
  const [statusCol, setStatusCol] = useState("分类方式");

  // Step 3: Filter & export
  const [filterValues, setFilterValues] = useState<string[]>(["待确认"]);
  const [filterInput, setFilterInput] = useState("待确认");
  const [exportMode, setExportMode] = useState<"details" | "statistics">("statistics");

  // Step 4: Execution
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    input_rows: number;
    target_rows: number;
    llm_completed: number;
    skipped_rows: number;
    output: string;
    export_mode: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ── Load preview for selected sheet ──
  const loadPreview = useCallback(async (path: string, sheet: string) => {
    if (!path || !sheet) return;
    setLoadingPreview(true);
    setPreview(null);
    try {
      const data = await bridge.call<PreviewData>("preview_excel_columns", { path, sheet_name: sheet });
      setPreview(data);
      if (data.columns.length > 0) {
        setContentCol(autoDetectColumn(data.columns, "content_column"));
        setCategoryCol(autoDetectColumn(data.columns, "category_column"));
        setMinorCol(autoDetectColumn(data.columns, "minor_column"));
        setStatusCol(autoDetectColumn(data.columns, "status_column"));
      }
    } catch (e) {
      setPreview(null);
      notify(`预览失败: ${e}`, "error");
    } finally {
      setLoadingPreview(false);
    }
  }, [bridge.call, notify]);

  // ── Fetch sheet list when file is selected ──
  const handleFileSelected = useCallback(async (path: string) => {
    setSheets([]);
    setSheetName("");
    setPreview(null);
    try {
      const res = await bridge.call<{ sheets: string[] }>("preview_excel_sheets", { path });
      const list = res.sheets || [];
      setSheets(list);
      // Auto-select "维修明细" if present, otherwise first sheet
      const defaultSheet = list.includes("维修明细") ? "维修明细" : (list[0] || "");
      setSheetName(defaultSheet);
      if (defaultSheet) {
        loadPreview(path, defaultSheet);
      }
    } catch (e) {
      notify(`读取 Sheet 列表失败: ${e}`, "error");
    }
  }, [bridge.call, loadPreview, notify]);

  const handleSheetChange = (sheet: string) => {
    setSheetName(sheet);
    if (filePath && sheet) {
      loadPreview(filePath, sheet);
    }
  };

  // ── Collect unique values from status column for filter suggestions ──
  const statusValues = preview?.sample
    ? [...new Set(preview.sample.map((r) => String(r[statusCol] || "")).filter(Boolean))]
    : [];

  const handleAddFilter = () => {
    const vals = filterInput.split(",").map((v) => v.trim()).filter(Boolean);
    const newVals = [...new Set([...filterValues, ...vals])];
    setFilterValues(newVals);
    setFilterInput("");
  };

  const handleRemoveFilter = (val: string) => {
    setFilterValues((prev) => prev.filter((v) => v !== val));
  };

  // ── Cancel labeling ──
  const handleCancel = async () => {
    try {
      await invoke("cancel_task");
      notify("正在取消...", "info");
    } catch {
      // ignore
    }
  };

  // ── Execute labeling ──
  const handleExecute = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress(null);
    try {
      const res = await bridge.call<{
        input_rows: number;
        target_rows: number;
        llm_completed: number;
        skipped_rows: number;
        output: string;
        export_mode: string;
        cancelled?: boolean;
      }>("process_maintenance_llm", {
        path: filePath,
        content_column: contentCol,
        category_column: categoryCol,
        minor_column: minorCol,
        status_column: statusCol,
        filter_values: filterValues.length > 0 ? filterValues : undefined,
        export_mode: exportMode,
      });
      if (res.cancelled) {
        setError(`已取消，已完成 ${res.llm_completed} 条（可断点续跑）`);
      } else {
        setResult(res);
        setStep(4);
        notify("LLM 标注完成", "success");
      }
    } catch (e) {
      setError(String(e));
      notify(`LLM 标注失败: ${e}`, "error");
    } finally {
      setLoading(false);
      setProgress(null);
    }
  };

  // ── Column selector helper ──
  const colOptions = (preview?.columns || []).map((c) => ({ label: c, value: c }));

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
          <BotIcon /> LLM 标注
        </h2>
        <p className="text-sm text-slate-500 mt-0.5">对维修明细进行大模型智能分类标注</p>
      </div>

      <StepIndicator current={step} labels={["选择文件", "列映射", "筛选与导出", "执行标注"]} />

      {/* ── Step 1: File Selection ── */}
      <div className={`bg-white rounded-lg border p-4 ${step === 1 ? "border-blue-200" : "border-slate-200"}`}>
        <h3 className="text-sm font-medium text-slate-700 mb-3">1. 选择文件</h3>
        <PathInput value={filePath} onChange={setFilePath} placeholder="选择维修明细 Excel 文件..."
          defaultPath={initialDir} onFileSelected={handleFileSelected} />
        {filePath === "" && (
          <div className="mt-1.5 flex items-center gap-1 text-xs text-amber-600"><AlertTriangleIcon /> 请先选择输入文件</div>
        )}
        {sheets.length > 0 && (
          <div className="mt-3">
            <label className="text-xs font-medium text-slate-500 mb-1.5 block">选择 Sheet</label>
            <div className="flex gap-2 items-center">
              <div className="relative flex-1 max-w-xs">
                <select value={sheetName} onChange={(e) => handleSheetChange(e.target.value)}
                  className={`${inputClass} appearance-none pr-8 w-full`}>
                  {sheets.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none"><ChevronDownIcon /></div>
              </div>
              <button onClick={() => filePath && sheetName && loadPreview(filePath, sheetName)}
                disabled={!filePath || !sheetName || loadingPreview} className={`${btnSecondaryClass} text-xs`}>
                {loadingPreview ? "加载中..." : "刷新预览"}
              </button>
            </div>
          </div>
        )}
        {preview && (
          <div className="mt-3 text-xs text-slate-500">
            共 <span className="font-medium text-slate-700">{preview.rows}</span> 行，
            <span className="font-medium text-slate-700">{preview.columns.length}</span> 列：
            {preview.columns.join(", ")}
          </div>
        )}
        {preview && step === 1 && (
          <button onClick={() => setStep(2)} className={`${btnPrimaryClass} mt-3`}>下一步：列映射</button>
        )}
      </div>

      {/* ── Step 2: Column Mapping ── */}
      {step >= 2 && (
        <div className={`bg-white rounded-lg border p-4 ${step === 2 ? "border-blue-200" : "border-slate-200"}`}>
          <h3 className="text-sm font-medium text-slate-700 mb-3 flex items-center gap-2">
            <ColumnsIcon /> 2. 列映射
          </h3>
          <p className="text-xs text-slate-500 mb-3">指定各列的用途，系统已自动识别常见列名</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">维修内容列 *</label>
              <StyledSelect value={contentCol} onChange={setContentCol} options={colOptions} />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">大类列</label>
              <StyledSelect value={categoryCol} onChange={setCategoryCol} options={colOptions} />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">小类列</label>
              <StyledSelect value={minorCol} onChange={setMinorCol} options={colOptions} />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 mb-1 block">分类方式列</label>
              <StyledSelect value={statusCol} onChange={setStatusCol} options={colOptions} />
            </div>
          </div>
          {preview && preview.sample.length > 0 && (
            <div className="mt-3 border border-slate-100 rounded-md overflow-auto max-h-40">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50">
                    <th className="px-2 py-1.5 text-left text-slate-500 font-medium">{contentCol}</th>
                    <th className="px-2 py-1.5 text-left text-slate-500 font-medium">{categoryCol}</th>
                    <th className="px-2 py-1.5 text-left text-slate-500 font-medium">{minorCol}</th>
                    <th className="px-2 py-1.5 text-left text-slate-500 font-medium">{statusCol}</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.sample.map((row, i) => (
                    <tr key={i} className="border-t border-slate-50">
                      <td className="px-2 py-1 text-slate-700 max-w-[200px] truncate">{String(row[contentCol] || "")}</td>
                      <td className="px-2 py-1 text-slate-600">{String(row[categoryCol] || "")}</td>
                      <td className="px-2 py-1 text-slate-600">{String(row[minorCol] || "")}</td>
                      <td className="px-2 py-1 text-slate-600">{String(row[statusCol] || "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <button onClick={() => setStep(1)} className={btnSecondaryClass}>上一步</button>
            <button onClick={() => setStep(3)} className={btnPrimaryClass}>下一步：筛选与导出</button>
          </div>
        </div>
      )}

      {/* ── Step 3: Filter & Export ── */}
      {step >= 3 && (
        <div className={`bg-white rounded-lg border p-4 ${step === 3 ? "border-blue-200" : "border-slate-200"}`}>
          <h3 className="text-sm font-medium text-slate-700 mb-3 flex items-center gap-2">
            <FilterIcon /> 3. 筛选与导出
          </h3>

          {/* Filter values */}
          <div className="mb-4">
            <label className="text-xs font-medium text-slate-500 mb-1.5 block">
              用于 LLM 标注的「{statusCol}」值
            </label>
            <p className="text-xs text-slate-400 mb-2">只有分类方式匹配这些值的记录会被发送给 LLM 标注，留空则标注所有记录</p>
            <div className="flex gap-2 mb-2">
              <input type="text" value={filterInput} onChange={(e) => setFilterInput(e.target.value)}
                placeholder='输入值，如"待确认"，多个用逗号分隔'
                className={`${inputClass} flex-1`}
                onKeyDown={(e) => e.key === "Enter" && handleAddFilter()} />
              <button onClick={handleAddFilter} className={btnSecondaryClass}>添加</button>
            </div>
            {statusValues.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                <span className="text-xs text-slate-400">检测到的值：</span>
                {statusValues.map((v) => (
                  <button key={v} onClick={() => {
                    if (!filterValues.includes(v)) setFilterValues((prev) => [...prev, v]);
                  }}
                    className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${
                      filterValues.includes(v)
                        ? "bg-blue-50 border-blue-200 text-blue-700"
                        : "border-slate-200 text-slate-500 hover:border-blue-300 hover:text-blue-600"
                    }`}>
                    {v}
                  </button>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-1.5">
              {filterValues.map((v) => (
                <span key={v} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
                  {v}
                  <button onClick={() => handleRemoveFilter(v)} className="text-blue-400 hover:text-blue-600">&times;</button>
                </span>
              ))}
              {filterValues.length === 0 && <span className="text-xs text-slate-400">将标注所有记录</span>}
            </div>
          </div>

          {/* Export mode */}
          <div>
            <label className="text-xs font-medium text-slate-500 mb-1.5 block">导出方式</label>
            <div className="space-y-2">
              <label className="flex items-start gap-2.5 cursor-pointer p-2 rounded-md border border-slate-200 hover:border-blue-200 transition-colors">
                <input type="radio" name="export" value="details" checked={exportMode === "details"}
                  onChange={() => setExportMode("details")} className="mt-0.5" />
                <div>
                  <span className="text-sm text-slate-700 font-medium">导出标注明细</span>
                  <p className="text-xs text-slate-500 mt-0.5">只输出标注后的维修明细 Excel（含 LLM 大类、小类、置信度、理由列）</p>
                </div>
              </label>
              <label className="flex items-start gap-2.5 cursor-pointer p-2 rounded-md border border-slate-200 hover:border-blue-200 transition-colors">
                <input type="radio" name="export" value="statistics" checked={exportMode === "statistics"}
                  onChange={() => setExportMode("statistics")} className="mt-0.5" />
                <div>
                  <span className="text-sm text-slate-700 font-medium">导出汇总统计</span>
                  <p className="text-xs text-slate-500 mt-0.5">输出包含维修明细 + 按大类/小类/设备/月份统计的完整报告</p>
                </div>
              </label>
            </div>
          </div>

          <div className="mt-4 flex gap-2">
            <button onClick={() => setStep(2)} className={btnSecondaryClass}>上一步</button>
            <button onClick={handleExecute} disabled={loading || !filePath}
              className={`${btnPrimaryClass} flex items-center gap-2`}>
              {loading ? (
                <>
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  标注中...
                </>
              ) : (
                <><PlayIcon /> 开始标注</>
              )}
            </button>
            {loading && (
              <button onClick={handleCancel}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors">
                取消
              </button>
            )}
          </div>

          {/* Progress bar */}
          {loading && progress && (
            <div className="mt-3 space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-600 font-medium">
                  {progress.stage === "llm_labeling" ? "LLM 标注" : progress.stage}
                </span>
                <span className="text-slate-500 tabular-nums">
                  {progress.current}/{progress.total} 条 ({progress.percent}%)
                </span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${Math.max(1, progress.percent)}%` }}
                />
              </div>
              {progress.detail && (
                <p className="text-xs text-slate-400 truncate">{progress.detail}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Step 4: Results ── */}
      {step >= 4 && (
        <div className={`bg-white rounded-lg border p-4 ${result ? "border-emerald-200" : error ? "border-red-200" : "border-slate-200"}`}>
          <h3 className="text-sm font-medium text-slate-700 mb-3">4. 标注结果</h3>
          {result && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 rounded-md px-3 py-2">
                <CheckCircleIcon />
                标注完成
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-50 rounded-md px-3 py-2">
                  <span className="text-slate-500">输入行数</span>
                  <p className="text-slate-800 font-medium text-lg">{result.input_rows}</p>
                </div>
                <div className="bg-slate-50 rounded-md px-3 py-2">
                  <span className="text-slate-500">符合条件</span>
                  <p className="text-slate-800 font-medium text-lg">{result.target_rows}</p>
                </div>
                <div className="bg-blue-50 rounded-md px-3 py-2">
                  <span className="text-blue-600">LLM 标注成功</span>
                  <p className="text-blue-800 font-medium text-lg">{result.llm_completed}</p>
                </div>
                <div className="bg-amber-50 rounded-md px-3 py-2">
                  <span className="text-amber-600">跳过</span>
                  <p className="text-amber-800 font-medium text-lg">{result.skipped_rows}</p>
                </div>
              </div>
              <div className="text-xs text-slate-500">
                导出方式: <span className="font-medium text-slate-700">{result.export_mode === "details" ? "标注明细" : "汇总统计"}</span>
              </div>
              <div className="text-xs text-slate-500">
                输出文件: <span className="font-medium text-slate-700 break-all">{result.output}</span>
              </div>
              <button onClick={() => { setStep(1); setResult(null); setFilePath(""); setPreview(null); }}
                className={`${btnSecondaryClass} mt-2`}>
                继续标注其他文件
              </button>
            </div>
          )}
          {error && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs text-red-700 bg-red-50 rounded-md px-3 py-2">
                <XCircleIcon /> {error}
              </div>
              <button onClick={() => { setError(null); setStep(3); }} className={btnSecondaryClass}>
                返回修改
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
