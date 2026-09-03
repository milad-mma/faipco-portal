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
from app.services.system_settings_service import SystemSettingsService
from app.services.usage_stats_service import get_usage_stats
from app.services.server_stats_service import get_server_stats
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


@router.get("/usage-stats")
async def usage_stats(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.backup")),
):
    """
    داده خام ساعتی استفاده از پرتال (آخرین ۹۰ روز) — برای نمودار «میزان
    استفاده» در پنل Admin. تجمیع روزانه/هفتگی/ماهانه و «کدام ساعت
    شبانه‌روز پرترافیک‌تر است» عمداً در فرانت‌اند انجام می‌شود.
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
    عمداً در فرانت‌اند انجام می‌شود.
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


# ---------- عکس پس‌زمینه صفحه ورود («تنظیمات سامانه») ----------

ALLOWED_LOGIN_BACKGROUND_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_LOGIN_BACKGROUND_SIZE = 8 * 1024 * 1024  # ۸ مگابایت — کافی برای یک عکس پس‌زمینه با کیفیت خوب


@router.get("/login-background")
async def get_login_background(db: AsyncSession = Depends(get_db)):
    """
    ⚠️ عمداً بدون هیچ احراز هویتی — صفحه ورود قبل از Login نمایش داده
    می‌شود، پس این تصویر باید همان‌جا هم قابل‌دریافت باشد. اگر هنوز چیزی
    آپلود نشده، ۴۰۴ برمی‌گرداند (فرانت‌اند این حالت را با پس‌زمینه پیش‌فرض
    فعلی جایگزین می‌کند).
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
    await SystemSettingsService(db).delete_login_background()
    return {"success": True}


# ---------- برندینگ (لوگوها + متن‌های مجزا) — «تنظیمات سامانه» ----------

ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}
MAX_LOGO_SIZE = 4 * 1024 * 1024  # ۴ مگابایت — لوگو معمولاً خیلی کوچک‌تر از یک عکس پس‌زمینه است

# چهار لوگوی کاملاً مستقل — هرکدام برای یک مصرف متفاوت با سایز توصیه‌شده خودش:
#   app_logo        → درون‌برنامه‌ای، اندازه‌های بزرگ (اسپلش، پنل کاربری) — هر اندازه‌ای
#   app_logo_small  → درون‌برنامه‌ای، اندازه‌های کوچک (نوار بالا، صفحه ورود) — اگر
#                      تنظیم نشود، همان app_logo (با Scale کوچک‌تر) استفاده می‌شود
#   pwa_icon        → آیکون Manifest/صفحه اصلی گوشی بعد از نصب — ترجیحاً ۵۱۲×۵۱۲ مربعی
#   favicon         → آیکون تب مرورگر — ترجیحاً ۳۲×۳۲ یا ۱۹۲×۱۹۲ مربعی
_VALID_LOGO_SLUGS = {"app-logo", "app-logo-small", "pwa-icon", "favicon"}


def _logo_slug_to_key(slug: str) -> str:
    if slug not in _VALID_LOGO_SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نوع لوگو نامعتبر است")
    return slug.replace("-", "_")


@router.get("/branding", response_model=BrandingOut)
async def get_branding(db: AsyncSession = Depends(get_db)):
    """⚠️ عمداً بدون احراز هویت — اسپلش‌اسکرین و صفحه ورود قبل از Login این را نیاز دارند."""
    return await SystemSettingsService(db).get_branding()


@router.put("/branding", response_model=BrandingOut)
async def update_branding(
    payload: BrandingIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.settings")),
):
    # ⚠️ عمداً exclude_unset=True: صفحه «تنظیمات سامانه» هر گروه از فیلدها
    # (Manifest، اسپلش‌اسکرین، صفحه ورود، ...) را کاملاً مستقل و جداگانه
    # ذخیره می‌کند — یعنی هر درخواست فقط شامل همان چند فیلد یک گروه است.
    # با model_dump() ساده، فیلدهای گروه‌های دیگر (که اصلاً در بدنه
    # درخواست نبودند) هم به‌عنوان None در نظر گرفته می‌شدند و set_branding
    # آن‌ها را بی‌صدا به پیش‌فرض برمی‌گرداند — یعنی ذخیره‌کردن یک گروه،
    # مقادیر گروه‌های دیگر را پاک می‌کرد. exclude_unset فقط همان فیلدهایی
    # که واقعاً در درخواست حاضر بودند را نگه می‌دارد.
    return await SystemSettingsService(db).set_branding(**payload.model_dump(exclude_unset=True))


@router.get("/logo/{slug}")
async def get_logo(slug: str, db: AsyncSession = Depends(get_db)):
    """
    ⚠️ بدون احراز هویت — دقیقاً هم‌الگو با /system/login-background.
    slug یکی از: app-logo، pwa-icon، favicon.
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
    key = _logo_slug_to_key(slug)
    await SystemSettingsService(db).delete_logo(key)
    return {"success": True}


@router.get("/manifest.json")
async def get_dynamic_manifest(db: AsyncSession = Depends(get_db)):
    """
    نسخه پویای PWA Manifest — جایگزین فایل ثابت frontend/public/manifest.json
    (که هرگز نمی‌توانست نام/آیکون سفارشی کارفرما را نشان بدهد). Nginx باید
    مسیر /manifest.json را به همین Endpoint هدایت کند (به install.sh مراجعه
    کنید) — نه به فایل ثابت قدیمی.

    ⚠️ محدودیت واقعی پلتفرم (نه یک نقص این پیاده‌سازی): مرورگرها/سیستم‌عامل‌ها
    معمولاً Manifest را فقط هنگام نصب اولیه PWA می‌خوانند؛ برای کسانی که از
    قبل پرتال را روی صفحه اصلی نصب کرده‌اند، تغییر لوگو/اسم اینجا معمولاً
    فقط با حذف‌وبازنصب آن اپ روی گوشی‌شان اعمال می‌شود — نه خودکار.
    """
    branding = await SystemSettingsService(db).get_branding()

    if branding["has_custom_pwa_icon"]:
        # ⚠️ یک محدودیت واقعی: چون فقط یک عکس (نه سه اندازه جداگانه) برای
        # آیکون PWA ذخیره می‌شود، همان یک آدرس برای هر سه اندازه/نوع آیکون
        # استفاده می‌شود — مرورگر/سیستم‌عامل خودش آن را Scale می‌کند. برای
        # بهترین نتیجه، بهتر است این آیکون حداقل ۵۱۲×۵۱۲ و مربعی باشد.
        icons = [
            {"src": "/api/v1/system/logo/pwa-icon", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/api/v1/system/logo/pwa-icon", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/api/v1/system/logo/pwa-icon", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ]
    else:
        icons = [
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ]

    manifest = {
        "id": "/",
        "name": branding["browser_title"],
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


# ---------- index.html پویا — رفع «FAIPCO Portal» ثابت در تب مرورگر قبل از اجرای JS ----------

_FRONTEND_INDEX_HTML_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "frontend" / "dist" / "index.html"
)
_TITLE_TAG_PATTERN = re.compile(r"<title>.*?</title>", re.DOTALL)


@router.get("/index.html", response_class=Response)
async def get_dynamic_index_html(db: AsyncSession = Depends(get_db)):
    """
    نسخه پویای index.html — جایگزین فایل ثابت frontend/dist/index.html
    برای Fallback مسیرهای SPA (به install.sh مراجعه کنید: location @index_html_dynamic).

    ⚠️ رفع یک محدودیت واقعی که کاربر گزارش داد: چون index.html یک فایل
    ثابت Build-شده است، تگ <title> آن (که مرورگر تا قبل از اجرای کامل
    جاوااسکریپت React نشان می‌دهد) همیشه همان مقدار ثابت زمان Build را
    داشت (مثلاً "FAIPCO Portal") — حتی وقتی Admin اسم را از پنل عوض کرده
    بود. اینجا، همان فایل HTML بدون تغییر خوانده می‌شود، فقط محتوای همان
    یک تگ <title> با عنوان واقعی از تنظیمات جایگزین می‌شود — همه‌چیز
    دیگر (اسکریپت‌ها، لینک‌ها، Manifest) دقیقاً همان خروجی Build اصلی است.
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
    """رمز عبور هرگز در پاسخ برنمی‌گردد — فقط has_password (بولی)."""
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
    """برای رمز عبور: اگر خالی فرستاده شود، رمز قبلاً ذخیره‌شده دست‌نخورده می‌ماند."""
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
    """یک ایمیل آزمایشی با تنظیمات فعلاً *ذخیره‌شده* SMTP می‌فرستد (نه یک تنظیم موقت وارد‌شده در فرم)."""
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
    """API Key هرگز در پاسخ برنمی‌گردد — فقط has_api_key (بولی)."""
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
    """برای API Key: اگر خالی فرستاده شود، مقدار قبلاً ذخیره‌شده دست‌نخورده می‌ماند."""
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
    """یک پیامک آزمایشی با تنظیمات فعلاً ذخیره‌شده می‌فرستد (کد تست: 000000)."""
    try:
        await send_sms_code(db, to_mobile=payload.to_mobile, code="000000")
    except (SmsNotConfiguredError, SmsError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"success": True, "message": "پیامک آزمایشی با موفقیت ارسال شد."}
