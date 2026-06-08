import { LedgerPage, type LedgerPageConfig } from "./LedgerPage";

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

const IconDroplet = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a8.966 8.966 0 01-5.982-2.275M12 21a8.966 8.966 0 005.982-2.275M12 21V3m0 18c-2.21 0-4.253-.804-5.822-2.135M12 21c2.21 0 4.253-.804 5.822-2.135M12 3c-3.75 4.5-7.5 9-7.5 13.5C4.5 19.485 7.015 21 12 21m0-18c3.75 4.5 7.5 9 7.5 13.5 0 2.985-2.515 4.5-7.5 4.5" />
  </svg>
);

const OIL_LEDGER_COLUMNS = [
  "油品名称",
  "标准油品名称",
];

const config: LedgerPageConfig = {
  title: "油品台账",
  icon: <IconDroplet />,
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
