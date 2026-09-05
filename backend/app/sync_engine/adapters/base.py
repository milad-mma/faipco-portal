"""
اینترفیس مشترک همه Adapter های دیتابیس سایت‌ها.

برای پشتیبانی از یک نوع دیتابیس جدید (مثلاً Oracle)، کافی است یک کلاس جدید
از BaseSiteAdapter بسازید و در app/sync_engine/adapter_factory.py ثبتش کنید —
هیچ تغییری در SyncService یا بقیه سیستم لازم نیست.
"""
from abc import ABC, abstractmethod


class BaseSiteAdapter(ABC):
    def __init__(self, *, host: str, port: int, database: str, username: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str | None]:
        """
        بررسی برقراری اتصال.
        خروجی: (موفق بود؟, پیام خطا در صورت شکست یا None در صورت موفقیت)
        """

    @abstractmethod
    async def fetch_rows(self, table_name: str, columns: list[str]) -> list[dict]:
        """
        خواندن تمام ردیف‌های جدول مشخص‌شده، فقط با ستون‌های داده‌شده.
        خروجی: لیستی از dict که کلیدهای آن دقیقاً همان نام ستون‌های خام دیتابیس مبدأ است.
        """

    @abstractmethod
    async def update_field(
        self, table_name: str, id_column: str, id_value: str, field_column: str, field_value: str
    ) -> None:
        """
        به‌روزرسانی یک ستون برای دقیقاً یک ردیف (شناسایی‌شده با id_column=id_value)
        - برای «ویرایش ایمیل/موبایل خودم» توسط خودِ پرسنل (Write-back به دیتابیس
        اصلی همان Site، نه فقط دیتابیس داخلی پرتال).
        """

    @abstractmethod
    async def discover_schema(self) -> dict:
        """
        کشف کامل ساختار دیتابیس (فقط خواندن فراداده - INFORMATION_SCHEMA یا
        معادل آن؛ هیچ داده واقعی خوانده نمی‌شود) - برای کمک به مدیر در تنظیم
        Mapping ها، بدون نیاز به باز کردن ابزار جدا (SSMS/pgAdmin/...).

        خروجی: {"tables": [{"name": str, "columns": [{"name", "data_type",
        "nullable", "max_length"}], "foreign_keys": [{"column",
        "references_table", "references_column"}]}]}

        ⚠️ foreign_keys فقط روابطی را نشان می‌دهد که رسماً در دیتابیس
        به‌عنوان Constraint ثبت شده‌اند - در بسیاری از نرم‌افزارهای قدیمی
        حضور و غیاب/ERP، روابط منطقی وجود دارند بدون این‌که هرگز چنین
        Constraint ای رسماً تعریف شده باشد؛ نبود FK در این خروجی به‌معنای
        نبود رابطه واقعی نیست، فقط یعنی رسماً اعلام نشده است.
        """

    @abstractmethod
    async def sample_column_values(self, table_name: str, column_name: str, limit: int = 5) -> list:
        """
        مرحله سوم نگاشت داینامیک - چند مقدار واقعی نمونه از یک ستون
        می‌خواند (نه کل جدول) - برای کمک به تشخیص الگوی داده (مثلاً
        «مقادیر ۸ رقمی در بازه منطقی یعنی احتمالاً تاریخ شمسی فشرده»)
        وقتی نام ستون به‌تنهایی برای پیشنهاد کافی نبوده است.

        ⚠️ فقط خواندن - و فقط برای ستون‌هایی که مدیر یا الگوریتم پیشنهاد
        صراحتاً درخواست کرده، نه کل جدول.
        """


def build_schema_dict(column_rows: list[dict], fk_rows: list[dict]) -> dict:
    """
    مشترک بین هر سه Adapter - ردیف‌های خام دو کوئری (ستون‌ها + کلیدهای
    خارجی، هرکدام با کلیدهای یکسان TABLE_NAME/COLUMN_NAME/...، صرف‌نظر
    از این‌که کوئری اصلی هرکدام دقیقاً چه نحوی داشته) را به یک ساختار
    درختی (یک ورودی به‌ازای هر جدول) تبدیل می‌کند.
    """
    tables: dict[str, dict] = {}
    for row in column_rows:
        table_name = row["TABLE_NAME"]
        table = tables.setdefault(table_name, {"name": table_name, "columns": [], "foreign_keys": []})
        table["columns"].append(
            {
                "name": row["COLUMN_NAME"],
                "data_type": row["DATA_TYPE"],
                "nullable": str(row["IS_NULLABLE"]).upper() == "YES",
                "max_length": row.get("CHARACTER_MAXIMUM_LENGTH"),
            }
        )
    for row in fk_rows:
        table_name = row["TABLE_NAME"]
        table = tables.setdefault(table_name, {"name": table_name, "columns": [], "foreign_keys": []})
        table["foreign_keys"].append(
            {
                "column": row["COLUMN_NAME"],
                "references_table": row["REFERENCED_TABLE_NAME"],
                "references_column": row["REFERENCED_COLUMN_NAME"],
            }
        )
    return {"tables": sorted(tables.values(), key=lambda t: t["name"])}
