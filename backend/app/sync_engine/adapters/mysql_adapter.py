"""Adapter اتصال به دیتابیس منبع از نوع MySQL (با pymysql، به‌صورت Thread-safe در Executor)."""
import asyncio

import pymysql
import pymysql.cursors

from app.sync_engine.adapters.base import BaseSiteAdapter


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
