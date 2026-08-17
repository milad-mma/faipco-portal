"""
/system/cache-bust   (POST)   نصب اجباری Service Worker جدید برای همه کاربران
                                (پاک‌کردن کامل کش اپلیکیشن — انگار همه دارند
                                اولین‌بار اپ را باز می‌کنند) — فقط Admin کامل.
/system/ip-allowlist (GET/PUT) وضعیت کامل قابلیت محدودیت IP: یک متن
                                ویرایش‌پذیر (هر رنج در یک خط) + کلید
                                فعال/غیرفعال مستقل — فقط Admin کامل.
/system/ip-blocked-message (GET/PUT) پیامی که به کاربر مسدودشده نمایش داده می‌شود.
"""
import ipaddress
import logging
import re

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.models.ip_allowlist_entry import IpAllowlistEntry
from app.models.user import User
from app.schemas.system import IpAllowlistStateIn, IpAllowlistStateOut, IpBlockedMessageIn, IpBlockedMessageOut
from app.services.auth_service import AuthError, AuthService
from app.services.cache_service import CacheBustError, bump_app_cache_version
from app.services.system_settings_service import SystemSettingsService
from app.services.update_service import (
    UPDATE_CONFIRMATION_PHRASE,
    UpdateError,
    check_for_update,
    get_update_status,
    schedule_update,
)

logger = logging.getLogger("faipco.system")
router = APIRouter()

# فقط IPv4 (با یا بدون /CIDR) — کافی برای Use Case واقعی (فهرست دستی IP دفتر
# یا حتی یک فایل فایروال کامل)؛ هر چیز دیگری در متن (توضیح، خط خالی) نادیده گرفته می‌شود
_IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")


def _normalize_cidr(raw: str) -> str | None:
    try:
        network = ipaddress.ip_network(raw, strict=False)
    except ValueError:
        return None
    return str(network) if "/" in raw else f"{network.network_address}/32"


@router.get("/version")
async def get_app_version():
    """
    نسخه فعلی برنامه — عمداً بدون هیچ احراز هویتی، چون قرار است حتی در
    صفحه ورود (قبل از Login) هم قابل دیدن باشد — مثلاً برای تأیید اینکه
    آخرین Deploy واقعاً روی سرور نشسته، بدون نیاز به SSH یا ورود به پنل.
    """
    settings = get_settings()
    return {"version": settings.APP_VERSION}


@router.get("/check-update")
async def check_update(
    _user=Depends(require_permission("system.backup")),
):
    """
    بررسی وجود نسخه جدیدتر در GitHub — کاملاً Read-Only. همان مجوز
    Backup/Restore را می‌خواهد چون این قابلیت هم عملاً یک قابلیت
    سطح-زیرساخت است، نه یک تنظیم معمولی.
    """
    return await check_for_update()


@router.post("/apply-update")
async def apply_update(
    confirm: str = Form(..., description=f'برای تأیید باید دقیقاً "{UPDATE_CONFIRMATION_PHRASE}" ارسال شود'),
    password: str = Form(..., description="رمز عبور فعلی همین حساب — برای تأیید اضافی، مستقل از Session"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system.backup")),
):
    """
    ⚠️ این Endpoint عملاً معادل اجرای دستی «sudo bash install.sh» از طریق
    SSH است — نصب/آپدیت کامل (شامل نصب پکیج‌های سیستمی در صورت نیاز، Build
    مجدد فرانت‌اند، Migration های دیتابیس، و Restart سرویس) را از راه دور،
    از همین پنل، راه می‌اندازد. مثل Restore، فقط اعتبارسنجی سریع همین‌جا
    انجام می‌شود؛ خودِ کار واقعی (که سرویس را چند لحظه متوقف می‌کند) در
    پس‌زمینه ادامه پیدا می‌کند — این پاسخ فقط یعنی «شروع شد».

    علاوه بر عبارت تأیید، رمز عبور فعلی حساب هم دوباره خواسته می‌شود —
    چون این یک عملیات با دسترسی کامل root است، تکیه‌کردن فقط به همان
    Session ورود (که در صورت دزدیده‌شدن Token به‌تنهایی کافی می‌بود) کافی
    نیست.
    """
    try:
        await AuthService(db).verify_current_credential(current_user, password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    try:
        schedule_update(confirm_phrase=confirm)
    except UpdateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("راه‌اندازی فرآیند آپدیت با خطای پیش‌بینی‌نشده مواجه شد")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="راه‌اندازی فرآیند آپدیت با خطای پیش‌بینی‌نشده مواجه شد — جزئیات کامل در لاگ سرور ثبت شد.",
        )
    return {
        "success": True,
        "message": "آپدیت شروع شد. سرویس چند لحظه (بسته به حجم تغییرات، معمولاً یک تا چند دقیقه) در دسترس "
        "نخواهد بود، سپس خودکار دوباره بالا می‌آید.",
    }


@router.get("/update-status")
async def update_status(
    _user=Depends(require_permission("system.backup")),
):
    """وضعیت زنده آخرین آپدیت — دقیقاً همان الگوی /backup/restore-status."""
    return get_update_status()


@router.post("/cache-bust")
async def cache_bust(
    _user=Depends(require_permission("system.cache_bust")),
):
    try:
        new_version = bump_app_cache_version()
    except CacheBustError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception:
        logger.exception("پاک‌کردن کش با خطای پیش‌بینی‌نشده مواجه شد")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="پاک‌کردن کش با خطای پیش‌بینی‌نشده مواجه شد — جزئیات کامل در لاگ سرور ثبت شد.",
        )

    return {
        "success": True,
        "version": new_version,
        "message": "با موفقیت انجام شد. هر کاربر دفعه بعدی که سایت را باز کند (یا صفحه را Refresh کند)، "
        "نسخه کاملاً تازه دریافت می‌کند — انگار اولین‌بار است.",
    }


async def _build_ip_allowlist_state(db: AsyncSession) -> IpAllowlistStateOut:
    result = await db.execute(select(IpAllowlistEntry.cidr).order_by(IpAllowlistEntry.cidr))
    cidrs = [row[0] for row in result.all()]
    enabled = await SystemSettingsService(db).get_ip_allowlist_enabled()
    return IpAllowlistStateOut(enabled=enabled, text="\n".join(cidrs), count=len(cidrs))


@router.get("/ip-allowlist", response_model=IpAllowlistStateOut)
async def get_ip_allowlist(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    return await _build_ip_allowlist_state(db)


@router.put("/ip-allowlist", response_model=IpAllowlistStateOut)
async def save_ip_allowlist(
    payload: IpAllowlistStateIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    """
    ویرایشگر متنی: کل محتوای فعلی جعبه متن (هر رنج در یک خط) عیناً جایگزین
    فهرست فعلی دیتابیس می‌شود — خط‌های خالی/نامعتبر نادیده گرفته می‌شوند،
    تکراری‌ها خودکار یکی می‌شوند. برای فهرست‌های بزرگ (حتی چند هزار خط، مثل
    یک فایروال کامل) هم مناسب است: یک Delete کلی + یک Insert دسته‌ای، نه
    عملیات ردیف‌به‌ردیف.
    """
    valid_cidrs: set[str] = set()
    for line in payload.text.splitlines():
        line = line.strip()
        if not line:
            continue
        normalized = _normalize_cidr(line)
        if normalized:
            valid_cidrs.add(normalized)

    await db.execute(delete(IpAllowlistEntry))
    now = datetime.now(timezone.utc)
    for cidr in valid_cidrs:
        db.add(IpAllowlistEntry(cidr=cidr, created_at=now))

    await SystemSettingsService(db).set_ip_allowlist_enabled(payload.enabled)
    await db.commit()

    return await _build_ip_allowlist_state(db)


@router.get("/ip-blocked-message", response_model=IpBlockedMessageOut)
async def get_ip_blocked_message(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    message = await SystemSettingsService(db).get_ip_blocked_message()
    return IpBlockedMessageOut(message=message)


@router.put("/ip-blocked-message", response_model=IpBlockedMessageOut)
async def update_ip_blocked_message(
    payload: IpBlockedMessageIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    try:
        message = await SystemSettingsService(db).set_ip_blocked_message(payload.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return IpBlockedMessageOut(message=message)
