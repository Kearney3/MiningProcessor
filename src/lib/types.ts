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
  level: string;
  message: string;
  timestamp?: string;
  seq?: number;  // M13: 用于 React key，保证稳定性
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
  | "equipment-ledger"
  | "oil-ledger"
  | "load-config"
  | "maint-config"
  | "user-config";
