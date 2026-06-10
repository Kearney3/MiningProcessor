import { LedgerPage, type LedgerPageConfig } from "./LedgerPage";
import type { BridgeProp } from "../../lib/types";

const IconTruck = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 00-3.213-9.193 2.056 2.056 0 00-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 00-10.026 0 1.106 1.106 0 00-.987 1.106v7.635m12-6.677v6.677m0 4.5v-4.5m0 0h-12" />
  </svg>
);

const EQUIPMENT_LEDGER_COLUMNS = [
  "设备名称",
  "设备编号",
  "公司",
  "标准设备名称",
  "标准设备编号",
  "标准公司名称",
];

const config: LedgerPageConfig = {
  title: "设备台账",
  icon: <IconTruck />,
  standardColumns: EQUIPMENT_LEDGER_COLUMNS,
  loadDataMethod: "get_equipment_ledger_data",
  importMethod: "import_equipment_ledger",
  loadFileColumnsMethod: "load_ledger_file_columns",
  exportTemplateMethod: "export_equipment_ledger_template",
  setDefaultMethod: "set_default_equipment_ledger",
  cancelDefaultMethod: "cancel_default_equipment_ledger",
  clearMethod: "clear_equipment_ledger",
  emptyMessage: "暂无设备台账数据，请先导入设备台账 Excel",
};

export function EquipmentLedgerPage({ bridge }: { bridge: BridgeProp }) {
  return <LedgerPage bridge={bridge} config={config} />;
}
