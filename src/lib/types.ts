/** Python bridge 类型定义 */

/** Tauri Python bridge 调用接口 (M9) */
export interface BridgeProp {
  call: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>;
}

/** Python RPC 请求 */
export interface RpcRequest {
  id: number;
  method: string;
  params: Record<string, unknown>;
}

/** Python RPC 成功响应 */
export interface RpcResponse {
  id: number;
  result: unknown;
}

/** Python RPC 错误响应 */
export interface RpcError {
  id: number;
  error: string;
}

/** Python 异步事件 */
export interface PythonEvent {
  event: string;
  data: Record<string, unknown>;
}

/** 日志事件 */
export interface LogEntry {
  seq: number;
  level: string;
  message: string;
  timestamp: string;
  logger?: string;
  /** 完整诊断信息；界面显示 message，复制/导出使用 detail。 */
  detail?: string;
}

/** 批处理进度事件 */
export interface BatchProgress {
  stage: string;
  state?: "preparing" | "running" | "cancelling" | "completed" | "cancelled" | "failed";
  percent: number;
  current: number;
  total: number;
  detail: string;
  succeeded?: number;
  skipped?: number;
  failed?: number;
  retried?: number;
  running?: number;
  from_checkpoint?: number;
  rate?: number;
  eta_seconds?: number | null;
  completed_batches?: number;
  total_batches?: number;
}

/** 扫描结果 */
export interface ScanResult {
  matched: Record<string, string[]>;
  missing: string[];
}

/** 批量处理摘要 */
export interface BatchSummary {
  success_modules: string[];
  failed_modules: string[];
  warnings: string[];
  anomalies?: AnomalyRecord[];
}

/** 异常值明细 */
export interface AnomalyRecord {
  数据类型?: string;
  行号?: number | string;
  日期?: unknown;
  班次?: unknown;
  设备名称?: unknown;
  设备编号?: unknown;
  异常列?: string;
  异常值?: unknown;
  检测方法?: string;
  说明?: string;
}

/** 同步警告条目 */
export interface SyncWarning {
  row: number | string;
  field: string;
  value: string;
  message: string;
}

/** 同步结果 */
export interface SyncResult {
  results: Record<string, { success: number; skipped: number; failed: number; warnings?: SyncWarning[] }>;
  dry_run_file?: string;
}

/** 台账数据 */
export interface LedgerData {
  rows: Record<string, unknown>[];
  columns: string[];
}

/** 连接状态 */
export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

/** 连接日志条目 */
export interface ConnectionLog {
  level: string;
  message: string;
  timestamp: string;
}

/** 桥接进程信息 (从 Rust 侧获取) */
export interface BridgeInfo {
  mode: "sidecar" | "dev" | null;
  pid: number | null;
  alive: boolean;
  command: string | null;
}

/** 页面 ID */
export type PageId =
  | "data-processing"
  | "batch-processing"
  | "data-sync"
  | "ledger-match"
  | "llm-labeling"
  | "equipment-ledger"
  | "oil-ledger"
  | "model-ledger"
  | "daily-report"
  | "load-config"
  | "maint-config"
  | "user-config";
