import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import {
  ImportIcon, ExportIcon, RestoreIcon, RefreshIcon,
  TrashIcon, SaveIcon, ApplyIcon, PlusIcon,
  CheckIcon, AlertTriangleIcon, ChevronLeftIcon,
  ChevronRightIcon, SettingsIcon,
} from "../../lib/icons";

type LoadMap = Record<string, number>;

const PAGE_SIZE = 20;

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
  const { t } = useTranslation();
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
            {t("pages:LoadConfigPage.ui.cancel")}
          </button>
          <button
            onClick={onConfirm}
            className="btn-danger text-sm px-4 py-1.5"
          >
            {confirmLabel ?? t("pages:LoadConfigPage.ui.confirm")}
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
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-lg border border-slate-200 p-6 w-[400px] max-w-[90vw]">
        <h3 className="text-base font-semibold text-slate-800 mb-2">{t("pages:LoadConfigPage.restoreDefaults")}</h3>
        <p className="text-sm text-slate-600 mb-5">
          {t("pages:LoadConfigPage.ui.chooseDefaultVersion")}
        </p>
        <div className="flex flex-col gap-2 mb-5">
          <button
            onClick={() => onPick("new")}
            className="w-full text-left text-sm px-4 py-3 rounded-lg border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <span className="font-medium text-slate-700">{t("pages:LoadConfigPage.newVersion")}</span>
            <span className="block text-xs text-slate-400 mt-0.5">{t("pages:LoadConfigPage.factoryDefaultsForCurrentVersion")}</span>
          </button>
          <button
            onClick={() => onPick("old")}
            className="w-full text-left text-sm px-4 py-3 rounded-lg border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <span className="font-medium text-slate-700">{t("pages:LoadConfigPage.oldVersion")}</span>
            <span className="block text-xs text-slate-400 mt-0.5">{t("pages:LoadConfigPage.legacyCompatibleDefaultValues")}</span>
          </button>
        </div>
        <div className="flex justify-end">
          <button
            onClick={onCancel}
            className="btn-secondary text-sm px-4 py-1.5"
          >
            {t("pages:LoadConfigPage.ui.cancel")}
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
  const { notify } = useToast();
  const { t } = useTranslation();
  const [loadMap, setLoadMap] = useState<LoadMap>({});
  const [persistedMap, setPersistedMap] = useState<LoadMap>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newValue, setSetValue] = useState("");
  const [newNameError, setNewNameError] = useState<string | null>(null);
  const [newValueError, setNewValueError] = useState<string | null>(null);

  // version selection ("new" | "old")
  const [mapVersion, setMapVersion] = useState<"new" | "old">("new");

  // selection
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // pagination
  const [page, setPage] = useState(0);

  // dialogs
  const [confirmDeleteDialog, setConfirmDeleteDialog] = useState(false);
  const [restoreDialog, setRestoreDialog] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  /* ---- helpers --------------------------------------------------- */

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

  const loadData = useCallback(async (version?: "new" | "old") => {
    setLoading(true);
    setError(null);
    try {
      const ver = version ?? mapVersion;
      const res = await bridge.call<LoadMap>("get_device_load_map", { version: ver });
      const map = res || {};
      setLoadMap(map);
      setPersistedMap(map);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [bridge, mapVersion]);

  useEffect(() => {
    // Load persisted version preference, then load data with that version
    (async () => {
      try {
        const res = await bridge.call<{ version: string }>("get_load_map_version");
        const ver = res?.version === "old" ? "old" : "new";
        setMapVersion(ver);
        loadData(ver);
      } catch {
        // fallback: use default "new" and load data
        loadData("new");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bridge]);

  /* ---- version switch ------------------------------------------- */

  const handleVersionSwitch = async (ver: "new" | "old") => {
    if (ver === mapVersion) return;
    setMapVersion(ver);
    try {
      await bridge.call("set_load_map_version", { version: ver });
    } catch {
      // non-critical, continue
    }
    loadData(ver);
    notify(t("pages:LoadConfigPage.switchedToLoadCapacityConfiguration", { versionLabel: ver === "old" ? t("pages:LoadConfigPage.old") : t("pages:LoadConfigPage.new") }), "info");
  };

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
    notify(t("pages:LoadConfigPage.deleted"), "info");
  };

  const handleAdd = () => {
    let hasError = false;
    if (!newName.trim()) {
      setNewNameError(t("pages:LoadConfigPage.enterADeviceName"));
      hasError = true;
    } else {
      setNewNameError(null);
    }
    const num = parseFloat(newValue);
    if (isNaN(num) || num <= 0) {
      setNewValueError(t("pages:LoadConfigPage.enterAValidLoadCapacity"));
      hasError = true;
    } else {
      setNewValueError(null);
    }
    if (hasError) return;

    setLoadMap((prev) => ({ ...prev, [newName.trim()]: num }));
    setNewName("");
    setSetValue("");
    notify(t("pages:LoadConfigPage.added"), "success");
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
    notify(t("pages:LoadConfigPage.deletedRecords", { count: selected.size }), "success");
    setSelected(new Set());
    setConfirmDeleteDialog(false);
  };

  /* ---- apply / save --------------------------------------------- */

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      await bridge.call("apply_device_load_map", { map_data: loadMap, version: mapVersion });
      notify(t("pages:LoadConfigPage.appliedItemsave"), "info");
    } catch (e) {
      setError(String(e));
      notify(t("pages:LoadConfigPage.applyFailed"), "error");
    } finally {
      setApplying(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await bridge.call("update_device_load_map", { map_data: loadMap, version: mapVersion });
      setPersistedMap({ ...loadMap });
      notify(t("pages:LoadConfigPage.saved"), "success");
    } catch (e) {
      setError(String(e));
      notify(t("pages:LoadConfigPage.saveFailed"), "error");
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
        throw new Error(t("pages:LoadConfigPage.jsonItemItemItem"));
      }
      const imported: LoadMap = {};
      for (const [k, v] of Object.entries(parsed)) {
        const num = typeof v === "number" ? v : parseFloat(String(v));
        if (!isNaN(num)) imported[k] = num;
      }
      const count = Object.keys(imported).length;
      if (count === 0) throw new Error(t("pages:LoadConfigPage.datavalidrecords"));
      setLoadMap((prev) => ({ ...prev, ...imported }));
      notify(t("pages:LoadConfigPage.importedRecords", { count }), "success");
    } catch (err) {
      notify(t("pages:LoadConfigPage.importFailed", { error: err instanceof Error ? err.message : String(err) }), "error");
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
    notify(t("pages:LoadConfigPage.configurationexportconfigurationfile"), "success");
  };

  /* ---- restore defaults ------------------------------------------ */

  const handleRestore = async (version: "new" | "old") => {
    setRestoreDialog(false);
    try {
      const defaults = await bridge.call<LoadMap>("get_default_load_map", { version });
      if (defaults && typeof defaults === "object") {
        setLoadMap(defaults);
        notify(t("pages:LoadConfigPage.configurationDefaultConfigurationConfigurationsave", { versionLabel: version === "new" ? t("pages:LoadConfigPage.new") : t("pages:LoadConfigPage.old") }), "info");
      }
    } catch {
      notify(t("pages:LoadConfigPage.failedToLoadDefaultConfiguration"), "error");
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
        <span className="text-sm">{t("pages:LoadConfigPage.textVariant")}</span>
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
          <SettingsIcon />
          <h2 className="text-base font-semibold text-slate-800">{t("pages:LoadConfigPage.loadConfig")}</h2>

          {/* version toggle */}
          <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden ml-3">
            <button
              onClick={() => handleVersionSwitch("new")}
              className={`text-xs px-3 py-1.5 transition-colors ${
                mapVersion === "new"
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-slate-500 hover:bg-slate-50"
              }`}
            >
              {t("pages:LoadConfigPage.new")}
            </button>
            <button
              onClick={() => handleVersionSwitch("old")}
              className={`text-xs px-3 py-1.5 border-l border-slate-200 transition-colors ${
                mapVersion === "old"
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-slate-500 hover:bg-slate-50"
              }`}
            >
              {t("pages:LoadConfigPage.old")}
            </button>
          </div>
        </div>

        {/* status badges */}
        {isDirty ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-2.5 py-0.5">
            <AlertTriangleIcon />
            {t("pages:LoadConfigPage.ui.modifiedUnsaved")}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-0.5">
            <CheckIcon />
            {t("pages:LoadConfigPage.saved")}
          </span>
        )}
      </div>

      {/* ---- toolbar ---------------------------------------------- */}
      <div className="flex items-center gap-2 mb-4">
        <button onClick={handleImport} className="btn-secondary">
          <ImportIcon />
          {t("pages:LoadConfigPage.ui.import")}
        </button>
        <button onClick={handleExport} className="btn-secondary">
          <ExportIcon />
          {t("pages:LoadConfigPage.ui.export")}
        </button>

        {selected.size > 0 && (
          <>
            <div className="w-px h-5 bg-slate-200 mx-0.5" />
            <button
              onClick={() => setConfirmDeleteDialog(true)}
              className="btn-danger"
            >
              <TrashIcon />
              {t("pages:LoadConfigPage.ui.deleteSelected", { count: selected.size })}
            </button>
          </>
        )}

        <button onClick={() => setRestoreDialog(true)} className="btn-secondary">
          <RestoreIcon />
          {t("pages:LoadConfigPage.ui.restoreDefault")}
        </button>

        <div className="flex-1" />

        <button onClick={() => loadData()} className="btn-secondary">
          <RefreshIcon />
          {t("pages:LoadConfigPage.ui.reload")}
        </button>
        <button
          onClick={handleApply}
          disabled={applying || !isDirty}
          className={`btn-secondary ${applying || !isDirty ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <ApplyIcon />
          {applying ? t("pages:LoadConfigPage.textVariant2") : t("pages:LoadConfigPage.apply")}
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !isDirty}
          className={`btn-primary ${saving || !isDirty ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <SaveIcon />
          {saving ? t("pages:LoadConfigPage.text") : t("pages:LoadConfigPage.save")}
        </button>
      </div>

      {/* ---- error ----------------------------------------------- */}
      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-center gap-2">
          <AlertTriangleIcon />
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
                  {t("pages:LoadConfigPage.ui.deviceName")}
                </th>
                <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  {t("pages:LoadConfigPage.ui.capacity")}
                </th>
                <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider w-20">
                  {t("pages:LoadConfigPage.ui.actions")}
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
                        <p className="text-red-500 text-xs mt-0.5">{t("pages:LoadConfigPage.valueMustBeGreaterThan0")}</p>
                      )}
                    </td>
                    <td className="px-3 text-right">
                      <button
                        onClick={() => handleDelete(name)}
                        className="inline-flex items-center gap-1 text-xs text-red-700 hover:text-red-800 px-1.5 py-1 rounded hover:bg-red-50 transition-colors"
                      >
                        <TrashIcon />
                        {t("pages:LoadConfigPage.ui.delete")}
                      </button>
                    </td>
                  </tr>
                );
              })}

              {/* empty state */}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-center py-16">
                    <p className="text-slate-400 text-sm">{t("pages:LoadConfigPage.noConfigurationItems")}</p>
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
                        placeholder={t("pages:LoadConfigPage.newDeviceName")}
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
                        placeholder={t("pages:LoadConfigPage.capacity")}
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
                      <PlusIcon />
                      {t("pages:LoadConfigPage.ui.add")}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* ---- footer: pagination + count -------------------------- */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100">
          <span className="text-xs text-slate-500">{t("pages:LoadConfigPage.ui.deviceCount", { count: entries.length })}</span>

          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={safePage === 0}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                <ChevronLeftIcon />
                {t("pages:LoadConfigPage.ui.previousPage")}
              </button>
              <span className="text-xs text-slate-500 min-w-[4rem] text-center">
                {safePage + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={safePage >= totalPages - 1}
                className="text-xs text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-0.5"
              >
                {t("pages:LoadConfigPage.ui.nextPage")}
                <ChevronRightIcon />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ---- dialogs ---------------------------------------------- */}
      {confirmDeleteDialog && (
        <ConfirmDialog
          title={t("pages:LoadConfigPage.confirmDelete")}
          body={
            <span>
              {t("pages:LoadConfigPage.ui.deleteConfirm", { count: selected.size })}
            </span>
          }
          confirmLabel={t("pages:LoadConfigPage.itemItems", { count: selected.size })}
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
    </div>
  );
}
