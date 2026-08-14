import { LedgerPage, type LedgerPageConfig } from "./LedgerPage";
import { useTranslation } from "react-i18next";
import type { BridgeProp } from "../../lib/types";

const IconModel = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 5.5 12 2l8 3.5v13L12 22l-8-3.5v-13Z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 5.5 12 9l8-3.5M12 9v13" />
  </svg>
);

const config: LedgerPageConfig = {
  title: "型号台账",
  icon: <IconModel />,
  standardColumns: ["标准设备编号", "标准公司名称", "所有权", "设备型号", "设备类型", "内部分类"],
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
  emptyMessage: "暂无型号台账数据，请先导入型号台账 Excel",
};

export function ModelLedgerPage({ bridge }: { bridge: BridgeProp }) {
  const { t } = useTranslation();

  const translatedConfig: LedgerPageConfig = {
    ...config,
    title: t("pages:ModelLedgerPage.型号台账_3e0b"),
    standardColumns: [
      t("pages:ModelLedgerPage.标准设备编号_d45a"),
      t("pages:ModelLedgerPage.标准公司名称_907e"),
      t("pages:ModelLedgerPage.所有权_ed84"),
      t("pages:ModelLedgerPage.设备型号_5858"),
      t("pages:ModelLedgerPage.设备类型_02f4"),
      t("pages:ModelLedgerPage.内部分类_b310"),
    ],
    emptyMessage: t("pages:ModelLedgerPage.暂无型号台账数据，请先导入型号_2bfc"),
  };

  return <LedgerPage bridge={bridge} config={translatedConfig} />;
}

