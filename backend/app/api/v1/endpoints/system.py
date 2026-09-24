"""
Endpoint های تنظیمات و ابزارهای سیستمی (پنل Admin → System):

/system/version                    (GET)  نسخه برنامه — بدون احراز هویت
/system/usage-stats, /server-stats (GET)  داده خام نمودارهای استفاده و مصرف سرور
/system/check-update               (GET)  بررسی نسخه جدیدتر در GitHub
/system/apply-update               (POST) اجرای install.sh در پس‌زمینه
/system/run-checks, /check-status  اجرای check.sh و وضعیت آن
/system/update-status              (GET)  وضعیت زنده آپدیت
/system/cache-bust   (POST)   نصب اجباری Service Worker جدید برای همه کاربران
                                (پاک‌کردن کامل کش اپلیکیشن — انگار همه دارند
                                اولین‌بار اپ را باز می‌کنند).
/system/ip-allowlist (GET/PUT) وضعیت کامل قابلیت محدودیت IP: یک متن
                                ویرایش‌پذیر (هر رنج در یک خط) + کلید
                                فعال/غیرفعال مستقل.
/system/ip-blocked-message (GET/PUT) پیامی که به کاربر مسدودشده نمایش داده می‌شود.
/system/login-background           عکس پس‌زمینه صفحه ورود (دریافت عمومی، آپلود/حذف)
/system/branding, /logo/{slug}, /pwa-icon/{variant}.png  برندینگ، لوگوها و آیکون‌های PWA
/system/manifest.json, /index.html نسخه‌های پویای Manifest و index.html با برندینگ فعلی
/system/smtp-settings, /sms-settings  تنظیمات و تست ایمیل و پیامک
"""
import ipaddress
import hashlib
import json
import logging
import re

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.models.ip_allowlist_entry import IpAllowlistEntry
from app.models.user import User
from app.schemas.system import (
    BrandingIn,
    BrandingSurfaceIn,
    PwaIconSettingsIn,
    BrandingOut,
    IpAllowlistStateIn,
    IpAllowlistStateOut,
    IpBlockedMessageIn,
    IpBlockedMessageOut,
)
from app.schemas.smtp import SmtpSettingsIn, SmtpSettingsOut, SmtpTestEmailIn
from app.schemas.sms import SmsSettingsIn, SmsSettingsOut, SmsTestSendIn
from app.services.auth_service import AuthError, AuthService
from app.services.cache_service import CacheBustError, bump_app_cache_version
from app.services.email_service import EmailError, EmailNotConfiguredError, get_smtp_settings, send_email
from app.services.sms_service import SmsError, SmsNotConfiguredError, get_sms_settings, send_sms_code
from app.core.security import decrypt_secret, encrypt_secret
from app.services import branding_surfaces, pwa_icon_service
from app.services.system_settings_service import PWA_ICON_SETTINGS_KEY, SystemSettingsService
from app.services.usage_stats_service import get_usage_stats
from app.services.server_stats_service import get_server_stats
from app.services.update_service import (
    UPDATE_CONFIRMATION_PHRASE,
    UpdateError,
    check_for_update,
    get_check_status,
    get_update_status,
    schedule_checks,
    schedule_update,
)

logger = logging.getLogger("faipco.system")
router = APIRouter()

# فقط IPv4 (با یا بدون /CIDR) — کافی برای Use Case واقعی (فهرست دستی IP دفتر
# یا حتی یک فایل فایروال کامل)؛ هر چیز دیگری در متن (توضیح، خط خالی) نادیده گرفته می‌شود
_IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")


def _normalize_cidr(raw: str) -> str | None:
    """
    ورودی: یک رشته IP یا CIDR. خروجی: شکل استاندارد CIDR (IP تکی ← /32)، یا None اگر نامعتبر باشد.
    """
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
    خروجی: version و update_channel.
    """
    settings = get_settings()
    return {"version": settings.APP_VERSION, "update_channel": settings.UPDATE_CHANNEL}


@router.get("/usage-stats")
async def usage_stats(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.backup")),
):
    """
    داده خام ساعتی استفاده از پرتال (آخرین ۹۰ روز) — برای نمودار «میزان
    استفاده» در پنل Admin. تجمیع روزانه/هفتگی/ماهانه و «کدام ساعت
    شبانه‌روز پرترافیک‌تر است» عمداً در فرانت‌اند انجام می‌شود.
    مجوز system.backup.
    """
    stats = await get_usage_stats(db)
    return [
        {"date": s.date.isoformat(), "hour": s.hour, "request_count": s.request_count} for s in stats
    ]


@router.get("/server-stats")
async def server_stats(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.backup")),
):
    """
    داده خام مصرف CPU/RAM/دیسک خودِ سرور (آخرین ۷ روز، هر ۱۰ دقیقه یک
    نمونه) — برای نمودار «مصرف سرور» در پنل Admin. تجمیع/محاسبه اوج مصرف
    عمداً در فرانت‌اند انجام می‌شود. مجوز system.backup.
    """
    stats = await get_server_stats(db)
    return [
        {
            "recorded_at": s.recorded_at.isoformat(),
            "cpu_percent": s.cpu_percent,
            "ram_percent": s.ram_percent,
            "ram_used_mb": s.ram_used_mb,
            "ram_total_mb": s.ram_total_mb,
            "disk_percent": s.disk_percent,
            "disk_used_gb": s.disk_used_gb,
            "disk_total_gb": s.disk_total_gb,
        }
        for s in stats
    ]


@router.get("/check-update")
async def check_update(
    _user=Depends(require_permission("system.backup")),
):
    """
    بررسی وجود نسخه جدیدتر در GitHub — کاملاً Read-Only. همان مجوز
    Backup/Restore را می‌خواهد چون این قابلیت هم عملاً یک قابلیت
    سطح-زیرساخت است، نه یک تنظیم معمولی. مجوز system.backup.
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
    این Endpoint عملاً معادل اجرای دستی «sudo bash install.sh» از طریق
    SSH است — نصب/آپدیت کامل (شامل نصب پکیج‌های سیستمی در صورت نیاز، Build
    مجدد فرانت‌اند، Migration های دیتابیس، و Restart سرویس) را از راه دور،
    از همین پنل، راه می‌اندازد. مثل Restore، فقط اعتبارسنجی سریع همین‌جا
    انجام می‌شود؛ خودِ کار واقعی (که سرویس را چند لحظه متوقف می‌کند) در
    پس‌زمینه ادامه پیدا می‌کند — این پاسخ فقط یعنی «شروع شد».

    علاوه بر عبارت تأیید، رمز عبور فعلی حساب هم دوباره خواسته می‌شود —
    چون این یک عملیات با دسترسی کامل root است، تکیه‌کردن فقط به همان
    Session ورود (که در صورت دزدیده‌شدن Token به‌تنهایی کافی می‌بود) کافی
    نیست.
    مجوز system.backup. خطا: 401 رمز اشتباه، 400 عبارت تأیید اشتباه/نبود install.sh، 500 خطای پیش‌بینی‌نشده.
    """
    # تأیید دوباره رمز عبور حساب جاری
    try:
        await AuthService(db).verify_current_credential(current_user, password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # راه‌اندازی install.sh در پس‌زمینه
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


@router.post("/run-checks")
async def run_checks(
    _user=Depends(require_permission("system.backup")),
):
    """
    اجرای بررسی‌های سلامت پروژه (مسیرهای API، تست‌ها، Migration ها روی دیتابیس
    موقت) از پنل - فقط خواندن/تست، بدون تغییر در پروژه یا دیتابیس واقعی؛ به
    همین دلیل برخلاف آپدیت، رمز عبور دوباره خواسته نمی‌شود.
    مجوز system.backup. خطا: 400 اگر اسکریپت نباشد، بررسی دیگری در جریان باشد یا راه‌اندازی شکست بخورد.
    """
    try:
        schedule_checks()
    except UpdateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"success": True}


@router.get("/check-status")
async def check_status(
    _user=Depends(require_permission("system.backup")),
):
    """وضعیت زنده آخرین اجرای بررسی‌ها (log، is_running، is_passed، is_failed). مجوز system.backup."""
    return get_check_status()


@router.get("/update-status")
async def update_status(
    _user=Depends(require_permission("system.backup")),
):
    """وضعیت زنده آخرین آپدیت (log، is_running، is_finished، is_failed). مجوز system.backup."""
    return get_update_status()


@router.post("/cache-bust")
async def cache_bust(
    _user=Depends(require_permission("system.cache_bust")),
):
    """
    با تغییر sw.js همه کاربران را وادار به دریافت نسخه تازه اپ می‌کند. مجوز system.cache_bust.
    خروجی: نسخه جدید cache-bust. خطا: 500 اگر sw.js پیدا نشود یا خطای دیگری رخ دهد.
    """
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
    """خروجی: همه CIDR های ذخیره‌شده (مرتب، هر کدام در یک خط)، تعداد آن‌ها و وضعیت فعال بودن محدودیت IP."""
    result = await db.execute(select(IpAllowlistEntry.cidr).order_by(IpAllowlistEntry.cidr))
    cidrs = [row[0] for row in result.all()]
    enabled = await SystemSettingsService(db).get_ip_allowlist_enabled()
    return IpAllowlistStateOut(enabled=enabled, text="\n".join(cidrs), count=len(cidrs))


@router.get("/ip-allowlist", response_model=IpAllowlistStateOut)
async def get_ip_allowlist(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    """وضعیت کامل محدودیت IP را برمی‌گرداند. مجوز system.ip_allowlist."""
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
    عملیات ردیف‌به‌ردیف. مجوز system.ip_allowlist.
    """
    # استخراج و استانداردسازی CIDR های معتبر از خطوط متن (set برای حذف تکراری‌ها)
    valid_cidrs: set[str] = set()
    for line in payload.text.splitlines():
        line = line.strip()
        if not line:
            continue
        normalized = _normalize_cidr(line)
        if normalized:
            valid_cidrs.add(normalized)

    # جایگزینی کامل فهرست: حذف همه ردیف‌ها و درج فهرست جدید
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
    """پیام نمایش‌داده‌شده به IP مسدود را برمی‌گرداند. مجوز system.ip_allowlist."""
    message = await SystemSettingsService(db).get_ip_blocked_message()
    return IpBlockedMessageOut(message=message)


@router.put("/ip-blocked-message", response_model=IpBlockedMessageOut)
async def update_ip_blocked_message(
    payload: IpBlockedMessageIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    """پیام مسدودی IP را ذخیره می‌کند. مجوز system.ip_allowlist. خطا: 400 برای متن خالی."""
    try:
        message = await SystemSettingsService(db).set_ip_blocked_message(payload.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return IpBlockedMessageOut(message=message)


# ---------- عکس پس‌زمینه صفحه ورود («تنظیمات سامانه») ----------

ALLOWED_LOGIN_BACKGROUND_TYPES = {"image/jpeg", "image/png", "image/webp"}  # بر اساس Content-Type اعلام‌شده کلاینت
MAX_LOGIN_BACKGROUND_SIZE = 8 * 1024 * 1024  # ۸ مگابایت — کافی برای یک عکس پس‌زمینه با کیفیت خوب


@router.get("/login-background")
async def get_login_background(db: AsyncSession = Depends(get_db)):
    """
    عکس پس‌زمینه صفحه ورود را برمی‌گرداند؛ عمداً بدون هیچ احراز هویتی — صفحه ورود قبل از Login نمایش داده
    می‌شود، پس این تصویر باید همان‌جا هم قابل‌دریافت باشد. اگر هنوز چیزی
    آپلود نشده، ۴۰۴ برمی‌گرداند (فرانت‌اند این حالت را با پس‌زمینه پیش‌فرض
    جایگزین می‌کند).
    """
    result = await SystemSettingsService(db).get_login_background()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="عکس پس‌زمینه‌ای تنظیم نشده")
    content, content_type = result
    return Response(content=content, media_type=content_type)


@router.post("/login-background")
async def upload_login_background(
    file: UploadFile = File(..., description="عکس پس‌زمینه صفحه ورود (jpg/png/webp)"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    عکس پس‌زمینه صفحه ورود را ذخیره می‌کند. مجوز system.settings.
    خطا: 400 برای نوع غیرمجاز یا حجم بیش از ۸ مگابایت.
    """
    if file.content_type not in ALLOWED_LOGIN_BACKGROUND_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط فایل تصویری (jpg/png/webp) پذیرفته می‌شود",
        )
    content = await file.read()
    if len(content) > MAX_LOGIN_BACKGROUND_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حجم فایل نباید بیشتر از ۸ مگابایت باشد",
        )
    await SystemSettingsService(db).set_login_background(content, file.content_type)
    return {"success": True}


@router.delete("/login-background")
async def delete_login_background(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """عکس پس‌زمینه صفحه ورود را حذف می‌کند (بازگشت به پیش‌فرض). مجوز system.settings."""
    await SystemSettingsService(db).delete_login_background()
    return {"success": True}


# ---------- برندینگ (لوگوها + متن‌های مجزا) — «تنظیمات سامانه» ----------

ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}
MAX_LOGO_SIZE = 4 * 1024 * 1024  # ۴ مگابایت — لوگو معمولاً خیلی کوچک‌تر از یک عکس پس‌زمینه است

# لوگوهای مستقل — هرکدام برای یک مصرف متفاوت با سایز توصیه‌شده خودش
# (به‌علاوه لوگوی اختصاصی هر جای نمایش با slug به شکل surface-<name>):
#   app_logo        → درون‌برنامه‌ای، اندازه‌های بزرگ (اسپلش، پنل کاربری) — هر اندازه‌ای
#   app_logo_small  → درون‌برنامه‌ای، اندازه‌های کوچک (نوار بالا، صفحه ورود) — اگر
#                      تنظیم نشود، همان app_logo (با Scale کوچک‌تر) استفاده می‌شود
#   pwa_icon        → آیکون Manifest/صفحه اصلی گوشی بعد از نصب — ترجیحاً ۵۱۲×۵۱۲ مربعی
#   favicon         → آیکون تب مرورگر — ترجیحاً ۳۲×۳۲ یا ۱۹۲×۱۹۲ مربعی
_VALID_LOGO_SLUGS = {"app-logo", "app-logo-small", "pwa-icon", "favicon"} | {
    f"surface-{name}" for name in branding_surfaces.SURFACES
}


def _logo_slug_to_key(slug: str) -> str:
    """slug مسیر (مثل app-logo) را به نام لوگو در سرویس (app_logo) تبدیل می‌کند. خطا: 404 برای slug نامعتبر."""
    if slug not in _VALID_LOGO_SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نوع لوگو نامعتبر است")
    return slug.replace("-", "_")


@router.get("/branding", response_model=BrandingOut)
async def get_branding(db: AsyncSession = Depends(get_db)):
    """تنظیمات کامل برندینگ؛ عمداً بدون احراز هویت — اسپلش‌اسکرین و صفحه ورود قبل از Login این را نیاز دارند."""
    return await SystemSettingsService(db).get_branding()


@router.put("/branding", response_model=BrandingOut)
async def update_branding(
    payload: BrandingIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """متن‌های برندینگ ارسالی را ذخیره می‌کند (None/خالی = بازگشت به پیش‌فرض). مجوز system.settings."""
    # exclude_unset=True: صفحه «تنظیمات سامانه» هر گروه از فیلدها (Manifest،
    # اسپلش‌اسکرین، صفحه ورود، ...) را جداگانه ذخیره می‌کند؛ فقط فیلدهای حاضر در
    # بدنه درخواست پاس داده می‌شوند تا فیلدهای غایب به‌عنوان None به پیش‌فرض برنگردند.
    return await SystemSettingsService(db).set_branding(**payload.model_dump(exclude_unset=True))


@router.put("/branding/surfaces/{surface}", response_model=BrandingOut)
async def update_branding_surface(
    surface: str,
    payload: BrandingSurfaceIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    تنظیمات یک جای نمایش (لوگو/اندازه/مقیاس/قاب/فونت/رنگ) - فقط کلیدهای ارسالی.
    مجوز system.settings. خطا: 404 برای جای نمایش نامعتبر.
    """
    try:
        return await SystemSettingsService(db).set_surface(surface, payload.values)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/branding/surfaces/{surface}", response_model=BrandingOut)
async def reset_branding_surface(
    surface: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    برگرداندن یک جای نمایش به پیش‌فرض (لوگوی اختصاصی‌اش حذف نمی‌شود).
    مجوز system.settings. خطا: 404 برای جای نمایش نامعتبر.
    """
    try:
        return await SystemSettingsService(db).reset_surface(surface)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/branding/pwa-icon", response_model=BrandingOut)
async def update_pwa_icon_settings(
    payload: PwaIconSettingsIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """ذخیره مقیاس و پس‌زمینه آیکون‌های تولیدشده PWA (اندروید/iOS/ویندوز). مجوز system.settings."""
    return await SystemSettingsService(db).set_pwa_icon_settings(payload.values)


@router.get("/pwa-icon/{variant}.png")
async def get_pwa_icon_variant(variant: str, db: AsyncSession = Depends(get_db)):
    """
    بدون احراز هویت (Manifest/مرورگر بدون Header می‌گیرد). آیکون استاندارد
    تولیدشده از آیکون PWA آپلودی: any-192/512، maskable-192/512، apple-180،
    favicon-32/16. اگر آیکونی آپلود نشده: ۴۰۴ (فرانت به فایل‌های ثابت برمی‌گردد).
    """
    if variant not in pwa_icon_service.VARIANTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نوع آیکون نامعتبر است")
    service = SystemSettingsService(db)
    result = await service.get_logo("pwa_icon")
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="آیکون PWA هنوز تنظیم نشده")
    raw, content_type = result
    # تولید نسخه درخواستی با تنظیمات فعلی آیکون PWA
    settings = branding_surfaces.merged_pwa_icon(await service._get_raw(PWA_ICON_SETTINGS_KEY))
    content, media_type = pwa_icon_service.render_icon(raw, content_type, variant, settings)
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "public, max-age=300"})  # کش ۵ دقیقه‌ای مرورگر


@router.get("/logo/{slug}")
async def get_logo(slug: str, db: AsyncSession = Depends(get_db)):
    """
    فایل یک لوگو را برمی‌گرداند؛ بدون احراز هویت — هم‌الگو با /system/login-background.
    slug یکی از: app-logo، app-logo-small، pwa-icon، favicon، surface-<name>.
    خطا: 404 برای slug نامعتبر یا لوگوی تنظیم‌نشده.
    """
    key = _logo_slug_to_key(slug)
    result = await SystemSettingsService(db).get_logo(key)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این لوگو هنوز تنظیم نشده")
    content, content_type = result
    return Response(content=content, media_type=content_type)


@router.post("/logo/{slug}")
async def upload_logo(
    slug: str,
    file: UploadFile = File(..., description="لوگو (jpg/png/webp/svg)"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    یک لوگو را آپلود و ذخیره می‌کند. مجوز system.settings.
    خطا: 404 برای slug نامعتبر، 400 برای نوع غیرمجاز یا حجم بیش از ۴ مگابایت.
    """
    key = _logo_slug_to_key(slug)
    if file.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط فایل تصویری (jpg/png/webp/svg) پذیرفته می‌شود",
        )
    content = await file.read()
    if len(content) > MAX_LOGO_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="حجم فایل نباید بیشتر از ۴ مگابایت باشد")
    await SystemSettingsService(db).set_logo(key, content, file.content_type)
    return {"success": True}


@router.delete("/logo/{slug}")
async def delete_logo(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """یک لوگوی سفارشی را حذف می‌کند (بازگشت به پیش‌فرض). مجوز system.settings. خطا: 404 برای slug نامعتبر."""
    key = _logo_slug_to_key(slug)
    await SystemSettingsService(db).delete_logo(key)
    return {"success": True}


def _pwa_icon_version(pwa_settings: dict) -> str:
    """هش ۸ کاراکتری تنظیمات آیکون PWA؛ به‌عنوان پارامتر نسخه در URL آیکون‌ها برای شکستن کش."""
    return hashlib.sha1(json.dumps(pwa_settings, sort_keys=True).encode()).hexdigest()[:8]


@router.get("/manifest.json")
async def get_dynamic_manifest(db: AsyncSession = Depends(get_db)):
    """
    نسخه پویای PWA Manifest با نام و آیکون‌های برندینگ فعلی — بدون احراز هویت.
    Nginx مسیر /manifest.json را به همین Endpoint هدایت می‌کند (install.sh)،
    نه به فایل ثابت frontend/public/manifest.json.

    محدودیت پلتفرم (نه یک نقص این پیاده‌سازی): مرورگرها/سیستم‌عامل‌ها
    معمولاً Manifest را فقط هنگام نصب اولیه PWA می‌خوانند؛ برای کسانی که از
    قبل پرتال را روی صفحه اصلی نصب کرده‌اند، تغییر لوگو/اسم اینجا معمولاً
    فقط با حذف‌وبازنصب آن اپ روی گوشی‌شان اعمال می‌شود — نه خودکار.
    """
    branding = await SystemSettingsService(db).get_branding()

    if branding["has_custom_pwa_icon"]:
        # آیکون‌های استاندارد تولیدشده از یک تصویر (pwa_icon_service): "any" برای
        # ویندوز/کروم دسکتاپ، "maskable" با پس‌زمینه پر و لوگو در ناحیه امن برای
        # اندروید. یک پارامتر نسخه (هش تنظیمات) تا با تغییر مقیاس، کش مرورگر عوض شود.
        v = _pwa_icon_version(branding["pwa_icon"])
        icons = [
            {"src": f"/api/v1/system/pwa-icon/any-192.png?v={v}", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"/api/v1/system/pwa-icon/any-512.png?v={v}", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": f"/api/v1/system/pwa-icon/maskable-192.png?v={v}", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": f"/api/v1/system/pwa-icon/maskable-512.png?v={v}", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ]
    else:
        # بدون آیکون سفارشی: آیکون‌های ثابت داخل Build فرانت
        icons = [
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ]

    manifest = {
        "id": "/",
        # ویندوز/اندروید name را به‌عنوان نام اپ نصب‌شده نشان می‌دهند؛ مستقل از عنوان تب مرورگر است
        "name": branding["manifest_name"],
        "short_name": branding["manifest_short_name"],
        "description": branding["manifest_description"],
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "display_override": ["standalone", "minimal-ui"],
        "orientation": "portrait-primary",
        "dir": "rtl",
        "lang": "fa",
        "background_color": "#FFFFFF",
        "theme_color": "#1468A7",
        "prefer_related_applications": False,
        "icons": icons,
    }
    return Response(content=json.dumps(manifest, ensure_ascii=False), media_type="application/manifest+json")


# ---------- index.html پویا — عنوان تب مرورگر از برندینگ، حتی قبل از اجرای JS ----------

_FRONTEND_INDEX_HTML_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "frontend" / "dist" / "index.html"
)
_TITLE_TAG_PATTERN = re.compile(r"<title>.*?</title>", re.DOTALL)


@router.get("/index.html", response_class=Response)
async def get_dynamic_index_html(db: AsyncSession = Depends(get_db)):
    """
    نسخه پویای index.html — جایگزین فایل ثابت frontend/dist/index.html
    برای Fallback مسیرهای SPA (به install.sh مراجعه کنید: location @index_html_dynamic).

    چون index.html یک فایل ثابت Build-شده است، تگ <title> آن (که مرورگر تا قبل
    از اجرای جاوااسکریپت React نشان می‌دهد) مقدار ثابت زمان Build را دارد.
    این‌جا همان فایل HTML خوانده می‌شود و فقط محتوای تگ <title> با عنوان مرورگر
    از تنظیمات جایگزین می‌شود — بقیه (اسکریپت‌ها، لینک‌ها، Manifest) همان خروجی Build است.
    بدون احراز هویت. خطا: 404 اگر فرانت Build نشده باشد.
    """
    if not _FRONTEND_INDEX_HTML_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="فایل index.html پیدا نشد")

    html = _FRONTEND_INDEX_HTML_PATH.read_text(encoding="utf-8")
    branding = await SystemSettingsService(db).get_branding()
    # escape ساده برای جلوگیری از شکستن HTML اگر عنوان شامل < یا & باشد
    safe_title = branding["browser_title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = _TITLE_TAG_PATTERN.sub(f"<title>{safe_title}</title>", html, count=1)

    return Response(content=html, media_type="text/html")


@router.get("/smtp-settings", response_model=SmtpSettingsOut)
async def get_smtp_settings_endpoint(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    تنظیمات فعلی SMTP را برمی‌گرداند. مجوز system.settings.
    رمز عبور هرگز در پاسخ برنمی‌گردد — فقط has_password (بولی).
    """
    settings = await get_smtp_settings(db)
    return SmtpSettingsOut(
        enabled=settings.enabled,
        host=settings.host,
        port=settings.port,
        username=settings.username,
        has_password=bool(settings.password_encrypted),
        from_address=settings.from_address,
        from_name=settings.from_name,
        encryption_mode=settings.encryption_mode,
        password_reset_email_subject=settings.password_reset_email_subject,
        password_reset_email_body=settings.password_reset_email_body,
    )


@router.put("/smtp-settings", response_model=SmtpSettingsOut)
async def update_smtp_settings(
    payload: SmtpSettingsIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    تنظیمات SMTP را ذخیره می‌کند. مجوز system.settings.
    برای رمز عبور: اگر خالی فرستاده شود، رمز ذخیره‌شده دست‌نخورده می‌ماند.
    """
    settings = await get_smtp_settings(db)
    settings.enabled = payload.enabled
    settings.host = payload.host
    settings.port = payload.port
    settings.username = payload.username
    if payload.password:
        settings.password_encrypted = encrypt_secret(payload.password)
    settings.from_address = payload.from_address
    settings.from_name = payload.from_name
    settings.encryption_mode = payload.encryption_mode
    settings.password_reset_email_subject = payload.password_reset_email_subject
    settings.password_reset_email_body = payload.password_reset_email_body
    await db.commit()
    await db.refresh(settings)
    # پاسخ بدون رمز (فقط has_password)
    return SmtpSettingsOut(
        enabled=settings.enabled,
        host=settings.host,
        port=settings.port,
        username=settings.username,
        has_password=bool(settings.password_encrypted),
        from_address=settings.from_address,
        from_name=settings.from_name,
        encryption_mode=settings.encryption_mode,
        password_reset_email_subject=settings.password_reset_email_subject,
        password_reset_email_body=settings.password_reset_email_body,
    )


@router.post("/smtp-settings/test")
async def test_smtp_settings(
    payload: SmtpTestEmailIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    یک ایمیل آزمایشی با تنظیمات *ذخیره‌شده* SMTP می‌فرستد (نه یک تنظیم موقت وارد‌شده در فرم).
    مجوز system.settings. خطا: 400 اگر SMTP تنظیم نشده باشد یا ارسال شکست بخورد.
    """
    try:
        await send_email(
            db,
            to_address=payload.to_address,
            subject="تست تنظیمات SMTP - پرتال سازمانی",
            body_text="این یک ایمیل آزمایشی است. اگر این پیام را دریافت کرده‌اید، تنظیمات SMTP درست کار می‌کند.",
        )
    except (EmailNotConfiguredError, EmailError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"success": True, "message": "ایمیل آزمایشی با موفقیت ارسال شد."}


@router.get("/sms-settings", response_model=SmsSettingsOut)
async def get_sms_settings_endpoint(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    تنظیمات فعلی پیامک را برمی‌گرداند. مجوز system.settings.
    API Key هرگز در پاسخ برنمی‌گردد — فقط has_api_key (بولی).
    """
    settings = await get_sms_settings(db)
    return SmsSettingsOut(
        enabled=settings.enabled,
        has_api_key=bool(settings.api_key_encrypted),
        from_number=settings.from_number,
        sending_type=settings.sending_type,
        pattern_code=settings.pattern_code,
        webservice_message_template=settings.webservice_message_template,
    )


@router.put("/sms-settings", response_model=SmsSettingsOut)
async def update_sms_settings(
    payload: SmsSettingsIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    تنظیمات پیامک را ذخیره می‌کند. مجوز system.settings.
    برای API Key: اگر خالی فرستاده شود، مقدار ذخیره‌شده دست‌نخورده می‌ماند.
    """
    settings = await get_sms_settings(db)
    settings.enabled = payload.enabled
    if payload.api_key:
        settings.api_key_encrypted = encrypt_secret(payload.api_key)
    settings.from_number = payload.from_number
    settings.sending_type = payload.sending_type
    settings.pattern_code = payload.pattern_code
    settings.webservice_message_template = payload.webservice_message_template
    await db.commit()
    await db.refresh(settings)
    return SmsSettingsOut(
        enabled=settings.enabled,
        has_api_key=bool(settings.api_key_encrypted),
        from_number=settings.from_number,
        sending_type=settings.sending_type,
        pattern_code=settings.pattern_code,
        webservice_message_template=settings.webservice_message_template,
    )


@router.post("/sms-settings/test")
async def test_sms_settings(
    payload: SmsTestSendIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    """
    یک پیامک آزمایشی با تنظیمات ذخیره‌شده می‌فرستد (کد تست: 000000).
    مجوز system.settings. خطا: 400 اگر پیامک تنظیم نشده باشد یا ارسال شکست بخورد.
    """
    try:
        await send_sms_code(db, to_mobile=payload.to_mobile, code="000000")
    except (SmsNotConfiguredError, SmsError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"success": True, "message": "پیامک آزمایشی با موفقیت ارسال شد."}
