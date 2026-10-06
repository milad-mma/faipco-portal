"""
اپ اندروید (docs/android-app.md):

- اتصال گوشی: پرتال داخل اپ یک کد یک‌بارمصرف ۱۰ دقیقه‌ای می‌گیرد و به بخش بومی اپ می‌دهد؛ بخش بومی با آن یک
  «توکن دستگاه» می‌گیرد که فقط برای Endpointهای /mobile/device/* معتبر است (هش SHA-256 در دیتابیس).
- وضعیت: اپ با هر بار باز شدن و روزانه وضعیت دسترسی‌ها و Geofenceها را گزارش می‌دهد؛ «سالم» بودن گوشی مبنای
  پیش‌نیاز دسترسی «اپ اندروید با دسترسی موقعیت» است (access_gate_service).
- رویدادها: ورود (enter/dwell) و خروج (exit) از محدوده‌ی سایت → لاگ GPS با source=geofence (فقط گزارش پرتال،
  به کاراوب نوشته نمی‌شود). GPS جعلی ثبت نمی‌شود؛ ورود پشت ورود (یا خروج پشت خروج) در repeat_guard_hours نادیده.
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import haversine_distance_meters
from app.core.request_context import current_user_agent, is_android_user_agent
from app.models.employee import Employee
from app.models.gps_activity_log import GpsActivityLog, GpsLogType
from app.models.presence_session import PresenceSession
from app.models.mobile_device import (
    DevicePairingCode,
    GeofenceEvent,
    MobileAppExemption,
    MobileAppRelease,
    MobileDevice,
)
from app.models.site import Site
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.mobile import (
    ConnectivityEventsIn,
    DeviceRegisterIn,
    DeviceStatusIn,
    GeofenceEventIn,
    GeofenceEventsIn,
    MobileAppSettings,
)

logger = logging.getLogger(__name__)

SETTINGS_KEY = "mobile_app"
PAIRING_TTL_MINUTES = 10
# اتصال خودکار: کد تصادفی‌ای که خود اپ ساخته و در آدرس پرتال (#link=...) فرستاده؛ پرتال بعد از ورود کاربر آن را
# به حساب او وصل می‌کند و بخش بومی اپ با همان کد توکن دستگاه می‌گیرد
LINK_TTL_MINUTES = 15
# کد پیام‌ها برای وضعیت گوشی؛ BLOCKING_ISSUES مانع «سالم» بودن‌اند، بقیه فقط هشدارند
ISSUE_LABELS = {
    "revoked": "این گوشی توسط مدیر باطل شده است",
    "no_fine_location": "دسترسی موقعیت به اپ داده نشده است",
    "no_background_location": "دسترسی موقعیت روی «همیشه مجاز» نیست",
    "location_off": "موقعیت‌یاب (GPS) گوشی خاموش است",
    "no_geofences": "محدوده‌های کارخانه در گوشی ثبت نشده‌اند",
    "stale": "چند روز است از این گوشی گزارشی نرسیده (شاید اپ حذف شده)",
    "outdated": "نسخه‌ی اپ قدیمی است؛ نسخه‌ی جدید را نصب کنید",
    "no_notifications": "اجازه‌ی اعلان داده نشده است",
    "battery_restricted": "محدودیت باتری برای اپ برداشته نشده است",
}
# اعلان هم الزامی است (اپ بدون آن باز نمی‌شود)؛ «محدودیت باتری» فقط هشدار
BLOCKING_ISSUES = {
    "revoked", "no_fine_location", "no_background_location", "location_off", "no_geofences", "stale", "outdated",
    "no_notifications",
}
# مشکلاتی که داخل خود اپ هم پرتال را قفل می‌کنند (کاربر وسط کار دسترسی را گرفته یا GPS را خاموش کرده)
PERMISSION_ISSUES = ("no_fine_location", "no_background_location", "location_off", "no_notifications")
STATUS_LABELS = {
    "logged": "ثبت شد",
    "duplicate": "تکراری",
    "already_in": "ورود قبلی باز است",
    "already_out": "خروج قبلاً ثبت شده",
    "mock": "GPS جعلی",
    "disabled": "ثبت خودکار خاموش است",
    "unknown_site": "سایت نامعتبر",
    "no_employee": "بدون پرسنل",
    "no_location": "بدون مختصات",
    "out_of_range": "خارج از محدوده‌ی سایت",
    "bad_time": "زمان رویداد نامعتبر",
    "flap": "خروج کوتاه (لغو شد)",
}
# «آنلاین در محیط کار» با اپ بسته: نرسیدن گزارش «هنوز آنلاین» بیش از این = نشست قبلی تمام شده و آنلاین شدن بعدی
# نشست تازه است (همان BACKGROUND_STALE_SECONDS سرویس حضور)
ONLINE_SESSION_GAP = timedelta(minutes=25)
# خروجی که در این فاصله با ورود دوباره به همان سایت دنبال شود، خروج واقعی حساب نمی‌شود و لغو می‌شود
FLAP_WINDOW = timedelta(minutes=15)
NETWORK_LABELS = {"wifi": "وای‌فای", "cellular": "اینترنت همراه", "other": "شبکه"}
# رویداد خروجی که واقعاً خروج است (نه جعلی/خارج از بازه‌ی زمان/از عمق محدوده)
EXIT_OK_STATUSES = ("logged", "already_out", "duplicate", "disabled")
# اعتبارسنجی رویداد Geofencing: دقت GPS بیش از این مقدار در محاسبه‌ی فاصله حساب نمی‌شود، رویداد قدیمی‌تر از
# EVENT_MAX_AGE یا جلوتر از EVENT_MAX_FUTURE (ساعت گوشی) پذیرفته نمی‌شود — مانع جعل ورود/خروج با رویداد ساختگی
EVENT_ACCURACY_CAP_METERS = 100.0
# رویدادها در گوشی صف می‌شوند و با WorkManager (قطع شبکه، Doze) ممکن است ساعت‌ها بعد برسند؛ سقف ۴۸ ساعت
EVENT_MAX_AGE = timedelta(hours=48)
EVENT_MAX_FUTURE = timedelta(minutes=2)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- کلید اصلی قابلیت

FEATURE_KEY = "mobile_app_feature_enabled"


async def is_feature_enabled(db: AsyncSession) -> bool:
    """
    کلید اصلی قابلیت اپ اندروید (پیش‌فرض خاموش). خاموش = انگار قابلیت وجود ندارد: همه‌ی Endpointهای /mobile
    (به‌جز همین کلید) 404، منوها و یادآورها پنهان، پیش‌نیاز «اپ اندروید و موقعیت» بی‌اثر و پایش GPS «داخل اپ» غیرفعال.
    داده‌ها (گوشی‌ها، رویدادها، نسخه‌ها، تنظیمات) حذف نمی‌شوند و با روشن کردن دوباره برمی‌گردند.
    """
    row = await db.get(SystemSetting, FEATURE_KEY)
    return row is not None and row.value == "true"


async def set_feature_enabled(db: AsyncSession, enabled: bool) -> bool:
    row = await db.get(SystemSetting, FEATURE_KEY)
    value = "true" if enabled else "false"
    if row is None:
        db.add(SystemSetting(key=FEATURE_KEY, value=value))
    else:
        row.value = value
    await db.commit()
    return enabled


# ---------------------------------------------------------------- تنظیمات


async def get_mobile_settings(db: AsyncSession) -> MobileAppSettings:
    row = await db.get(SystemSetting, SETTINGS_KEY)
    if row is None or not row.value:
        return MobileAppSettings()
    try:
        return MobileAppSettings.model_validate(json.loads(row.value))
    except Exception:  # noqa: BLE001
        logger.warning("تنظیمات اپ اندروید نامعتبر است؛ پیش‌فرض‌ها اعمال شد")
        return MobileAppSettings()


async def save_mobile_settings(db: AsyncSession, data: MobileAppSettings) -> MobileAppSettings:
    row = await db.get(SystemSetting, SETTINGS_KEY)
    if row is None:
        db.add(SystemSetting(key=SETTINGS_KEY, value=data.model_dump_json()))
    else:
        row.value = data.model_dump_json()
    await db.commit()
    write_assetlinks(data.signing_sha256)
    return data


ANDROID_PACKAGE = "ir.faipco.portal"
ASSETLINKS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist" / ".well-known" / "assetlinks.json"


def assetlinks_json(fingerprint: str) -> str:
    return json.dumps(
        [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": ANDROID_PACKAGE,
                    "sha256_cert_fingerprints": [fingerprint] if fingerprint else [],
                },
            }
        ],
        indent=2,
    )


def write_assetlinks(fingerprint: str) -> bool:
    """
    فایل dist/.well-known/assetlinks.json را با اثر انگشت کلید امضا می‌نویسد (Nginx همین فایل را سرو می‌کند).
    بدون اثر انگشت یا بدون Build فرانت کاری نمی‌کند. خطا فقط لاگ می‌شود.
    """
    if not fingerprint or not ASSETLINKS_PATH.parent.parent.exists():
        return False
    try:
        ASSETLINKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        content = assetlinks_json(fingerprint)
        if ASSETLINKS_PATH.exists() and ASSETLINKS_PATH.read_text(encoding="utf-8") == content:
            return False
        ASSETLINKS_PATH.write_text(content, encoding="utf-8")
        logger.info("assetlinks.json با اثر انگشت کلید امضای اپ نوشته شد")
        return True
    except OSError as e:
        logger.warning("نوشتن assetlinks.json ناموفق بود: %s", e)
        return False


# ---------------------------------------------------------------- اتصال و احراز هویت دستگاه


async def create_pairing_code(db: AsyncSession, user: User) -> dict:
    """کد یک‌بارمصرف اتصال گوشی برای کاربر جاری؛ کدهای منقضی همان‌جا پاک می‌شوند."""
    now = _now()
    await db.execute(delete(DevicePairingCode).where(DevicePairingCode.expires_at < now - timedelta(days=1)))
    code = secrets.token_urlsafe(24)
    db.add(DevicePairingCode(code_hash=_hash(code), user_id=user.id, expires_at=now + timedelta(minutes=PAIRING_TTL_MINUTES)))
    await db.commit()
    return {"code": code, "expires_in": PAIRING_TTL_MINUTES * 60}


class DeviceAuthError(Exception):
    """کد اتصال یا توکن دستگاه نامعتبر (پیام فارسی)."""


class DeviceLinkExpiredError(DeviceAuthError):
    """کد اتصال قبلاً مصرف شده یا منقضی است (اپ دیگر تلاش نمی‌کند)."""


def _link_hash(link: str) -> str:
    """هش کد اتصال خودکار با پیشوند جدا، تا هرگز با کد اتصال دستی (همان جدول) یکی نشود."""
    return _hash("link:" + link)


async def claim_device_link(db: AsyncSession, user: User, link: str) -> bool:
    """
    اتصال خودکار: کد ساخته‌شده توسط اپ را به کاربر واردشده وصل می‌کند (بدون هیچ اقدام کاربر).
    کد قبلاً مصرف‌شده دوباره وصل نمی‌شود (False). کدی که قبلاً به حساب دیگری وصل شده هم هرگز به کاربر فعلی
    منتقل نمی‌شود (False + لاگ) — وگرنه هرکس کد اتصال را می‌دانست می‌توانست گوشیِ دیگری را به حساب خودش بچسباند.
    ارسال دوباره‌ی همان کاربر (مثلاً رفرش صفحه) فقط مهلت را تازه می‌کند (True).
    """
    now = _now()
    await db.execute(delete(DevicePairingCode).where(DevicePairingCode.expires_at < now - timedelta(days=1)))
    row = (
        await db.execute(select(DevicePairingCode).where(DevicePairingCode.code_hash == _link_hash(link)))
    ).scalar_one_or_none()
    if row is not None and row.used_at is not None:
        await db.commit()
        return False
    if row is None:
        db.add(
            DevicePairingCode(code_hash=_link_hash(link), user_id=user.id, expires_at=now + timedelta(minutes=LINK_TTL_MINUTES))
        )
    elif row.user_id != user.id:
        # اولین ادعا برنده است؛ کد وصل‌شده به حساب دیگر دست‌نخورده می‌ماند
        logger.warning("تلاش برای انتقال کد اتصال اپ از کاربر %s به کاربر %s رد شد", row.user_id, user.id)
        await db.commit()
        return False
    else:
        row.expires_at = now + timedelta(minutes=LINK_TTL_MINUTES)
    await db.commit()
    return True


async def register_device(db: AsyncSession, payload: DeviceRegisterIn, ip: str | None) -> tuple[MobileDevice, str]:
    """کد اتصال را مصرف می‌کند و دستگاه + توکن تازه می‌سازد. نصب قبلی همین گوشی (همان device_uid) باطل می‌شود."""
    now = _now()
    # کد اتصال دستی (از پرتال) یا کد اتصال خودکار (ساخته‌ی خود اپ)
    pairing = (
        await db.execute(
            select(DevicePairingCode).where(
                DevicePairingCode.code_hash.in_([_hash(payload.code), _link_hash(payload.code)])
            )
        )
    ).scalars().first()
    if pairing is None:
        # اتصال خودکار: هنوز کسی در پرتال با این کد وارد نشده؛ اپ کمی بعد دوباره می‌پرسد
        raise DeviceAuthError("این گوشی هنوز به حسابی وصل نشده است؛ داخل اپ وارد پرتال شوید.")
    if pairing.used_at is not None or pairing.expires_at < now:
        raise DeviceLinkExpiredError("کد اتصال نامعتبر یا منقضی است؛ اپ را ببندید و دوباره باز کنید.")
    user = await db.get(User, pairing.user_id)
    if user is None or not user.is_active:
        raise DeviceAuthError("حساب کاربری فعال نیست.")
    pairing.used_at = now

    old = (
        await db.execute(
            select(MobileDevice).where(MobileDevice.device_uid == payload.device_uid, MobileDevice.revoked_at.is_(None))
        )
    ).scalars().all()
    token = secrets.token_urlsafe(40)
    # همان گوشی، همان کاربر (مثلاً اتصال خودکار در هر باز شدن اپ): همان رکورد با توکن تازه، بدون ردیف جدید
    same = next((d for d in old if d.user_id == user.id), None)
    if same is not None:
        same.token_hash = _hash(token)
        same.employee_id = user.employee_id
        for field in ("manufacturer", "model", "os_version", "sdk_int", "app_version_code", "app_version_name"):
            setattr(same, field, getattr(payload, field))
        same.last_ip = (ip or "")[:64] or same.last_ip
        for device in old:
            if device is not same:
                device.revoked_at = now
                device.revoked_reason = "اتصال دوباره‌ی همین گوشی"
        await db.commit()
        await db.refresh(same)
        return same, token
    # همان گوشی قبلاً برای کاربر دیگری ثبت شده (حساب عوض شده): نسخه‌ی قبلی باطل می‌شود
    for device in old:
        device.revoked_at = now
        device.revoked_reason = "اتصال همین گوشی به حساب دیگر"

    device = MobileDevice(
        user_id=user.id,
        employee_id=user.employee_id,
        device_uid=payload.device_uid,
        token_hash=_hash(token),
        manufacturer=payload.manufacturer,
        model=payload.model,
        os_version=payload.os_version,
        sdk_int=payload.sdk_int,
        app_version_code=payload.app_version_code,
        app_version_name=payload.app_version_name,
        created_at=now,
        last_ip=(ip or "")[:64] or None,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device, token


async def get_device_by_token(db: AsyncSession, token: str | None) -> MobileDevice:
    if not token:
        raise DeviceAuthError("توکن دستگاه ارسال نشده است.")
    device = (await db.execute(select(MobileDevice).where(MobileDevice.token_hash == _hash(token)))).scalar_one_or_none()
    if device is None or device.revoked_at is not None:
        raise DeviceAuthError("این گوشی از حساب جدا شده است؛ از داخل پرتال دوباره «فعال‌سازی» را بزنید.")
    user = await db.get(User, device.user_id)
    if user is None or not user.is_active:
        raise DeviceAuthError("حساب کاربری فعال نیست.")
    return device


# ---------------------------------------------------------------- وضعیت


async def configured_sites(db: AsyncSession) -> list[Site]:
    result = await db.execute(
        select(Site).where(
            Site.gps_latitude.is_not(None), Site.gps_longitude.is_not(None), Site.gps_radius_meters.is_not(None)
        )
    )
    return [s for s in result.scalars().all() if s.gps_radius_meters]


def device_issues(device: MobileDevice, cfg: MobileAppSettings, has_sites: bool, now: datetime | None = None) -> list[str]:
    """فهرست کد مشکلات یک گوشی (ترتیب: مهم‌ترین اول)."""
    now = now or _now()
    issues: list[str] = []
    if device.revoked_at is not None:
        return ["revoked"]
    if not device.perm_fine_location:
        issues.append("no_fine_location")
    elif not device.perm_background_location:
        issues.append("no_background_location")
    if not device.location_enabled:
        issues.append("location_off")
    if has_sites and not device.geofences_registered:
        issues.append("no_geofences")
    if device.status_reported_at is None or device.status_reported_at < now - timedelta(days=cfg.status_stale_days):
        issues.append("stale")
    if cfg.min_version_code and (device.app_version_code or 0) < cfg.min_version_code:
        issues.append("outdated")
    if not device.perm_notifications:
        issues.append("no_notifications")
    if not device.battery_unrestricted:
        issues.append("battery_restricted")
    return issues


def is_healthy(issues: list[str]) -> bool:
    return not any(i in BLOCKING_ISSUES for i in issues)


async def update_device_status(db: AsyncSession, device: MobileDevice, payload: DeviceStatusIn, ip: str | None) -> dict:
    """گزارش وضعیت اپ را ذخیره می‌کند؛ خروجی: سالم بودن، مشکلات و اطلاعات نسخه‌ی جدید."""
    device.perm_fine_location = payload.fine_location
    device.perm_background_location = payload.background_location
    device.perm_notifications = payload.notifications
    device.battery_unrestricted = payload.battery_unrestricted
    device.location_enabled = payload.location_enabled
    device.has_gms = payload.has_gms
    device.geofence_engine = payload.engine
    device.geofences_registered = payload.geofences_registered
    device.geofence_count = payload.geofence_count
    if payload.app_version_code is not None:
        device.app_version_code = payload.app_version_code
    if payload.app_version_name:
        device.app_version_name = payload.app_version_name
    if payload.os_version:
        device.os_version = payload.os_version
    if payload.sdk_int is not None:
        device.sdk_int = payload.sdk_int
    device.status_reported_at = _now()
    device.last_ip = (ip or "")[:64] or None
    await db.commit()
    cfg = await get_mobile_settings(db)
    issues = device_issues(device, cfg, bool(await configured_sites(db)))
    latest = await latest_release_info(db)
    return {
        "healthy": is_healthy(issues),
        "issues": [{"code": i, "label": ISSUE_LABELS[i], "blocking": i in BLOCKING_ISSUES} for i in issues],
        "latest_version_code": latest["version_code"] if latest else None,
        "latest_version_name": latest["version_name"] if latest else None,
        "min_version_code": cfg.min_version_code,
    }


async def geofence_config(db: AsyncSession) -> dict:
    """محدوده‌ها و پارامترهای Geofencing برای اپ؛ version با هر تغییر سایت یا تنظیمات عوض می‌شود."""
    cfg = await get_mobile_settings(db)
    sites = [
        {"id": s.id, "name": s.name, "latitude": s.gps_latitude, "longitude": s.gps_longitude, "radius": int(s.gps_radius_meters)}
        for s in await configured_sites(db)
    ][:100]
    body = {
        "enabled": cfg.auto_clock_enabled,
        # اپ فقط وقتی داخل محدوده است آنلاین شدن گوشی را گزارش می‌دهد (اپ قدیمی این کلید را نادیده می‌گیرد)
        "online_tracking": cfg.online_tracking_enabled,
        "loitering_ms": cfg.loitering_seconds * 1000,
        "responsiveness_ms": cfg.responsiveness_seconds * 1000,
        "sites": sites,
    }
    body["version"] = _hash(json.dumps(body, sort_keys=True))[:16]
    return body


# ---------------------------------------------------------------- رویدادها


def _event_time(ms: int, received: datetime) -> datetime:
    """زمان رویداد از ساعت گوشی؛ اگر آینده یا خیلی قدیمی باشد (ساعت اشتباه)، زمان دریافت."""
    try:
        at = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return received
    if at > received + timedelta(minutes=2) or at < received - timedelta(days=3):
        return received
    return at


def _event_time_valid(ms: int, received: datetime) -> bool:
    """
    آیا زمان خام رویداد (ساعت گوشی) در بازه‌ی پذیرفتنی است؟ قدیمی‌تر از EVENT_MAX_AGE یا جلوتر از EVENT_MAX_FUTURE
    (یا غیرقابل تبدیل) = نامعتبر؛ رویداد ساختگی با زمان دلخواه نباید به ورود/خروج تبدیل شود.
    """
    try:
        at = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return False
    return received - EVENT_MAX_AGE <= at <= received + EVENT_MAX_FUTURE


def resolve_event_time(
    occurred_ms: int,
    elapsed_ms: int | None,
    boot_count: int | None,
    now_elapsed_ms: int | None,
    now_boot_count: int | None,
    received: datetime,
    now_wall_ms: int | None = None,
) -> tuple[datetime, bool, bool]:
    """
    زمان واقعی رویداد، بدون اعتماد به ساعت گوشی. خروجی: (زمان، زمان نامطمئن است؟، معتبر است؟)

    «کرنومتر» گوشی (elapsedRealtime) از لحظه‌ی روشن شدن گوشی می‌شمارد و کاربر نمی‌تواند تغییرش دهد. اپ کرنومتر لحظه‌ی
    رویداد و لحظه‌ی ارسال را می‌فرستد؛ زمان رویداد = زمان رسیدن به سرور منهای فاصله‌ی این دو. تغییر ساعت، تاریخ یا
    منطقه‌ی زمانی گوشی اثری ندارد.
    - همان روشن شدن گوشی (boot_count برابر) ← زمان دقیق. قدیمی‌تر از EVENT_MAX_AGE ← نامعتبر.
      اندروید ۶ شماره‌ی روشن شدن ندارد: «همان روشن شدن» یعنی فاصله‌ی کرنومتر با فاصله‌ی ساعت گوشی (now_wall_ms −
      occurred_ms) حداکثر ۵ دقیقه فرق کند؛ وگرنه (خاموش/روشن یا دستکاری ساعت در این فاصله) نامطمئن.
    - گوشی بین رویداد و ارسال خاموش/روشن شده ← کرنومتر قابل استفاده نیست: ساعت گوشی (با همان بازه‌ی مجاز قبلی) و
      «زمان نامطمئن» (در گزارش با برچسب نمایش داده می‌شود).
    - نسخه‌ی قدیمی اپ بدون کرنومتر ← رفتار قبلی (ساعت گوشی).
    """
    if elapsed_ms is not None and now_elapsed_ms is not None:
        age_ms = now_elapsed_ms - elapsed_ms
        if boot_count is not None and now_boot_count is not None:
            same_boot = boot_count == now_boot_count
        elif now_wall_ms is not None:
            same_boot = abs((now_wall_ms - occurred_ms) - age_ms) <= 5 * 60 * 1000
        else:
            same_boot = False
        if same_boot and age_ms >= 0:
            # مقایسه پیش از ساختن timedelta: عدد خیلی بزرگ (درخواست دستکاری‌شده) OverflowError نمی‌دهد
            if age_ms > EVENT_MAX_AGE.total_seconds() * 1000:
                return received, False, False
            return received - timedelta(milliseconds=age_ms), False, True
        return _event_time(occurred_ms, received), True, _event_time_valid(occurred_ms, received)
    return _event_time(occurred_ms, received), False, _event_time_valid(occurred_ms, received)


def _event_rejection(
    ev: GeofenceEventIn, site: Site, distance: float | None, received: datetime, time_valid: bool | None = None
) -> str | None:
    """
    اعتبارسنجی رویداد نسبت به سایت: کد وضعیت رد (mock / no_location / bad_time / out_of_range) یا None اگر معتبر.
    - ورود/حضور (enter/dwell): مختصات لازم است و فاصله باید ≤ شعاع سایت + دقت GPS (حداکثر EVENT_ACCURACY_CAP_METERS).
    - خروج (exit): طبق تعریف بیرون از حصار رخ می‌دهد و موتور سیستمی اندروید ممکن است مختصات نداشته باشد؛
      فقط زمان بررسی می‌شود (و اگر مختصات دارد، نباید به‌وضوح داخل حصار باشد).
    """
    if ev.is_mock:
        return "mock"
    if time_valid is None:
        time_valid = _event_time_valid(ev.occurred_at, received)
    if not time_valid:
        return "bad_time"
    tolerance = min(ev.accuracy or 0.0, EVENT_ACCURACY_CAP_METERS)
    radius = float(site.gps_radius_meters)
    if (ev.transition or "").lower() == "exit":
        if distance is not None and distance < max(radius - tolerance, 0.0) * 0.5:
            return "out_of_range"  # «خروج» از عمق داخل حصار معنا ندارد
        return None
    if ev.latitude is None or ev.longitude is None or distance is None:
        return "no_location"
    if distance > radius + tolerance:
        return "out_of_range"
    return None


async def process_geofence_events(
    db: AsyncSession, device: MobileDevice, events: list[GeofenceEventIn] | GeofenceEventsIn
) -> list[dict]:
    """
    رویدادها را به ترتیب زمان پردازش می‌کند؛ خروجی برای هر رویداد: id، status، پیام کوتاه برای اعلان اپ.
    زمان هر رویداد با resolve_event_time (کرنومتر گوشی + ساعت سرور) حساب می‌شود.
    """
    received = _now()
    if isinstance(events, GeofenceEventsIn):
        now_elapsed, now_boot, now_wall = events.now_elapsed_ms, events.boot_count, events.now_wall_ms
        events = events.events
    else:
        now_elapsed = now_boot = now_wall = None
    cfg = await get_mobile_settings(db)
    sites = {s.id: s for s in await configured_sites(db)}
    out: list[dict] = []
    times = {
        id(ev): resolve_event_time(
            ev.occurred_at, ev.elapsed_ms, ev.boot_count, now_elapsed, now_boot, received, now_wall
        )
        for ev in events
    }

    for ev in sorted(events, key=lambda e: times[id(e)][0]):
        existing = (
            await db.execute(
                select(GeofenceEvent).where(GeofenceEvent.device_id == device.id, GeofenceEvent.client_event_id == ev.id)
            )
        ).scalar_one_or_none()
        if existing is not None:  # ارسال دوباره‌ی همان رویداد (مثلاً قطع شبکه بعد از ثبت)
            out.append({"id": ev.id, "status": existing.status, "message": None})
            continue

        occurred, time_uncertain, time_valid = times[id(ev)]
        site = sites.get(ev.site_id)
        log_type = GpsLogType.check_out if ev.transition == "exit" else GpsLogType.check_in
        distance = None
        if site is not None and ev.latitude is not None and ev.longitude is not None:
            distance = haversine_distance_meters(ev.latitude, ev.longitude, site.gps_latitude, site.gps_longitude)

        status = "logged"
        rejection = _event_rejection(ev, site, distance, received, time_valid) if site is not None else None
        if device.employee_id is None:
            status = "no_employee"
        elif site is None:
            status = "unknown_site"
        elif rejection is not None:
            # رویداد نامعتبر (GPS جعلی، بدون مختصات، زمان نامعتبر، خارج از محدوده): ثبت نمی‌شود ولی برای ردیابی لاگ می‌ماند
            status = rejection
            logger.info(
                "رویداد Geofencing دستگاه %s (پرسنل %s) رد شد: %s — سایت %s، فاصله %s متر، دقت %s متر",
                device.id,
                device.employee_id,
                status,
                site.id,
                None if distance is None else round(distance),
                ev.accuracy,
            )
        elif not cfg.auto_clock_enabled:
            status = "disabled"
        else:
            last = (
                await db.execute(
                    select(GpsActivityLog)
                    .where(
                        GpsActivityLog.employee_id == device.employee_id,
                        GpsActivityLog.log_type != GpsLogType.presence,
                        GpsActivityLog.created_at <= occurred + timedelta(minutes=1),
                    )
                    .order_by(GpsActivityLog.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if last is not None and last.log_type == log_type:
                gap = occurred - last.created_at
                if gap < timedelta(minutes=2):
                    status = "duplicate"
                elif gap < timedelta(hours=cfg.repeat_guard_hours):
                    status = "already_in" if log_type == GpsLogType.check_in else "already_out"
            elif (
                last is not None
                and log_type == GpsLogType.check_in
                and last.log_type == GpsLogType.check_out
                and last.source == "geofence"
                and last.matched_site_id == site.id
                and occurred - last.created_at < FLAP_WINDOW
            ):
                # خروج و ورود دوباره‌ی کوتاه (خاموش/روشن کردن GPS، لبه‌ی محدوده، پرش موقعیت داخل سالن): خروج قبلی لغو
                # می‌شود و پرسنل همچنان «داخل» است — نه یک خروج و یک ورود اضافه
                await _cancel_flap_exit(db, last)
                status = "already_in"

        gps_log = None
        if status == "logged":
            gps_log = GpsActivityLog(
                employee_id=device.employee_id,
                log_type=log_type,
                latitude=ev.latitude,
                longitude=ev.longitude,
                accuracy_meters=ev.accuracy,
                matched_site_id=site.id,
                distance_meters=distance,
                is_within_geofence=ev.transition != "exit",
                is_manual=False,
                source="geofence",
                device_id=device.id,
                created_at=occurred,
                time_uncertain=time_uncertain,
            )
            db.add(gps_log)
            await db.flush()

        db.add(
            GeofenceEvent(
                device_id=device.id,
                employee_id=device.employee_id,
                site_id=site.id if site else None,
                client_event_id=ev.id,
                transition=ev.transition,
                engine=ev.engine,
                occurred_at=occurred,
                received_at=received,
                latitude=ev.latitude,
                longitude=ev.longitude,
                accuracy_meters=ev.accuracy,
                distance_meters=distance,
                is_mock=ev.is_mock,
                time_uncertain=time_uncertain,
                status=status,
                gps_log_id=gps_log.id if gps_log else None,
            )
        )
        # خروج از محدوده: نشست «آنلاین در محیط کار» (اپ بسته) این سایت که پیش از خروج شروع شده همان‌جا تمام می‌شود
        if ev.transition == "exit" and site is not None and device.employee_id is not None and status in EXIT_OK_STATUSES:
            await _close_background_sessions(db, device.employee_id, site.id, before=occurred)
        message = None
        if status == "logged":
            from app.core.persian_date import to_tehran_time_str

            action = "ورود" if log_type == GpsLogType.check_in else "خروج"
            message = f"{action} شما به «{site.name}» ساعت {to_tehran_time_str(occurred)} ثبت شد."
        elif status == "mock":
            message = "موقعیت جعلی تشخیص داده شد؛ ورود/خروج ثبت نشد."
        out.append({"id": ev.id, "status": status, "message": message})

    device.last_event_at = received
    await db.commit()
    return out


# ---------------------------------------------------------------- «آنلاین در محیط کار» (اپ بسته)


async def _cancel_flap_exit(db: AsyncSession, exit_log: GpsActivityLog) -> None:
    """لاگ خروج کوتاه حذف و رویداد Geofencing آن «flap» علامت می‌خورد (در فهرست رویدادها برای ردیابی می‌ماند)."""
    events = (
        await db.execute(select(GeofenceEvent).where(GeofenceEvent.gps_log_id == exit_log.id))
    ).scalars().all()
    for event in events:
        event.status = "flap"
        event.gps_log_id = None
    await db.flush()
    await db.delete(exit_log)
    await db.flush()


async def _close_background_sessions(
    db: AsyncSession, employee_id: int, site_id: int, before: datetime | None = None
) -> None:
    """
    نشست‌های پس‌زمینه‌ی باز این پرسنل در این سایت را با آخرین زمان دیده‌شده می‌بندد.
    before (زمان خروج): فقط نشست‌هایی که پیش از آن شروع شده‌اند، و پایان حداکثر همان زمان (خروج دیررسیده نشست تازه‌تر را
    نمی‌بندد).
    """
    conds = [
        PresenceSession.employee_id == employee_id,
        PresenceSession.matched_site_id == site_id,
        PresenceSession.source == "background",
        PresenceSession.disconnected_at.is_(None),
    ]
    if before is not None:
        conds.append(PresenceSession.connected_at <= before)
    rows = (await db.execute(select(PresenceSession).where(*conds))).scalars().all()
    for row in rows:
        end = row.last_seen_at or row.connected_at
        if before is not None:
            end = max(min(end, before), row.connected_at)
        row.disconnected_at = end
        row.duration_seconds = max(int((end - row.connected_at).total_seconds()), 0)


async def _exited_between(db: AsyncSession, employee_id: int, site_id: int, start: datetime, end: datetime) -> bool:
    """آیا بین start و end یک خروج واقعی از این سایت ثبت شده است؟"""
    row = await db.execute(
        select(GeofenceEvent.id)
        .where(
            GeofenceEvent.employee_id == employee_id,
            GeofenceEvent.site_id == site_id,
            GeofenceEvent.transition == "exit",
            GeofenceEvent.status.in_(EXIT_OK_STATUSES),
            GeofenceEvent.occurred_at > start,
            GeofenceEvent.occurred_at <= end,
        )
        .limit(1)
    )
    return row.first() is not None


async def _portal_gps_live(db: AsyncSession, employee_id: int, site_id: int) -> bool:
    """نشست «آنلاین در محیط کار» با منبع پرتال (پرتال باز داخل اپ) برای این سایت همین الان زنده است؟"""
    from app.services.gps_attendance_service import presence_alive_since

    row = await db.execute(
        select(PresenceSession.id)
        .where(
            PresenceSession.employee_id == employee_id,
            PresenceSession.matched_site_id == site_id,
            PresenceSession.kind == "gps",
            PresenceSession.source == "portal",
            PresenceSession.disconnected_at.is_(None),
            func.coalesce(PresenceSession.last_seen_at, PresenceSession.connected_at) >= presence_alive_since("portal"),
        )
        .limit(1)
    )
    return row.first() is not None


# رویداد ورود/خروجی که نشان می‌دهد پرسنل واقعاً آن‌جا بوده (نه جعلی یا خارج از بازه)
PRESENCE_OK_STATUSES = ("logged", "already_in", "already_out", "duplicate", "disabled")
NATIVE_INSIDE_MAX_AGE = timedelta(hours=16)


async def native_inside_site(db: AsyncSession, employee_id: int) -> int | None:
    """
    سایتی که بخش بومی اپ (Geofencing) این پرسنل را الان داخلش می‌داند: آخرین رویداد معتبرش ورود/حضور (نه خروج) و
    کمتر از NATIVE_INSIDE_MAX_AGE پیش است. پشتیبان «آنلاین در محیط کار» برای پرتالِ داخل اپ وقتی مرورگر داخل سالن
    موقعیت ندارد.
    """
    row = (
        await db.execute(
            select(GeofenceEvent.site_id, GeofenceEvent.transition, GeofenceEvent.occurred_at)
            .where(
                GeofenceEvent.employee_id == employee_id,
                GeofenceEvent.status.in_(PRESENCE_OK_STATUSES),
                GeofenceEvent.site_id.is_not(None),
            )
            .order_by(GeofenceEvent.occurred_at.desc())
            .limit(1)
        )
    ).first()
    if row is None or row.transition == "exit" or row.occurred_at < _now() - NATIVE_INSIDE_MAX_AGE:
        return None
    return row.site_id


def _network_label(network: str | None) -> str:
    return "اپ (پس‌زمینه) · " + NETWORK_LABELS.get(network or "other", "شبکه")


async def process_connectivity_events(db: AsyncSession, device: MobileDevice, payload: ConnectivityEventsIn) -> int:
    """
    گزارش‌های «گوشی داخل محدوده آنلاین است» (اپ بسته) → نشست «آنلاین در محیط کار» با source=background.
    online = لحظه‌ی وصل شدن (دقیق)، alive = هنوز وصل است (حدود هر ۱۵ دقیقه). گزارش در فاصله‌ی ONLINE_SESSION_GAP از
    نشست موجود همان نشست را ادامه می‌دهد؛ وگرنه نشست قبلی (با آخرین زمان دیده‌شده) بسته و نشست تازه باز می‌شود.
    پایان واقعی آنلاین بودن را اندروید بدون باز بودن اپ خبر نمی‌دهد ← پایان نشست = آخرین گزارش (حداکثر ~۱۵ دقیقه خطا).
    خروجی: تعداد گزارش‌های اعمال‌شده. ارسال دوباره‌ی همان گزارش اثری ندارد (زمانش داخل نشست موجود است).
    """
    cfg = await get_mobile_settings(db)
    if not cfg.online_tracking_enabled or device.employee_id is None or not payload.events:
        return 0
    received = _now()
    sites = {s.id: s for s in await configured_sites(db)}
    resolved = []
    for ev in payload.events:
        at, uncertain, valid = resolve_event_time(
            ev.occurred_at, ev.elapsed_ms, ev.boot_count, payload.now_elapsed_ms, payload.boot_count, received,
            payload.now_wall_ms,
        )
        if valid and ev.site_id in sites:
            resolved.append((min(at, received), uncertain, ev))
    resolved.sort(key=lambda item: item[0])

    applied = 0
    for at, uncertain, ev in resolved:
        site = sites[ev.site_id]
        # پرتال همین الان داخل اپ باز است و نشست «پرتال باز» همین سایت زنده است: دوباره شمرده نمی‌شود
        if await _portal_gps_live(db, device.employee_id, site.id):
            continue
        session = (
            await db.execute(
                select(PresenceSession)
                .where(
                    PresenceSession.employee_id == device.employee_id,
                    PresenceSession.matched_site_id == site.id,
                    PresenceSession.source == "background",
                    PresenceSession.connected_at <= at + ONLINE_SESSION_GAP,
                )
                .order_by(PresenceSession.connected_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if session is not None:
            last = session.last_seen_at or session.connected_at
            end = session.disconnected_at or last
            if session.connected_at - ONLINE_SESSION_GAP <= at <= end + ONLINE_SESSION_GAP:
                if session.disconnected_at is None:
                    # ادامه‌ی همان نشست (گزارش دیررسیده‌ی قبل از شروع هم شروع را عقب می‌برد)
                    session.connected_at = min(session.connected_at, at)
                    session.last_seen_at = max(last, at)
                    session.time_uncertain = session.time_uncertain or uncertain
                    applied += 1
                elif at <= end:
                    pass  # داخل نشست بسته‌شده‌ی قبلی (ارسال دوباره)
                elif not await _exited_between(db, device.employee_id, site.id, end, at):
                    # گزارش دیررسیده (Doze) بعد از اینکه Job نشست را بسته بود: همان نشست ادامه پیدا می‌کند
                    from app.services.gps_attendance_service import presence_alive_since

                    session.last_seen_at = at
                    session.time_uncertain = session.time_uncertain or uncertain
                    if at >= presence_alive_since("background"):
                        session.disconnected_at = None
                        session.duration_seconds = None
                    else:
                        session.disconnected_at = at
                        session.duration_seconds = max(int((at - session.connected_at).total_seconds()), 0)
                    applied += 1
                else:
                    session = None
                if session is not None:
                    continue
        newer_open = (
            await db.execute(
                select(PresenceSession.id).where(
                    PresenceSession.employee_id == device.employee_id,
                    PresenceSession.matched_site_id == site.id,
                    PresenceSession.source == "background",
                    PresenceSession.disconnected_at.is_(None),
                    PresenceSession.connected_at > at,
                )
            )
        ).first()
        if newer_open is not None:
            # گزارش خیلی دیررسیده از قبل از نشست فعلی: نشست کوتاه جدا و بسته، بدون دست زدن به نشست فعلی
            db.add(
                PresenceSession(
                    employee_id=device.employee_id, kind="gps", source="background", connected_at=at,
                    last_seen_at=at, disconnected_at=at, duration_seconds=0, client=_network_label(ev.network),
                    matched_site_id=site.id, is_within_geofence=True, time_uncertain=uncertain,
                )
            )
            await db.flush()
            applied += 1
            continue
        await _close_background_sessions(db, device.employee_id, site.id)
        db.add(
            PresenceSession(
                employee_id=device.employee_id,
                kind="gps",
                source="background",
                connected_at=at,
                last_seen_at=at,
                client=_network_label(ev.network),
                matched_site_id=site.id,
                is_within_geofence=True,
                time_uncertain=uncertain,
            )
        )
        await db.flush()
        applied += 1
    device.last_event_at = received
    await db.commit()
    return applied


# ---------------------------------------------------------------- کاربر جاری (پرتال) و پیش‌نیاز دسترسی


async def is_exempt(db: AsyncSession, employee_id: int | None) -> bool:
    if employee_id is None:
        return True
    row = await db.execute(select(MobileAppExemption.id).where(MobileAppExemption.employee_id == employee_id))
    return row.scalar_one_or_none() is not None


async def user_devices_health(db: AsyncSession, user: User) -> tuple[bool, list[dict]]:
    """(حداقل یک گوشی سالم دارد؟، خلاصه‌ی گوشی‌های فعال کاربر)."""
    cfg = await get_mobile_settings(db)
    has_sites = bool(await configured_sites(db))
    result = await db.execute(
        select(MobileDevice)
        .where(MobileDevice.user_id == user.id, MobileDevice.revoked_at.is_(None))
        .order_by(MobileDevice.created_at.desc())
    )
    devices = []
    healthy_any = False
    for d in result.scalars().all():
        issues = device_issues(d, cfg, has_sites)
        ok = is_healthy(issues)
        healthy_any = healthy_any or ok
        devices.append(
            {
                "id": d.id,
                "model": " ".join(x for x in (d.manufacturer, d.model) if x) or "گوشی اندروید",
                "app_version_name": d.app_version_name,
                "healthy": ok,
                "issues": [{"code": i, "label": ISSUE_LABELS[i], "blocking": i in BLOCKING_ISSUES} for i in issues],
                "status_reported_at": d.status_reported_at,
            }
        )
    return healthy_any, devices


async def location_app_required(db: AsyncSession, user: User, user_agent: str | None = None) -> bool:
    """
    آیا پیش‌نیاز «اپ اندروید با دسترسی موقعیت» برای این درخواست اعمال می‌شود؟
    فقط برای پرسنل (نه superuser)، فقط روی گوشی اندروید (User-Agent؛ آیفون و کامپیوتر معاف‌اند) و نه معاف‌شده‌ها.
    """
    if user.is_superuser or user.employee_id is None:
        return False
    if not await is_feature_enabled(db):
        return False
    ua = user_agent if user_agent is not None else current_user_agent.get()
    if not is_android_user_agent(ua):
        return False
    return not await is_exempt(db, user.employee_id)


async def location_app_blocked(db: AsyncSession, user: User, user_agent: str | None = None) -> bool:
    if not await location_app_required(db, user, user_agent):
        return False
    healthy, _ = await user_devices_health(db, user)
    return not healthy


async def my_status(db: AsyncSession, user: User) -> dict:
    required = await location_app_required(db, user)
    healthy, devices = await user_devices_health(db, user)
    latest = await latest_release_info(db)
    # قفل داخل اپ: آخرین گوشی متصل کاربر گزارش داده که دسترسی موقعیت/اعلان گرفته شده یا GPS خاموش است
    # (بدون گوشی متصل ← قفلی نیست؛ اپ تازه‌نصب هنوز در حال اتصال است و خودش هنگام ورود دسترسی‌ها را چک کرده)
    # گوشی تازه‌متصلی که هنوز اولین گزارش وضعیتش نرسیده (همه‌ی دسترسی‌ها پیش‌فرض false است) یا گزارش‌هایش قطع شده
    # (stale) قفل نمی‌شود؛ خود اپ هنگام ورود دسترسی‌ها را چک کرده است
    permission_issues = []
    if required and devices and devices[0]["status_reported_at"] is not None:
        latest_issues = devices[0]["issues"]
        if not any(i["code"] == "stale" for i in latest_issues):
            permission_issues = [i for i in latest_issues if i["code"] in PERMISSION_ISSUES]
    return {
        "required": required,
        "exempt": user.employee_id is not None and await is_exempt(db, user.employee_id),
        "healthy": healthy,
        "devices": devices,
        "latest_release": latest,
        "permission_issues": permission_issues,
    }


# ---------------------------------------------------------------- نسخه‌های APK


async def latest_release_info(db: AsyncSession) -> dict | None:
    row = (
        await db.execute(
            select(
                MobileAppRelease.id,
                MobileAppRelease.version_code,
                MobileAppRelease.version_name,
                MobileAppRelease.notes,
                MobileAppRelease.file_size,
                MobileAppRelease.sha256,
                MobileAppRelease.uploaded_at,
            )
            .order_by(MobileAppRelease.version_code.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return {
        "id": row.id,
        "version_code": row.version_code,
        "version_name": row.version_name,
        "notes": row.notes,
        "file_size": row.file_size,
        "sha256": row.sha256,
        "uploaded_at": row.uploaded_at,
        "download_path": "/api/v1/mobile/app/download",
    }


async def count_devices_by_health(db: AsyncSession, site_ids: set[int] | None) -> dict:
    """شمارش گوشی‌های فعال سالم/ناسالم (برای کارت‌های خلاصه‌ی پنل)."""
    cfg = await get_mobile_settings(db)
    has_sites = bool(await configured_sites(db))
    stmt = select(MobileDevice).where(MobileDevice.revoked_at.is_(None))
    if site_ids is not None:
        stmt = stmt.join(Employee, Employee.id == MobileDevice.employee_id).where(Employee.site_id.in_(site_ids))
    healthy = unhealthy = 0
    for d in (await db.execute(stmt)).scalars().all():
        if is_healthy(device_issues(d, cfg, has_sites)):
            healthy += 1
        else:
            unhealthy += 1
    total_emp_stmt = select(func.count(Employee.id)).where(Employee.is_active.is_(True), Employee.is_enabled.is_(True))
    if site_ids is not None:
        total_emp_stmt = total_emp_stmt.where(Employee.site_id.in_(site_ids))
    return {"healthy": healthy, "unhealthy": unhealthy, "active_employees": int((await db.execute(total_emp_stmt)).scalar_one())}
