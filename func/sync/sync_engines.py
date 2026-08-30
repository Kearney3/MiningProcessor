"""
同步引擎：API 模式、直连数据库模式、连接测试。

包含 sync_via_api()、sync_via_db()、test_api_connection()、test_db_connection()。
"""
import contextlib
import sys
import time
from typing import Any

from func.logger import get_logger
from func.sync.api_client import (
    MineBaseAPIError,
    SessionExpiredError,
    SessionLimitReachedError,
)
from func.sync.constants import BATCH_SIZE, CONFLICT_POLICIES, DATA_TYPE_REGISTRY, DEDUP_FIELDS_MAP
from func.sync.row_helpers import (
    _build_field_mappings,
    _map_row_to_db_columns,
    _resolve_fks_for_db,
)

logger = get_logger(__name__)


# MineBase v2 在首次 confirm 返回 serverContinuation=true 后，会由服务端
# 自己处理剩余窗口。客户端只能读取会话快照，不能继续 POST confirm。
_TERMINAL_SESSION_STATES = frozenset({
    "COMPLETED",
    "PARTIAL",
    "FAILED",
    "CANCELLED",
    "EXPIRED",
})
_CONFIRM_RECONCILE_ERROR_CODES = frozenset({
    "IMPORT_CONFIRM_LEASE_LOST",
    "SESSION_BUSY",
    "STALE_VERSION",
})
_CONFIRM_POLL_INTERVAL_SECONDS = 0.5
_CONFIRM_MAX_POLL_ATTEMPTS = 1_200
_CONFIRM_MAX_WAIT_SECONDS = 10 * 60


def _response_data(response: Any) -> dict[str, Any]:
    """提取 MineBase 标准响应中的 data 对象。"""
    if not isinstance(response, dict):
        return {}
    data = response.get("data", response)
    return data if isinstance(data, dict) else {}


def _session_from_response(response: Any) -> dict[str, Any]:
    """提取 MineBase 响应中的 session 快照。"""
    data = _response_data(response)
    session = data.get("session")
    return session if isinstance(session, dict) else {}


def _is_terminal_session(session: dict[str, Any]) -> bool:
    return session.get("state") in _TERMINAL_SESSION_STATES


def _summary_count(summary: dict[str, Any], field: str, fallback: int = 0) -> int:
    value = summary.get(field)
    return value if isinstance(value, int) and value >= 0 else fallback


def _counts_from_terminal_session(
    session: dict[str, Any],
    row_count: int,
) -> dict[str, int] | None:
    """从终态会话的权威 summary 生成同步结果计数。"""
    summary = session.get("summary")
    if not isinstance(summary, dict):
        return None

    inserted = _summary_count(summary, "inserted")
    updated = _summary_count(summary, "updated")
    skipped = _summary_count(summary, "skipped")
    fallback_failed = max(0, row_count - inserted - updated - skipped)
    return {
        "success": inserted + updated,
        "skipped": skipped,
        "failed": _summary_count(summary, "failed", fallback_failed),
    }


def _wait_for_terminal_session(
    api_client: Any,
    table: str,
    session_id: str,
    initial_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """轮询服务端 continuation，直到会话进入终态。"""
    session = initial_session if isinstance(initial_session, dict) else {}
    started_at = time.monotonic()
    for attempt in range(_CONFIRM_MAX_POLL_ATTEMPTS):
        if _is_terminal_session(session):
            return session
        if (
            attempt == _CONFIRM_MAX_POLL_ATTEMPTS - 1
            or time.monotonic() - started_at >= _CONFIRM_MAX_WAIT_SECONDS
        ):
            break
        time.sleep(_CONFIRM_POLL_INTERVAL_SECONDS)
        session = _session_from_response(api_client.get_session(table, session_id))

    raise MineBaseAPIError(
        f"导入会话未在限定时间内进入终态: {session_id}",
        error_code="IMPORT_CONFIRM_TIMEOUT",
    )


def _cancel_import_if_active(api_client: Any, table: str, session_id: str, expected_version: int) -> None:
    """仅取消仍可取消的会话，避免与后台确认或终态会话竞争。"""
    try:
        session = _session_from_response(api_client.get_session(table, session_id))
    except Exception:
        # 查询快照失败时保留旧行为，尽力清理可能仍处于暂存阶段的会话。
        session = {}

    state = session.get("state")
    if state == "CONFIRMING" or state in _TERMINAL_SESSION_STATES:
        return
    api_client.cancel_import(table, session_id, expected_version=expected_version)


# ---------------------------------------------------------------------------
# API 同步模式 (contractVersion 2, 窗口化 confirm)
# ---------------------------------------------------------------------------


def sync_via_api(
    data_type: str,
    rows: list[dict],
    column_mapping: dict[str, str],
    api_client: Any,
    dry_run: bool = False,
    row_warnings: list[dict[str, Any]] | None = None,
    conflict_policy: str = "SKIP",
) -> dict[str, Any]:
    """通过 API 模式同步数据 (contractVersion 2)。

    流程: create_session → send_batch × N → confirm (窗口化循环)。
    confirm 可能需要多次调用直到 done=true。

    Args:
        row_warnings: 可选警告收集列表（来自台账匹配阶段），
                      合并服务端返回的 warnings/errors 后一并返回。
        conflict_policy: 冲突策略 ('SKIP' | 'UPDATE' | 'REJECT')。

    Returns:
        {"success": N, "skipped": N, "failed": N, "warnings": [...]}
    """
    table = DATA_TYPE_REGISTRY[data_type]["table"]
    collected_warnings: list[dict[str, Any]] = list(row_warnings) if row_warnings else []

    if not rows:
        logger.info("[%s] 无数据可同步", data_type)
        return {"success": 0, "skipped": 0, "failed": 0, "warnings": collected_warnings}

    if dry_run:
        logger.info("[DRY-RUN] %s: 将同步 %d 行到 %s", data_type, len(rows), table)
        return {
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "warnings": collected_warnings,
            "dry_run_rows": rows,
        }

    field_mappings = _build_field_mappings(column_mapping, table)

    # 计算批次数
    total_batches = max(1, (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE)

    # 创建会话 (contractVersion 2)
    try:
        session_resp = api_client.create_session(
            table,
            expected_batches=total_batches,
            total_rows=len(rows),
            conflict_policy=conflict_policy,
        )
    except SessionLimitReachedError as e:
        logger.error("[%s] 并发导入会话数已达上限: %s", data_type, e)
        return {"success": 0, "skipped": 0, "failed": len(rows), "warnings": collected_warnings}
    except MineBaseAPIError as e:
        logger.error("[%s] 创建会话失败: %s", data_type, e)
        return {"success": 0, "skipped": 0, "failed": len(rows), "warnings": collected_warnings}

    # 提取 session id 和 version
    session_data = session_resp.get("data", {})
    session_obj = session_data.get("session", {})
    session_id = session_data.get("sessionId") or session_obj.get("id", "")
    if not session_id:
        logger.error("[%s] 创建会话响应缺少 sessionId: %s", data_type, session_resp)
        return {"success": 0, "skipped": 0, "failed": len(rows), "warnings": collected_warnings}

    expected_version = session_obj.get("version", 0)

    # 剥离内部元数据字段，不发送到 API
    _META_KEYS = {"_row_num"}
    rows = [{k: v for k, v in row.items() if k not in _META_KEYS} for row in rows]

    total_success = 0
    total_skipped = 0
    total_failed = 0

    try:
        batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
        total_batches = len(batches)

        for idx, batch in enumerate(batches):
            row_offset = idx * BATCH_SIZE
            resp = api_client.send_batch(
                table, session_id, batch, field_mappings,
                idx, total_batches,
                expected_version=expected_version,
                row_offset=row_offset,
            )
            data = resp.get("data", {})
            # v2 响应: receipt.result 包含校验结果
            receipt = data.get("receipt", {})
            result = receipt.get("result", data)
            s = result.get("success", 0)
            sk = result.get("skipped", 0)
            f = result.get("failed", 0)
            total_success += s
            total_skipped += sk
            total_failed += f

            # 更新 version（服务端可能在 session snapshot 中返回新版本）
            new_version = data.get("session", {}).get("version")
            if new_version is not None:
                expected_version = new_version

            # 收集 warnings
            if result.get("warnings"):
                for w in result["warnings"]:
                    val = w.get("value")
                    if not val and val != 0:
                        val = (w.get("rawValue") or w.get("raw_value")
                               or w.get("originalValue") or w.get("original_value"))
                    val_str = str(val) if val is not None and str(val).strip() != "" else "（空）"
                    warning_item = {
                        "row": w.get("row", "?"),
                        "field": w.get("field", ""),
                        "value": val_str,
                        "message": w.get("message", ""),
                    }
                    collected_warnings.append(warning_item)
                    logger.warning("  [%s] 行%s: %s", data_type, warning_item["row"], warning_item["message"])
            if result.get("errors"):
                for e in result["errors"]:
                    val = e.get("value")
                    if not val and val != 0:
                        val = (e.get("rawValue") or e.get("raw_value")
                               or e.get("originalValue") or e.get("original_value"))
                    val_str = str(val) if val is not None and str(val).strip() != "" else "（空）"
                    error_item = {
                        "row": e.get("row", "?"),
                        "field": e.get("field", ""),
                        "value": val_str,
                        "message": e.get("message", ""),
                    }
                    collected_warnings.append(error_item)
                    logger.error("  [%s] 行%s: %s", data_type, error_item["row"], error_item["message"])

        # 窗口化 confirm：旧版服务端循环调用；MineBase 新版若返回
        # serverContinuation=true，则由服务端处理剩余窗口，客户端改为轮询快照。
        total_inserted = 0
        total_updated = 0
        total_confirmed_skipped = 0
        total_rejected = 0
        confirm_rounds = 0
        terminal_counts_applied = False

        while True:
            try:
                confirm_resp = api_client.confirm_batch(table, session_id, expected_version=expected_version)
            except SessionExpiredError as e:
                logger.error("[%s] 导入会话已过期: %s", data_type, e)
                # staging 数据未提交，批量阶段的 success 不算最终成功
                total_success = 0
                total_failed = len(rows) - total_skipped
                with contextlib.suppress(Exception):
                    _cancel_import_if_active(api_client, table, session_id, expected_version)
                break
            except MineBaseAPIError as e:
                if e.error_code not in _CONFIRM_RECONCILE_ERROR_CODES:
                    raise

                # 另一个确认 worker 可能已经接管或完成了会话。先读取权威终态，
                # 不要把租约竞争误报为整批失败，也不要取消后台 worker 的会话。
                terminal_session = _wait_for_terminal_session(
                    api_client,
                    table,
                    session_id,
                )
                terminal_counts = _counts_from_terminal_session(terminal_session, len(rows))
                if terminal_counts is None:
                    raise MineBaseAPIError(
                        f"导入会话终态缺少 summary: {session_id}",
                        error_code="IMPORT_PROTOCOL_ERROR",
                    ) from e
                total_success = terminal_counts["success"]
                total_skipped = terminal_counts["skipped"]
                total_failed = terminal_counts["failed"]
                terminal_counts_applied = True
                confirm_rounds += 1
                logger.info(
                    "[%s] 确认租约由服务端接管，已从终态恢复 (插入/更新=%d, 跳过=%d, 失败=%d)",
                    data_type,
                    total_success,
                    total_skipped,
                    total_failed,
                )
                break

            confirm_data = _response_data(confirm_resp)
            done = confirm_data.get("done", False)

            # 更新 version
            new_version = confirm_data.get("session", {}).get("version")
            if new_version is not None:
                expected_version = new_version

            # 累加窗口统计
            total_inserted += confirm_data.get("inserted", 0)
            total_updated += confirm_data.get("updated", 0)
            total_confirmed_skipped += confirm_data.get("skipped", 0)
            total_rejected += confirm_data.get("rejected", 0)
            confirm_rounds += 1

            if not done and confirm_data.get("serverContinuation") and confirm_data.get("hasMore"):
                terminal_session = _wait_for_terminal_session(
                    api_client,
                    table,
                    session_id,
                    initial_session=_session_from_response(confirm_resp),
                )
                terminal_counts = _counts_from_terminal_session(terminal_session, len(rows))
                if terminal_counts is None:
                    raise MineBaseAPIError(
                        f"导入会话终态缺少 summary: {session_id}",
                        error_code="IMPORT_PROTOCOL_ERROR",
                    )
                total_success = terminal_counts["success"]
                total_skipped = terminal_counts["skipped"]
                total_failed = terminal_counts["failed"]
                terminal_counts_applied = True
                logger.info(
                    "[%s] 服务端 continuation 完成 (插入/更新=%d, 跳过=%d, 失败=%d)",
                    data_type,
                    total_success,
                    total_skipped,
                    total_failed,
                )
                break

            if done:
                break

        if confirm_rounds:
            if terminal_counts_applied:
                logger.info(
                    "[%s] API 同步完成 (v2): 成功=%d, 跳过=%d, 失败=%d, confirm轮次=%d",
                    data_type, total_success, total_skipped, total_failed, confirm_rounds,
                )
            else:
                logger.info(
                    "[%s] API 同步完成 (v2): 插入=%d, 更新=%d, 跳过=%d, 拒绝=%d, confirm轮次=%d",
                    data_type, total_inserted, total_updated,
                    total_confirmed_skipped, total_rejected, confirm_rounds,
                )
                total_success = total_inserted + total_updated
                total_skipped = total_confirmed_skipped
                # MineBase reports REJECT duplicates separately from skipped
                # rows; expose them as failures in the sync result.
                total_failed += total_rejected

    except SessionExpiredError as e:
        logger.error("[%s] 导入会话已过期: %s", data_type, e)
        # 会话过期意味着 staging 数据未提交，所有未跳过的行视为失败
        total_success = 0
        total_failed = len(rows) - total_skipped
        try:
            _cancel_import_if_active(api_client, table, session_id, expected_version)
        except Exception as cancel_err:
            logger.warning("[%s] 取消导入会话失败: %s", data_type, cancel_err)
    except SessionLimitReachedError as e:
        logger.error("[%s] 并发导入会话数已达上限: %s", data_type, e)
        total_failed = len(rows) - total_success - total_skipped
    except Exception as e:
        logger.error("[%s] API 同步失败: %s", data_type, e)
        try:
            _cancel_import_if_active(api_client, table, session_id, expected_version)
        except Exception as cancel_err:
            logger.warning("[%s] 取消导入会话失败: %s", data_type, cancel_err)
        total_failed = len(rows) - total_success - total_skipped

    return {"success": total_success, "skipped": total_skipped, "failed": total_failed, "warnings": collected_warnings}


# ---------------------------------------------------------------------------
# 连接测试
# ---------------------------------------------------------------------------


def test_api_connection(url: str, username: str, password: str) -> tuple[bool, str]:
    """测试 API 连接（尝试登录），返回 (成功, 描述信息)。"""
    MineBaseAPIClient = sys.modules["func.sync_to_minebase"].MineBaseAPIClient
    try:
        client = MineBaseAPIClient(url, username, password)
        client.login()
        return True, f"连接成功: {url}"
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def test_db_connection(
    host: str, port: int, database: str, user: str, password: str,
) -> tuple[bool, str]:
    """测试数据库连接，返回 (成功, 描述信息)。"""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=database,
            user=user, password=password, connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return True, f"连接成功: {user}@{host}:{port}/{database}"
    except psycopg2.OperationalError as e:
        return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# 直连数据库同步模式
# ---------------------------------------------------------------------------


def sync_via_db(
    data_type: str,
    rows: list[dict],
    column_mapping: dict[str, str],
    db_client: Any,
    dry_run: bool = False,
    row_warnings: list[dict[str, Any]] | None = None,
    conflict_policy: str = "SKIP",
) -> dict[str, Any]:
    """通过直连数据库模式同步数据。

    Args:
        row_warnings: 可选警告收集列表（来自台账匹配阶段），
                      合并 FK 解析阶段的警告后一并返回。
        conflict_policy: 冲突策略 ('SKIP' | 'UPDATE' | 'REJECT')，与 API 模式一致。

    Returns:
        {"success": N, "skipped": N, "failed": N, "warnings": [...]}
    """
    table = DATA_TYPE_REGISTRY[data_type]["table"]
    collected_warnings: list[dict[str, Any]] = list(row_warnings) if row_warnings else []

    if conflict_policy not in CONFLICT_POLICIES:
        raise ValueError(f"无效的冲突策略: {conflict_policy}（支持: SKIP、UPDATE、REJECT）")

    if not rows:
        logger.info("[%s] 无数据可同步", data_type)
        return {"success": 0, "skipped": 0, "failed": 0, "warnings": collected_warnings}

    if dry_run:
        logger.info("[DRY-RUN] %s: 将同步 %d 行到 %s", data_type, len(rows), table)
        return {
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "warnings": collected_warnings,
            "dry_run_rows": rows,
        }

    total_success = 0
    total_skipped = 0
    total_failed = 0

    # Each row is its own transaction.  PostgreSQL marks a transaction as
    # aborted after an INSERT error; without a rollback here, every following
    # row and the final commit would fail and discard earlier successes.
    for row in rows:
        try:
            # FK 解析
            resolved_row = _resolve_fks_for_db(data_type, row, db_client, warnings=collected_warnings)
            if resolved_row is None:
                total_skipped += 1
                continue

            # 转换为 PostgreSQL 列名
            columns, values = _map_row_to_db_columns(resolved_row)
            if not columns:
                total_skipped += 1
                continue

            # 去重检查
            dedup_cols = DEDUP_FIELDS_MAP.get(table, [])
            dedup_values = {}
            for col, val in zip(columns, values, strict=False):
                if col in dedup_cols:
                    dedup_values[col] = val

            if dedup_values and db_client.check_duplicate(table, dedup_values):
                if conflict_policy == "SKIP":
                    total_skipped += 1
                    continue
                if conflict_policy == "REJECT":
                    total_failed += 1
                    continue

                updated = db_client.update_row(table, columns, values, dedup_values)
                if updated != 1:
                    raise RuntimeError(f"重复行更新失败: {table}")
                db_client.commit()
                total_success += 1
                continue

            # 插入并立即提交，保证之前成功的行不依赖后续行的结果。
            db_client.insert_rows(table, columns, [values])
            db_client.commit()
            total_success += 1

        except Exception as e:
            logger.error("[%s] 行处理失败: %s — %s", data_type, row, e)
            try:
                db_client.rollback()
            except Exception as rollback_error:
                logger.error("[%s] 行失败后的回滚也失败: %s", data_type, rollback_error)
            total_failed += 1

    logger.info("[%s] DB 同步完成: 成功=%d, 跳过=%d, 失败=%d", data_type, total_success, total_skipped, total_failed)

    return {"success": total_success, "skipped": total_skipped, "failed": total_failed, "warnings": collected_warnings}
