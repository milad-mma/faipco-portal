"""
داشبورد مدیریتی — آمار به تفکیک سایت.

GET /dashboard/site-stats: برای هر سایت فعالِ در دسترس کاربر یک ردیف با همان شاخص‌های کارت‌های داشبورد
(پرسنل فعال، واحدها و واحدهای بدون سرپرست، وضعیت همگام‌سازی امروز، اطلاعیه‌های ۷ روز اخیر، پرسنل بدون دسترسی پرتال).
فرانت با همین داده هم کارت‌های «همه‌ی سایت‌ها» را جمع می‌زند و هم با انتخاب یک سایت فقط آن را نشان می‌دهد.

ایزوله‌سازی چندسایتی مثل Endpointهای اصلی هر کارت: پرسنل/واحدها با get_accessible_site_ids، همگام‌سازی فقط برای
سایت‌های دارای sync.view (وگرنه null)، اطلاعیه‌ها فقط با notices.view (وگرنه null).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_accessible_site_ids, get_sites_with_permission
from app.db.session import get_db
from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.sync_log import SyncLog, SyncRunStatus
from app.models.user import User
from app.services.notice_service import NoticeService

router = APIRouter()


class SiteStatsOut(BaseModel):
    """آمار یک سایت برای کارت‌های داشبورد. مقدار null = کاربر برای این سایت مجوز آن شاخص را ندارد."""

    site_id: int
    site_name: str
    employees_active: int
    departments_total: int
    departments_without_supervisor: int
    sync_today: str | None  # success / failed / partial / running / not_run / null (بدون مجوز sync.view)
    notices_week: int | None  # اطلاعیه‌های منتشرشده‌ی ۷ روز اخیر که به این سایت می‌رسند؛ null = بدون notices.view
    portal_disabled: int


@router.get("/site-stats", response_model=list[SiteStatsOut])
async def site_stats(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """آمار کارت‌های داشبورد به تفکیک سایت‌های فعالِ در دسترس کاربر (مرتب بر اساس نام). دسترسی: هر کاربر واردشده."""
    accessible = await get_accessible_site_ids(db, current_user)  # None = همه
    sites_stmt = select(Site.id, Site.name).where(Site.is_active.is_(True)).order_by(Site.name)
    if accessible is not None:
        sites_stmt = sites_stmt.where(Site.id.in_(accessible))
    sites = (await db.execute(sites_stmt)).all()
    if not sites:
        return []
    site_ids = [sid for sid, _ in sites]

    # پرسنل فعال و پرسنل بدون دسترسی پرتال، در یک کوئری
    emp_rows = (
        await db.execute(
            select(
                Employee.site_id,
                func.count(),
                func.count().filter(Employee.is_enabled.is_(False)),
            )
            .where(Employee.is_active.is_(True), Employee.site_id.in_(site_ids))
            .group_by(Employee.site_id)
        )
    ).all()
    employees = {sid: (int(total), int(disabled)) for sid, total, disabled in emp_rows}

    dept_rows = (
        await db.execute(
            select(
                Department.site_id,
                func.count(),
                func.count().filter(Department.supervisor_user_id.is_(None)),
            )
            .where(Department.site_id.in_(site_ids))
            .group_by(Department.site_id)
        )
    ).all()
    departments = {sid: (int(total), int(no_sup)) for sid, total, no_sup in dept_rows}

    # همگام‌سازی امروز: آخرین اجرای امروزِ هر سایت (مثل SyncService.get_status_summary؛ «امروز» از نیمه‌شب UTC)
    sync_sites = await get_sites_with_permission(db, current_user, "sync.view")  # None = همه، set خالی = هیچ
    sync_today: dict[int, str] = {}
    sync_allowed = set(site_ids) if sync_sites is None else sync_sites & set(site_ids)
    if sync_allowed:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        logs = (
            await db.execute(
                select(SyncLog.site_id, SyncLog.status)
                .where(SyncLog.site_id.in_(sync_allowed), SyncLog.started_at >= today_start)
                .order_by(SyncLog.site_id, SyncLog.started_at.desc())
            )
        ).all()
        latest: dict[int, SyncRunStatus] = {}
        for sid, run_status in logs:
            latest.setdefault(sid, run_status)
        for sid in sync_allowed:
            status = latest.get(sid)
            sync_today[sid] = "not_run" if status is None else status.value  # success / failed / partial / running

    # اطلاعیه‌های هفته‌ی اخیر که به هر سایت می‌رسند (فقط سایت‌های دارای notices.view)
    notice_sites = await get_sites_with_permission(db, current_user, "notices.view")
    notices_allowed = set(site_ids) if notice_sites is None else notice_sites & set(site_ids)
    notice_service = NoticeService(db)
    notices_week: dict[int, int] = {}
    for sid in notices_allowed:
        notices_week[sid] = await notice_service.count_published_this_week({sid})

    return [
        SiteStatsOut(
            site_id=sid,
            site_name=name,
            employees_active=employees.get(sid, (0, 0))[0],
            departments_total=departments.get(sid, (0, 0))[0],
            departments_without_supervisor=departments.get(sid, (0, 0))[1],
            sync_today=sync_today.get(sid),
            notices_week=notices_week.get(sid),
            portal_disabled=employees.get(sid, (0, 0))[1],
        )
        for sid, name in sites
    ]
