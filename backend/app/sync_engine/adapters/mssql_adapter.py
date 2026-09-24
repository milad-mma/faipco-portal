"""
Adapter اتصال به دیتابیس منبع از نوع SQL Server (مثلاً کاراوب) با pymssql.

همه عملیات درایور همگام‌اند و با asyncio.to_thread در Thread جدا اجرا می‌شوند؛
هر عملیات اتصال خودش را باز و در پایان می‌بندد.
"""
import asyncio

import pymssql

from app.sync_engine.adapters.base import BaseSiteAdapter, build_schema_dict


class MSSQLAdapter(BaseSiteAdapter):
    """پیاده‌سازی BaseSiteAdapter برای SQL Server؛ نام جدول/ستون‌ها با [ ] محصور می‌شوند."""

    def _connect(self):
        """یک اتصال همگام pymssql با timeout ده‌ثانیه‌ای به دیتابیس منبع باز می‌کند."""
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
        """تست اتصال را در Thread جدا اجرا می‌کند؛ خروجی: (موفق؟, پیام خطا یا None)."""
        return await asyncio.to_thread(self._test_connection_sync)

    def _test_connection_sync(self) -> tuple[bool, str | None]:
        """اتصال را باز و بلافاصله می‌بندد؛ هر خطا به‌صورت (False, متن خطا) برگردانده می‌شود."""
        try:
            conn = self._connect()
            conn.close()
            return True, None
        except Exception as e:  # noqa: BLE001
            return False, str(e)

    async def fetch_rows(self, table_name: str, columns: list[str]) -> list[dict]:
        """همه ردیف‌های جدول را با ستون‌های داده‌شده (در Thread جدا) می‌خواند؛ خروجی: لیست dict."""
        return await asyncio.to_thread(self._fetch_rows_sync, table_name, columns)

    def _fetch_rows_sync(self, table_name: str, columns: list[str]) -> list[dict]:
        """SELECT روی ستون‌های داده‌شده (نام‌ها با [ ] محصور می‌شوند) و برگرداندن ردیف‌ها به‌صورت dict."""
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
        """یک ستون از یک ردیف (id_column=id_value) را در دیتابیس منبع به‌روز می‌کند (در Thread جدا)."""
        await asyncio.to_thread(self._update_field_sync, table_name, id_column, id_value, field_column, field_value)

    def _update_field_sync(
        self, table_name: str, id_column: str, id_value: str, field_column: str, field_value: str
    ) -> None:
        """UPDATE پارامتری یک ستون برای ردیف مشخص و commit آن."""
        conn = self._connect()
        try:
            query = f"UPDATE [{table_name}] SET [{field_column}] = %s WHERE [{id_column}] = %s"  # noqa: S608
            with conn.cursor() as cur:
                cur.execute(query, (field_value, id_value))
            conn.commit()
        finally:
            conn.close()

    async def discover_schema(self) -> dict:
        """ساختار دیتابیس (ستون‌ها و کلیدهای خارجی) را در Thread جدا کشف می‌کند."""
        return await asyncio.to_thread(self._discover_schema_sync)

    def _discover_schema_sync(self) -> dict:
        """دو کوئری فراداده (ستون‌ها و کلیدهای خارجی) اجرا و با build_schema_dict به ساختار درختی تبدیل می‌کند."""
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

                # کلیدهای خارجی از جداول سیستمی sys.foreign_keys خوانده می‌شوند
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

    async def sample_column_values(self, table_name: str, column_name: str, limit: int = 5) -> list:
        """حداکثر limit مقدار نمونه از یک ستون را (در Thread جدا) برمی‌گرداند."""
        return await asyncio.to_thread(self._sample_column_values_sync, table_name, column_name, limit)

    def _sample_column_values_sync(self, table_name: str, column_name: str, limit: int) -> list:
        """خواندن چند مقدار اول یک ستون، بدون خواندن کل جدول."""
        conn = self._connect()
        try:
            query = f"SELECT TOP {int(limit)} [{column_name}] FROM [{table_name}]"  # noqa: S608
            with conn.cursor() as cur:
                cur.execute(query)
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
