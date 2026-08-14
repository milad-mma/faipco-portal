"""
/attendance/presence     (POST)  حضور دوره‌ای — وقتی اپ باز است، هر چند دقیقه
                                  یک‌بار موقعیت چک و لاگ می‌شود. برای همه
                                  پرسنل سینک‌شده در دسترس است (بدون مجوز خاص).
/attendance/clock-in     (POST)  ثبت ورود آزمایشی — فقط با مجوز attendance.clock_in_out
/attendance/clock-out    (POST)  ثبت خروج آزمایشی — فقط با مجوز attendance.clock_in_out
/attendance/my-logs      (GET)   تاریخچه ورود/خروج خودِ کاربر جاری
/attendance/logs         (GET)   گزارش کامل Admin — همه لاگ‌ها (حضور دوره‌ای
                                  + ورود/خروج) برای همه پرسنل، Paginated —
                                  فقط با مجوز attendance.view_logs
/attendance/presence-ws  (WS)    نشانگر زنده «آنلاین/آفلاین» — دقیقاً مثل یک
                                  سیستم چت: وصل‌شدن Socket = شروع Session،
                                  قطع‌شدن (بستن تب/قطعی شبکه/هرچیز دیگر) =
                                  پایان Session با duration دقیق.
/attendance/presence-sessions (GET) گزارش Admin از همان Session ها.

⚠️ این قابلیت آزمایشی است. ثبت ورود/خروج رسمی باید از طریق دستگاه‌های
تعبیه‌شده در کارخانه انجام شود.
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal, get_db
from app.models.employee import Employee
from app.models.gps_activity_log import GpsLogType
from app.models.presence_session import PresenceSession
from app.models.site import Site
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.gps_attendance import (
    GpsActivityLogAdminOut,
    GpsActivityLogOut,
    GpsActivityLogPageOut,
    GpsCheckResultOut,
    GpsPositionIn,
    PresenceSessionAdminOut,
    PresenceSessionPageOut,
)
from app.services.gps_attendance_service import GpsAttendanceError, GpsAttendanceService, check_geofence

logger = logging.getLogger("faipco.attendance")
router = APIRouter()

# اگه بیش از این مدت هیچ پیامی (Heartbeat) از کلاینت نرسه، Session رو «قطع‌شده»
# در نظر می‌گیریم — حتی اگه خودِ اتصال TCP هنوز فنی باز مونده باشه (مثلاً
# شبکه بی‌صدا قطع شده). کلاینت باید هر ۳۰-۶۰ ثانیه یک‌بار Heartbeat بفرسته.
_HEARTBEAT_TIMEOUT_SECONDS = 90


def _require_employee(current_user: User) -> int:
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این قابلیت فقط برای کاربرانی است که به یک رکورد پرسنلی متصل‌اند.",
        )
    return current_user.employee_id


@router.post("/presence", response_model=GpsCheckResultOut)
async def log_presence(
    payload: GpsPositionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = _require_employee(current_user)
    log = await GpsAttendanceService(db).log_presence(
        employee_id=employee_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        site_id=payload.site_id,
    )
    matched_site_name = None
    if log.matched_site_id is not None:
        from app.models.site import Site

        site = await db.get(Site, log.matched_site_id)
        matched_site_name = site.name if site else None

    return GpsCheckResultOut(
        is_within_geofence=log.is_within_geofence,
        matched_site_name=matched_site_name,
        distance_meters=log.distance_meters,
    )


async def _clock(
    payload: GpsPositionIn,
    log_type: GpsLogType,
    db: AsyncSession,
    current_user: User,
) -> GpsActivityLogOut:
    employee_id = _require_employee(current_user)
    try:
        log = await GpsAttendanceService(db).clock_in_out(
            employee_id=employee_id,
            log_type=log_type,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters,
            site_id=payload.site_id,
        )
    except GpsAttendanceError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return GpsActivityLogOut.model_validate(log)


@router.post("/clock-in", response_model=GpsActivityLogOut)
async def clock_in(
    payload: GpsPositionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("attendance.clock_in_out")),
):
    return await _clock(payload, GpsLogType.check_in, db, current_user)


@router.post("/clock-out", response_model=GpsActivityLogOut)
async def clock_out(
    payload: GpsPositionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("attendance.clock_in_out")),
):
    return await _clock(payload, GpsLogType.check_out, db, current_user)


@router.get("/my-logs", response_model=list[GpsActivityLogOut])
async def my_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("attendance.clock_in_out")),
):
    employee_id = _require_employee(current_user)
    logs = await GpsAttendanceService(db).get_my_logs(employee_id)
    return [GpsActivityLogOut.model_validate(log) for log in logs]


@router.get("/logs", response_model=GpsActivityLogPageOut)
async def list_all_logs(
    page: int = 1,
    page_size: int = 50,
    employee_id: int | None = None,
    log_type: GpsLogType | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("attendance.view_logs")),
):
    """
    گزارش کامل Admin — همان چیزی که «حضور دوره‌ای» هر ۱۰ دقیقه برای پرسنل
    آزمایش ثبت می‌کند، به‌همراه ثبت‌های ورود/خروج، همه‌جا یک‌جا. چون حضور
    دوره‌ای می‌تواند حجم بالایی تولید کند، همیشه Paginated است.
    """
    logs, total = await GpsAttendanceService(db).get_all_logs_page(
        page=page, page_size=page_size, employee_id=employee_id, log_type=log_type
    )
    if not logs:
        return GpsActivityLogPageOut(items=[], total=total)

    employee_ids = {log.employee_id for log in logs}
    site_ids = {log.matched_site_id for log in logs if log.matched_site_id is not None}

    employees_result = await db.execute(select(Employee).where(Employee.id.in_(employee_ids)))
    employees_by_id = {e.id: e for e in employees_result.scalars().all()}

    sites_by_id = {}
    if site_ids:
        sites_result = await db.execute(select(Site).where(Site.id.in_(site_ids)))
        sites_by_id = {s.id: s for s in sites_result.scalars().all()}

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
                created_at=log.created_at,
                employee_id=log.employee_id,
                employee_name=employee_name,
                personnel_code=personnel_code,
                matched_site_name=matched_site.name if matched_site else None,
            )
        )

    return GpsActivityLogPageOut(items=items, total=total)


async def _authenticate_websocket_user(token: str) -> User | None:
    """
    احراز هویت دستی برای WebSocket — مرورگرها اجازه نمی‌دهند هدر Authorization
    سفارشی روی یک اتصال WebSocket تنظیم شود، پس Token از طریق Query Param
    فرستاده می‌شود (?token=...) نه هدر.
    """
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None

    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_id(int(user_id))
        if user is None or user.employee_id is None:
            return None
        has_permission = user.is_superuser or "attendance.clock_in_out" in (
            await UserRepository(db).get_permission_codes(user.id)
        )
        return user if has_permission else None


@router.websocket("/presence-ws")
async def presence_websocket(websocket: WebSocket, token: str = Query(...)):
    """
    نشانگر زنده «آنلاین/آفلاین» — دقیقاً مثل نشانگر آنلاین یک سیستم چت، با
    یک شرط اضافه: **هیچ Session ای تا وقتی موقعیت داخل محدوده مجاز یک سایت
    تأیید نشود، اصلاً ساخته نمی‌شود** — یعنی اگر پرسنل خارج از محدوده کارخانه
    باشد، هیچ لاگی ثبت نمی‌شود، نه حتی یک ردیف ناقص.

    - Socket وصل می‌شود، ولی هنوز هیچ Session ای در دیتابیس ساخته نمی‌شود
    - کلاینت هر ۳۰-۶۰ ثانیه یک Heartbeat (با موقعیت GPS فعلی) می‌فرستد
    - همان لحظه که یک Heartbeat نشان بدهد داخل محدوده است → یک PresenceSession
      تازه با connected_at=همان‌لحظه ساخته می‌شود
    - همان لحظه که یک Heartbeat نشان بدهد خارج از محدوده رفته (یا Socket قطع
      شود، یا سکوت بیش از ۹۰ ثانیه) → همان Session با disconnected_at و
      duration_seconds دقیق بسته می‌شود؛ اگر بعداً دوباره وارد محدوده شود،
      یک Session کاملاً جدید و جدا ساخته می‌شود (نه ادامه همان قبلی)
    - اگر برای هیچ سایتی موقعیت GPS تنظیم نشده باشد، هیچ محدودیتی اعمال
      نمی‌شود (مثل بقیه بخش‌های این قابلیت) — همه Heartbeat ها به‌عنوان
      «داخل محدوده» شمرده می‌شوند
    """
    user = await _authenticate_websocket_user(token)
    if user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    async with AsyncSessionLocal() as db:
        session: PresenceSession | None = None

        async def close_open_session() -> None:
            nonlocal session
            if session is None:
                return
            now = datetime.now(timezone.utc)
            session.disconnected_at = now
            session.duration_seconds = int((now - session.connected_at).total_seconds())
            await db.commit()
            session = None

        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=_HEARTBEAT_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    logger.info("Presence WS for employee %s: heartbeat timeout, closing.", user.employee_id)
                    break

                latitude = data.get("latitude")
                longitude = data.get("longitude")
                if latitude is None or longitude is None:
                    # بدون موقعیت نمی‌شود محدوده را تأیید کرد — این Heartbeat نادیده گرفته می‌شود؛
                    # ولی برای اینکه مشکل احتمالی (مثلاً رد کردن دسترسی GPS در مرورگر) قابل‌تشخیص
                    # باشد، همیشه یک پاسخ تشخیصی به کلاینت برمی‌گردد (کنسول DevTools قابل‌مشاهده است)
                    await websocket.send_json({"status": "no_position", "message": "موقعیتی در این Heartbeat ارسال نشده بود."})
                    continue

                geofence = await check_geofence(db, data.get("site_id"), latitude, longitude)

                if not geofence.is_within:
                    # خارج از محدوده — اگر Session بازی داشتیم می‌بندیمش؛ چیز جدیدی ثبت نمی‌شود
                    await close_open_session()
                    await websocket.send_json(
                        {
                            "status": "outside_geofence",
                            "matched_site_name": geofence.matched_site.name if geofence.matched_site else None,
                            "distance_meters": geofence.distance_meters,
                            "allowed_radius_meters": geofence.matched_site.gps_radius_meters if geofence.matched_site else None,
                        }
                    )
                    continue

                if session is None:
                    session = PresenceSession(
                        employee_id=user.employee_id, connected_at=datetime.now(timezone.utc)
                    )
                    db.add(session)

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
            pass
        except Exception:
            logger.exception("Presence WS for employee %s ended with an unexpected error", user.employee_id)
        finally:
            await close_open_session()


@router.get("/presence-sessions", response_model=PresenceSessionPageOut)
async def list_presence_sessions(
    page: int = 1,
    page_size: int = 50,
    employee_id: int | None = None,
    only_online: bool = False,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("attendance.view_logs")),
):
    """گزارش Admin از Session های آنلاین/آفلاین — با duration دقیق برای هرکدام."""
    sessions, total = await GpsAttendanceService(db).get_presence_sessions_page(
        page=page, page_size=page_size, employee_id=employee_id, only_online=only_online
    )
    if not sessions:
        return PresenceSessionPageOut(items=[], total=total)

    employee_ids = {s.employee_id for s in sessions}
    site_ids = {s.matched_site_id for s in sessions if s.matched_site_id is not None}

    employees_result = await db.execute(select(Employee).where(Employee.id.in_(employee_ids)))
    employees_by_id = {e.id: e for e in employees_result.scalars().all()}

    sites_by_id = {}
    if site_ids:
        sites_result = await db.execute(select(Site).where(Site.id.in_(site_ids)))
        sites_by_id = {s.id: s for s in sites_result.scalars().all()}

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
                is_online_now=s.disconnected_at is None,
                matched_site_name=matched_site.name if matched_site else None,
                last_distance_meters=s.last_distance_meters,
                is_within_geofence=s.is_within_geofence,
            )
        )

    return PresenceSessionPageOut(items=items, total=total)
