import { useState, useEffect, useCallback } from "react";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import {
  TableHeaderIcon, SaveIcon, RefreshIcon, RestoreIcon, PlusIcon, CloseIcon,
} from "../../lib/icons";
import { SectionCard, StatusMessage, KeywordChipInput } from "./_shared";
import { useTranslation } from "react-i18next";

// ---------------------------------------------------------------------------
// Types & Defaults
// ---------------------------------------------------------------------------

interface HeaderMappingEntry {
  index: number | null;
  keywords: string[];
  new: string;
}

interface HeaderMappingConfig {
  mode: "position" | "name";
  entries: HeaderMappingEntry[];
}

const DEFAULT_HEADER_MAPPING: HeaderMappingConfig = {
  mode: "position",
  entries: [
    { index: 1, keywords: [], new: "日期" },
    { index: 2, keywords: [], new: "班次" },
    { index: 3, keywords: [], new: "序号" },
    { index: 4, keywords: [], new: "设备名称" },
    { index: 5, keywords: [], new: "公司" },
    { index: 6, keywords: [], new: "应运行分钟" },
    { index: 7, keywords: [], new: "应运行小时数" },
    { index: 8, keywords: [], new: "停车/换班" },
    { index: 9, keywords: [], new: "转移" },
    { index: 10, keywords: [], new: "挖机场地推土/清理墙壁" },
    { index: 11, keywords: [], new: "等待装货" },
    { index: 12, keywords: [], new: "爆破" },
    { index: 13, keywords: [], new: "就餐/休息时间" },
    { index: 14, keywords: [], new: "柴油" },
    { index: 15, keywords: [], new: "计划维修/润滑" },
    { index: 16, keywords: [], new: "未计划/故障" },
    { index: 17, keywords: [], new: "待命" },
    { index: 18, keywords: [], new: "因天气：大风暴，雨，雪" },
    { index: 19, keywords: [], new: "扬尘：洒水车不足" },
    { index: 20, keywords: [], new: "排队/装水" },
    { index: 21, keywords: [], new: "总产量生产运行分钟" },
    { index: 22, keywords: [], new: "因电力原因停车/计划" },
    { index: 23, keywords: [], new: "因电力原因停车/未计划" },
    { index: 24, keywords: [], new: "总产量生产运行小时" },
    { index: 25, keywords: [], new: "注释" },
  ],
};

// ---------------------------------------------------------------------------
// Header Mapping Section
// ---------------------------------------------------------------------------

export function HeaderMappingSection({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ msg: string; kind: "success" | "error" | "info" }>({ msg: "", kind: "info" });
  const [entries, setEntries] = useState<HeaderMappingEntry[]>([]);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");

  const reload = useCallback(async () => {
    try {
      const raw = await bridge.call<HeaderMappingConfig>("get_config", { key: "worktime_header_mapping" });
      if (raw && typeof raw === "object" && Array.isArray(raw.entries)) {
        setEntries(raw.entries.map((e) => ({
          index: e.index ?? null,
          keywords: Array.isArray(e.keywords) ? e.keywords : [],
          new: e.new ?? "",
        })));
      } else {
        setEntries(DEFAULT_HEADER_MAPPING.entries.map((e) => ({ ...e })));
      }
      setExpandedRows(new Set());
      setStatus({ msg: "", kind: "info" });
    } catch {
      setEntries(DEFAULT_HEADER_MAPPING.entries.map((e) => ({ ...e })));
      setExpandedRows(new Set());
    }
  }, [bridge.call]);

  useEffect(() => { reload(); }, [reload]);

  const validate = (): string | null => {
    const seen: Record<number, number> = {};
    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      if (!e.new.trim()) return t("userConfig:HeaderMappingSection.第$行：新列名不能为空_3d11", { row: i + 1 });
      if (e.index !== null) {
        if (seen[e.index] !== undefined) {
          return t("userConfig:HeaderMappingSection.行号$重复（第$行和第$行）_e259", { index: e.index, first: seen[e.index], second: i + 1 });
        }
        seen[e.index] = i + 1;
      }
    }
    return null;
  };

  const save = async () => {
    const err = validate();
    if (err) {
      setStatus({ msg: err, kind: "error" });
      return;
    }
    setSaving(true);
    try {
      const cleanEntries = entries
        .filter((e) => e.index !== null || e.keywords.length > 0 || e.new.trim())
        .map((e) => {
          const entry: Record<string, unknown> = { new: e.new.trim() };
          if (e.index !== null) entry.index = e.index;
          if (e.keywords.length > 0) entry.keywords = e.keywords;
          return entry;
        });
      await bridge.call("save_config", {
        data: { worktime_header_mapping: { mode: "position", entries: cleanEntries } },
        target: "user",
      });
      const posCount = cleanEntries.filter((e) => e.index !== undefined).length;
      const kwCount = cleanEntries.filter((e) => Array.isArray(e.keywords)).length;
      const hints: string[] = [];
      if (posCount) hints.push(t("userConfig:HeaderMappingSection.$条按位置匹配_43d3", { count: posCount }));
      if (kwCount) hints.push(t("userConfig:HeaderMappingSection.$条按关键字匹配_21f7", { count: kwCount }));
      const hintText = hints.length ? `（${hints.join("；")}）` : "";
      setStatus({ msg: t("userConfig:HeaderMappingSection.已保存$条表头映射$_74b8", { count: cleanEntries.length, hint: hintText }), kind: "success" });
      notify(t("userConfig:HeaderMappingSection.已保存$条表头映射_7bcf", { count: cleanEntries.length }), "success");
      setTimeout(() => setStatus({ msg: "", kind: "info" }), 2500);
    } catch (e) {
      setStatus({ msg: t("userConfig:HeaderMappingSection.保存失败:$_2655", { error: String(e) }), kind: "error" });
      notify(t("userConfig:HeaderMappingSection.保存失败:$_e5b7", { error: String(e) }), "error");
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setEntries(DEFAULT_HEADER_MAPPING.entries.map((e) => ({ ...e })));
    setExpandedRows(new Set());
    setStatus({ msg: t("userConfig:HeaderMappingSection.已恢复默认配置（需点击保存生效_c62f"), kind: "info" });
  };

  const addRow = () => {
    const newIdx = entries.length;
    setEntries((prev) => [...prev, { index: null, keywords: [], new: "" }]);
    setExpandedRows((prev) => new Set([...prev, newIdx]));
  };

  const removeRow = (idx: number) => {
    setEntries((prev) => prev.filter((_, i) => i !== idx));
    setExpandedRows((prev) => {
      const next = new Set<number>();
      prev.forEach((v) => { if (v < idx) next.add(v); else if (v > idx) next.add(v - 1); });
      return next;
    });
  };

  const updateEntry = (idx: number, field: keyof HeaderMappingEntry, value: unknown) => {
    setEntries((prev) =>
      prev.map((e, i) => (i === idx ? { ...e, [field]: value } : e))
    );
  };

  const toggleRow = (idx: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const matchesSearch = (entry: HeaderMappingEntry): boolean => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    if (entry.new.toLowerCase().includes(q)) return true;
    if (entry.keywords.some((kw) => kw.toLowerCase().includes(q))) return true;
    if (entry.index !== null && String(entry.index).includes(q)) return true;
    return false;
  };

  const filteredEntries = entries.map((e, i) => ({ entry: e, idx: i })).filter(({ entry }) => matchesSearch(entry));

  return (
    <SectionCard
      title={t("userConfig:HeaderMappingSection.工时表头映射_b8a9")}
      subtitle={t("userConfig:HeaderMappingSection.配置列号（位置匹配）或关键字（_afad")}
      icon={<TableHeaderIcon />}
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
    >
      {/* Search + primary actions toolbar */}
      <div className="flex items-center gap-2 mb-3">
        <div className="relative flex-1">
          <svg className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t("userConfig:HeaderMappingSection.搜索列名或关键字..._a031")}
            className="input w-full pl-8"
          />
        </div>
        <button
          onClick={save}
          disabled={saving}
          className={`inline-flex items-center gap-1 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-md transition-colors ${saving ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <SaveIcon />
          {saving ? t("userConfig:HeaderMappingSection.保存中..._2a33") : t("userConfig:HeaderMappingSection.保存_be5f")}
        </button>
        <button
          onClick={addRow}
          className="inline-flex items-center gap-1 text-xs font-medium text-teal-700 bg-teal-50 hover:bg-teal-100 px-3 py-1.5 rounded-md transition-colors"
        >
          <PlusIcon />
          添加映射
        </button>
      </div>

      {/* Secondary actions */}
      <div className="flex items-center gap-1.5 mb-3">
        <button onClick={reload} className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-50 transition-colors">
          <RefreshIcon /> 重新加载
        </button>
        <button onClick={resetToDefault} className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 transition-colors">
          <RestoreIcon /> {t("userConfig:HeaderMappingSection.restoreDefault")}
        </button>
        <span className="mx-1 text-slate-200">|</span>
        <button onClick={() => setExpandedRows(new Set(entries.map((_, i) => i)))} className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-50 transition-colors">
          全部展开
        </button>
        <button onClick={() => setExpandedRows(new Set())} className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-50 transition-colors">
          {t("userConfig:HeaderMappingSection.collapseAll")}
        </button>
      </div>

      {/* Hint text */}
      <p className="text-xs text-slate-400 mb-2">
        {t("userConfig:HeaderMappingSection.editHint")}
      </p>

      {/* Table header */}
      <div className="bg-slate-50 rounded-t-lg border border-slate-200 border-b-0">
        <div className="grid grid-cols-[52px_56px_1fr_140px_36px] gap-1 px-2 py-1.5">
          <span className="text-xs font-semibold text-slate-500">{t("userConfig:HeaderMappingSection.列号_27c2")}</span>
          <span className="text-xs font-semibold text-slate-500">{t("userConfig:HeaderMappingSection.匹配_f504")}</span>
          <span className="text-xs font-semibold text-slate-500">{t("userConfig:HeaderMappingSection.关键字（名称匹配）_c92b")}</span>
          <span className="text-xs font-semibold text-slate-500">{t("userConfig:HeaderMappingSection.新列名_d6e7")}</span>
          <span />
        </div>
      </div>

      {/* Mapping rows */}
      <div className="border border-slate-200 border-t-0 rounded-b-lg overflow-hidden max-h-96 overflow-y-auto">
        {filteredEntries.length === 0 && (
          <div className="py-8 text-center text-xs text-slate-400">
            {entries.length === 0 ? t("userConfig:HeaderMappingSection.暂无映射配置，点击「添加映射」_2fd0") : t("userConfig:HeaderMappingSection.没有匹配的映射_97b7")}
          </div>
        )}
        {filteredEntries.map(({ entry, idx }, visibleIdx) => {
          const isRowExpanded = expandedRows.has(idx);
          const hasIndex = entry.index !== null;
          const hasKw = entry.keywords.length > 0;
          const matchMode = hasIndex ? t("userConfig:HeaderMappingSection.位置_d4d2") : hasKw ? t("userConfig:HeaderMappingSection.关键字_cfb5") : "—";
          const badgeCls = hasIndex
            ? "bg-teal-100 text-teal-800"
            : hasKw
              ? "bg-amber-100 text-amber-800"
              : "bg-slate-100 text-slate-500";

          return (
            <div
              key={idx}
              className={`border-t border-slate-100 transition-colors ${
                visibleIdx % 2 === 0 ? "bg-white" : "bg-slate-50/50"
              } ${isRowExpanded ? "bg-blue-50/30" : "hover:bg-slate-50"}`}
            >
              {isRowExpanded ? (
                /* ── Expanded editing mode ── */
                <div className="px-2 py-2 space-y-2">
                  <div className="flex items-center gap-1.5">
                    <input
                      type="number"
                      min={1}
                      value={entry.index ?? ""}
                      onChange={(e) => {
                        const v = e.target.value.trim();
                        updateEntry(idx, "index", v ? parseInt(v, 10) : null);
                      }}
                      placeholder={t("userConfig:HeaderMappingSection.从1起_ad5f")}
                      className="input w-[52px]"
                    />
                    <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${badgeCls}`}>
                      {matchMode}
                    </span>
                    <input
                      type="text"
                      value={entry.new}
                      onChange={(e) => updateEntry(idx, "new", e.target.value)}
                      placeholder={t("userConfig:HeaderMappingSection.新列名_d6e7")}
                      className="input flex-1"
                    />
                    <div className="flex items-center gap-0.5 ml-auto shrink-0">
                      <button
                        onClick={() => toggleRow(idx)}
                        className="w-7 h-7 flex items-center justify-center rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                        title={t("userConfig:HeaderMappingSection.折叠_e082")}
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
                        </svg>
                      </button>
                      <button
                        onClick={() => removeRow(idx)}
                        className="w-7 h-7 flex items-center justify-center rounded text-slate-600 hover:text-red-500 hover:bg-red-50 transition-colors"
                        title={t("userConfig:HeaderMappingSection.删除此行_43e8")}
                      >
                        <CloseIcon />
                      </button>
                    </div>
                  </div>
                  <KeywordChipInput
                    label=""
                    items={entry.keywords}
                    placeholder={t("userConfig:HeaderMappingSection.输入关键字后回车添加_fafd")}
                    onChange={(items) => updateEntry(idx, "keywords", items)}
                  />
                </div>
              ) : (
                /* ── Compact read-only mode ── */
                <div
                  className="grid grid-cols-[52px_56px_1fr_140px_36px] gap-1 px-2 py-1.5 items-center cursor-pointer"
                  onClick={() => toggleRow(idx)}
                >
                  <span className="text-xs font-medium text-slate-700 text-center">
                    {entry.index ?? "—"}
                  </span>
                  <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full text-center ${badgeCls}`}>
                    {matchMode}
                  </span>
                  <div className="flex flex-wrap gap-1 min-h-[20px]">
                    {entry.keywords.length > 0 ? (
                      entry.keywords.map((kw, ki) => (
                        <span key={ki} className="inline-block text-xs bg-sky-50 text-sky-700 px-1.5 py-0.5 rounded-full">
                          {kw}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-300">—</span>
                    )}
                  </div>
                  <span className="text-xs text-slate-700 truncate" title={entry.new}>
                    {entry.new || "—"}
                  </span>
                  <span className="flex items-center justify-center text-slate-400">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <StatusMessage message={status.msg} kind={status.kind} />
    </SectionCard>
  );
}
