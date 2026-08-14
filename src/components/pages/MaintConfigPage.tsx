import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { open, save } from "@tauri-apps/plugin-dialog";
import type { BridgeProp } from "../../lib/types";
import { useToast } from "../Toast";
import { btnSecondaryClass } from "../../lib/ui-classes";

interface ClassificationEntry {
  major: string;
  minor: string;
  keywords: string[];
}

interface MaintClassConfig {
  classifications: ClassificationEntry[];
  noise_exact: string[];
  noise_patterns: string[];
  reason_rules: Record<string, string>;
}

const REASON_LABEL_KEYS: Record<string, string> = {
  fault: "pages:MaintConfigPage.ui.fault",
  check_content: "pages:MaintConfigPage.ui.checkContent",
  non_fault: "pages:MaintConfigPage.ui.nonFault",
  skip: "pages:MaintConfigPage.ui.skip",
};

export function MaintConfigPage({ bridge }: { bridge: BridgeProp }) {
  const { notify } = useToast();
  const { t } = useTranslation();
  const [config, setConfig] = useState<MaintClassConfig | null>(null);
  const [loading, setLoading] = useState(false);

  const loadConfig = useCallback(async () => {
    try {
      const data = await bridge.call<MaintClassConfig>("get_maintenance_classifications");
      setConfig(data);
    } catch (e) {
      console.error("Failed to load maintenance classifications:", e);
    }
  }, [bridge]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const handleImport = async () => {
    const selected = await open({
      multiple: false,
      filters: [{ name: "Excel", extensions: ["xlsx", "xls"] }],
    });
    if (!selected) return;
    setLoading(true);
    try {
      const data = await bridge.call<MaintClassConfig>("import_maintenance_classifications", {
        path: selected as string,
      });
      setConfig(data);
      notify(t("pages:MaintConfigPage.分类配置已导入_c8a0"), "success");
    } catch (e) {
      notify(t("pages:MaintConfigPage.导入失败:$_d39c", { error: String(e) }), "error");
    } finally {
      setLoading(false);
    }
  };

  const handleExportTemplate = async (withDefaults: boolean) => {
    const path = await save({
      defaultPath: withDefaults ? t("pages:MaintConfigPage.维修分类配置_默认.xlsx_23f6") : t("pages:MaintConfigPage.维修分类配置模板.xlsx_c2d8"),
      filters: [{ name: "Excel", extensions: ["xlsx"] }],
    });
    if (!path) return;
    setLoading(true);
    try {
      await bridge.call("export_maintenance_template", { path, with_defaults: withDefaults });
      notify(t("pages:MaintConfigPage.模板已导出:$_9238", { path }), "success");
    } catch (e) {
      notify(t("pages:MaintConfigPage.导出失败:$_d4b1", { error: String(e) }), "error");
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async () => {
    if (!confirm(t("pages:MaintConfigPage.将恢复为系统默认分类规则，自定_04c3"))) return;
    setLoading(true);
    try {
      await bridge.call("update_maintenance_classifications", {
        rules: {
          classifications: [],
          noise_exact: [],
          noise_patterns: [],
          reason_rules: {},
        },
      });
      await loadConfig();
      notify(t("pages:MaintConfigPage.已恢复默认分类配置_f4e7"), "success");
    } catch (e) {
      notify(t("pages:MaintConfigPage.恢复失败:$_e447", { error: String(e) }), "error");
    } finally {
      setLoading(false);
    }
  };

  // 按大类分组
  const grouped = config?.classifications.reduce(
    (acc, entry) => {
      if (!acc[entry.major]) acc[entry.major] = [];
      acc[entry.major].push(entry);
      return acc;
    },
    {} as Record<string, ClassificationEntry[]>,
  );

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">{t("pages:MaintConfigPage.维修分类配置_4ee9")}</h2>
        <p className="text-sm text-slate-500">{t("pages:MaintConfigPage.管理维修记录的故障分类规则_c92e")}</p>
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={handleImport} disabled={loading} className={btnSecondaryClass}>
          {t("pages:MaintConfigPage.ui.importExcel")}
        </button>
        <button onClick={() => handleExportTemplate(false)} disabled={loading} className={btnSecondaryClass}>
          {t("pages:MaintConfigPage.ui.exportBlankTemplate")}
        </button>
        <button onClick={() => handleExportTemplate(true)} disabled={loading} className={btnSecondaryClass}>
          {t("pages:MaintConfigPage.ui.exportDefault")}
        </button>
        <button onClick={handleRestore} disabled={loading} className={btnSecondaryClass}>
          {t("pages:MaintConfigPage.ui.restoreDefault")}
        </button>
      </div>

      {/* 当前配置概览 */}
      {config && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4" />
              <path d="M12 8h.01" />
            </svg>
            <h3 className="text-sm font-medium text-slate-700">{t("pages:MaintConfigPage.当前配置概览_1419")}</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div className="bg-slate-50 rounded-md p-3">
              <div className="text-2xl font-bold text-slate-800">{grouped ? Object.keys(grouped).length : 0}</div>
              <div className="text-xs text-slate-500">{t("pages:MaintConfigPage.大类_d196")}</div>
            </div>
            <div className="bg-slate-50 rounded-md p-3">
              <div className="text-2xl font-bold text-slate-800">{config.classifications.length}</div>
              <div className="text-xs text-slate-500">{t("pages:MaintConfigPage.小类_7f69")}</div>
            </div>
            <div className="bg-slate-50 rounded-md p-3">
              <div className="text-2xl font-bold text-slate-800">{config.noise_exact.length}</div>
              <div className="text-xs text-slate-500">{t("pages:MaintConfigPage.精确噪声_d680")}</div>
            </div>
            <div className="bg-slate-50 rounded-md p-3">
              <div className="text-2xl font-bold text-slate-800">{config.noise_patterns.length}</div>
              <div className="text-xs text-slate-500">{t("pages:MaintConfigPage.正则噪声_bd0e")}</div>
            </div>
          </div>
        </div>
      )}

      {/* 分类规则详情 */}
      {grouped && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-sm font-medium text-slate-700 mb-3">{t("pages:MaintConfigPage.分类规则_be84")}</h3>
          <div className="space-y-4">
            {Object.entries(grouped).map(([major, entries]) => (
              <div key={major} className="border border-slate-100 rounded-md">
                <div className="px-3 py-2 bg-slate-50 rounded-t-md flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-700">{major}</span>
                  <span className="text-xs text-slate-400">{entries.length} {t("pages:MaintConfigPage.小类_7f69")}</span>
                </div>
                <div className="divide-y divide-slate-50">
                  {entries.map((entry, i) => (
                    <div key={i} className="px-3 py-2 flex items-start gap-3">
                      <span className="text-xs font-medium text-slate-600 w-32 shrink-0 pt-0.5">{entry.minor}</span>
                      <div className="flex flex-wrap gap-1">
                        {entry.keywords.map((kw, j) => (
                          <span key={j} className="inline-block text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">
                            {kw}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 原因规则 */}
      {config && Object.keys(config.reason_rules).length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-sm font-medium text-slate-700 mb-3">{t("pages:MaintConfigPage.原因规则_f475")}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(config.reason_rules).map(([reason, rule]) => (
              <div key={reason} className="flex items-center gap-2 text-sm">
                <span className="text-slate-600">{reason}</span>
                <span className="text-slate-400">→</span>
                <span className={`font-medium ${
                  rule === "fault" ? "text-red-600" :
                  rule === "skip" ? "text-slate-400" :
                  rule === "non_fault" ? "text-green-600" :
                  "text-amber-600"
                }`}>
                  {REASON_LABEL_KEYS[rule] ? t(REASON_LABEL_KEYS[rule]) : rule}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 配置说明 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-medium text-slate-700 mb-2">{t("pages:MaintConfigPage.配置说明_7b4a")}</h3>
        <ul className="text-xs text-slate-500 space-y-1">
          <li>{t("pages:MaintConfigPage.•从Excel导入：选择包含「_928d")}</li>
          <li>{t("pages:MaintConfigPage.•导出空白模板：导出仅有表头的_959f")}</li>
          <li>{t("pages:MaintConfigPage.•导出默认配置：导出包含系统默_905f")}</li>
          <li>{t("pages:MaintConfigPage.•恢复默认配置：将当前配置重置_0115")}</li>
          <li>{t("pages:MaintConfigPage.•关键词使用中文顿号「、」分隔_eb32")}</li>
          <li>{t("pages:MaintConfigPage.•分类按行顺序匹配，更具体的关_fe2b")}</li>
        </ul>
      </div>
    </div>
  );
}
