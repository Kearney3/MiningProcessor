import { lazy, Suspense, useState, useEffect } from "react";
import { getVersion } from "@tauri-apps/api/app";
import { useTranslation } from "react-i18next";
import { usePythonBridge } from "./hooks/usePythonBridge";
import type { PageId } from "./lib/types";
import { Sidebar } from "./components/Sidebar";
import { LogPanel } from "./components/LogPanel";
import { ToastProvider } from "./components/Toast";
import { ConnectionStatusBadge } from "./components/ConnectionStatusBadge";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { ErrorBoundary } from "./components/ErrorBoundary";

// Keep page code out of the initial bundle and mount only the active page. The
// old display:none wrappers mounted every page at startup, so every page-level
// effect ran before the user opened that page.
const DataProcessingPage = lazy(() =>
  import("./components/pages/DataProcessingPage").then(({ DataProcessingPage }) => ({ default: DataProcessingPage })),
);
const BatchProcessingPage = lazy(() =>
  import("./components/pages/BatchProcessingPage").then(({ BatchProcessingPage }) => ({ default: BatchProcessingPage })),
);
const DataSyncPage = lazy(() =>
  import("./components/pages/DataSyncPage").then(({ DataSyncPage }) => ({ default: DataSyncPage })),
);
const LedgerMatchPage = lazy(() =>
  import("./components/pages/LedgerMatchPage").then(({ LedgerMatchPage }) => ({ default: LedgerMatchPage })),
);
const LLMLabelingPage = lazy(() =>
  import("./components/pages/LLMLabelingPage").then(({ LLMLabelingPage }) => ({ default: LLMLabelingPage })),
);
const EquipmentLedgerPage = lazy(() =>
  import("./components/pages/EquipmentLedgerPage").then(({ EquipmentLedgerPage }) => ({ default: EquipmentLedgerPage })),
);
const OilLedgerPage = lazy(() =>
  import("./components/pages/OilLedgerPage").then(({ OilLedgerPage }) => ({ default: OilLedgerPage })),
);
const ModelLedgerPage = lazy(() =>
  import("./components/pages/ModelLedgerPage").then(({ ModelLedgerPage }) => ({ default: ModelLedgerPage })),
);
const DailyReportPage = lazy(() =>
  import("./components/pages/DailyReportPage").then(({ DailyReportPage }) => ({ default: DailyReportPage })),
);
const LoadConfigPage = lazy(() =>
  import("./components/pages/LoadConfigPage").then(({ LoadConfigPage }) => ({ default: LoadConfigPage })),
);
const MaintConfigPage = lazy(() =>
  import("./components/pages/MaintConfigPage").then(({ MaintConfigPage }) => ({ default: MaintConfigPage })),
);
const UserConfigPage = lazy(() =>
  import("./components/pages/UserConfigPage").then(({ UserConfigPage }) => ({ default: UserConfigPage })),
);

type Bridge = ReturnType<typeof usePythonBridge>;

function ActivePage({ currentPage, bridge }: { currentPage: PageId; bridge: Bridge }) {
  switch (currentPage) {
    case "data-processing":
      return <DataProcessingPage bridge={bridge} />;
    case "batch-processing":
      return <BatchProcessingPage bridge={bridge} />;
    case "data-sync":
      return <DataSyncPage bridge={bridge} />;
    case "ledger-match":
      return <LedgerMatchPage bridge={bridge} />;
    case "llm-labeling":
      return <LLMLabelingPage bridge={bridge} progress={bridge.progress} setProgress={bridge.setProgress} />;
    case "equipment-ledger":
      return <EquipmentLedgerPage bridge={bridge} />;
    case "oil-ledger":
      return <OilLedgerPage bridge={bridge} />;
    case "model-ledger":
      return <ModelLedgerPage bridge={bridge} />;
    case "daily-report":
      return <DailyReportPage bridge={bridge} />;
    case "load-config":
      return <LoadConfigPage bridge={bridge} />;
    case "maint-config":
      return <MaintConfigPage bridge={bridge} />;
    case "user-config":
      return <UserConfigPage bridge={bridge} />;
  }
}

function PageLoading() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-48 items-center justify-center text-sm text-slate-500">
      {t("pages:LLMLabelingPage.text")}
    </div>
  );
}

function App() {
  const { t } = useTranslation();
  const [currentPage, setCurrentPage] = useState<PageId>("data-processing");
  const [appVersion, setAppVersion] = useState("v2.8.0");
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
          <Suspense fallback={<PageLoading />}>
            <ActivePage currentPage={currentPage} bridge={bridge} />
          </Suspense>
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
