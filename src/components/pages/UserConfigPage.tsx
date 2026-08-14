import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import {
  LLMConfigSection,
  MineBaseSection,
  FileKeywordsSection,
  HeaderMappingSection,
  ColumnMappingSection,
  AnomalyConfigSection,
  DailyReportConfigSection,
} from "../user-config";
import { RestoreIcon } from "../../lib/icons";

// ---------------------------------------------------------------------------
// Confirm Dialog
// ---------------------------------------------------------------------------

function ConfirmDialog({
  title,
  message,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl max-w-sm w-full mx-4 p-5">
        <h3 className="text-sm font-semibold text-slate-800 mb-2">{title}</h3>
        <p className="text-xs text-slate-600 mb-5">
          {message.split("\n").map((line, i) => (
            <span key={i}>
              {line}
              {i < message.split("\n").length - 1 && <br />}
            </span>
          ))}
        </p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
          >
            {t("pages:UserConfigPage.ui.cancel")}
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 text-xs text-white bg-red-600 hover:bg-red-700 rounded-md transition-colors"
          >
            {t("pages:UserConfigPage.确认还原_f1bf")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function UserConfigPage({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const { t } = useTranslation();
  const [resetKey, setResetKey] = useState(0);
  const [showConfirm, setShowConfirm] = useState(false);

  const handleResetAll = useCallback(async () => {
    try {
      await bridge.call("reset_user_config");
      setResetKey((k) => k + 1);
      notify(t("pages:UserConfigPage.已还原所有用户配置为默认值_c205"), "success");
    } catch (e) {
      notify(t("pages:UserConfigPage.还原失败:$_5a84", { error: String(e) }), "error");
    }
    setShowConfirm(false);
  }, [bridge.call, notify]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-slate-800">{t("pages:UserConfigPage.用户配置_dd1e")}</h2>
          <p className="text-xs text-slate-500 mt-0.5">{t("pages:UserConfigPage.管理与业务处理无关的个人偏好设_a426")}</p>
        </div>
        <button
          onClick={() => setShowConfirm(true)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-red-600 hover:text-red-700 px-3 py-1.5 rounded-md border border-red-200 hover:bg-red-50 transition-colors"
        >
          <RestoreIcon />
          {t("pages:UserConfigPage.restoreDefault")}
        </button>
      </div>

      <div className="space-y-2">
        <LLMConfigSection key={`llm-${resetKey}`} bridge={bridge} />
        <MineBaseSection key={`mb-${resetKey}`} bridge={bridge} />
        <FileKeywordsSection key={`kw-${resetKey}`} bridge={bridge} />
        <HeaderMappingSection key={`hm-${resetKey}`} bridge={bridge} />
        <ColumnMappingSection key={`cm-${resetKey}`} bridge={bridge} />
        <AnomalyConfigSection key={`anomaly-${resetKey}`} bridge={bridge} />
        <DailyReportConfigSection key={`daily-report-${resetKey}`} bridge={bridge} />
      </div>

      {showConfirm && (
        <ConfirmDialog
          title={t("pages:UserConfigPage.确认还原_f1bf")}
          message={t("pages:UserConfigPage.将清除所有用户自定义配置，恢复_7bee")}
          onConfirm={handleResetAll}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}
