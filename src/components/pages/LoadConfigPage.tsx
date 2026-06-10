import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import type { BridgeProp } from "../../lib/types";

type LoadMap = Record<string, number>;

const PAGE_SIZE = 20;

/* ------------------------------------------------------------------ */
/*  SVG Icons (16x16)                                                  */
/* ------------------------------------------------------------------ */

const IconImport = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
  </svg>
);

const IconExport = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
  </svg>
);

const IconRestore = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a5 5 0 015 5v2M3 10l4-4M3 10l4 4" />
  </svg>
);

const IconRefresh = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);

const IconTrash = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);

const IconSave = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
  </svg>
);

const IconApply = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
  </svg>
);

const IconPlus = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
  </svg>
);

const IconCheck = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
  </svg>
);

const IconWarning = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
  </svg>
);

const IconChevronLeft = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
  </svg>
);

const IconChevronRight = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
  </svg>
);

const IconSettings = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

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

  const icon =
    kind === "success" ? (
      <IconCheck />
    ) : kind === "error" ? (
      <IconWarning />
    ) : null;

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 ${bg} text-white text-sm px-5 py-2.5 rounded-lg flex items-center gap-2`}
    >
      {icon}
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
      <div className="bg-white rounded-lg border border-slate-200 p-6 w-[400px] max-w-[90vw]">
        <h3 className="text-base font-semibold text-slate-800 mb-2">{title}</h3>
        <div className="text-sm text-slate-600 mb-5">{body}</div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="btn-secondary text-sm px-4 py-1.5"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="btn-danger text-sm px-4 py-1.5"
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
      <div className="bg-white rounded-lg border border-slate-200 p-6 w-[400px] max-w-[90vw]">
        <h3 className="text-base font-semibold text-slate-800 mb-2">恢复默认配置</h3>
        <p className="text-sm text-slate-600 mb-5">
          选择要恢复的默认版本：
        </p>
        <div className="flex flex-col gap-2 mb-5">
          <button
            onClick={() => onPick("new")}
            className="w-full text-left text-sm px-4 py-3 rounded-lg border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <span className="font-medium text-slate-700">新版配置</span>
            <span className="block text-xs text-slate-400 mt-0.5">当前版本的出厂默认值</span>
          </button>
          <button
            onClick={() => onPick("old")}
            className="w-full text-left text-sm px-4 py-3 rounded-lg border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <span className="font-medium text-slate-700">旧版配置</span>
            <span className="block text-xs text-slate-400 mt-0.5">兼容旧版系统的默认值</span>
          </button>
        </div>
        <div className="flex justify-end">
          <button
            onClick={onCancel}
            className="btn-secondary text-sm px-4 py-1.5"
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
  const [newNameError, setNewNameError] = useState<string | null>(null);
  const [newValueError, setNewValueError] = useState<string | null>(null);

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

  // M14: 使用 stable stringify 避免 key 顺序变化导致误判
  const stableStringify = useCallback(
    (obj: unknown): string => JSON.stringify(obj, (_key: string, value: unknown) => {
      if (value && typeof value === "object" && !Array.isArray(value)) {
        return Object.keys(value as Record<string, unknown>).sort().reduce(
          (sorted: Record<string, unknown>, k) => { sorted[k] = (value as Record<string, unknown>)[k]; return sorted; },
          {},
        );
      }
      return value;
    }),
    [],
  );
  const isDirty = useMemo(
    () => stableStringify(loadMap) !== stableStringify(persistedMap),
    [loadMap, persistedMap, stableStringify],
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
    let hasError = false;
    if (!newName.trim()) {
      setNewNameError("请输入设备名称");
      hasError = true;
    } else {
      setNewNameError(null);
    }
    const num = parseFloat(newValue);
    if (isNaN(num) || num <= 0) {
      setNewValueError("请输入有效的装载量");
      hasError = true;
    } else {
      setNewValueError(null);
    }
    if (hasError) return;

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

  /* ---- render ---------------------------------------------------- */

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400 gap-3">
        <svg className="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <span className="text-sm">加载中...</span>
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
        <div className="flex items-center gap-2">
          <IconSettings />
          <h2 className="text-base font-semibold text-slate-800">装载量配置</h2>
        </div>

        {/* status badges */}
        {isDirty ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-2.5 py-0.5">
            <IconWarning />
            已修改（未保存）
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-0.5">
            <IconCheck />
            已保存
          </span>
        )}
      </div>

      {/* ---- toolbar ---------------------------------------------- */}
      <div className="flex items-center gap-2 mb-4">
        <button onClick={handleImport} className="btn-secondary">
          <IconImport />
          导入
        </button>
        <button onClick={handleExport} className="btn-secondary">
          <IconExport />
          导出
        </button>

        {selected.size > 0 && (
          <>
            <div className="w-px h-5 bg-slate-200 mx-0.5" />
            <button
              onClick={() => setConfirmDeleteDialog(true)}
              className="btn-danger"
            >
              <IconTrash />
              删除选中 ({selected.size})
            </button>
          </>
        )}

        <button onClick={() => setRestoreDialog(true)} className="btn-secondary">
          <IconRestore />
          恢复默认
        </button>

        <div className="flex-1" />

        <button onClick={loadData} className="btn-secondary">
          <IconRefresh />
          重载
        </button>
        <button
          onClick={handleApply}
          disabled={applying || !isDirty}
          className={`btn-secondary ${applying || !isDirty ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <IconApply />
          {applying ? "应用中..." : "应用"}
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !isDirty}
          className={`btn-primary ${saving || !isDirty ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <IconSave />
          {saving ? "保存中..." : "保存"}
        </button>
      </div>

      {/* ---- error ----------------------------------------------- */}
      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-center gap-2">
          <IconWarning />
          {error}
        </div>
      )}

      {/* ---- table ----------------------------------------------- */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50">
                <th className="w-10 px-3 py-2">
                  <input
                    ref={checkboxRef}
                    type="checkbox"
                    checked={allPageSelected}
                    onChange={toggleSelectAll}
                    className="w-4 h-4 rounded border-slate-300 cursor-pointer"
                  />
                </th>
                <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  设备名称
                </th>
                <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  装载量 (吨)
                </th>
                <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider w-20">
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
                    className={`h-9 border-b border-slate-100 transition-colors ${
                      selected.has(name) ? "bg-blue-50/50" : "bg-white"
                    } hover:bg-slate-50`}
                  >
                    <td className="w-10 px-3">
                      <input
                        type="checkbox"
                        checked={selected.has(name)}
                        onChange={() => toggleRow(name)}
                        className="w-4 h-4 rounded border-slate-300 cursor-pointer"
                      />
                    </td>
                    <td className="px-3 text-slate-700 text-sm">
                      {name}
                    </td>
                    <td className="px-3">
                      <input
                        type="number"
                        value={value}
                        onChange={(e) => handleUpdate(name, e.target.value)}
                        className={`w-24 text-sm border rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-colors ${
                          invalid
                            ? "border-red-300 bg-red-50 text-red-700"
                            : "border-slate-300 focus:border-blue-500"
                        }`}
                      />
                      {invalid && (
                        <p className="text-red-500 text-xs mt-0.5">数值必须大于 0</p>
                      )}
                    </td>
                    <td className="px-3 text-right">
                      <button
                        onClick={() => handleDelete(name)}
                        className="inline-flex items-center gap-1 text-xs text-slate-600 hover:text-red-600 px-1.5 py-1 rounded hover:bg-red-50 transition-colors"
                      >
                        <IconTrash />
                        删除
                      </button>
                    </td>
                  </tr>
                );
              })}

              {/* empty state */}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-center py-16">
                    <p className="text-slate-400 text-sm">暂无配置项</p>
                  </td>
                </tr>
              )}

              {/* add row — dashed separator */}
              <tr>
                <td className="w-10 px-3" />
                <td colSpan={3} className="p-0">
                  <div className="flex items-center gap-3 px-3 py-2.5 border-b border-dashed border-slate-200 bg-slate-50/30">
                    <div className="flex-1">
                      <input
                        type="text"
                        value={newName}
                        onChange={(e) => { setNewName(e.target.value); setNewNameError(null); }}
                        onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                        placeholder="新设备名称"
                        className={`w-full text-sm border rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20 bg-white transition-colors ${
                          newNameError ? "border-red-300" : "border-slate-300 focus:border-blue-500"
                        }`}
                      />
                      {newNameError && <p className="text-red-500 text-xs mt-0.5">{newNameError}</p>}
                    </div>
                    <div className="w-28">
                      <input
                        type="number"
                        value={newValue}
                        onChange={(e) => { setSetValue(e.target.value); setNewValueError(null); }}
                        onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                        placeholder="吨数"
                        className={`w-full text-sm border rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20 bg-white transition-colors ${
                          newValueError ? "border-red-300" : "border-slate-300 focus:border-blue-500"
                        }`}
                      />
                      {newValueError && <p className="text-red-500 text-xs mt-0.5">{newValueError}</p>}
                    </div>
                    <button
                      onClick={handleAdd}
                      className="btn-primary"
                    >
                      <IconPlus />
                      添加
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* ---- footer: pagination + count -------------------------- */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100">
          <span className="text-xs text-slate-500">共 {entries.length} 台设备</span>

          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={safePage === 0}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                <IconChevronLeft />
                上一页
              </button>
              <span className="text-xs text-slate-500 min-w-[4rem] text-center">
                {safePage + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={safePage >= totalPages - 1}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                下一页
                <IconChevronRight />
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
