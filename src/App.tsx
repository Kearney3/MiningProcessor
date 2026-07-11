import { useState } from "react";
import { usePythonBridge } from "./hooks/usePythonBridge";
import type { PageId } from "./lib/types";
import { Sidebar } from "./components/Sidebar";
import { LogPanel } from "./components/LogPanel";
import { ToastProvider } from "./components/Toast";
import { ConnectionStatusBadge } from "./components/ConnectionStatusBadge";
import { DataProcessingPage } from "./components/pages/DataProcessingPage";
import { BatchProcessingPage } from "./components/pages/BatchProcessingPage";
import { DataSyncPage } from "./components/pages/DataSyncPage";
import { LedgerMatchPage } from "./components/pages/LedgerMatchPage";
import { EquipmentLedgerPage } from "./components/pages/EquipmentLedgerPage";
import { OilLedgerPage } from "./components/pages/OilLedgerPage";
import { LoadConfigPage } from "./components/pages/LoadConfigPage";
import { MaintConfigPage } from "./components/pages/MaintConfigPage";
import { UserConfigPage } from "./components/pages/UserConfigPage";

function App() {
  const [currentPage, setCurrentPage] = useState<PageId>("data-processing");
  const bridge = usePythonBridge();

  return (
    <ToastProvider>
    <div className="flex flex-col h-screen bg-[var(--color-bg)]">
      {/* Header */}
      <header
        data-tauri-drag-region
        className="flex items-center h-11 px-4 bg-white border-b border-slate-200 select-none shrink-0"
      >
        {/* Logo */}
        <div className="flex items-center gap-2">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-slate-700"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          <span className="text-sm font-semibold text-slate-800">
            矿山数据处理工具
          </span>
        </div>

        {/* Connection badge */}
        <ConnectionStatusBadge
          status={bridge.connectionStatus}
          error={bridge.connectionError}
          logs={bridge.connectionLogs}
          bridgeInfo={bridge.bridgeInfo}
          onReconnect={bridge.reconnect}
        />

        {/* Version */}
        <span className="text-xs text-slate-400 ml-auto">v1.2.0</span>
      </header>

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} />
        <main className="flex-1 overflow-auto p-5">
          <div style={{ display: currentPage === "data-processing" ? "block" : "none" }}>
            <DataProcessingPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "batch-processing" ? "block" : "none" }}>
            <BatchProcessingPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "data-sync" ? "block" : "none" }}>
            <DataSyncPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "ledger-match" ? "block" : "none" }}>
            <LedgerMatchPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "equipment-ledger" ? "block" : "none" }}>
            <EquipmentLedgerPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "oil-ledger" ? "block" : "none" }}>
            <OilLedgerPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "load-config" ? "block" : "none" }}>
            <LoadConfigPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "maint-config" ? "block" : "none" }}>
            <MaintConfigPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "user-config" ? "block" : "none" }}>
            <UserConfigPage bridge={bridge} />
          </div>
        </main>
      </div>

      {/* Log panel */}
      <LogPanel logs={bridge.logs} onClear={bridge.clearLogs} />
    </div>
    </ToastProvider>
  );
}

export default App;
