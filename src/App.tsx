import { useState, useEffect } from "react";
import { getVersion } from "@tauri-apps/api/app";
import { useTranslation } from "react-i18next";
import { usePythonBridge } from "./hooks/usePythonBridge";
import type { PageId } from "./lib/types";
import { Sidebar } from "./components/Sidebar";
import { LogPanel } from "./components/LogPanel";
import { ToastProvider } from "./components/Toast";
import { ConnectionStatusBadge } from "./components/ConnectionStatusBadge";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { DataProcessingPage } from "./components/pages/DataProcessingPage";
import { BatchProcessingPage } from "./components/pages/BatchProcessingPage";
import { DataSyncPage } from "./components/pages/DataSyncPage";
import { LedgerMatchPage } from "./components/pages/LedgerMatchPage";
import { EquipmentLedgerPage } from "./components/pages/EquipmentLedgerPage";
import { OilLedgerPage } from "./components/pages/OilLedgerPage";
import { ModelLedgerPage } from "./components/pages/ModelLedgerPage";
import { DailyReportPage } from "./components/pages/DailyReportPage";
import { LoadConfigPage } from "./components/pages/LoadConfigPage";
import { MaintConfigPage } from "./components/pages/MaintConfigPage";
import { UserConfigPage } from "./components/pages/UserConfigPage";
import { LLMLabelingPage } from "./components/pages/LLMLabelingPage";
import { ErrorBoundary } from "./components/ErrorBoundary";

function App() {
  const { t } = useTranslation();
  const [currentPage, setCurrentPage] = useState<PageId>("data-processing");
  const [appVersion, setAppVersion] = useState("v2.7.0");
  const bridge = usePythonBridge();

  useEffect(() => {
    getVersion()
      .then((v) => setAppVersion(`v${v}`))
      .catch(() => {});
  }, []);

  return (
    <ToastProvider>
    <div className="app-shell flex flex-col h-screen">
      {/* Header */}
      <header
        data-tauri-drag-region
        className="app-header flex items-center select-none shrink-0"
      >
        {/* Logo */}
        <div className="app-brand flex items-center gap-2.5">
          <span className="app-brand-mark">
          <svg
            width="17"
            height="17"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M4 18.5 9.2 9l3.1 5 2.4-3.5L20 18.5" />
            <path d="M4 18.5h16" />
            <path d="M6.2 15.5h11.6" opacity=".65" />
          </svg>
          </span>
          <span className="text-sm font-semibold text-slate-800">
            {t("app:miningData")}
          </span>
        </div>

        <div className="flex flex-1 items-center px-4">
          {/* Connection badge */}
          <ConnectionStatusBadge
            status={bridge.connectionStatus}
            error={bridge.connectionError}
            logs={bridge.connectionLogs}
            bridgeInfo={bridge.bridgeInfo}
            onReconnect={bridge.reconnect}
          />

          {/* Version */}
          <span className="text-xs text-slate-500 ml-auto tabular-nums">
            {appVersion}
          </span>
          <LanguageSwitcher />
        </div>
      </header>

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} />
        <ErrorBoundary>
        <main className="workspace-content flex-1 overflow-auto">
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
          <div style={{ display: currentPage === "llm-labeling" ? "block" : "none" }}>
            <LLMLabelingPage bridge={bridge} progress={bridge.progress} setProgress={bridge.setProgress} />
          </div>
          <div style={{ display: currentPage === "equipment-ledger" ? "block" : "none" }}>
            <EquipmentLedgerPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "oil-ledger" ? "block" : "none" }}>
            <OilLedgerPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "model-ledger" ? "block" : "none" }}>
            <ModelLedgerPage bridge={bridge} />
          </div>
          <div style={{ display: currentPage === "daily-report" ? "block" : "none" }}>
            <DailyReportPage bridge={bridge} />
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
        </ErrorBoundary>
      </div>

      {/* Log panel */}
      <LogPanel logs={bridge.logs} onClear={bridge.clearLogs} />
    </div>
    </ToastProvider>
  );
}

export default App;
