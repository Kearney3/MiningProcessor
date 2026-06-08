import type { JSX } from "react";
import type { PageId } from "../lib/types";

// --- Inline SVG icons (Lucide-style, 16x16, stroke-width 2) ---

function IconTable() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18" />
      <path d="M3 15h18" />
      <path d="M9 3v18" />
    </svg>
  );
}

function IconFolderOpen() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
      <path d="M2 10h20" />
    </svg>
  );
}

function IconRefreshCw() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M21 21v-5h-5" />
    </svg>
  );
}

function IconLink() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}

function IconTruck() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h1" />
      <path d="M15 18h-1" />
      <path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14" />
      <circle cx="7" cy="18" r="2" />
      <circle cx="19" cy="18" r="2" />
    </svg>
  );
}

function IconDroplet() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z" />
    </svg>
  );
}

function IconSlidersHorizontal() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="21" y1="4" x2="14" y2="4" />
      <line x1="10" y1="4" x2="3" y2="4" />
      <line x1="21" y1="12" x2="12" y2="12" />
      <line x1="8" y1="12" x2="3" y2="12" />
      <line x1="21" y1="20" x2="16" y2="20" />
      <line x1="12" y1="20" x2="3" y2="20" />
      <line x1="14" y1="2" x2="14" y2="6" />
      <line x1="8" y1="10" x2="8" y2="14" />
      <line x1="16" y1="18" x2="16" y2="22" />
    </svg>
  );
}

function IconUserCog() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="7" r="4" />
      <path d="M5.5 21a6.5 6.5 0 0 1 13 0" />
      <path d="M17 11l.003-.001" />
      <path d="M17 15l.003-.001" />
      <path d="M20.4 13.5l.002-.001" />
      <path d="M20.4 17.5l.002-.001" />
      <path d="M23.8 15.5l.002-.001" />
    </svg>
  );
}

// --- Icon registry ---

const ICONS: Record<string, () => JSX.Element> = {
  "data-processing": IconTable,
  "batch-processing": IconFolderOpen,
  "data-sync": IconRefreshCw,
  "ledger-match": IconLink,
  "equipment-ledger": IconTruck,
  "oil-ledger": IconDroplet,
  "load-config": IconSlidersHorizontal,
  "user-config": IconUserCog,
};

// --- Nav item definitions ---

interface NavItem {
  id: PageId;
  label: string;
}

const WORKSPACE_ITEMS: NavItem[] = [
  { id: "data-processing", label: "数据处理" },
  { id: "batch-processing", label: "批量处理" },
  { id: "data-sync", label: "数据同步" },
  { id: "ledger-match", label: "台账匹配" },
];

const MANAGEMENT_ITEMS: NavItem[] = [
  { id: "equipment-ledger", label: "设备台账" },
  { id: "oil-ledger", label: "油品台账" },
  { id: "load-config", label: "装载量配置" },
  { id: "user-config", label: "用户配置" },
];

// --- Component ---

interface SidebarProps {
  currentPage: PageId;
  onNavigate: (page: PageId) => void;
}

export function Sidebar({ currentPage, onNavigate }: SidebarProps) {
  const renderGroup = (title: string, items: NavItem[]) => (
    <div className="mb-3">
      <div className="px-3 mb-1 text-[10px] font-medium text-slate-400 uppercase tracking-wider">
        {title}
      </div>
      <div className="space-y-0.5 px-2">
        {items.map((item) => {
          const isActive = currentPage === item.id;
          const Icon = ICONS[item.id];
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`
                w-full flex items-center gap-2.5 px-3 py-1.5 rounded-md text-[13px]
                transition-colors duration-150 cursor-pointer
                ${isActive
                  ? "bg-blue-50 text-blue-700 font-medium border-l-2 border-blue-600"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-800"
                }
              `}
            >
              <span className="shrink-0 leading-none">
                {Icon ? <Icon /> : null}
              </span>
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );

  return (
    <aside className="w-48 shrink-0 bg-slate-50 border-r border-slate-200 overflow-y-auto thin-scrollbar flex flex-col">
      {/* Nav sections */}
      <nav className="py-3 flex-1">
        {renderGroup("工作区", WORKSPACE_ITEMS)}
        {renderGroup("管理", MANAGEMENT_ITEMS)}
      </nav>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-slate-200">
        <span className="text-[10px] text-slate-400">
          Tauri + Python
        </span>
      </div>
    </aside>
  );
}
