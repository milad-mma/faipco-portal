"""Adapter اتصال به دیتابیس منبع از نوع PostgreSQL (با psycopg2، به‌صورت Thread-safe در Executor)."""
import asyncio

import psycopg2
import psycopg2.extras

from app.sync_engine.adapters.base import BaseSiteAdapter, build_schema_dict


class PostgreSQLAdapter(BaseSiteAdapter):
    def _connect(self):
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.username,
            password=self.password,
            connect_timeout=10,
        )

    async def test_connection(self) -> tuple[bool, str | None]:
        return await asyncio.to_thread(self._test_connection_sync)

    def _test_connection_sync(self) -> tuple[bool, str | None]:
        try:
            conn = self._connect()
            conn.close()
            return True, None
        except Exception as e:  # noqa: BLE001 - خطای واقعی درایور باید به کاربر نمایش داده شود
            return False, str(e)

    async def fetch_rows(self, table_name: str, columns: list[str]) -> list[dict]:
        return await asyncio.to_thread(self._fetch_rows_sync, table_name, columns)

    def _fetch_rows_sync(self, table_name: str, columns: list[str]) -> list[dict]:
        conn = self._connect()
        try:
            cols_sql = ", ".join(f'"{c}"' for c in columns)
            query = f'SELECT {cols_sql} FROM "{table_name}"'  # noqa: S608 - نام جدول/ستون از Mapping مدیریتی می‌آید نه ورودی کاربر نهایی
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                return [dict(row) for row in cur.fetchall()]
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
            query = f'UPDATE "{table_name}" SET "{field_column}" = %s WHERE "{id_column}" = %s'  # noqa: S608
            with conn.cursor() as cur:
                cur.execute(query, (field_value, id_value))
            conn.commit()
        finally:
            conn.close()

    async def discover_schema(self) -> dict:
        return await asyncio.to_thread(self._discover_schema_sync)

    def _discover_schema_sync(self) -> dict:
        # ⚠️ information_schema در PostgreSQL نام ستون‌ها را کوچک برمی‌گرداند
        # (table_name نه TABLE_NAME)؛ با AS "..." با حروف بزرگ، خروجی این
        # Adapter دقیقاً هم‌شکل با MSSQL/MySQL می‌شود - build_schema_dict
        # (مشترک بین هر سه) به همین کلیدهای یکسان نیاز دارد.
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT table_name AS "TABLE_NAME", column_name AS "COLUMN_NAME",
                           data_type AS "DATA_TYPE", is_nullable AS "IS_NULLABLE",
                           character_maximum_length AS "CHARACTER_MAXIMUM_LENGTH"
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                    """
                )
                column_rows = [dict(row) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        tc.table_name AS "TABLE_NAME",
                        kcu.column_name AS "COLUMN_NAME",
                        ccu.table_name AS "REFERENCED_TABLE_NAME",
                        ccu.column_name AS "REFERENCED_COLUMN_NAME"
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
                    """
                )
                fk_rows = [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
        return build_schema_dict(column_rows, fk_rows)
