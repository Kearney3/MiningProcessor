import { useState } from "react";
import { usePythonBridge } from "./hooks/usePythonBridge";
import type { PageId } from "./lib/types";
import { Sidebar } from "./components/Sidebar";
import { LogPanel } from "./components/LogPanel";
import { DataProcessingPage } from "./components/pages/DataProcessingPage";
import { BatchProcessingPage } from "./components/pages/BatchProcessingPage";
import { DataSyncPage } from "./components/pages/DataSyncPage";
import { LedgerMatchPage } from "./components/pages/LedgerMatchPage";
import { EquipmentLedgerPage } from "./components/pages/EquipmentLedgerPage";
import { OilLedgerPage } from "./components/pages/OilLedgerPage";
import { LoadConfigPage } from "./components/pages/LoadConfigPage";
import { UserConfigPage } from "./components/pages/UserConfigPage";

const PAGE_TITLES: Record<PageId, string> = {
  "data-processing": "数据处理",
  "batch-processing": "批量处理",
  "data-sync": "数据同步",
  "ledger-match": "台账匹配",
  "equipment-ledger": "设备台账",
  "oil-ledger": "油品台账",
  "load-config": "装载量配置",
  "user-config": "用户配置",
};

function App() {
  const [currentPage, setCurrentPage] = useState<PageId>("data-processing");
  const bridge = usePythonBridge();

  const renderPage = () => {
    switch (currentPage) {
      case "data-processing":
        return <DataProcessingPage bridge={bridge} />;
      case "batch-processing":
        return <BatchProcessingPage bridge={bridge} />;
      case "data-sync":
        return <DataSyncPage bridge={bridge} />;
      case "ledger-match":
        return <LedgerMatchPage bridge={bridge} />;
      case "equipment-ledger":
        return <EquipmentLedgerPage bridge={bridge} />;
      case "oil-ledger":
        return <OilLedgerPage bridge={bridge} />;
      case "load-config":
        return <LoadConfigPage bridge={bridge} />;
      case "user-config":
        return <UserConfigPage bridge={bridge} />;
      default:
        return (
          <div className="flex items-center justify-center h-full text-slate-400">
            页面开发中...
          </div>
        );
    }
  };

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header
        data-tauri-drag-region
        className="flex items-center h-12 px-5 select-none shrink-0"
        style={{
          background: "linear-gradient(to right, #0F172A 0%, #1E293B 100%)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <span className="text-sm font-semibold text-white tracking-tight">
            矿山数据处理工具
          </span>
          <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium text-slate-300 bg-slate-700/80 rounded-full">
            v0.2.0
          </span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/5 border border-white/10">
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full ${
                bridge.isConnected ? "bg-green-400 shadow-[0_0_4px_rgba(74,222,128,0.4)]" : "bg-red-400"
              }`}
            />
            <span className="text-[11px] text-slate-400 font-medium">
              {bridge.isConnected ? "已连接" : "未连接"}
            </span>
          </div>
        </div>
      </header>

      {/* Page title breadcrumb */}
      <div className="h-9 px-6 flex items-center border-b border-slate-200/80 bg-white shrink-0">
        <span className="text-xs text-slate-400">首页</span>
        <span className="mx-2 text-slate-300 text-xs">/</span>
        <span className="text-xs font-medium text-slate-600">
          {PAGE_TITLES[currentPage] ?? currentPage}
        </span>
      </div>

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} />
        <main className="flex-1 overflow-auto p-6 bg-slate-50/50">
          {renderPage()}
        </main>
      </div>

      {/* Log panel */}
      <LogPanel logs={bridge.logs} onClear={bridge.clearLogs} />
    </div>
  );
}

export default App;
