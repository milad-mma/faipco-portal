"""
سرویس «ویرایش ایمیل/موبایل خودم» توسط خودِ پرسنل، از پنل کاربری.

منطق: اگر برای سایت این پرسنل، نگاشت ستون‌ها (EmployeeMapping) برای همان
فیلد (ایمیل یا موبایل) تنظیم شده باشد و اتصال دیتابیس آن سایت فعال باشد،
مقدار جدید مستقیماً در دیتابیس اصلی همان سایت هم به‌روزرسانی می‌شود
(Write-back - برخلاف Sync Engine که فقط می‌خواند، اینجا می‌نویسد). در
غیر این صورت، فقط در دیتابیس داخلی پرتال ذخیره می‌شود.

صرف‌نظر از این‌که Write-back انجام شود یا نه، مقدار همیشه در دیتابیس
داخلی پرتال (Employee.email/mobile؛ برای کاربران بدون Employee، فقط
User.email) هم به‌روزرسانی می‌شود - تا تغییر فوراً در برنامه دیده شود،
نه فقط بعد از چرخه Sync بعدی.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.models.employee import Employee, EmployeeMapping
from app.models.site import SiteConnection
from app.models.user import User
from app.sync_engine.adapter_factory import get_adapter


class ContactInfoUpdateError(Exception):
    """خطای قابل‌نمایش به کاربر هنگام ویرایش ایمیل/موبایل (ورودی نامعتبر یا خطای نوشتن در منبع)."""

    pass


def normalize_mobile(raw: str) -> str:
    """
    ورودی: شماره موبایل خام. فقط ارقام را نگه می‌دارد و بررسی می‌کند ۱۱ رقم و با ۰ شروع شود.
    خروجی: شماره نرمال‌شده؛ در غیر این صورت ContactInfoUpdateError.
    """
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) != 11 or not digits.startswith("0"):
        raise ContactInfoUpdateError("شماره موبایل باید ۱۱ رقم و با صفر شروع شود (مثلاً 09123456789)")
    return digits


async def _get_mapping_and_connection(
    db: AsyncSession, site_id: int
) -> tuple[EmployeeMapping | None, SiteConnection | None]:
    """نگاشت پرسنل سایت و اتصال فعال آن را برمی‌گرداند (هرکدام ممکن است None باشد)."""
    result = await db.execute(select(EmployeeMapping).where(EmployeeMapping.site_id == site_id))
    mapping = result.scalar_one_or_none()
    result = await db.execute(
        select(SiteConnection).where(SiteConnection.site_id == site_id, SiteConnection.is_active.is_(True))
    )
    connection = result.scalar_one_or_none()
    return mapping, connection


async def _write_back_to_source(
    mapping: EmployeeMapping, connection: SiteConnection, personnel_code: str, source_column: str, value: str
) -> None:
    """
    مقدار جدید را در ستون source_column ردیفِ همین کد پرسنلی در جدول پرسنل دیتابیس منبع می‌نویسد.
    خطای درایور/اتصال به ContactInfoUpdateError تبدیل می‌شود.
    """
    adapter = get_adapter(
        connection.db_type,
        host=connection.host,
        port=connection.port,
        database=connection.database_name,
        username=connection.username,
        password=decrypt_secret(connection.password_encrypted),
    )
    try:
        await adapter.update_field(
            mapping.table_name, mapping.personnel_code_column, personnel_code, source_column, value
        )
    except Exception as e:  # noqa: BLE001 - خطای واقعی درایور باید به کاربر نمایش داده شود
        raise ContactInfoUpdateError(f"ذخیره در دیتابیس اصلی سایت ناموفق بود: {e}") from e


async def update_my_contact_info(
    db: AsyncSession, user: User, *, email: str | None = None, mobile: str | None = None
) -> dict[str, bool | None]:
    """
    ایمیل و/یا موبایل کاربر جاری را در پرتال و (در صورت امکان) در دیتابیس منبع سایت به‌روز می‌کند.
    خروجی: {"email_synced_to_source": bool | None, "mobile_synced_to_source": bool | None}
    - None یعنی آن فیلد اصلاً درخواست تغییر نداشت؛ True/False یعنی درخواست
      تغییر داشت و به دیتابیس اصلی سایت هم نوشته شد یا نه (نگاشت نداشت).
    """
    if email is None and mobile is None:
        raise ContactInfoUpdateError("هیچ مقداری برای به‌روزرسانی ارسال نشده است")

    result: dict[str, bool | None] = {"email_synced_to_source": None, "mobile_synced_to_source": None}
    normalized_mobile = normalize_mobile(mobile) if mobile is not None else None

    # پرسنل متصل به این حساب کاربری (در صورت وجود)
    employee: Employee | None = None
    if user.employee_id is not None:
        employee = await db.get(Employee, user.employee_id)

    if employee is None:
        # کاربر بدون Employee (مثلاً یک حساب خالص ادمین) - موبایل جایی برای
        # ذخیره‌شدن ندارد (مدل User فیلد موبایل ندارد)؛ فقط ایمیل روی خودِ User.
        if normalized_mobile is not None:
            raise ContactInfoUpdateError("این حساب به هیچ پرسنلی متصل نیست، پس موبایل قابل‌ذخیره نیست")
        if email is not None:
            user.email = email
            await db.commit()
        return result

    mapping, connection = (None, None)
    if employee.site_id is not None:
        mapping, connection = await _get_mapping_and_connection(db, employee.site_id)

    # نوشتن در منبع فقط با نگاشت + اتصال فعال + ستون کد پرسنلی ممکن است
    can_write_back = bool(mapping and connection and mapping.personnel_code_column)

    # ایمیل: در صورت نگاشت ستون ایمیل، در منبع هم نوشته می‌شود
    if email is not None:
        if can_write_back and mapping.email_column:
            await _write_back_to_source(mapping, connection, employee.personnel_code, mapping.email_column, email)
            result["email_synced_to_source"] = True
        else:
            result["email_synced_to_source"] = False
        employee.email = email

    # موبایل: در صورت نگاشت ستون موبایل، در منبع هم نوشته می‌شود
    if normalized_mobile is not None:
        if can_write_back and mapping.mobile_column:
            await _write_back_to_source(
                mapping, connection, employee.personnel_code, mapping.mobile_column, normalized_mobile
            )
            result["mobile_synced_to_source"] = True
        else:
            result["mobile_synced_to_source"] = False
        employee.mobile = normalized_mobile

    await db.commit()
    return result
