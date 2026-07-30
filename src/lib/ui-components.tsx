/**
 * 共享 UI 组件库
 *
 * 从各页面文件中提取的通用交互组件，统一维护。
 */

// ═══════════════════════════════════════
// ToggleSwitch — 通用开关控件
// ═══════════════════════════════════════

export function ToggleSwitch({
  checked,
  onChange,
  activeColor = "bg-blue-600",
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  /** 选中时的背景色，默认 bg-blue-600；LedgerMatchPage 使用 bg-slate-900 */
  activeColor?: string;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-8 items-center rounded-full transition-colors ${
        checked ? activeColor : "bg-slate-200"
      }`}
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
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer select-none">
      <ToggleSwitch checked={checked} onChange={onChange} />
      <span className="text-sm text-slate-700">{label}</span>
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
