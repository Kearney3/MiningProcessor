/** Python bridge 类型定义 */

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
  level: string;
  message: string;
  timestamp?: string;
}

/** 批处理进度事件 */
export interface BatchProgress {
  stage: string;
  percent: number;
  current: number;
  total: number;
  detail: string;
}

/** 扫描结果 */
export interface ScanResult {
  matched: Record<string, string[]>;
  missing: string[];
}

/** 同步结果 */
export interface SyncResult {
  results: Record<string, { success: number; skipped: number; failed: number }>;
}

/** 台账数据 */
export interface LedgerData {
  rows: Record<string, unknown>[];
  columns: string[];
}

/** 页面 ID */
export type PageId =
  | "data-processing"
  | "batch-processing"
  | "data-sync"
  | "ledger-match"
  | "equipment-ledger"
  | "oil-ledger"
  | "load-config"
  | "user-config";
