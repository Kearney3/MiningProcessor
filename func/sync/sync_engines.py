"""
同步引擎：API 模式、直连数据库模式、连接测试。

包含 sync_via_api()、sync_via_db()、test_api_connection()、test_db_connection()。
"""
import sys
from typing import Any

from func.logger import get_logger
from func.sync.constants import BATCH_SIZE, DATA_TYPE_REGISTRY, DEDUP_FIELDS_MAP
from func.sync.file_processors import (
    _build_field_mappings,
    _map_row_to_db_columns,
    _resolve_fks_for_db,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# API 同步模式
# ---------------------------------------------------------------------------


def sync_via_api(
    data_type: str,
    rows: list[dict],
    column_mapping: dict[str, str],
    api_client: Any,
    dry_run: bool = False,
) -> dict[str, int]:
    """通过 API 模式同步数据。

    Returns:
        {"success": N, "skipped": N, "failed": N}
    """
    table = DATA_TYPE_REGISTRY[data_type]["table"]

    if not rows:
        logger.info("[%s] 无数据可同步", data_type)
        return {"success": 0, "skipped": 0, "failed": 0}

    if dry_run:
        logger.info("[DRY-RUN] %s: 将同步 %d 行到 %s", data_type, len(rows), table)
        for row in rows[:3]:
            logger.info("  示例: %s", row)
        if len(rows) > 3:
            logger.info("  ... 共 %d 行", len(rows))
        return {"success": 0, "skipped": 0, "failed": 0}

    field_mappings = _build_field_mappings(column_mapping, table)
    session_id = api_client.create_session(table)

    total_success = 0
    total_skipped = 0
    total_failed = 0

    try:
        batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
        total_batches = len(batches)

        for idx, batch in enumerate(batches):
            resp = api_client.send_batch(table, session_id, batch, field_mappings, idx, total_batches)
            data = resp.get("data", {})
            s = data.get("success", 0)
            sk = data.get("skipped", 0)
            f = data.get("failed", 0)
            total_success += s
            total_skipped += sk
            total_failed += f

            if data.get("warnings"):
                for w in data["warnings"][:5]:
                    logger.warning("  [%s] 行%d: %s", data_type, w.get("row", "?"), w.get("message", ""))
            if data.get("errors"):
                for e in data["errors"][:5]:
                    logger.error("  [%s] 行%d: %s", data_type, e.get("row", "?"), e.get("message", ""))

        # 确认导入（batchIndex=0 处理所有 staging 数据）
        confirm_resp = api_client.confirm_batch(table, session_id, batch_index=0)
        confirm_data = confirm_resp.get("data", {})
        inserted = confirm_data.get("inserted", 0)
        updated = confirm_data.get("updated", 0)
        confirmed_skipped = confirm_data.get("skipped", 0)
        logger.info(
            "[%s] API 同步完成: 插入=%d, 更新=%d, 跳过=%d",
            data_type,
            inserted,
            updated,
            confirmed_skipped,
        )
        # 以 confirm 返回值为最终统计（批处理阶段的计数可能包含被去重的记录）
        total_success = inserted + updated
        total_skipped = confirmed_skipped

    except Exception as e:
        logger.error("[%s] API 同步失败: %s", data_type, e)
        try:
            api_client.cancel_import(table, session_id)
        except Exception as cancel_err:
            logger.warning("[%s] 取消导入会话失败: %s", data_type, cancel_err)
        total_failed += len(rows) - total_success - total_skipped

    return {"success": total_success, "skipped": total_skipped, "failed": total_failed}


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
) -> dict[str, int]:
    """通过直连数据库模式同步数据。

    Returns:
        {"success": N, "skipped": N, "failed": N}
    """
    table = DATA_TYPE_REGISTRY[data_type]["table"]

    if not rows:
        logger.info("[%s] 无数据可同步", data_type)
        return {"success": 0, "skipped": 0, "failed": 0}

    if dry_run:
        logger.info("[DRY-RUN] %s: 将同步 %d 行到 %s", data_type, len(rows), table)
        for row in rows[:3]:
            logger.info("  示例: %s", row)
        if len(rows) > 3:
            logger.info("  ... 共 %d 行", len(rows))
        return {"success": 0, "skipped": 0, "failed": 0}

    total_success = 0
    total_skipped = 0
    total_failed = 0

    try:
        for row in rows:
            try:
                # FK 解析
                resolved_row = _resolve_fks_for_db(data_type, row, db_client)
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
                for col, val in zip(columns, values):
                    if col in dedup_cols:
                        dedup_values[col] = val

                if dedup_values and db_client.check_duplicate(table, dedup_values):
                    total_skipped += 1
                    continue

                # 插入
                db_client.insert_rows(table, columns, [values])
                total_success += 1

            except Exception as e:
                logger.error("[%s] 行处理失败: %s — %s", data_type, row, e)
                total_failed += 1

        db_client.commit()
        logger.info("[%s] DB 同步完成: 成功=%d, 跳过=%d, 失败=%d", data_type, total_success, total_skipped, total_failed)

    except Exception as e:
        logger.error("[%s] DB 同步失败，已回滚: %s", data_type, e)
        db_client.rollback()
        total_failed += len(rows) - total_success - total_skipped

    return {"success": total_success, "skipped": total_skipped, "failed": total_failed}
