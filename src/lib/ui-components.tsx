/**
 * 共享 UI 组件库
 *
 * 从各页面文件中提取的通用交互组件，统一维护。
 */
import * as React from "react";
import { useTranslation } from "react-i18next";
import { open } from "@tauri-apps/plugin-dialog";
import { FolderIcon, FileIcon, AlertTriangleIcon, ChevronDownIcon } from "./icons";
import { inputClass, btnSecondaryClass, btnDangerClass } from "./ui-classes";

// ═══════════════════════════════════════
// ToggleSwitch — 通用开关控件
// ═══════════════════════════════════════

export function ToggleSwitch({
  checked,
  onChange,
  activeColor = "bg-blue-600",
  disabled = false,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  /** 选中时的背景色，默认 bg-blue-600；LedgerMatchPage 使用 bg-slate-900 */
  activeColor?: string;
  disabled?: boolean;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-disabled={disabled}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
        checked ? activeColor : "bg-slate-200"
      } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
          checked ? "translate-x-4" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

// ═══════════════════════════════════════
// StyledToggle — 带标签的开关控件
// ═══════════════════════════════════════

export function StyledToggle({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <label className={`flex items-center gap-2.5 select-none ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}>
      <ToggleSwitch checked={checked} onChange={onChange} disabled={disabled} />
      <span className={`text-sm ${disabled ? "text-slate-400" : "text-slate-700"}`}>{label}</span>
    </label>
  );
}

// ═══════════════════════════════════════
// ChipToggle — 芯片式互斥选项切换
// ═══════════════════════════════════════

export function ChipToggle({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string; tip?: string }[];
}) {
  return (
    <div className="inline-flex rounded-md border border-slate-200 overflow-hidden">
      {options.map((o, i) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          title={o.tip}
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
// PathInput — 文件/文件夹选择输入
// ═══════════════════════════════════════

export function PathInput({
  value,
  onChange,
  placeholder,
  directory = false,
  defaultPath,
  onFileSelected,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  directory?: boolean;
  defaultPath?: string;
  onFileSelected?: (path: string) => void;
}) {
  const { t } = useTranslation();
  const browse = async () => {
    const selected = await open({
      directory,
      multiple: false,
      defaultPath,
      filters: directory
        ? undefined
        : [{ name: "Excel", extensions: ["xlsx", "xls"] }],
    });
    if (selected) {
      const p = selected as string;
      onChange(p);
      onFileSelected?.(p);
    }
  };

  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`${inputClass} flex-1 ${value === "" ? "border-amber-300 bg-amber-50/30" : ""}`}
      />
      <button onClick={browse} className={btnSecondaryClass} title={directory ? t("lib:ui-components.selectFolder") : t("lib:ui-components.selectFile")}>
        {directory ? <FolderIcon /> : <FileIcon />}
      </button>
    </div>
  );
}

// ═══════════════════════════════════════
// ConfirmDialog — 确认弹窗
// ═══════════════════════════════════════

export function ConfirmDialog({
  title,
  message,
  details,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  details?: string[];
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-lg shadow-lg max-w-md w-full mx-4 overflow-hidden">
        <div className="px-6 pt-6 pb-2">
          <div className="flex items-center gap-3 mb-3">
            <div className="shrink-0 w-9 h-9 rounded-md bg-amber-50 flex items-center justify-center">
              <AlertTriangleIcon />
            </div>
            <h3 className="text-base font-semibold text-slate-800">{title}</h3>
          </div>
          <p className="text-sm text-slate-600 leading-relaxed">{message}</p>
          {details && details.length > 0 && (
            <ul className="mt-3 space-y-1">
              {details.map((d, i) => (
                <li key={i} className="flex items-center gap-2 text-xs text-slate-500">
                  <span className="w-1 h-1 rounded-full bg-slate-400 shrink-0" />
                  {d}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex justify-end gap-2 px-6 py-4 bg-slate-50 border-t border-slate-100">
          <button onClick={onCancel} className={btnSecondaryClass}>
            {cancelLabel ?? t("lib:ui-components.cancel")}
          </button>
          <button onClick={onConfirm} className={btnDangerClass}>
            {confirmLabel ?? t("lib:ui-components.ok")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// Collapsible — 可折叠区域
// ═══════════════════════════════════════

export function Collapsible({
  title,
  icon,
  summary,
  defaultOpen = false,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  summary?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
      >
        {icon && <span className="text-slate-400">{icon}</span>}
        <span className="flex-1 text-left">{title}</span>
        {!open && summary}
        <ChevronDownIcon />
      </button>
      {open && <div className="px-4 pb-4 pt-1">{children}</div>}
    </div>
  );
}

// ═══════════════════════════════════════
// SectionDivider — 区域分隔线
// ═══════════════════════════════════════

export function SectionDivider({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 my-4">
      <div className="flex-1 h-px bg-slate-200" />
      {label && <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</span>}
      <div className="flex-1 h-px bg-slate-200" />
    </div>
  );
}
