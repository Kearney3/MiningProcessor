"""MineBase PostgreSQL 直连客户端。"""
from typing import Any

from func.logger import get_logger
from func.sync.constants import VALID_TABLES

logger = get_logger(__name__)


class MineBaseDBClient:
    """MineBase PostgreSQL 直连客户端。"""

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        import psycopg2
        self.conn = psycopg2.connect(
            host=host, port=port, dbname=database, user=user, password=password,
        )
        self.conn.autocommit = False
        logger.info("已连接 MineBase 数据库: %s@%s:%d/%s", user, host, port, database)

    def close(self) -> None:
        if self.conn and not self.conn.closed:
            self.conn.close()

    def resolve_equipment_id(self, equip_name: str) -> str | None:
        """通过 3 级级联查找设备 ID（与 MineBase API 一致）。"""
        with self.conn.cursor() as cur:
            # 1. 直接查找 equipment.equip_name
            cur.execute(
                "SELECT id FROM equipment WHERE LOWER(equip_name) = LOWER(%s) LIMIT 1",
                (equip_name,),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])

            # 2. 精确匹配 equipment_match_table.equip_name
            cur.execute(
                "SELECT equipment_id FROM equipment_match_table WHERE LOWER(equip_name) = LOWER(%s) AND equipment_id IS NOT NULL LIMIT 1",
                (equip_name,),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])

            # 3. 模糊匹配 equipment_match_table.equip_name（包含关系）
            cur.execute(
                "SELECT equipment_id FROM equipment_match_table WHERE LOWER(equip_name) LIKE LOWER(%s) AND equipment_id IS NOT NULL LIMIT 1",
                (f"%{equip_name}%",),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])

        return None

    def resolve_material_type_id(self, material_name: str) -> str | None:
        """通过 material_type.code 查找物料类型 ID。"""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM material_type WHERE LOWER(code) = LOWER(%s) LIMIT 1",
                (material_name,),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])
        return None

    def check_duplicate(self, table: str, dedup_fields: dict[str, Any]) -> bool:
        """检查是否已存在重复记录。"""
        if not dedup_fields:
            return False
        if table not in VALID_TABLES:
            raise ValueError(f"Invalid table name: {table}")

        from psycopg2 import sql

        conditions = sql.SQL(" AND ").join(
            sql.SQL("{} = %s").format(sql.Identifier(k)) for k in dedup_fields
        )
        query = sql.SQL("SELECT id FROM {} WHERE {} LIMIT 1").format(
            sql.Identifier(table), conditions
        )
        with self.conn.cursor() as cur:
            cur.execute(query, list(dedup_fields.values()))
            return cur.fetchone() is not None

    def insert_rows(self, table: str, columns: list[str], values_list: list[list[Any]]) -> int:
        """批量插入数据。返回插入行数。"""
        if not values_list:
            return 0
        if table not in VALID_TABLES:
            raise ValueError(f"Invalid table name: {table}")

        import psycopg2.extras
        from psycopg2 import sql

        cols = sql.SQL(", ").join(map(sql.Identifier, columns))
        query = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
            sql.Identifier(table), cols
        )

        with self.conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, query, values_list, page_size=200)
        return len(values_list)

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()
