"""Adapter اتصال به دیتابیس منبع از نوع MySQL (با pymysql، به‌صورت Thread-safe در Executor)."""
import asyncio

import pymysql
import pymysql.cursors

from app.sync_engine.adapters.base import BaseSiteAdapter, build_schema_dict


class MySQLAdapter(BaseSiteAdapter):
    def _connect(self):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.username,
            password=self.password,
            connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
        )

    async def test_connection(self) -> tuple[bool, str | None]:
        return await asyncio.to_thread(self._test_connection_sync)

    def _test_connection_sync(self) -> tuple[bool, str | None]:
        try:
            conn = self._connect()
            conn.close()
            return True, None
        except Exception as e:  # noqa: BLE001
            return False, str(e)

    async def fetch_rows(self, table_name: str, columns: list[str]) -> list[dict]:
        return await asyncio.to_thread(self._fetch_rows_sync, table_name, columns)

    def _fetch_rows_sync(self, table_name: str, columns: list[str]) -> list[dict]:
        conn = self._connect()
        try:
            cols_sql = ", ".join(f"`{c}`" for c in columns)
            query = f"SELECT {cols_sql} FROM `{table_name}`"  # noqa: S608
            with conn.cursor() as cur:
                cur.execute(query)
                return list(cur.fetchall())
        finally:
            conn.close()

    async def update_field(
        self, table_name: str, id_column: str, id_value: str, field_column: str, field_value: str
    ) -> None:
        await asyncio.to_thread(self._update_field_sync, table_name, id_column, id_value, field_column, field_value)

    def _update_field_sync(
        self, table_name: str, id_column: str, id_value: str, field_column: str, field_value: str
    ) -> None:
        conn = self._connect()
        try:
            query = f"UPDATE `{table_name}` SET `{field_column}` = %s WHERE `{id_column}` = %s"  # noqa: S608
            with conn.cursor() as cur:
                cur.execute(query, (field_value, id_value))
            conn.commit()
        finally:
            conn.close()

    async def discover_schema(self) -> dict:
        return await asyncio.to_thread(self._discover_schema_sync)

    def _discover_schema_sync(self) -> dict:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                # ⚠️ فیلتر TABLE_SCHEMA لازم است - وگرنه INFORMATION_SCHEMA.COLUMNS
                # ستون‌های همه دیتابیس‌های قابل‌مشاهده روی همان سرور را برمی‌گرداند،
                # نه فقط دیتابیس این اتصال.
                cur.execute(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %(database)s
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """,
                    {"database": self.database},
                )
                column_rows = list(cur.fetchall())

                cur.execute(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME,
                           REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %(database)s AND REFERENCED_TABLE_NAME IS NOT NULL
                    """,
                    {"database": self.database},
                )
                fk_rows = list(cur.fetchall())
        finally:
            conn.close()
        return build_schema_dict(column_rows, fk_rows)

    async def sample_column_values(self, table_name: str, column_name: str, limit: int = 5) -> list:
        return await asyncio.to_thread(self._sample_column_values_sync, table_name, column_name, limit)

    def _sample_column_values_sync(self, table_name: str, column_name: str, limit: int) -> list:
        conn = self._connect()
        try:
            query = f"SELECT `{column_name}` FROM `{table_name}` LIMIT {int(limit)}"  # noqa: S608
            with conn.cursor() as cur:
                cur.execute(query)
                return [row[column_name] for row in cur.fetchall()]
        finally:
            conn.close()
