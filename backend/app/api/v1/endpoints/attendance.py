"""
/attendance/presence     (POST)  حضور دوره‌ای — وقتی اپ باز است، هر چند دقیقه
                                  یک‌بار موقعیت چک و لاگ می‌شود. برای همه
                                  پرسنل سینک‌شده در دسترس است (بدون مجوز خاص).
/attendance/clock-in     (POST)  ثبت ورود آزمایشی — فقط با مجوز attendance.clock_in_out
/attendance/clock-out    (POST)  ثبت خروج آزمایشی — فقط با مجوز attendance.clock_in_out
/attendance/my-logs      (GET)   تاریخچه ورود/خروج خودِ کاربر جاری

⚠️ این قابلیت آزمایشی است. ثبت ورود/خروج رسمی باید از طریق دستگاه‌های
تعبیه‌شده در کارخانه انجام شود.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.gps_activity_log import GpsLogType
from app.models.user import User
from app.schemas.gps_attendance import GpsActivityLogOut, GpsCheckResultOut, GpsPositionIn
from app.services.gps_attendance_service import GpsAttendanceError, GpsAttendanceService

router = APIRouter()


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
