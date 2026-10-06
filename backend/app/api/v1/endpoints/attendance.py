"""
Endpoint های «حضور مبتنی بر موقعیت مکانی» (GPS).

ثبت دستی ورود/خروج توسط خود پرسنل (clock-in / clock-out / my-logs) در Migration 104 حذف شد؛ ورود/خروج فقط
خودکار با اپ اندروید (Geofencing) ثبت می‌شود. همه‌ی گزارش‌ها با یک مجوز: attendance.manage_clock_records (سایت‌محور).

/attendance/logs         (GET)   گزارش کامل ورود/خروج همه‌ی پرسنل، صفحه‌بندی‌شده
/attendance/logs         (POST)  افزودن دستی یک رکورد ورود/خروج (مدیر)
/attendance/logs/{id}    (PUT)   ویرایش دستی یک رکورد — همان مجوز
/attendance/logs/{id}    (DELETE) حذف یک رکورد — همان مجوز
/attendance/presence-ws  (WS)    نشانگر زنده‌ی «آنلاین/آفلاین»: با Heartbeat های داخل
                                  محدوده یک PresenceSession باز می‌شود و با خروج از
                                  محدوده/قطع اتصال/سکوت با duration دقیق بسته می‌شود
/attendance/presence-sessions (GET) گزارش «پرسنل آنلاین» و «آنلاین در محیط کار» (پرتال باز + اپ در پس‌زمینه)

ثبت ورود/خروج رسمی از طریق دستگاه‌های حضور و غیاب کارخانه انجام می‌شود؛
این لاگ یک منبع مکمل دیجیتال است.
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission
from app.core.persian_date import get_current_jalali_year_month
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal, get_db
from app.models.employee import Employee
from app.models.gps_activity_log import GpsActivityLog, GpsLogType
from app.models.presence_session import PresenceSession
from app.models.site import Site
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.gps_attendance import (
    GpsActivityLogAdminOut,
    GpsActivityLogOut,
    GpsActivityLogPageOut,
    GpsLogUpdateIn,
    GpsManualLogIn,
    PresenceSessionAdminOut,
    PresenceSessionPageOut,
)
from app.services.gps_attendance_service import (
    GpsAttendanceService,
    check_geofence,
    is_presence_alive,
)

logger = logging.getLogger("faipco.attendance")
router = APIRouter()

# همه‌ی گزارش‌ها و ویرایش دستی رکوردها (Migration 104: view_logs و view_clock_records در این ادغام شدند)
CLOCK_PERMISSION = "attendance.manage_clock_records"

# اگر بیش از این مدت هیچ Heartbeat از کلاینت نرسد، Session «قطع‌شده» در نظر گرفته می‌شود
# حتی اگر اتصال TCP هنوز باز باشد (مثلاً قطعی بی‌صدای شبکه). کلاینت هر ۳۰-۶۰ ثانیه Heartbeat می‌فرستد.
_HEARTBEAT_TIMEOUT_SECONDS = 90

# Heartbeat با دقت موقعیت بدتر از این مقدار (مثلاً موقعیت‌یابی بر پایه‌ی IP/شبکه با خطای کیلومتری)
# قابل‌اعتماد نیست و برای تصمیم محدوده استفاده نمی‌شود. ۵۰۰ متر به‌اندازه‌ی کافی بزرگ‌تر از شعاع
# معمول محدوده (۱۰۰-۳۰۰ متر) است تا GPS متوسط داخل ساختمان رد نشود ولی داده‌ی خراب گرفته شود.
_MAX_TRUSTED_ACCURACY_METERS = 500


@router.get("/logs", response_model=GpsActivityLogPageOut)
async def list_all_logs(
    page: int = 1,
    page_size: int = 50,
    employee_id: int | None = None,
    log_type: GpsLogType | None = None,
    year: int | None = None,
    month: int | None = None,
    site_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    گزارش صفحه‌بندی‌شده‌ی همه‌ی لاگ‌های GPS (حضور دوره‌ای + ورود/خروج) برای Admin/hr-manager.
    همیشه به یک ماه شمسی محدود است (پیش‌فرض: ماه جاری)؛ فیلتر اختیاری روی پرسنل، نوع لاگ و سایت.
    مجوز attendance.manage_clock_records به‌صورت سایت‌محور بررسی می‌شود؛ 403 اگر برای هیچ سایتی نداشته باشد.

    ایزوله‌سازی چندسایتی: چون این Endpoint site_id ثابتی در Path ندارد که require_permission
    بتواند از آن بخواند، get_sites_with_permission دقیقاً سایت‌هایی را برمی‌گرداند که کاربر این
    مجوز را برایشان دارد (None = همه‌ی سایت‌ها). پارامتر site_id با این مجموعه تقاطع گرفته می‌شود
    تا hr-manager سایت‌محور نتواند با تغییر آن به سایت دیگری برسد.
    """
    # سایت‌های مجاز کاربر برای این مجوز (None یعنی بدون محدودیت)
    access_site_ids = await get_sites_with_permission(db, current_user, CLOCK_PERMISSION)
    if access_site_ids is not None and not access_site_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی لازم را ندارید")

    # فیلتر site_id فقط داخل سایت‌های مجاز اعمال می‌شود
    if site_id is not None:
        site_ids = {site_id} if access_site_ids is None else (access_site_ids & {site_id})
    else:
        site_ids = access_site_ids

    # پیش‌فرض: ماه شمسی جاری
    if year is None or month is None:
        year, month = get_current_jalali_year_month()
    logs, total = await GpsAttendanceService(db).get_all_logs_page(
        page=page, page_size=page_size, employee_id=employee_id, log_type=log_type, year=year, month=month,
        site_ids=site_ids,
    )
    if not logs:
        return GpsActivityLogPageOut(items=[], total=total, year=year, month=month)

    # پرسنل و سایت‌های این صفحه با دو کوئری خوانده می‌شوند تا نام‌ها به خروجی اضافه شوند
    employee_ids = {log.employee_id for log in logs}
    site_ids = {log.matched_site_id for log in logs if log.matched_site_id is not None}

    employees_result = await db.execute(select(Employee).where(Employee.id.in_(employee_ids)))
    employees_by_id = {e.id: e for e in employees_result.scalars().all()}

    sites_by_id = {}
    if site_ids:
        sites_result = await db.execute(select(Site).where(Site.id.in_(site_ids)))
        sites_by_id = {s.id: s for s in sites_result.scalars().all()}

    # ساخت آیتم‌های خروجی با هویت پرسنل و نام سایت
    items = []
    for log in logs:
        employee = employees_by_id.get(log.employee_id)
        employee_name = f"{employee.first_name} {employee.last_name}" if employee else "—"
        personnel_code = employee.personnel_code if employee else "—"
        matched_site = sites_by_id.get(log.matched_site_id) if log.matched_site_id else None

        items.append(
            GpsActivityLogAdminOut(
                id=log.id,
                log_type=log.log_type,
                latitude=log.latitude,
                longitude=log.longitude,
                accuracy_meters=log.accuracy_meters,
                matched_site_id=log.matched_site_id,
                distance_meters=log.distance_meters,
                is_within_geofence=log.is_within_geofence,
                is_manual=log.is_manual,
                source=log.source or "web",
                time_uncertain=bool(log.time_uncertain),
                created_at=log.created_at,
                employee_id=log.employee_id,
                employee_name=employee_name,
                personnel_code=personnel_code,
                matched_site_name=matched_site.name if matched_site else None,
            )
        )

    return GpsActivityLogPageOut(items=items, total=total, year=year, month=month)


async def _check_clock_manage_access(db: AsyncSession, current_user: User, site_id: int | None) -> None:
    """
    بررسی می‌کند کاربر مجوز attendance.manage_clock_records را برای سایت پرسنلِ هدف دارد؛ وگرنه 403.
    site_id واقعی پرسنل هدف بررسی می‌شود تا hr-manager سایت‌محور فقط رکوردهای سایت خودش را مدیریت کند.
    """
    if current_user.is_superuser:  # superuser همیشه مجاز است
        return
    codes = await UserRepository(db).get_permission_codes(current_user.id, site_id=site_id)
    if CLOCK_PERMISSION not in codes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی لازم برای این عملیات را ندارید (این پرسنل خارج از محدوده سایت شماست)",
        )


@router.post("/logs", response_model=GpsActivityLogOut, status_code=status.HTTP_201_CREATED)
async def create_manual_log(
    payload: GpsManualLogIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    افزودن دستی یک رکورد ورود/خروج برای یک پرسنل (مجوز attendance.manage_clock_records روی سایت پرسنل).
    بدون مختصات GPS ثبت می‌شود و در گزارش با is_manual مشخص است.
    خطاها: 404 پرسنل نامعتبر، 403 بدون مجوز روی سایت پرسنل، 400 نوع رکورد نامعتبر.
    """
    employee = await db.get(Employee, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    await _check_clock_manage_access(db, current_user, employee.site_id)
    # نوع رکورد باید یکی از مقادیر GpsLogType باشد
    try:
        log_type = GpsLogType(payload.log_type)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="نوع رکورد نامعتبر است")

    log = await GpsAttendanceService(db).create_manual_log(
        employee_id=payload.employee_id,
        log_type=log_type,
        created_at=payload.created_at,
        site_id=payload.site_id,
    )
    return GpsActivityLogOut.model_validate(log)


@router.put("/logs/{log_id}", response_model=GpsActivityLogOut)
async def update_log(
    log_id: int,
    payload: GpsLogUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ویرایش دستی فیلدهای داده‌شده‌ی یک لاگ (مجوز attendance.manage_clock_records روی سایت پرسنل رکورد).
    خطاها: 404 رکورد نامعتبر، 403 بدون مجوز، 400 نوع رکورد نامعتبر.
    """
    existing = await db.get(GpsActivityLog, log_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="رکورد یافت نشد")
    # مجوز بر اساس سایت پرسنلِ صاحب رکورد
    employee = await db.get(Employee, existing.employee_id)
    await _check_clock_manage_access(db, current_user, employee.site_id if employee else None)

    # نوع رکورد فقط اگر داده شده باشد اعتبارسنجی می‌شود
    log_type = None
    if payload.log_type is not None:
        try:
            log_type = GpsLogType(payload.log_type)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="نوع رکورد نامعتبر است")

    log = await GpsAttendanceService(db).update_log(
        log_id, log_type=log_type, created_at=payload.created_at, site_id=payload.site_id
    )
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="رکورد یافت نشد")
    return GpsActivityLogOut.model_validate(log)


@router.delete("/logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حذف یک لاگ (مجوز attendance.manage_clock_records روی سایت پرسنل رکورد). 404 اگر نباشد، 403 بدون مجوز."""
    existing = await db.get(GpsActivityLog, log_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="رکورد یافت نشد")
    # مجوز بر اساس سایت پرسنلِ صاحب رکورد
    employee = await db.get(Employee, existing.employee_id)
    await _check_clock_manage_access(db, current_user, employee.site_id if employee else None)

    deleted = await GpsAttendanceService(db).delete_log(log_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="رکورد یافت نشد")


async def _authenticate_websocket_user(token: str, in_app: bool = False) -> tuple[User, bool, bool] | None:
    """
    احراز هویت WebSocket از روی access token در Query Param (?token=...)، چون مرورگر اجازه‌ی
    هدر Authorization روی WebSocket را نمی‌دهد.
    خروجی: (کاربر، آیا پایش GPS برایش فعال است، داخل اپ) اگر توکن معتبر و کاربر به پرسنل متصل باشد؛ وگرنه None.
    «آنلاین بودن در اپ» برای همه‌ی پرسنل ثبت می‌شود؛ پایش محدوده‌ی GPS («آنلاین در محیط کار») فقط برای پرتالِ
    داخل اپ اندروید (in_app؛ پرتال در اپ ?app=android می‌فرستد) و وقتی قابلیت اپ روشن است.
    """
    # توکن باید از نوع access و دارای شناسه‌ی کاربر باشد
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None

    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_id(int(user_id))
        if user is None or user.employee_id is None or not user.is_active:
            return None
        # «داخل اپ» فقط وقتی قابلیت اپ اندروید روشن است اثر دارد
        if in_app:
            from app.services.mobile_app_service import is_feature_enabled

            in_app = await is_feature_enabled(db)
        return user, in_app, in_app


def _client_label(user_agent: str | None) -> str | None:
    """برچسب کوتاه دستگاه/مرورگر از User-Agent برای گزارش (مثل «اندروید · Chrome»)."""
    ua = (user_agent or "").lower()
    if not ua:
        return None
    if "android" in ua:
        device = "اندروید"
    elif "iphone" in ua or "ipad" in ua:
        device = "iOS"
    elif "windows" in ua:
        device = "ویندوز"
    elif "mac os" in ua or "macintosh" in ua:
        device = "مک"
    elif "linux" in ua:
        device = "لینوکس"
    else:
        device = "نامشخص"
    if "edg/" in ua:
        browser = "Edge"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "chrome" in ua or "crios" in ua:
        browser = "Chrome"
    elif "safari" in ua:
        browser = "Safari"
    else:
        browser = ""
    return f"{device} · {browser}" if browser else device


@router.websocket("/presence-ws")
async def presence_websocket(websocket: WebSocket, token: str = Query(...), app: str | None = Query(default=None)):
    """
    WebSocket نشانگر زنده‌ی «آنلاین/آفلاین» پرسنل (توکن در ?token=). دو نوع نشست ثبت می‌شود:

    - «اپ» (kind=app): برای هر پرسنلی که پرتال را باز کرده، از لحظه‌ی اتصال تا قطع؛ بدون نیاز به GPS.
    - «GPS» (kind=gps، «آنلاین در محیط کار» با منبع portal): فقط پرتالِ داخل اپ اندروید، بازه‌هایی که موقعیت داخل
      محدوده‌ی سایت است:
      اولین Heartbeat داخل محدوده نشست را باز می‌کند؛ Heartbeat خارج از محدوده، قطع یا سکوت آن را می‌بندد.

    ورودی: Heartbeat های JSON هر ۴۵ ثانیه (با latitude/longitude/accuracy_meters برای پایش GPS، یا خالی).
    هر Heartbeat زمان last_seen_at نشست‌های باز را تازه می‌کند؛ نشستی که به‌خاطر ری‌استارت سرور یا قطع ناگهانی
    بسته نشده، با Job دوره‌ای (close_stale_presence_sessions) با همان آخرین زمان دیده‌شده بسته می‌شود.
    توکن نامعتبر یا کاربر بدون پرسنل: بستن با کد 4401 (کلاینت دوباره تلاش نمی‌کند).
    """
    in_app = app == "android"
    auth = await _authenticate_websocket_user(token, in_app=in_app)
    if auth is None:
        await websocket.close(code=4401)  # کد سفارشی: احراز هویت ناموفق
        return
    user, gps_enabled, in_app = auth

    await websocket.accept()

    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        app_session = PresenceSession(
            employee_id=user.employee_id,
            kind="app",
            connected_at=now,
            last_seen_at=now,
            client=("اپ اندروید" if in_app else _client_label(websocket.headers.get("user-agent"))),
        )
        db.add(app_session)
        await db.commit()
        session: PresenceSession | None = None  # نشست GPS باز فعلی (None = خارج از محدوده یا هنوز تأیید نشده)

        async def close_session(target: PresenceSession | None) -> None:
            """نشست را با زمان قطع و مدت دقیق می‌بندد (اگر باز باشد)."""
            if target is None or target.disconnected_at is not None:
                return
            end = datetime.now(timezone.utc)
            target.disconnected_at = end
            target.duration_seconds = int((end - target.connected_at).total_seconds())

        async def close_gps_session() -> None:
            nonlocal session
            await close_session(session)
            session = None

        try:
            # حلقه‌ی دریافت Heartbeat تا قطع اتصال یا timeout
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=_HEARTBEAT_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:  # سکوت طولانی = قطع‌شده
                    logger.info("Presence WS for employee %s: heartbeat timeout, closing.", user.employee_id)
                    break
                if not isinstance(data, dict):
                    data = {}

                # هر Heartbeat یعنی اپ هنوز باز است
                seen = datetime.now(timezone.utc)
                app_session.last_seen_at = seen
                if session is not None:
                    session.last_seen_at = seen  # نشست GPS باز هم با هر Heartbeat زنده می‌ماند

                if not gps_enabled:
                    await db.commit()
                    await websocket.send_json({"status": "online"})
                    continue

                latitude = data.get("latitude")
                longitude = data.get("longitude")
                if latitude is None or longitude is None:
                    # بدون موقعیت نمی‌شود محدوده را تأیید کرد؛ یک پاسخ تشخیصی برمی‌گردد تا مشکل
                    # (مثلاً رد دسترسی GPS در مرورگر) قابل‌تشخیص باشد. نشست «اپ» همچنان ادامه دارد.
                    await db.commit()
                    await websocket.send_json({"status": "no_position", "message": "موقعیتی در این Heartbeat ارسال نشده بود."})
                    continue

                accuracy_meters = data.get("accuracy_meters")
                if accuracy_meters is not None and accuracy_meters > _MAX_TRUSTED_ACCURACY_METERS:
                    # موقعیت با خطای زیاد قابل‌اعتماد نیست: نشست GPS نه بسته می‌شود و نه چیزی با این داده ثبت می‌شود
                    await db.commit()
                    await websocket.send_json(
                        {
                            "status": "low_accuracy",
                            "accuracy_meters": accuracy_meters,
                            "message": f"دقت موقعیت (±{int(accuracy_meters)}m) خیلی پایین است — نادیده گرفته شد.",
                        }
                    )
                    continue

                # بررسی محدوده‌ی سایت با مختصات این Heartbeat
                geofence = await check_geofence(db, data.get("site_id"), latitude, longitude)

                if not geofence.is_within:
                    payload = {
                        "status": "outside_geofence",
                        "matched_site_name": geofence.matched_site.name if geofence.matched_site else None,
                        "distance_meters": geofence.distance_meters,
                        "allowed_radius_meters": geofence.matched_site.gps_radius_meters if geofence.matched_site else None,
                    }
                    # خارج از محدوده: نشست GPS (اگر باشد) بسته می‌شود. commit (نه rollback) تا اتصال به Pool
                    # برگردد و اشیاء نشست‌ها منقضی نشوند
                    await close_gps_session()
                    await db.commit()
                    await websocket.send_json(payload)
                    continue

                # داخل محدوده: اگر نشست GPS بازی نیست، همین لحظه یکی ساخته می‌شود
                if session is None:
                    session = PresenceSession(
                        employee_id=user.employee_id, kind="gps", connected_at=seen, last_seen_at=seen,
                        client=app_session.client,
                    )
                    db.add(session)

                # آخرین موقعیت و سایت منطبق روی نشست به‌روز می‌شود
                session.last_latitude = latitude
                session.last_longitude = longitude
                session.last_accuracy_meters = data.get("accuracy_meters")
                session.matched_site_id = geofence.matched_site.id if geofence.matched_site else None
                session.last_distance_meters = geofence.distance_meters
                session.is_within_geofence = True
                await db.commit()
                await websocket.send_json(
                    {
                        "status": "logged",
                        "matched_site_name": geofence.matched_site.name if geofence.matched_site else None,
                        "distance_meters": geofence.distance_meters,
                    }
                )
        except WebSocketDisconnect:
            pass  # قطع عادی از سمت کلاینت
        except Exception:
            logger.exception("Presence WS for employee %s ended with an unexpected error", user.employee_id)
        finally:
            # در هر حالت خروج، نشست‌های باز بسته می‌شوند
            try:
                await close_gps_session()
                await close_session(app_session)
                await db.commit()
            except Exception:  # noqa: BLE001 - اگر این هم نشد، Job نشست‌های رهاشده را می‌بندد
                logger.exception("بستن نشست حضور پرسنل %s ناموفق بود", user.employee_id)


@router.get("/presence-sessions", response_model=PresenceSessionPageOut)
async def list_presence_sessions(
    page: int = 1,
    page_size: int = 50,
    employee_id: int | None = None,
    only_online: bool = False,
    site_id: int | None = None,
    kind: str = Query(default="app", pattern="^(app|gps)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    گزارش صفحه‌بندی‌شده‌ی Session های آنلاین/آفلاین با مدت دقیق هرکدام، برای Admin/hr-manager.
    kind: "app" = باز بودن پرتال (همه‌ی پرسنل، بدون GPS)، "gps" = «آنلاین در محیط کار»: پرتال باز داخل محدوده
    (source=portal) یا آنلاین شدن گوشی داخل محدوده با اپ بسته (source=background).
    فیلتر اختیاری روی پرسنل، فقط آنلاین‌ها و سایت. مجوز attendance.manage_clock_records سایت‌محور بررسی می‌شود؛
    403 اگر برای هیچ سایتی نداشته باشد. ایزوله‌سازی چندسایتی همان الگوی list_all_logs است.
    """
    # سایت‌های مجاز کاربر برای این مجوز (None یعنی بدون محدودیت)
    access_site_ids = await get_sites_with_permission(db, current_user, CLOCK_PERMISSION)
    if access_site_ids is not None and not access_site_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی لازم را ندارید")

    # فیلتر site_id فقط داخل سایت‌های مجاز اعمال می‌شود
    if site_id is not None:
        accessible_site_ids = {site_id} if access_site_ids is None else (access_site_ids & {site_id})
    else:
        accessible_site_ids = access_site_ids

    sessions, total = await GpsAttendanceService(db).get_presence_sessions_page(
        page=page, page_size=page_size, employee_id=employee_id, only_online=only_online,
        site_ids=accessible_site_ids, kind=kind,
    )
    if not sessions:
        return PresenceSessionPageOut(items=[], total=total)

    # پرسنل و سایت‌های این صفحه برای افزودن نام‌ها به خروجی
    employee_ids = {s.employee_id for s in sessions}
    site_ids = {s.matched_site_id for s in sessions if s.matched_site_id is not None}

    employees_result = await db.execute(select(Employee).where(Employee.id.in_(employee_ids)))
    employees_by_id = {e.id: e for e in employees_result.scalars().all()}

    sites_by_id = {}
    if site_ids:
        sites_result = await db.execute(select(Site).where(Site.id.in_(site_ids)))
        sites_by_id = {s.id: s for s in sites_result.scalars().all()}

    # ساخت آیتم‌های خروجی؛ Session بدون زمان قطع یعنی هم‌اکنون آنلاین است
    items = []
    for s in sessions:
        employee = employees_by_id.get(s.employee_id)
        matched_site = sites_by_id.get(s.matched_site_id) if s.matched_site_id else None
        items.append(
            PresenceSessionAdminOut(
                id=s.id,
                employee_id=s.employee_id,
                employee_name=f"{employee.first_name} {employee.last_name}" if employee else "—",
                personnel_code=employee.personnel_code if employee else "—",
                connected_at=s.connected_at,
                disconnected_at=s.disconnected_at,
                duration_seconds=s.duration_seconds,
                is_online_now=is_presence_alive(s),
                kind=s.kind,
                last_seen_at=s.last_seen_at,
                client=s.client,
                matched_site_name=matched_site.name if matched_site else None,
                last_distance_meters=s.last_distance_meters,
                is_within_geofence=s.is_within_geofence,
                source=s.source or "portal",
                time_uncertain=bool(s.time_uncertain),
            )
        )

    return PresenceSessionPageOut(items=items, total=total)
