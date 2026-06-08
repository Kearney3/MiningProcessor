import { LedgerPage, type LedgerPageConfig } from "./LedgerPage";

interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

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
