"""
Endpoint های «حضور مبتنی بر موقعیت مکانی» (GPS) و ثبت ورود/خروج با موبایل.

/attendance/clock-in     (POST)  ثبت ورود با مختصات فعلی — مجوز attendance.clock_in_out
/attendance/clock-out    (POST)  ثبت خروج با مختصات فعلی — مجوز attendance.clock_in_out
/attendance/my-logs      (GET)   تاریخچه‌ی ورود/خروج خودِ کاربر جاری در یک ماه شمسی
/attendance/logs         (GET)   گزارش کامل Admin/hr-manager — همه‌ی لاگ‌ها برای همه‌ی
                                  پرسنل، صفحه‌بندی‌شده — مجوز attendance.view_clock_records
/attendance/logs         (POST)  افزودن دستی یک رکورد ورود/خروج — مجوز attendance.manage_clock_records
/attendance/logs/{id}    (PUT)   ویرایش دستی یک رکورد — همان مجوز
/attendance/logs/{id}    (DELETE) حذف یک رکورد — همان مجوز
/attendance/presence-ws  (WS)    نشانگر زنده‌ی «آنلاین/آفلاین»: با Heartbeat های داخل
                                  محدوده یک PresenceSession باز می‌شود و با خروج از
                                  محدوده/قطع اتصال/سکوت با duration دقیق بسته می‌شود
/attendance/presence-sessions (GET) گزارش Admin از همان Session ها — مجوز attendance.view_logs

ثبت ورود/خروج رسمی از طریق دستگاه‌های حضور و غیاب کارخانه انجام می‌شود؛
این لاگ یک منبع مکمل دیجیتال است.
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
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
    GpsPositionIn,
    MyClockLogsOut,
    PresenceSessionAdminOut,
    PresenceSessionPageOut,
)
from app.services.gps_attendance_service import GpsAttendanceError, GpsAttendanceService, check_geofence

logger = logging.getLogger("faipco.attendance")
router = APIRouter()

# اگر بیش از این مدت هیچ Heartbeat از کلاینت نرسد، Session «قطع‌شده» در نظر گرفته می‌شود
# حتی اگر اتصال TCP هنوز باز باشد (مثلاً قطعی بی‌صدای شبکه). کلاینت هر ۳۰-۶۰ ثانیه Heartbeat می‌فرستد.
_HEARTBEAT_TIMEOUT_SECONDS = 90

# Heartbeat با دقت موقعیت بدتر از این مقدار (مثلاً موقعیت‌یابی بر پایه‌ی IP/شبکه با خطای کیلومتری)
# قابل‌اعتماد نیست و برای تصمیم محدوده استفاده نمی‌شود. ۵۰۰ متر به‌اندازه‌ی کافی بزرگ‌تر از شعاع
# معمول محدوده (۱۰۰-۳۰۰ متر) است تا GPS متوسط داخل ساختمان رد نشود ولی داده‌ی خراب گرفته شود.
_MAX_TRUSTED_ACCURACY_METERS = 500


def _require_employee(current_user: User) -> int:
    """employee_id کاربر جاری را برمی‌گرداند؛ اگر به پرسنلی متصل نباشد 400 می‌دهد."""
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این قابلیت فقط برای کاربرانی است که به یک رکورد پرسنلی متصل‌اند.",
        )
    return current_user.employee_id


async def _clock(
    payload: GpsPositionIn,
    log_type: GpsLogType,
    db: AsyncSession,
    current_user: User,
) -> GpsActivityLogOut:
    """
    منطق مشترک ثبت ورود/خروج: لاگ را از طریق سرویس ثبت می‌کند و خروجی API را برمی‌گرداند.
    خطای منطقی سرویس (خارج از محدوده، ثبت تکراری) به 403 با همان پیام تبدیل می‌شود.
    """
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
    """ثبت ورود با مختصات فعلی (مجوز attendance.clock_in_out). 400 بدون پرسنل، 403 خارج از محدوده یا تکراری."""
    return await _clock(payload, GpsLogType.check_in, db, current_user)


@router.post("/clock-out", response_model=GpsActivityLogOut)
async def clock_out(
    payload: GpsPositionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("attendance.clock_in_out")),
):
    """ثبت خروج با مختصات فعلی (مجوز attendance.clock_in_out). 400 بدون پرسنل، 403 خارج از محدوده یا تکراری."""
    return await _clock(payload, GpsLogType.check_out, db, current_user)


@router.get("/my-logs", response_model=MyClockLogsOut)
async def my_logs(
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("attendance.clock_in_out")),
):
    """
    لاگ‌های ورود/خروج خودِ کاربر جاری در یک ماه شمسی (مجوز attendance.clock_in_out).
    بدون year/month، ماه جاری برگردانده می‌شود. 400 اگر کاربر به پرسنلی متصل نباشد.
    """
    employee_id = _require_employee(current_user)
    # پیش‌فرض: ماه شمسی جاری
    if year is None or month is None:
        year, month = get_current_jalali_year_month()
    logs = await GpsAttendanceService(db).get_my_logs(employee_id, year=year, month=month)
    return MyClockLogsOut(items=[GpsActivityLogOut.model_validate(log) for log in logs], year=year, month=month)


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
    مجوز attendance.view_clock_records به‌صورت سایت‌محور بررسی می‌شود؛ 403 اگر برای هیچ سایتی نداشته باشد.

    ایزوله‌سازی چندسایتی: چون این Endpoint site_id ثابتی در Path ندارد که require_permission
    بتواند از آن بخواند، get_sites_with_permission دقیقاً سایت‌هایی را برمی‌گرداند که کاربر این
    مجوز را برایشان دارد (None = همه‌ی سایت‌ها). پارامتر site_id با این مجموعه تقاطع گرفته می‌شود
    تا hr-manager سایت‌محور نتواند با تغییر آن به سایت دیگری برسد.
    """
    # سایت‌های مجاز کاربر برای این مجوز (None یعنی بدون محدودیت)
    access_site_ids = await get_sites_with_permission(db, current_user, "attendance.view_clock_records")
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
    if "attendance.manage_clock_records" not in codes:
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


async def _authenticate_websocket_user(token: str) -> User | None:
    """
    احراز هویت WebSocket از روی access token در Query Param (?token=...)، چون مرورگر اجازه‌ی
    هدر Authorization روی WebSocket را نمی‌دهد.
    کاربر را برمی‌گرداند اگر توکن معتبر، به پرسنل متصل و دارای مجوز attendance.clock_in_out باشد؛ وگرنه None.
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
        if user is None or user.employee_id is None:
            return None
        # بررسی «آیا این قابلیت برای کاربر فعال است» (نه محدود به یک سایت)؛
        # همه‌ی انتصاب‌های نقش (سراسری + سایت‌محور) دیده می‌شوند
        has_permission = user.is_superuser or "attendance.clock_in_out" in (
            await UserRepository(db).get_all_permission_codes(user.id)
        )
        return user if has_permission else None


@router.websocket("/presence-ws")
async def presence_websocket(websocket: WebSocket, token: str = Query(...)):
    """
    WebSocket نشانگر زنده‌ی «آنلاین/آفلاین» برای کاربر دارای مجوز attendance.clock_in_out (توکن در ?token=).
    ورودی: پیام‌های JSON Heartbeat با latitude/longitude/accuracy_meters/site_id هر ۳۰-۶۰ ثانیه.
    خروجی: برای هر Heartbeat یک JSON وضعیت (logged / outside_geofence / low_accuracy / no_position).

    - Socket وصل می‌شود ولی تا وقتی یک Heartbeat داخل محدوده‌ی سایت تأیید نشود، هیچ Session ای ساخته نمی‌شود
    - اولین Heartbeat داخل محدوده یک PresenceSession با connected_at همان لحظه می‌سازد
    - Heartbeat خارج از محدوده، قطع Socket یا سکوت بیش از _HEARTBEAT_TIMEOUT_SECONDS، Session را با
      disconnected_at و duration_seconds دقیق می‌بندد؛ ورود دوباره به محدوده Session جدیدی می‌سازد
    - اگر هیچ سایتی موقعیت GPS نداشته باشد، همه‌ی Heartbeat ها «داخل محدوده» شمرده می‌شوند
    - توکن نامعتبر یا بدون مجوز: بستن با کد 4401
    """
    user = await _authenticate_websocket_user(token)
    if user is None:
        await websocket.close(code=4401)  # کد سفارشی: احراز هویت ناموفق
        return

    await websocket.accept()

    async with AsyncSessionLocal() as db:
        session: PresenceSession | None = None  # Session باز فعلی (None = خارج از محدوده یا هنوز تأیید نشده)

        async def close_open_session() -> None:
            """Session باز را با زمان قطع و مدت دقیق می‌بندد و commit می‌کند (اگر Session ای باز باشد)."""
            nonlocal session
            if session is None:
                return
            now = datetime.now(timezone.utc)
            session.disconnected_at = now
            session.duration_seconds = int((now - session.connected_at).total_seconds())
            await db.commit()
            session = None

        try:
            # حلقه‌ی دریافت Heartbeat تا قطع اتصال یا timeout
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=_HEARTBEAT_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:  # سکوت طولانی = قطع‌شده
                    logger.info("Presence WS for employee %s: heartbeat timeout, closing.", user.employee_id)
                    break

                latitude = data.get("latitude")
                longitude = data.get("longitude")
                if latitude is None or longitude is None:
                    # بدون موقعیت نمی‌شود محدوده را تأیید کرد؛ Heartbeat نادیده گرفته می‌شود ولی
                    # یک پاسخ تشخیصی برمی‌گردد تا مشکل (مثلاً رد دسترسی GPS در مرورگر) قابل‌تشخیص باشد
                    await websocket.send_json({"status": "no_position", "message": "موقعیتی در این Heartbeat ارسال نشده بود."})
                    continue

                accuracy_meters = data.get("accuracy_meters")
                if accuracy_meters is not None and accuracy_meters > _MAX_TRUSTED_ACCURACY_METERS:
                    # موقعیت با خطای زیاد قابل‌اعتماد نیست: نه Session باز بسته می‌شود (ممکن است هنوز حاضر باشد)
                    # و نه چیزی با این داده ثبت می‌شود؛ فقط این Heartbeat رد می‌شود
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
                    # پاسخ قبل از پایان تراکنش ساخته می‌شود (بعد از rollback اشیاء منقضی می‌شوند)
                    payload = {
                        "status": "outside_geofence",
                        "matched_site_name": geofence.matched_site.name if geofence.matched_site else None,
                        "distance_meters": geofence.distance_meters,
                        "allowed_radius_meters": geofence.matched_site.gps_radius_meters if geofence.matched_site else None,
                    }
                    # خارج از محدوده: Session باز (اگر باشد) بسته می‌شود و چیز جدیدی ثبت نمی‌شود
                    await close_open_session()
                    # کوئری check_geofence تراکنشی باز کرده بود؛ اگر commit نشد، باید بسته شود تا
                    # اتصال دیتابیس تا Heartbeat بعدی (و در عمل تا قطع Socket) از Pool گرفته نماند
                    if db.in_transaction():
                        await db.rollback()
                    await websocket.send_json(payload)
                    continue

                # داخل محدوده: اگر Session بازی نیست، همین لحظه یکی ساخته می‌شود
                if session is None:
                    session = PresenceSession(
                        employee_id=user.employee_id, connected_at=datetime.now(timezone.utc)
                    )
                    db.add(session)

                # آخرین موقعیت و سایت منطبق روی Session به‌روز می‌شود
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
            await close_open_session()  # در هر حالت خروج، Session باز بسته می‌شود


@router.get("/presence-sessions", response_model=PresenceSessionPageOut)
async def list_presence_sessions(
    page: int = 1,
    page_size: int = 50,
    employee_id: int | None = None,
    only_online: bool = False,
    site_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    گزارش صفحه‌بندی‌شده‌ی Session های آنلاین/آفلاین با مدت دقیق هرکدام، برای Admin/hr-manager.
    فیلتر اختیاری روی پرسنل، فقط آنلاین‌ها و سایت. مجوز attendance.view_logs سایت‌محور بررسی می‌شود؛
    403 اگر برای هیچ سایتی نداشته باشد. ایزوله‌سازی چندسایتی همان الگوی list_all_logs است.
    """
    # سایت‌های مجاز کاربر برای این مجوز (None یعنی بدون محدودیت)
    access_site_ids = await get_sites_with_permission(db, current_user, "attendance.view_logs")
    if access_site_ids is not None and not access_site_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی لازم را ندارید")

    # فیلتر site_id فقط داخل سایت‌های مجاز اعمال می‌شود
    if site_id is not None:
        accessible_site_ids = {site_id} if access_site_ids is None else (access_site_ids & {site_id})
    else:
        accessible_site_ids = access_site_ids

    sessions, total = await GpsAttendanceService(db).get_presence_sessions_page(
        page=page, page_size=page_size, employee_id=employee_id, only_online=only_online,
        site_ids=accessible_site_ids,
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
                is_online_now=s.disconnected_at is None,
                matched_site_name=matched_site.name if matched_site else None,
                last_distance_meters=s.last_distance_meters,
                is_within_geofence=s.is_within_geofence,
            )
        )

    return PresenceSessionPageOut(items=items, total=total)
