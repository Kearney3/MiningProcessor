import { useState, useEffect, useCallback, useMemo, useRef } from "react";

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

type LoadMap = Record<string, number>;

const PAGE_SIZE = 20;

/* ------------------------------------------------------------------ */
/*  Toast                                                              */
/* ------------------------------------------------------------------ */

function Toast({
  message,
  kind,
  onClose,
}: {
  message: string;
  kind: "success" | "error" | "info";
  onClose: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onClose, 2500);
    return () => clearTimeout(t);
  }, [onClose]);

  const bg =
    kind === "success"
      ? "bg-emerald-600"
      : kind === "error"
        ? "bg-red-600"
        : "bg-slate-700";

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 ${bg} text-white text-sm px-5 py-2.5 rounded-lg shadow-lg animate-[fadeIn_.2s_ease-out]`}
    >
      {message}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Confirm dialog                                                     */
/* ------------------------------------------------------------------ */

function ConfirmDialog({
  title,
  body,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  body: React.ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl p-6 w-[400px] max-w-[90vw]">
        <h3 className="text-base font-semibold text-slate-800 mb-2">{title}</h3>
        <div className="text-sm text-slate-600 mb-5">{body}</div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="text-sm px-4 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="text-sm px-4 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium"
          >
            {confirmLabel ?? "确定"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Restore-defaults dialog                                            */
/* ------------------------------------------------------------------ */

function RestoreDefaultsDialog({
  onPick,
  onCancel,
}: {
  onPick: (version: "new" | "old") => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl p-6 w-[400px] max-w-[90vw]">
        <h3 className="text-base font-semibold text-slate-800 mb-2">恢复默认配置</h3>
        <p className="text-sm text-slate-600 mb-5">
          选择要恢复的默认版本：
        </p>
        <div className="flex flex-col gap-2 mb-5">
          <button
            onClick={() => onPick("new")}
            className="w-full text-left text-sm px-4 py-3 rounded-lg border border-slate-200 hover:border-cyan-400 hover:bg-cyan-50 transition-colors"
          >
            <span className="font-medium text-slate-700">新版配置</span>
            <span className="block text-xs text-slate-400 mt-0.5">当前版本的出厂默认值</span>
          </button>
          <button
            onClick={() => onPick("old")}
            className="w-full text-left text-sm px-4 py-3 rounded-lg border border-slate-200 hover:border-amber-400 hover:bg-amber-50 transition-colors"
          >
            <span className="font-medium text-slate-700">旧版配置</span>
            <span className="block text-xs text-slate-400 mt-0.5">兼容旧版系统的默认值</span>
          </button>
        </div>
        <div className="flex justify-end">
          <button
            onClick={onCancel}
            className="text-sm px-4 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

export function LoadConfigPage({ bridge }: { bridge: BridgeProp }) {
  const [loadMap, setLoadMap] = useState<LoadMap>({});
  const [persistedMap, setPersistedMap] = useState<LoadMap>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; kind: "success" | "error" | "info" } | null>(null);
  const [newName, setNewName] = useState("");
  const [newValue, setSetValue] = useState("");

  // selection
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // pagination
  const [page, setPage] = useState(0);

  // dialogs
  const [confirmDeleteDialog, setConfirmDeleteDialog] = useState(false);
  const [restoreDialog, setRestoreDialog] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  /* ---- helpers --------------------------------------------------- */

  const showToast = useCallback(
    (msg: string, kind: "success" | "error" | "info" = "info") => {
      setToast({ msg, kind });
    },
    [],
  );

  const isDirty = useMemo(
    () => JSON.stringify(loadMap) !== JSON.stringify(persistedMap),
    [loadMap, persistedMap],
  );

  /* ---- data loading ---------------------------------------------- */

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await bridge.call<LoadMap>("get_device_load_map");
      const map = res || {};
      setLoadMap(map);
      setPersistedMap(map);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [bridge]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  /* ---- sorted & paginated entries -------------------------------- */

  const entries = useMemo(
    () => Object.entries(loadMap).sort((a, b) => a[0].localeCompare(b[0])),
    [loadMap],
  );

  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const pageEntries = entries.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  // clamp page when entries shrink
  useEffect(() => {
    if (page >= totalPages) setPage(Math.max(0, totalPages - 1));
  }, [page, totalPages]);

  /* ---- row edit / delete ----------------------------------------- */

  const handleUpdate = (name: string, value: string) => {
    const num = parseFloat(value);
    if (!isNaN(num)) {
      setLoadMap((prev) => ({ ...prev, [name]: num }));
    }
  };

  const handleDelete = (name: string) => {
    setLoadMap((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
    setSelected((prev) => {
      const next = new Set(prev);
      next.delete(name);
      return next;
    });
    showToast("已删除", "info");
  };

  const handleAdd = () => {
    if (!newName.trim()) return;
    const num = parseFloat(newValue);
    if (isNaN(num)) return;
    setLoadMap((prev) => ({ ...prev, [newName.trim()]: num }));
    setNewName("");
    setSetValue("");
    showToast("已添加", "success");
  };

  /* ---- selection ------------------------------------------------- */

  const pageKeys = pageEntries.map(([k]) => k);
  const allPageSelected = pageKeys.length > 0 && pageKeys.every((k) => selected.has(k));
  const somePageSelected = pageKeys.some((k) => selected.has(k)) && !allPageSelected;

  const toggleSelectAll = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allPageSelected) {
        pageKeys.forEach((k) => next.delete(k));
      } else {
        pageKeys.forEach((k) => next.add(k));
      }
      return next;
    });
  };

  const toggleRow = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleBulkDelete = () => {
    setLoadMap((prev) => {
      const next = { ...prev };
      selected.forEach((k) => delete next[k]);
      return next;
    });
    showToast(`已删除 ${selected.size} 条记录`, "success");
    setSelected(new Set());
    setConfirmDeleteDialog(false);
  };

  /* ---- apply / save --------------------------------------------- */

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      await bridge.call("apply_device_load_map", { map_data: loadMap });
      showToast("已应用（未保存）", "info");
    } catch (e) {
      setError(String(e));
      showToast("应用失败", "error");
    } finally {
      setApplying(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await bridge.call("update_device_load_map", { map_data: loadMap });
      setPersistedMap({ ...loadMap });
      showToast("已保存", "success");
    } catch (e) {
      setError(String(e));
      showToast("保存失败", "error");
    } finally {
      setSaving(false);
    }
  };

  /* ---- import / export ------------------------------------------- */

  const handleImport = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        throw new Error("JSON 格式不正确，应为 {设备名: 数值} 对象");
      }
      const imported: LoadMap = {};
      for (const [k, v] of Object.entries(parsed)) {
        const num = typeof v === "number" ? v : parseFloat(String(v));
        if (!isNaN(num)) imported[k] = num;
      }
      const count = Object.keys(imported).length;
      if (count === 0) throw new Error("未找到有效记录");
      setLoadMap((prev) => ({ ...prev, ...imported }));
      showToast(`已导入 ${count} 条记录`, "success");
    } catch (err) {
      showToast(`导入失败: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      // reset so same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleExport = () => {
    const sorted: LoadMap = {};
    entries.forEach(([k, v]) => {
      sorted[k] = v;
    });
    const blob = new Blob([JSON.stringify(sorted, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "device_load_map.json";
    a.click();
    URL.revokeObjectURL(url);
    showToast("已导出配置文件", "success");
  };

  /* ---- restore defaults ------------------------------------------ */

  const handleRestore = async (version: "new" | "old") => {
    setRestoreDialog(false);
    try {
      const defaults = await bridge.call<LoadMap>("get_default_load_map", { version });
      if (defaults && typeof defaults === "object") {
        setLoadMap(defaults);
        showToast(`已恢复${version === "new" ? "新版" : "旧版"}默认配置（未保存）`, "info");
      }
    } catch {
      showToast("获取默认配置失败", "error");
    }
  };

  /* ---- validation helper ----------------------------------------- */

  const _isValidCapacity = (v: string) => {
    const n = parseFloat(v);
    return !isNaN(n) && n > 0;
  };

  void _isValidCapacity; // used in template validation

  /* ---- render ---------------------------------------------------- */

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        加载中...
      </div>
    );
  }

  const checkboxRef = (el: HTMLInputElement | null) => {
    if (el) el.indeterminate = somePageSelected;
  };

  return (
    <div>
      {/* hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* ---- header ----------------------------------------------- */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-800">装载量配置</h2>

        {/* dirty indicator */}
        {isDirty && (
          <span className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-full px-3 py-0.5">
            已修改（未保存）
          </span>
        )}
      </div>

      {/* ---- toolbar ---------------------------------------------- */}
      <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-slate-50 rounded-xl border border-slate-200">
        {/* import / export */}
        <button
          onClick={handleImport}
          className="inline-flex items-center gap-1.5 text-sm bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 px-3 py-1.5 rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
          </svg>
          导入配置
        </button>
        <button
          onClick={handleExport}
          className="inline-flex items-center gap-1.5 text-sm bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 px-3 py-1.5 rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M17 8l-5-5-5 5M12 3v12" />
          </svg>
          导出配置
        </button>

        <div className="w-px h-5 bg-slate-300 mx-1" />

        {/* delete selected */}
        {selected.size > 0 && (
          <>
            <button
              onClick={() => setConfirmDeleteDialog(true)}
              className="inline-flex items-center gap-1.5 text-sm bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 px-3 py-1.5 rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              删除选中 ({selected.size})
            </button>
            <div className="w-px h-5 bg-slate-300 mx-1" />
          </>
        )}

        {/* restore defaults */}
        <button
          onClick={() => setRestoreDialog(true)}
          className="inline-flex items-center gap-1.5 text-sm bg-white hover:bg-slate-100 text-slate-600 border border-slate-300 px-3 py-1.5 rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a5 5 0 015 5v2M3 10l4-4M3 10l4 4" />
          </svg>
          恢复默认
        </button>

        <div className="flex-1" />

        {/* right side: reload + apply + save */}
        <button
          onClick={loadData}
          className="text-sm bg-white hover:bg-slate-100 text-slate-600 border border-slate-300 px-3 py-1.5 rounded-lg transition-colors"
        >
          重载
        </button>
        <button
          onClick={handleApply}
          disabled={applying || !isDirty}
          className={`text-sm px-4 py-1.5 rounded-lg font-medium transition-colors ${
            applying || !isDirty
              ? "bg-slate-100 text-slate-400 cursor-not-allowed"
              : "bg-amber-500 hover:bg-amber-600 text-white"
          }`}
        >
          {applying ? "应用中..." : "应用"}
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !isDirty}
          className={`text-sm px-4 py-1.5 rounded-lg font-medium transition-colors ${
            saving || !isDirty
              ? "bg-slate-100 text-slate-400 cursor-not-allowed"
              : "bg-cyan-600 hover:bg-cyan-700 text-white"
          }`}
        >
          {saving ? "保存中..." : "保存"}
        </button>
      </div>

      {/* ---- error ----------------------------------------------- */}
      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {/* ---- table ----------------------------------------------- */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="w-10 px-3 py-2.5">
                  <input
                    ref={checkboxRef}
                    type="checkbox"
                    checked={allPageSelected}
                    onChange={toggleSelectAll}
                    className="w-4 h-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500 cursor-pointer"
                  />
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">
                  设备名称
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">
                  装载量 (吨)
                </th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-slate-500 w-20">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {pageEntries.map(([name, value]) => {
                const invalid = value <= 0;
                return (
                  <tr
                    key={name}
                    className={`border-b border-slate-50 transition-colors ${
                      selected.has(name) ? "bg-cyan-50/50" : "hover:bg-slate-50/50"
                    }`}
                  >
                    <td className="w-10 px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(name)}
                        onChange={() => toggleRow(name)}
                        className="w-4 h-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500 cursor-pointer"
                      />
                    </td>
                    <td className="px-4 py-2 text-slate-700 font-medium">
                      {name}
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        value={value}
                        onChange={(e) => handleUpdate(name, e.target.value)}
                        className={`w-24 text-sm border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-cyan-500/30 ${
                          invalid
                            ? "border-red-400 bg-red-50 text-red-700"
                            : "border-slate-200"
                        }`}
                      />
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => handleDelete(name)}
                        className="text-xs text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 transition-colors"
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                );
              })}

              {/* empty state */}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-center py-10 text-slate-400 text-sm">
                    暂无配置项
                  </td>
                </tr>
              )}

              {/* add row */}
              <tr>
                <td className="w-10 px-3 py-2" />
                <td colSpan={3} className="p-0">
                  <div className="flex items-center gap-3 px-4 py-3 border-t-2 border-dashed border-slate-200 bg-slate-50/30">
                    <input
                      type="text"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                      placeholder="新设备名称"
                      className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-cyan-500/30 bg-white"
                    />
                    <input
                      type="number"
                      value={newValue}
                      onChange={(e) => setSetValue(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                      placeholder="吨数"
                      className="w-24 text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-cyan-500/30 bg-white"
                    />
                    <button
                      onClick={handleAdd}
                      disabled={!newName.trim() || !newValue}
                      className="inline-flex items-center gap-1 text-sm text-cyan-600 hover:text-cyan-700 px-3 py-1.5 rounded-lg hover:bg-cyan-50 disabled:text-slate-300 disabled:hover:bg-transparent transition-colors font-medium"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                      </svg>
                      添加
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* ---- footer: pagination + count -------------------------- */}
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-slate-100">
          <span className="text-xs text-slate-400">共 {entries.length} 台设备</span>

          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={safePage === 0}
                className="text-xs px-2.5 py-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors"
              >
                上一页
              </button>
              <span className="text-xs text-slate-500">
                {safePage + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={safePage >= totalPages - 1}
                className="text-xs px-2.5 py-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors"
              >
                下一页
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ---- dialogs ---------------------------------------------- */}
      {confirmDeleteDialog && (
        <ConfirmDialog
          title="确认删除"
          body={
            <span>
              确定要删除选中的 <strong>{selected.size}</strong> 条设备记录吗？此操作需要点击"保存"后才会持久化。
            </span>
          }
          confirmLabel={`删除 ${selected.size} 条`}
          onConfirm={handleBulkDelete}
          onCancel={() => setConfirmDeleteDialog(false)}
        />
      )}

      {restoreDialog && (
        <RestoreDefaultsDialog
          onPick={handleRestore}
          onCancel={() => setRestoreDialog(false)}
        />
      )}

      {/* ---- toast ------------------------------------------------ */}
      {toast && (
        <Toast
          message={toast.msg}
          kind={toast.kind}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
