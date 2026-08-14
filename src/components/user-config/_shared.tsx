import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ChevronDownIcon,
  SaveIcon,
  RefreshIcon,
  RestoreIcon,
  PlusIcon,
  CheckIcon,
  AlertCircleIcon,
} from "../../lib/icons";

// ---------------------------------------------------------------------------
// Collapsible Section Card — NO colored left border
// ---------------------------------------------------------------------------

export function SectionCard({
  title,
  subtitle,
  icon,
  expanded,
  onToggle,
  children,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <span className="text-slate-500">{icon}</span>
          <div className="text-left">
            <h3 className="text-sm font-medium text-slate-700">{title}</h3>
            <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
          </div>
        </div>
        <span className={`transition-transform ${expanded ? "rotate-180" : ""}`}>
          <ChevronDownIcon />
        </span>
      </button>
      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3">{children}</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-section action buttons (text-xs)
// ---------------------------------------------------------------------------

export function ActionButtons({
  saving,
  onSave,
  onReload,
  onReset,
  onExtra,
  extraLabel,
}: {
  saving: boolean;
  onSave: () => void;
  onReload: () => void;
  onReset: () => void;
  onExtra?: () => void;
  extraLabel?: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex gap-2 flex-wrap mt-4 pt-3 border-t border-slate-100">
      <button
        onClick={onSave}
        disabled={saving}
        className={`inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700 px-2.5 py-1.5 rounded-md hover:bg-blue-50 transition-colors ${
          saving ? "opacity-50 cursor-not-allowed" : ""
        }`}
      >
        <SaveIcon />
        {saving ? t("userConfig:_shared.保存中..._2a33") : t("userConfig:_shared.保存_be5f")}
      </button>
      <button
        onClick={onReload}
        className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2.5 py-1.5 rounded-md hover:bg-slate-50 transition-colors"
      >
        <RefreshIcon />
        {t("userConfig:_shared.ui.reload")}
      </button>
      <button
        onClick={onReset}
        className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-700 px-2.5 py-1.5 rounded-md hover:bg-red-50 transition-colors"
      >
        <RestoreIcon />
        {t("userConfig:_shared.ui.restoreDefault")}
      </button>
      {onExtra && extraLabel && (
        <button
          onClick={onExtra}
          className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2.5 py-1.5 rounded-md hover:bg-slate-50 transition-colors"
        >
          <PlusIcon />
          {extraLabel}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status message
// ---------------------------------------------------------------------------

export function StatusMessage({ message, kind }: { message: string; kind: "success" | "error" | "info" }) {
  if (!message) return null;

  const cls =
    kind === "error"
      ? "text-red-700 bg-red-50 border-red-200"
      : kind === "success"
        ? "text-emerald-700 bg-emerald-50 border-emerald-200"
        : "text-slate-600 bg-slate-50 border-slate-200";

  const icon =
    kind === "error" ? <AlertCircleIcon /> : kind === "success" ? <CheckIcon /> : null;

  return (
    <div className={`mt-3 text-xs rounded-md px-3 py-2 border flex items-center gap-2 ${cls}`}>
      {icon}
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Keyword Chip Input
// ---------------------------------------------------------------------------

export function KeywordChipInput({
  label,
  items,
  placeholder,
  onChange,
}: {
  label: string;
  items: string[];
  placeholder: string;
  onChange: (items: string[]) => void;
}) {
  const { t } = useTranslation();
  const [inputValue, setInputValue] = useState("");

  const addItem = () => {
    const val = inputValue.trim();
    if (!val) return;
    onChange([...items, val]);
    setInputValue("");
  };

  const removeItem = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addItem();
    }
  };

  return (
    <div>
      <label className="text-xs font-medium text-slate-500 mb-1 block">{label}</label>
      <div className="flex flex-wrap gap-1.5 mb-1.5 min-h-[24px]">
        {items.map((kw, i) => (
          <span
            key={`${kw}-${i}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-sky-50 text-sky-700 cursor-pointer hover:bg-sky-100 transition-colors"
            onClick={() => removeItem(i)}
            title={t("userConfig:_shared.点击删除_4239")}
          >
            {kw}
            <svg className="w-3 h-3 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </span>
        ))}
      </div>
      <div className="flex gap-1.5">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="input flex-1"
        />
        <button
          type="button"
          onClick={addItem}
          className="btn btn-ghost px-2 text-teal-600 hover:text-teal-700"
          title={t("userConfig:_shared.添加关键字_f1cc")}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>
    </div>
  );
}
