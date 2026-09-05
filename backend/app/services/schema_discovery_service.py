"""
سرویس «کشف ساختار دیتابیس» - فقط خواندن فراداده (نام جدول‌ها/ستون‌ها/
نوع‌داده‌ها + کلیدهای خارجی رسماً تعریف‌شده)، بدون هیچ خواندن داده واقعی
یا نوشتنی. هدف: کمک به مدیر برای تنظیم Mapping ها (EmployeeMapping/
AttendanceMapping) بدون نیاز به باز کردن ابزار جدا (SSMS/pgAdmin/...).

⚠️ این یک قابلیت صرفاً «کشف و نمایش» است - هیچ پیشنهاد/حدس یا اعمال
خودکاری روی Mapping انجام نمی‌دهد (آن یک قابلیت جداگانه و بعدی است).
"""
from __future__ import annotations

from app.core.security import decrypt_secret
from app.models.site import SiteConnection
from app.sync_engine.adapter_factory import get_adapter


class SchemaDiscoveryError(Exception):
    pass


async def discover_site_schema(connection: SiteConnection) -> dict:
    adapter = get_adapter(
        connection.db_type,
        host=connection.host,
        port=connection.port,
        database=connection.database_name,
        username=connection.username,
        password=decrypt_secret(connection.password_encrypted),
    )
    try:
        return await adapter.discover_schema()
    except Exception as e:  # noqa: BLE001 - خطای واقعی درایور/اتصال باید به کاربر نمایش داده شود
        raise SchemaDiscoveryError(f"کشف ساختار دیتابیس با خطا مواجه شد: {e}") from e
