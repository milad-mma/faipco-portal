"""
سرویس «کشف ساختار دیتابیس» - فقط خواندن فراداده (نام جدول‌ها/ستون‌ها/
نوع‌داده‌ها + کلیدهای خارجی رسماً تعریف‌شده)، بدون هیچ خواندن داده واقعی
یا نوشتنی. هدف: کمک به مدیر برای تنظیم Mapping ها (EmployeeMapping/
AttendanceMapping) بدون نیاز به باز کردن ابزار جدا (SSMS/pgAdmin/...).

discover_site_schema فقط کشف و نمایش است و چیزی روی Mapping اعمال نمی‌کند.
پیشنهاد نگاشت (بر اساس نام ستون / نمونه داده واقعی) در
app/services/mapping_suggestion_service.py پیاده شده و suggest_mapping_for_table
آن را با یک اتصال واقعی به دیتابیس سایت ترکیب می‌کند.
"""
from __future__ import annotations

from app.core.security import decrypt_secret
from app.models.site import SiteConnection
from app.services.mapping_suggestion_service import suggest_mapping_with_samples
from app.sync_engine.adapter_factory import get_adapter
from app.sync_engine.adapters.base import BaseSiteAdapter


class SchemaDiscoveryError(Exception):
    """خطای اتصال/درایور هنگام کشف ساختار یا پیشنهاد نگاشت؛ پیامش به کاربر نمایش داده می‌شود."""

    pass


def _build_adapter(connection: SiteConnection) -> BaseSiteAdapter:
    """از روی رکورد اتصال سایت (با رمزگشایی پسورد) Adapter مناسب نوع دیتابیس را می‌سازد."""
    return get_adapter(
        connection.db_type,
        host=connection.host,
        port=connection.port,
        database=connection.database_name,
        username=connection.username,
        password=decrypt_secret(connection.password_encrypted),
    )


async def discover_site_schema(connection: SiteConnection) -> dict:
    """ساختار دیتابیس منبع سایت (جدول‌ها، ستون‌ها، کلیدهای خارجی) را برمی‌گرداند؛ خطاها به SchemaDiscoveryError تبدیل می‌شوند."""
    adapter = _build_adapter(connection)
    try:
        return await adapter.discover_schema()
    except Exception as e:  # noqa: BLE001 - خطای واقعی درایور/اتصال باید به کاربر نمایش داده شود
        raise SchemaDiscoveryError(f"کشف ساختار دیتابیس با خطا مواجه شد: {e}") from e


async def suggest_mapping_for_table(
    connection: SiteConnection, table_name: str, column_names: list[str], concepts: list[str]
) -> dict:
    """
    برای یک جدول، پیشنهاد نگاشت هر مفهوم را برمی‌گرداند: ابتدا بر اساس نام ستون و سپس (فقط برای
    مفاهیم بی‌پاسخ) با نمونه‌گیری داده واقعی از دیتابیس سایت. خطاها به SchemaDiscoveryError تبدیل می‌شوند.
    """
    adapter = _build_adapter(connection)
    try:
        return await suggest_mapping_with_samples(adapter, table_name, column_names, concepts)
    except Exception as e:  # noqa: BLE001 - خطای واقعی درایور/اتصال باید به کاربر نمایش داده شود
        raise SchemaDiscoveryError(f"پیشنهاد نگاشت با خطا مواجه شد: {e}") from e
