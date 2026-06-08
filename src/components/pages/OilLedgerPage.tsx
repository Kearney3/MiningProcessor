import { LedgerPage, type LedgerPageConfig } from "./LedgerPage";

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

const OIL_LEDGER_COLUMNS = [
  "油品名称",
  "标准油品名称",
];

const config: LedgerPageConfig = {
  title: "油品台账",
  standardColumns: OIL_LEDGER_COLUMNS,
  loadDataMethod: "get_oil_ledger_data",
  importMethod: "import_oil_ledger",
  loadFileColumnsMethod: "load_oil_ledger_file_columns",
  exportTemplateMethod: "export_oil_ledger_template",
  setDefaultMethod: "set_default_oil_ledger",
  cancelDefaultMethod: "cancel_default_oil_ledger",
  clearMethod: "clear_oil_ledger",
  emptyMessage: "暂无油品台账数据，请先导入油品台账 Excel",
};

export function OilLedgerPage({ bridge }: { bridge: BridgeProp }) {
  return <LedgerPage bridge={bridge} config={config} />;
}
