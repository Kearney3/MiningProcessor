import type { JSX } from "react";
import type { PageId } from "../lib/types";

// --- Inline SVG icons (Lucide-style, 18x18 viewBox) ---

function IconTable() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18" />
      <path d="M3 15h18" />
      <path d="M9 3v18" />
    </svg>
  );
}

function IconFolderStack() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2Z" />
      <path d="M12 13h4" />
      <path d="M12 17h4" />
      <circle cx="8" cy="15" r="1" fill="currentColor" />
    </svg>
  );
}

function IconRefresh() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M21 21v-5h-5" />
    </svg>
  );
}

function IconLink() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}

function IconTruck() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
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
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z" />
    </svg>
  );
}

function IconSliders() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </svg>
  );
}

function IconUser() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function IconPickaxe() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 10l-2 2m0 0l-7 7M12 12l7-7" />
      <path d="M5 21l2.5-2.5" />
      <path d="M21.5 2.5L17 7" />
      <path d="M19 2l-9 9" />
      <path d="M2 19l9-9" />
    </svg>
  );
}

// --- Icon registry ---

const ICONS: Record<string, () => JSX.Element> = {
  "data-processing": IconTable,
  "batch-processing": IconFolderStack,
  "data-sync": IconRefresh,
  "ledger-match": IconLink,
  "equipment-ledger": IconTruck,
  "oil-ledger": IconDroplet,
  "load-config": IconSliders,
  "user-config": IconUser,
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
      <div className="px-4 mb-2 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
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
                relative w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm
                transition-colors duration-150 cursor-pointer
                ${isActive
                  ? "bg-[#1E3A5F] text-white font-medium"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-300"
                }
              `}
            >
              {/* Active left accent bar */}
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-blue-400 rounded-r" />
              )}
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
    <aside className="w-52 shrink-0 bg-[#0F172A] overflow-y-auto thin-scrollbar flex flex-col">
      {/* Logo area */}
      <div className="flex items-center gap-2.5 px-4 pt-4 pb-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 shadow-lg shadow-blue-500/20">
          <span className="text-white">
            <IconPickaxe />
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-white tracking-tight leading-tight">
            矿山数据处理
          </span>
          <span className="text-[10px] text-slate-500 leading-tight">
            Mining Processor
          </span>
        </div>
      </div>

      {/* Divider */}
      <div className="mx-3 border-t border-white/5" />

      {/* Nav sections */}
      <nav className="py-3 flex-1">
        {renderGroup("工作区", WORKSPACE_ITEMS)}
        {renderGroup("管理", MANAGEMENT_ITEMS)}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-white/5">
        <span className="text-[10px] text-slate-600">
          Powered by Tauri + Python
        </span>
      </div>
    </aside>
  );
}
