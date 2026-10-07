"""
Endpointهای اپ اندروید (docs/android-app.md).

بخش بومی اپ (احراز هویت با هدر X-Device-Token، نه JWT کاربر):
- POST /devices/register        مصرف کد اتصال و گرفتن توکن دستگاه (عمومی؛ کد اتصال خودش اعتبار است)
- POST /device/status           گزارش وضعیت دسترسی‌ها و Geofenceها
- GET  /device/geofences        محدوده‌ها و پارامترهای Geofencing
- POST /device/events           رویدادهای ورود/خروج (ثبت خودکار در گزارش پرتال)
- POST /device/connectivity     «آنلاین در محیط کار»: گوشی داخل محدوده آنلاین است (اپ بسته)

پرتال (کاربر واردشده):
- POST /pairing-code            کد یک‌بارمصرف اتصال گوشی
- GET  /me                      وضعیت اپ برای کاربر جاری (لازم است؟ سالم است؟ مشکلات)

عمومی: GET /app/latest و GET /app/download (آخرین APK).

پنل: mobile.devices (سایت‌محور) → /summary، /devices، /devices/{id}/revoke، /exemptions، /geofence-events
     system.mobile_app (کل سیستم) → /settings، /app/releases
"""
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.deps import get_current_user, require_permission
from app.core.ip_allowlist import get_client_ip
from app.core.site_access import get_sites_with_permission
from app.core.text_normalize import normalize_search_text
from app.db.session import get_db
from app.models.employee import Employee
from app.models.mobile_device import GeofenceEvent, MobileAppExemption, MobileAppRelease, MobileDevice
from app.models.site import Site
from app.models.user import User
from app.schemas.mobile import (
    DeviceLinkIn,
    DeviceOut,
    DeviceRegisterIn,
    DeviceStatusIn,
    AppErrorsIn,
    ConnectivityEventsIn,
    ExemptionIn,
    GeofenceEventsIn,
    MobileAppSettings,
)
from app.services import mobile_app_service as svc

async def require_feature(db: AsyncSession = Depends(get_db)) -> None:
    """قابلیت اپ اندروید خاموش است ← 404 (انگار این Endpointها وجود ندارند)."""
    if not await svc.is_feature_enabled(db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


# همه‌ی مسیرهای این روتر پشت کلید اصلی قابلیت‌اند؛ خود کلید: GET/PUT /system/mobile-app-feature
router = APIRouter(dependencies=[Depends(require_feature)])
MAX_APK_BYTES = 24 * 1024 * 1024  # سقف Nginx برای بدنه ۲۵ مگابایت است


# ---------------------------------------------------------------- بخش بومی اپ


async def current_device(
    x_device_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db)
) -> MobileDevice:
    """دستگاه از روی هدر X-Device-Token؛ نامعتبر/باطل → 401 (اپ دوباره اتصال را درخواست می‌کند)."""
    try:
        return await svc.get_device_by_token(db, x_device_token)
    except svc.DeviceAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/devices/register")
async def register_device(payload: DeviceRegisterIn, request: Request, db: AsyncSession = Depends(get_db)):
    """
    کد اتصال (دستی از پرتال یا خودکار ساخته‌ی اپ) → توکن دستگاه. خروجی: {device_id, device_token}.
    هنوز وصل نشده → 400 (اپ دوباره می‌پرسد)؛ مصرف‌شده/منقضی → 410 (اپ دیگر نمی‌پرسد).
    """
    try:
        device, token = await svc.register_device(db, payload, get_client_ip(request))
    except svc.DeviceLinkExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
    except svc.DeviceAuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"device_id": device.id, "device_token": token}


@router.post("/device/status")
async def device_status(
    payload: DeviceStatusIn,
    request: Request,
    device: MobileDevice = Depends(current_device),
    db: AsyncSession = Depends(get_db),
):
    """وضعیت دسترسی‌ها و Geofenceها؛ خروجی: {healthy, issues, latest_version_code, ...}."""
    return await svc.update_device_status(db, device, payload, get_client_ip(request))


@router.get("/device/geofences")
async def device_geofences(device: MobileDevice = Depends(current_device), db: AsyncSession = Depends(get_db)):
    """محدوده‌های سایت‌ها و پارامترهای Geofencing (با version برای تشخیص تغییر)."""
    return await svc.geofence_config(db)


@router.post("/device/events")
async def device_events(
    payload: GeofenceEventsIn, device: MobileDevice = Depends(current_device), db: AsyncSession = Depends(get_db)
):
    """
    رویدادهای ورود/خروج؛ خروجی: {results: [{id, status, message}]} — اپ پیام را به‌صورت اعلان نشان می‌دهد.
    زمان هر رویداد از «کرنومتر» گوشی (elapsed_ms / now_elapsed_ms) و ساعت سرور حساب می‌شود، نه ساعت گوشی.
    """
    return {"results": await svc.process_geofence_events(db, device, payload)}


@router.post("/device/errors")
async def device_errors(
    payload: AppErrorsIn,
    request: Request,
    device: MobileDevice = Depends(current_device),
    db: AsyncSession = Depends(get_db),
):
    """
    خطاهای بخش بومی اپ (کرش، خطای ثبت محدوده‌ها، کارهای پس‌زمینه) برای «گزارش خطاها». مثل بقیه‌ی این روتر فقط وقتی
    قابلیت اپ اندروید روشن است (وگرنه 404 و اپ چیزی نمی‌فرستد). خروجی: {received}.
    """
    from app.services import error_log_service

    user = await db.get(User, device.user_id)
    user_ref = (user.id, user.username) if user else None
    label = " ".join(x for x in (device.manufacturer, device.model) if x) or f"گوشی {device.id}"
    ip = get_client_ip(request)
    for err in payload.errors:
        error_log_service.record_android_error(err.model_dump(), user_ref, label, ip)
    return {"received": len(payload.errors)}


@router.post("/device/connectivity")
async def device_connectivity(
    payload: ConnectivityEventsIn, device: MobileDevice = Depends(current_device), db: AsyncSession = Depends(get_db)
):
    """
    «آنلاین در محیط کار» با اپ بسته: گوشی داخل محدوده‌ی سایت آنلاین شد (online) یا هنوز آنلاین است (alive).
    خروجی: {applied}. همه‌ی گزارش‌ها از صف اپ پاک می‌شوند (ارسال دوباره بی‌اثر است).
    """
    return {"applied": await svc.process_connectivity_events(db, device, payload)}


# ---------------------------------------------------------------- پرتال: کاربر جاری


@router.post("/pairing-code")
async def pairing_code(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """کد یک‌بارمصرف ۱۰ دقیقه‌ای برای اتصال همین گوشی به حساب. فقط کاربر متصل به پرسنل."""
    if current_user.employee_id is None:
        raise HTTPException(status_code=400, detail="حساب شما به پرسنل متصل نیست.")
    return await svc.create_pairing_code(db, current_user)


@router.post("/link")
async def link_device(
    payload: DeviceLinkIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    اتصال خودکار گوشی: کدی که اپ هنگام باز کردن پرتال فرستاده به حساب کاربر واردشده وصل می‌شود؛ بخش بومی اپ
    خودش با همان کد توکن دستگاه می‌گیرد. خروجی: {linked}. فقط کاربر متصل به پرسنل.
    """
    if current_user.employee_id is None:
        raise HTTPException(status_code=400, detail="حساب شما به پرسنل متصل نیست.")
    return {"linked": await svc.claim_device_link(db, current_user, payload.link)}


@router.get("/me")
async def my_mobile_status(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    وضعیت اپ برای کاربر جاری: {required, exempt, healthy, devices, latest_release, permission_issues}.
    required: پرسنل غیرمعاف روی گوشی اندروید ← پرتال در مرورگر قفل است و فقط از اپ باز می‌شود (فرانت).
    permission_issues: مشکلات دسترسی آخرین گوشی متصل ← پرتالِ داخل اپ قفل می‌شود تا کاربر دسترسی‌ها را کامل کند.
    """
    return await svc.my_status(db, current_user)


# ---------------------------------------------------------------- عمومی: APK


@router.get("/app/latest")
async def app_latest(db: AsyncSession = Depends(get_db)):
    """آخرین نسخه‌ی APK (بدون فایل)؛ null اگر هنوز بارگذاری نشده."""
    return await svc.latest_release_info(db)


@router.get("/app/download")
async def app_download(db: AsyncSession = Depends(get_db)):
    """دانلود آخرین APK."""
    # data ستون deferred است؛ برای دانلود باید صریحاً undefer شود
    release = (
        await db.execute(
            select(MobileAppRelease)
            .options(undefer(MobileAppRelease.data))
            .order_by(MobileAppRelease.version_code.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if release is None:
        raise HTTPException(status_code=404, detail="هنوز نسخه‌ای از اپ بارگذاری نشده است.")
    filename = f"faipco-{release.version_name}.apk"
    return Response(
        content=release.data,
        media_type="application/vnd.android.package-archive",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-cache",
        },
    )


# ---------------------------------------------------------------- پنل: دستگاه‌ها (سایت‌محور)


async def _sites(db: AsyncSession, user: User, site_id: int | None) -> set[int] | None:
    sites = await get_sites_with_permission(db, user, "mobile.devices")
    if site_id is not None:
        if sites is not None and site_id not in sites:
            raise HTTPException(status_code=403, detail="به این سایت دسترسی ندارید.")
        return {site_id}
    return sites


@router.get("/summary")
async def mobile_summary(
    site_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("mobile.devices")),
):
    """شمارش گوشی‌های سالم/ناسالم و پرسنل فعال، به‌علاوه‌ی آخرین نسخه."""
    sites = await _sites(db, user, site_id)
    data = await svc.count_devices_by_health(db, sites)
    data["latest_release"] = await svc.latest_release_info(db)
    return data


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(
    site_id: int | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    health: str | None = Query(default=None, pattern="^(healthy|unhealthy)$"),
    include_revoked: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("mobile.devices")),
):
    """گوشی‌های متصل با وضعیت و مشکلات (حداکثر ۱۰۰۰ ردیف، جدیدترین اول)."""
    sites = await _sites(db, user, site_id)
    cfg = await svc.get_mobile_settings(db)
    has_sites = bool(await svc.configured_sites(db))
    stmt = (
        select(MobileDevice, Employee, Site.name)
        .outerjoin(Employee, Employee.id == MobileDevice.employee_id)
        .outerjoin(Site, Site.id == Employee.site_id)
        .order_by(MobileDevice.created_at.desc())
        .limit(1000)
    )
    if not include_revoked:
        stmt = stmt.where(MobileDevice.revoked_at.is_(None))
    if sites is not None:
        stmt = stmt.where(Employee.site_id.in_(sites))
    term = normalize_search_text(search)
    if term:
        pattern = f"%{term}%"
        stmt = stmt.where(
            or_(
                Employee.first_name.ilike(pattern),
                Employee.last_name.ilike(pattern),
                Employee.personnel_code.ilike(pattern),
                MobileDevice.model.ilike(pattern),
            )
        )
    out: list[DeviceOut] = []
    for device, emp, site_name in (await db.execute(stmt)).all():
        issues = svc.device_issues(device, cfg, has_sites)
        ok = svc.is_healthy(issues)
        if health == "healthy" and not ok or health == "unhealthy" and ok:
            continue
        out.append(
            DeviceOut(
                id=device.id,
                user_id=device.user_id,
                employee_id=device.employee_id,
                employee_name=f"{emp.first_name} {emp.last_name}" if emp else None,
                personnel_code=emp.personnel_code if emp else None,
                site_name=site_name,
                manufacturer=device.manufacturer,
                model=device.model,
                os_version=device.os_version,
                app_version_name=device.app_version_name,
                app_version_code=device.app_version_code,
                has_gms=device.has_gms,
                geofence_engine=device.geofence_engine,
                perm_fine_location=device.perm_fine_location,
                perm_background_location=device.perm_background_location,
                perm_notifications=device.perm_notifications,
                battery_unrestricted=device.battery_unrestricted,
                location_enabled=device.location_enabled,
                geofences_registered=device.geofences_registered,
                geofence_count=device.geofence_count,
                created_at=device.created_at,
                status_reported_at=device.status_reported_at,
                last_event_at=device.last_event_at,
                revoked_at=device.revoked_at,
                healthy=ok,
                issues=issues,
            )
        )
    return out


@router.get("/issue-labels")
async def issue_labels(_user: User = Depends(get_current_user)):
    """برچسب فارسی کد مشکلات گوشی و وضعیت رویدادها (برای نمایش در پنل)."""
    return {"issues": svc.ISSUE_LABELS, "blocking": sorted(svc.BLOCKING_ISSUES), "event_status": svc.STATUS_LABELS}


@router.post("/devices/{device_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("mobile.devices")),
):
    """ابطال گوشی: توکنش از کار می‌افتد و کاربر باید دوباره از داخل اپ «فعال‌سازی» کند."""
    device = await db.get(MobileDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="دستگاه پیدا نشد.")
    sites = await get_sites_with_permission(db, user, "mobile.devices")
    if sites is not None:
        emp = await db.get(Employee, device.employee_id) if device.employee_id else None
        if emp is None or emp.site_id not in sites:
            raise HTTPException(status_code=403, detail="به این دستگاه دسترسی ندارید.")
    if device.revoked_at is None:
        device.revoked_at = datetime.now(timezone.utc)
        device.revoked_reason = f"ابطال توسط {user.username}"[:120]
        await db.commit()


@router.get("/exemptions")
async def list_exemptions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("mobile.devices")),
):
    """پرسنل معاف از پیش‌نیاز اپ اندروید (سایت‌های مجاز کاربر)."""
    sites = await get_sites_with_permission(db, user, "mobile.devices")
    stmt = (
        select(MobileAppExemption, Employee, Site.name)
        .join(Employee, Employee.id == MobileAppExemption.employee_id)
        .outerjoin(Site, Site.id == Employee.site_id)
        .order_by(MobileAppExemption.created_at.desc())
    )
    if sites is not None:
        stmt = stmt.where(Employee.site_id.in_(sites))
    return [
        {
            "id": ex.id,
            "employee_id": emp.id,
            "employee_name": f"{emp.first_name} {emp.last_name}",
            "personnel_code": emp.personnel_code,
            "site_name": site_name,
            "reason": ex.reason,
            "created_at": ex.created_at,
        }
        for ex, emp, site_name in (await db.execute(stmt)).all()
    ]


@router.post("/exemptions", status_code=status.HTTP_201_CREATED)
async def add_exemption(
    payload: ExemptionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("mobile.devices")),
):
    """معاف کردن یک پرسنل (مثلاً گوشی ساده یا شرایط خاص)؛ تکراری → همان ردیف به‌روز می‌شود."""
    emp = await db.get(Employee, payload.employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="پرسنل پیدا نشد.")
    sites = await get_sites_with_permission(db, user, "mobile.devices")
    if sites is not None and emp.site_id not in sites:
        raise HTTPException(status_code=403, detail="به این پرسنل دسترسی ندارید.")
    row = (
        await db.execute(select(MobileAppExemption).where(MobileAppExemption.employee_id == emp.id))
    ).scalar_one_or_none()
    if row is None:
        db.add(
            MobileAppExemption(
                employee_id=emp.id, reason=payload.reason, created_by_user_id=user.id, created_at=datetime.now(timezone.utc)
            )
        )
    else:
        row.reason = payload.reason
    await db.commit()
    return {"ok": True}


@router.delete("/exemptions/{exemption_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exemption(
    exemption_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("mobile.devices")),
):
    row = await db.get(MobileAppExemption, exemption_id)
    if row is None:
        return
    sites = await get_sites_with_permission(db, user, "mobile.devices")
    if sites is not None:
        emp = await db.get(Employee, row.employee_id)
        if emp is None or emp.site_id not in sites:
            raise HTTPException(status_code=403, detail="به این پرسنل دسترسی ندارید.")
    await db.delete(row)
    await db.commit()


@router.get("/geofence-events")
async def list_geofence_events(
    site_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
    search: str | None = Query(default=None, max_length=100),
    hours: int = Query(default=24 * 7, ge=1, le=24 * 400),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("mobile.devices")),
):
    """رویدادهای ورود/خروج خودکار با نتیجه‌ی پردازش (جدیدترین اول). خروجی: {items, total}."""
    sites = await _sites(db, user, site_id)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    conds = [GeofenceEvent.occurred_at >= since]
    if status_filter:
        conds.append(GeofenceEvent.status == status_filter)
    if sites is not None:
        conds.append(Employee.site_id.in_(sites))
    term = normalize_search_text(search)
    if term:
        pattern = f"%{term}%"
        conds.append(
            or_(Employee.first_name.ilike(pattern), Employee.last_name.ilike(pattern), Employee.personnel_code.ilike(pattern))
        )
    base = select(GeofenceEvent, Employee, Site.name).outerjoin(Employee, Employee.id == GeofenceEvent.employee_id).outerjoin(
        Site, Site.id == GeofenceEvent.site_id
    )
    total = (
        await db.execute(
            select(func.count(GeofenceEvent.id)).select_from(GeofenceEvent).outerjoin(
                Employee, Employee.id == GeofenceEvent.employee_id
            ).where(*conds)
        )
    ).scalar_one()
    rows = (
        await db.execute(base.where(*conds).order_by(GeofenceEvent.occurred_at.desc()).limit(limit).offset(offset))
    ).all()
    return {
        "total": int(total or 0),
        "items": [
            {
                "id": ev.id,
                "employee_name": f"{emp.first_name} {emp.last_name}" if emp else None,
                "personnel_code": emp.personnel_code if emp else None,
                "site_name": site_name,
                "transition": ev.transition,
                "engine": ev.engine,
                "occurred_at": ev.occurred_at,
                "received_at": ev.received_at,
                "accuracy_meters": ev.accuracy_meters,
                "distance_meters": ev.distance_meters,
                "is_mock": ev.is_mock,
                "time_uncertain": ev.time_uncertain,
                "status": ev.status,
            }
            for ev, emp, site_name in rows
        ],
    }


# ---------------------------------------------------------------- پنل: تنظیمات و APK (کل سیستم)


@router.get("/settings", response_model=MobileAppSettings)
async def get_settings_endpoint(
    db: AsyncSession = Depends(get_db), _user: User = Depends(require_permission("system.mobile_app"))
):
    return await svc.get_mobile_settings(db)


@router.put("/settings", response_model=MobileAppSettings)
async def put_settings_endpoint(
    payload: MobileAppSettings,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("system.mobile_app")),
):
    """ذخیره؛ اپ‌ها تغییر پارامترهای Geofencing را در گزارش وضعیت بعدی (یا باز شدن اپ) می‌گیرند."""
    return await svc.save_mobile_settings(db, payload)


@router.get("/app/releases")
async def list_releases(db: AsyncSession = Depends(get_db), _user: User = Depends(require_permission("system.mobile_app"))):
    rows = await db.execute(
        select(
            MobileAppRelease.id,
            MobileAppRelease.version_code,
            MobileAppRelease.version_name,
            MobileAppRelease.notes,
            MobileAppRelease.file_size,
            MobileAppRelease.sha256,
            MobileAppRelease.uploaded_at,
        ).order_by(MobileAppRelease.version_code.desc())
    )
    return [dict(r._mapping) for r in rows.all()]


@router.post("/app/releases", status_code=status.HTTP_201_CREATED)
async def upload_release(
    file: UploadFile = File(...),
    version_code: int = Form(..., ge=1),
    version_name: str = Form(..., min_length=1, max_length=30),
    notes: str | None = Form(default=None, max_length=2000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("system.mobile_app")),
):
    """بارگذاری APK (فایل ZIP با AndroidManifest.xml). version_code باید از نسخه‌های قبلی بیشتر باشد."""
    data = await file.read(MAX_APK_BYTES + 1)
    if len(data) > MAX_APK_BYTES:
        raise HTTPException(status_code=413, detail="حجم فایل بیش از ۲۴ مگابایت است.")
    if not data.startswith(b"PK\x03\x04") or b"AndroidManifest.xml" not in data:
        raise HTTPException(status_code=400, detail="فایل APK معتبر نیست.")
    latest = (await db.execute(select(func.max(MobileAppRelease.version_code)))).scalar_one()
    if latest is not None and version_code <= latest:
        raise HTTPException(status_code=400, detail=f"شماره‌ی نسخه (versionCode) باید بیشتر از {latest} باشد.")
    db.add(
        MobileAppRelease(
            version_code=version_code,
            version_name=version_name.strip(),
            notes=(notes or "").strip() or None,
            file_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            data=data,
            uploaded_at=datetime.now(timezone.utc),
            uploaded_by_user_id=user.id,
        )
    )
    await db.commit()
    return await svc.latest_release_info(db)


@router.delete("/app/releases/{release_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_release(
    release_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require_permission("system.mobile_app"))
):
    row = await db.get(MobileAppRelease, release_id)
    if row is not None:
        await db.delete(row)
        await db.commit()

