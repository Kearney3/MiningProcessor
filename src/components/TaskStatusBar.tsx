import { useTranslation } from "react-i18next";
import type { BridgeTask, PageId } from "../lib/types";
import { useToast } from "./Toast";

const TASK_LABELS: Record<string, string> = {
  process_fuel: "pages:DataProcessingPage.fuelProcessing",
  process_tire: "pages:DataProcessingPage.tireProcessing",
  process_production: "pages:DataProcessingPage.productionData",
  process_electrical: "pages:DataProcessingPage.electricalConsumption",
  process_worktime: "pages:DataProcessingPage.worktimeProcessing",
  process_merge: "pages:DataProcessingPage.fileMerge",
  process_maintenance: "pages:DataProcessingPage.maintenanceRecords",
  process_maintenance_llm: "pages:LLMLabelingPage.useAnLlmToClassifyMaintenanceDetails",
  batch_process: "pages:BatchProcessingPage.batchProcessing",
  sync_minebase: "pages:DataSyncPage.dataSync",
  daily_report_export: "pages:DailyReportPage.dailyReport",
};

export function TaskStatusBar({
  task,
  currentPage,
  onCancel,
  onReturn,
  onDismiss,
}: {
  task: BridgeTask | null;
  currentPage: PageId;
  onCancel: () => Promise<void>;
  onReturn: (page: PageId) => void;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  const { notify } = useToast();
  if (!task) return null;

  const running = task.status === "running" || task.status === "cancelling";
  const canShowProgress = task.progress && Number.isFinite(task.progress.percent);
  const percent = canShowProgress
    ? Math.max(0, Math.min(100, Math.round(task.progress!.percent)))
    : null;
  const statusLabel = t(`components:TaskStatusBar.${task.status}`);
  const isAway = currentPage !== task.page;
  const handleCancel = async () => {
    try {
      await onCancel();
    } catch (error) {
      notify(t("components:TaskStatusBar.cancelFailed", { error: String(error) }), "error");
    }
  };

  return (
    <section
      aria-label={t("components:TaskStatusBar.processing")}
      aria-busy={running}
      className={`mb-5 rounded-lg border px-4 py-3 ${
        task.status === "failed"
          ? "border-red-200 bg-red-50"
          : task.status === "completed"
            ? "border-emerald-200 bg-emerald-50"
            : "border-blue-200 bg-blue-50"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className={`h-2 w-2 shrink-0 rounded-full ${
          task.status === "failed" ? "bg-red-500" : task.status === "completed" ? "bg-emerald-500" : "bg-blue-500"
        }`} aria-hidden="true" />
        <span className="text-sm font-medium text-slate-800">
          {t(TASK_LABELS[task.method] ?? "components:TaskStatusBar.processing")}
        </span>
        <span role="status" className="text-xs text-slate-600">{statusLabel}</span>
        {percent !== null && running && (
          <span className="text-xs tabular-nums text-slate-600">{percent}%</span>
        )}
        {isAway && (
          <button
            type="button"
            onClick={() => onReturn(task.page)}
            className="ml-auto text-xs font-medium text-blue-700 hover:text-blue-900"
          >
            {t("components:TaskStatusBar.openTask")}
          </button>
        )}
        {task.canCancel && task.status === "running" && isAway && (
          <button
            type="button"
            onClick={() => { void handleCancel(); }}
            className="rounded-md border border-red-200 bg-white px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
          >
            {t("components:TaskStatusBar.cancel")}
          </button>
        )}
        {task.status === "cancelling" && (
          <span className="text-xs text-slate-500">{t("components:TaskStatusBar.waitingForStop")}</span>
        )}
        {!running && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label={t("components:TaskStatusBar.dismiss")}
            className="ml-auto rounded px-2 py-1 text-xs text-slate-500 hover:bg-white/70 hover:text-slate-700"
          >
            {t("components:TaskStatusBar.dismiss")}
          </button>
        )}
      </div>
      {running && (
        <div className="mt-2">
          <div className="h-1.5 overflow-hidden rounded-full bg-white/80">
            {percent === null ? (
              <div className="h-full w-1/3 animate-pulse rounded-full bg-blue-500" />
            ) : (
              <div className="h-full rounded-full bg-blue-600 transition-[width] duration-300" style={{ width: `${percent}%` }} />
            )}
          </div>
          {task.progress?.detail && (
            <p className="mt-1 truncate text-xs text-slate-500">{task.progress.detail}</p>
          )}
        </div>
      )}
      {task.error && <p className="mt-2 text-xs text-red-700">{task.error}</p>}
    </section>
  );
}
