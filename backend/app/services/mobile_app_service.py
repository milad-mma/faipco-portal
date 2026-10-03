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
from app.schemas.mobile import DeviceRegisterIn, DeviceStatusIn, GeofenceEventIn, MobileAppSettings

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
BLOCKING_ISSUES = {"revoked", "no_fine_location", "no_background_location", "location_off", "no_geofences", "stale", "outdated"}
STATUS_LABELS = {
    "logged": "ثبت شد",
    "duplicate": "تکراری",
    "already_in": "ورود قبلی باز است",
    "already_out": "خروج قبلاً ثبت شده",
    "mock": "GPS جعلی",
    "disabled": "ثبت خودکار خاموش است",
    "unknown_site": "سایت نامعتبر",
    "no_employee": "بدون پرسنل",
}


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
    کد قبلاً مصرف‌شده دوباره وصل نمی‌شود (False). کد وصل‌شده ولی هنوز مصرف‌نشده به کاربر فعلی منتقل می‌شود.
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
    else:
        row.user_id = user.id
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


async def process_geofence_events(db: AsyncSession, device: MobileDevice, events: list[GeofenceEventIn]) -> list[dict]:
    """رویدادها را به ترتیب زمان پردازش می‌کند؛ خروجی برای هر رویداد: id، status، پیام کوتاه برای اعلان اپ."""
    received = _now()
    cfg = await get_mobile_settings(db)
    sites = {s.id: s for s in await configured_sites(db)}
    out: list[dict] = []

    for ev in sorted(events, key=lambda e: e.occurred_at):
        existing = (
            await db.execute(
                select(GeofenceEvent).where(GeofenceEvent.device_id == device.id, GeofenceEvent.client_event_id == ev.id)
            )
        ).scalar_one_or_none()
        if existing is not None:  # ارسال دوباره‌ی همان رویداد (مثلاً قطع شبکه بعد از ثبت)
            out.append({"id": ev.id, "status": existing.status, "message": None})
            continue

        occurred = _event_time(ev.occurred_at, received)
        site = sites.get(ev.site_id)
        log_type = GpsLogType.check_out if ev.transition == "exit" else GpsLogType.check_in
        distance = None
        if site is not None and ev.latitude is not None and ev.longitude is not None:
            distance = haversine_distance_meters(ev.latitude, ev.longitude, site.gps_latitude, site.gps_longitude)

        status = "logged"
        if device.employee_id is None:
            status = "no_employee"
        elif site is None:
            status = "unknown_site"
        elif ev.is_mock:
            status = "mock"
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
                status=status,
                gps_log_id=gps_log.id if gps_log else None,
            )
        )
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
    return {
        "required": required,
        "exempt": user.employee_id is not None and await is_exempt(db, user.employee_id),
        "healthy": healthy,
        "devices": devices,
        "latest_release": latest,
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
