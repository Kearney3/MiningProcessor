import type { PageId } from "../lib/types";

interface NavItem {
  id: PageId;
  label: string;
  icon: string;
}

const WORKSPACE_ITEMS: NavItem[] = [
  { id: "data-processing", label: "数据处理", icon: "📊" },
  { id: "batch-processing", label: "批量处理", icon: "📁" },
  { id: "data-sync", label: "数据同步", icon: "🔄" },
  { id: "ledger-match", label: "台账匹配", icon: "🔗" },
];

const MANAGEMENT_ITEMS: NavItem[] = [
  { id: "equipment-ledger", label: "设备台账", icon: "🏗️" },
  { id: "oil-ledger", label: "油品台账", icon: "🛢️" },
  { id: "load-config", label: "装载量配置", icon: "⚙️" },
  { id: "user-config", label: "用户配置", icon: "👤" },
];

interface SidebarProps {
  currentPage: PageId;
  onNavigate: (page: PageId) => void;
}

export function Sidebar({ currentPage, onNavigate }: SidebarProps) {
  const renderGroup = (title: string, items: NavItem[]) => (
    <div className="mb-2">
      <div className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
        {title}
      </div>
      <div className="space-y-0.5">
        {items.map((item) => {
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`
                group relative w-full flex items-center gap-2.5 pl-3 pr-3 py-2 rounded-lg text-sm
                transition-all duration-200 ease-out cursor-pointer
                ${isActive
                  ? "bg-cyan-50/80 text-cyan-700 font-medium shadow-sm shadow-cyan-100/50"
                  : "text-slate-500 hover:bg-slate-100/70 hover:text-slate-700 hover:scale-[1.02] active:scale-[0.98]"
                }
              `}
            >
              {/* Active indicator bar */}
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-cyan-500 rounded-r-full" />
              )}
              <span
                className={`
                  text-base leading-none transition-transform duration-200
                  group-hover:scale-110
                `}
              >
                {item.icon}
              </span>
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );

  return (
    <aside className="w-52 shrink-0 bg-white border-r border-slate-200/80 overflow-y-auto thin-scrollbar flex flex-col">
      <nav className="py-3 px-2 flex-1">
        {renderGroup("工作区", WORKSPACE_ITEMS)}
        {renderGroup("管理", MANAGEMENT_ITEMS)}
      </nav>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-slate-100">
        <div className="flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md bg-slate-50/80 border border-slate-200/50">
          <span className="text-[10px] text-slate-400 font-medium tracking-wide">Powered by</span>
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold text-cyan-700 bg-cyan-50 rounded border border-cyan-200/50">
            Tauri
          </span>
          <span className="text-[10px] text-slate-300">+</span>
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 bg-amber-50 rounded border border-amber-200/50">
            Python
          </span>
        </div>
      </div>
    </aside>
  );
}
