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
    <div className="flex flex-col h-screen bg-slate-50">
      {/* Header */}
      <header
        data-tauri-drag-region
        className="flex items-center h-12 px-5 select-none shrink-0 border-b border-slate-200/80"
        style={{
          background: "linear-gradient(to right, #ffffff 0%, #f0fdfa 50%, #ffffff 100%)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-6 h-6 rounded-md bg-gradient-to-br from-cyan-500 to-cyan-600 shadow-sm">
            <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          </div>
          <span className="text-sm font-semibold text-slate-800 tracking-tight">
            矿山数据处理工具
          </span>
          <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium text-cyan-700 bg-cyan-50 rounded-full border border-cyan-200/60">
            v0.2.0
          </span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200/60">
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full ${
                bridge.isConnected ? "bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.4)]" : "bg-red-400"
              }`}
            />
            <span className="text-[11px] text-slate-500 font-medium">
              {bridge.isConnected ? "已连接" : "未连接"}
            </span>
          </div>
        </div>
      </header>

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
