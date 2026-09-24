"""
Adapter اتصال به دیتابیس منبع از نوع MySQL با pymysql (DictCursor).

همه عملیات درایور همگام‌اند و با asyncio.to_thread در Thread جدا اجرا می‌شوند؛
هر عملیات اتصال خودش را باز و در پایان می‌بندد.
"""
import asyncio

import pymysql
import pymysql.cursors

from app.sync_engine.adapters.base import BaseSiteAdapter, build_schema_dict


class MySQLAdapter(BaseSiteAdapter):
    """پیاده‌سازی BaseSiteAdapter برای MySQL؛ نام جدول/ستون‌ها با backtick محصور می‌شوند."""

    def _connect(self):
        """یک اتصال همگام pymysql با timeout ده‌ثانیه‌ای به دیتابیس منبع باز می‌کند."""
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
        """SELECT روی ستون‌های داده‌شده (نام‌ها با backtick محصور می‌شوند) و برگرداندن ردیف‌ها به‌صورت dict."""
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
        """یک ستون از یک ردیف (id_column=id_value) را در دیتابیس منبع به‌روز می‌کند (در Thread جدا)."""
        await asyncio.to_thread(self._update_field_sync, table_name, id_column, id_value, field_column, field_value)

    def _update_field_sync(
        self, table_name: str, id_column: str, id_value: str, field_column: str, field_value: str
    ) -> None:
        """UPDATE پارامتری یک ستون برای ردیف مشخص و commit آن."""
        conn = self._connect()
        try:
            query = f"UPDATE `{table_name}` SET `{field_column}` = %s WHERE `{id_column}` = %s"  # noqa: S608
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
            with conn.cursor() as cur:
                # فیلتر TABLE_SCHEMA فقط ستون‌های دیتابیس همین اتصال را نگه می‌دارد؛ بدون آن
                # INFORMATION_SCHEMA.COLUMNS ستون‌های همه دیتابیس‌های روی سرور را برمی‌گرداند
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

                # کلیدهای خارجی: ردیف‌هایی از KEY_COLUMN_USAGE که به جدول دیگری ارجاع دارند
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
        """حداکثر limit مقدار نمونه از یک ستون را (در Thread جدا) برمی‌گرداند."""
        return await asyncio.to_thread(self._sample_column_values_sync, table_name, column_name, limit)

    def _sample_column_values_sync(self, table_name: str, column_name: str, limit: int) -> list:
        """خواندن چند مقدار اول یک ستون، بدون خواندن کل جدول."""
        conn = self._connect()
        try:
            query = f"SELECT `{column_name}` FROM `{table_name}` LIMIT {int(limit)}"  # noqa: S608
            with conn.cursor() as cur:
                cur.execute(query)
                return [row[column_name] for row in cur.fetchall()]  # DictCursor: دسترسی با نام ستون
        finally:
            conn.close()
