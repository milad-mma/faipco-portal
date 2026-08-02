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
