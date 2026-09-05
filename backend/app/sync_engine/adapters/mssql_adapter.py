"""Adapter اتصال به دیتابیس منبع از نوع SQL Server (با pymssql، به‌صورت Thread-safe در Executor)."""
import asyncio

import pymssql

from app.sync_engine.adapters.base import BaseSiteAdapter, build_schema_dict


class MSSQLAdapter(BaseSiteAdapter):
    def _connect(self):
        return pymssql.connect(
            server=self.host,
            port=str(self.port),
            database=self.database,
            user=self.username,
            password=self.password,
            timeout=10,
            login_timeout=10,
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
            cols_sql = ", ".join(f"[{c}]" for c in columns)
            query = f"SELECT {cols_sql} FROM [{table_name}]"  # noqa: S608
            with conn.cursor(as_dict=True) as cur:
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
            query = f"UPDATE [{table_name}] SET [{field_column}] = %s WHERE [{id_column}] = %s"  # noqa: S608
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
            with conn.cursor(as_dict=True) as cur:
                cur.execute(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                    FROM INFORMATION_SCHEMA.COLUMNS
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """
                )
                column_rows = list(cur.fetchall())

                cur.execute(
                    """
                    SELECT
                        tp.name AS TABLE_NAME,
                        cp.name AS COLUMN_NAME,
                        tr.name AS REFERENCED_TABLE_NAME,
                        cr.name AS REFERENCED_COLUMN_NAME
                    FROM sys.foreign_keys fk
                    INNER JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
                    INNER JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
                    INNER JOIN sys.columns cp
                        ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
                    INNER JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
                    INNER JOIN sys.columns cr
                        ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
                    """
                )
                fk_rows = list(cur.fetchall())
        finally:
            conn.close()
        return build_schema_dict(column_rows, fk_rows)
