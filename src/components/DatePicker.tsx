import { useState, useRef, useEffect } from "react";
import { DayPicker } from "react-day-picker";
import "react-day-picker/style.css";
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon } from "../lib/icons";
import { formatLocalDate, localToday, parseLocalDate } from "../lib/dateUtils";

// ─── Component ────────────────────────────────────────────────────────

export interface DatePickerProps {
  value: string;                     // ISO date string "YYYY-MM-DD" or ""
  onChange: (iso: string) => void;
  placeholder?: string;
  label?: string;
  className?: string;
}

export function DatePicker({
  value,
  onChange,
  placeholder = "选择日期",
  label,
  className = "",
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const selected = parseLocalDate(value);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleSelect = (day: Date | undefined) => {
    onChange(formatLocalDate(day));
    setOpen(false);
  };

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {label && (
        <label className="text-xs text-slate-400 mb-1 block">{label}</label>
      )}
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`
          flex items-center gap-2 w-full border rounded-md px-3 py-1.5 text-sm
          transition-colors outline-none
          ${open
            ? "border-blue-500 ring-2 ring-blue-500/20"
            : "border-slate-300 hover:border-slate-400"
          }
          ${value ? "text-slate-800" : "text-slate-400"}
          bg-white
        `}
      >
        <CalendarIcon className="w-4 h-4 shrink-0 text-slate-400" />
        <span className="flex-1 text-left truncate">
          {value || placeholder}
        </span>
      </button>

      {/* Popover calendar */}
      {open && (
        <div
          className="
            absolute z-50 mt-1.5 bg-white rounded-lg shadow-lg
            border border-slate-200 p-3
          "
          style={{ minWidth: 280 }}
        >
          <DayPicker
            mode="single"
            selected={selected}
            onSelect={handleSelect}
            defaultMonth={selected ?? localToday()}
            captionLayout="dropdown"
            navLayout="around"
            startMonth={new Date(2015, 0)}
            endMonth={new Date(2040, 11)}
            classNames={{
              root: "rdp-root",
              months: "flex flex-col gap-4",
              month: "flex flex-col gap-3",
              month_caption: "flex items-center justify-between px-1",
              caption_label: "text-sm font-medium text-slate-700",
              nav: "flex items-center gap-1",
              button_previous: cnNavBtn("order-first"),
              button_next: cnNavBtn(""),
              weekdays: "grid grid-cols-7",
              weekday: "text-xs font-medium text-slate-400 text-center py-1",
              weeks: "flex flex-col gap-0.5",
              week: "grid grid-cols-7",
              day: "text-center",
              day_button: cnDayBtn(),
              selected: "bg-slate-900 text-white hover:bg-slate-800 rounded-md",
              today: "font-semibold text-blue-600",
              outside: "text-slate-300",
              disabled: "text-slate-300 cursor-not-allowed",
              hidden: "invisible",
              range_start: "",
              range_end: "",
              range_middle: "",
            }}
            components={{
              Chevron: ({ orientation }) =>
                orientation === "left" ? <ChevronLeftIcon /> : <ChevronRightIcon />,
            }}
          />
        </div>
      )}
    </div>
  );
}

// ─── Tailwind class helpers ───────────────────────────────────────────

function cnNavBtn(extra: string): string {
  return `
    inline-flex items-center justify-center w-7 h-7 rounded-md
    text-slate-500 hover:bg-slate-100 hover:text-slate-700
    transition-colors cursor-pointer ${extra}
  `;
}

function cnDayBtn(): string {
  return `
    inline-flex items-center justify-center w-8 h-8 text-sm rounded-md
    text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer
    focus:outline-none focus:ring-2 focus:ring-blue-500/30
  `;
}
