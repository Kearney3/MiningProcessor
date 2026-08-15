import { LedgerPage, type LedgerPageConfig } from "./LedgerPage";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";

const IconModel = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 5.5 12 2l8 3.5v13L12 22l-8-3.5v-13Z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 5.5 12 9l8-3.5M12 9v13" />
  </svg>
);

type LedgerBackendConfig = Omit<LedgerPageConfig, "title" | "standardColumns" | "emptyMessage">;

const config: LedgerBackendConfig = {
  businessTitle: "型号台账",
  businessTemplateFilename: "型号台账模板.xlsx",
  icon: <IconModel />,
  loadDataMethod: "get_model_ledger_data",
  importMethod: "import_model_ledger",
  loadFileColumnsMethod: "load_model_ledger_file_columns",
  listSheetsMethod: "list_excel_sheets",
  exportTemplateMethod: "export_model_ledger_template",
  exportDataMethod: "export_ledger_data",
  exportDataType: "model",
  setDefaultMethod: "set_default_model_ledger",
  cancelDefaultMethod: "cancel_default_model_ledger",
  clearMethod: "clear_model_ledger",
};

export function ModelLedgerPage({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();

  const translatedConfig: LedgerPageConfig = {
    ...config,
    title: t("pages:ModelLedgerPage.modelLedger"),
    standardColumns: ["标准设备编号", "标准公司名称", "所有权", "设备型号", "设备类型", "内部分类"],
    emptyMessage: t("pages:ModelLedgerPage.noModelLedgerDataImportAModelLedgerExcelFileFirst"),
  };

  return <LedgerPage bridge={bridge} config={translatedConfig} />;
}
