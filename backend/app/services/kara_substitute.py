"""
جانشین مدیران کاراوب (جدول WF_Substitute؛ docs/leave-requests.md «جانشین مدیران»).

رفتار کاراوب (درخواست ۳۰۶، ۱۴۰۵/۰۸/۰۷): درخواست پیش مدیر اصلی می‌ماند (CurEmp_NO و CurSection دست نمی‌خورند) و جانشینِ
فعال (IsActive=1 و امروز بین StartDate و EndDate) هم می‌تواند تصمیم بگیرد؛ ApprovalByManagerEmp_No = کسی که تصمیم گرفت.
هر مدیر در هر زمان یک جانشین فعال دارد (تعیین جانشین جدید قبلی را غیرفعال می‌کند).

جدول فقط وقتی استفاده می‌شود که گروه wf_substitute در «نگاشت مرخصی/ماموریت» تنظیمات سایت نگاشت شده باشد. خواندن
فقط‌خواندنی است و ۶۰ ثانیه در حافظه نگه داشته می‌شود (کارتابل و شمارنده‌ی داشبورد زیاد صدا زده می‌شوند).
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.services import kara_attendance_writeback as kara_wb
from app.services.kara_schema import KaraNames, quote_mssql

logger = logging.getLogger(__name__)

_CACHE_SECONDS = 60
_cache: dict[int, tuple[float, dict[int, int]]] = {}


def _select_active_sync(conn, names: KaraNames) -> dict[int, int]:
    """{کد مدیر: کد جانشین} جانشینی‌های فعالِ امروز (به وقت ایران)."""
    from app.services.leave_request_service import _connect  # جلوگیری از import حلقه‌ای

    c = lambda role: names.c("wf_substitute", role)  # noqa: E731
    connection = _connect(conn)
    try:
        with connection.cursor(as_dict=True) as cur:
            cur.execute(
                f"SELECT {c('manager_emp_no')} AS M, {c('substitute_emp_no')} AS S "
                f"FROM {quote_mssql(names.raw('wf_substitute', 'table'))} "
                f"WHERE {c('is_active')} = 1 AND {c('start_date')} <= %(now)s "
                f"AND ({c('end_date')} IS NULL OR {c('end_date')} >= %(now)s) "
                f"ORDER BY {c('start_date')}",
                {"now": kara_wb.kara_now()},
            )
            out: dict[int, int] = {}
            for row in cur.fetchall():
                if row["M"] is not None and row["S"] is not None:
                    out[int(row["M"])] = int(row["S"])  # جدیدترین شروع برنده است
            return out
    finally:
        connection.close()


async def active_substitute_codes(db: AsyncSession, site_id: int) -> dict[int, int]:
    """{کد پرسنلی مدیر: کد پرسنلی جانشین فعال} از کاراوب این سایت؛ نگاشت‌نشده / خطا → {} (جانشینی خاموش)."""
    hit = _cache.get(site_id)
    if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    from app.services.leave_request_service import LeaveRequestService

    result: dict[int, int] = {}
    try:
        service = LeaveRequestService(db)
        mapping, conn = await service._get_mapping_and_connection(site_id)
        names = await service._get_kara_names(site_id, mapping, conn)
        if names is not None and names.has("wf_substitute"):
            result = await asyncio.to_thread(_select_active_sync, conn, names)
    except Exception:  # noqa: BLE001 — نبودن ماژول/اتصال یعنی جانشینی خاموش
        logger.info("خواندن جانشین‌های کاراوب سایت %s ممکن نشد", site_id, exc_info=True)
    _cache[site_id] = (time.monotonic(), result)
    return result


async def active_substitute_employees(db: AsyncSession, site_id: int) -> dict[int, int]:
    """
    همان جانشینی‌ها به شناسه‌ی پرسنل پورتال (برای وام و مساعده): {مدیر: جانشین}. کد پرسنلی فقط در همین سایت و
    سایت‌های هم‌منبع معنی دارد؛ جانشین باید فعال، فعال‌شده توسط ادمین و دارای کد عددی باشد.
    """
    codes = await active_substitute_codes(db, site_id)
    if not codes:
        return {}
    from app.services.leave_request_service import LeaveRequestService

    site_ids = await LeaveRequestService(db)._same_source_site_ids(site_id)
    wanted = {str(c) for pair in codes.items() for c in pair}
    rows = (
        await db.execute(
            select(Employee.id, Employee.personnel_code, Employee.site_id, Employee.is_active, Employee.is_enabled).where(
                Employee.site_id.in_(site_ids), Employee.personnel_code.in_(wanted)
            )
        )
    ).all()
    by_code: dict[int, int] = {}
    # همان سایت مقدم؛ فقط پرسنل فعال
    for emp_id, code, emp_site, is_active, is_enabled in sorted(rows, key=lambda r: r[2] != site_id):
        if is_active and is_enabled and str(code).isdigit():
            by_code.setdefault(int(code), emp_id)
    return {by_code[m]: by_code[s] for m, s in codes.items() if m in by_code and s in by_code and m != s}


def clear_cache() -> None:
    _cache.clear()


# ---------- وام و مساعده (با تنظیم allow_kara_substitute هر سایت) ----------


async def _allowed_site_ids(db: AsyncSession, settings_model) -> list[int]:
    rows = await db.execute(
        select(settings_model.site_id).where(
            settings_model.is_enabled.is_(True), settings_model.allow_kara_substitute.is_(True)
        )
    )
    return list(rows.scalars().all())


async def substitute_scope(db: AsyncSession, settings_model, employee_id: int) -> dict[int, set[int]]:
    """{سایت: شناسه‌ی مدیرانی که این پرسنل الان جانشین فعالشان است} — فقط سایت‌هایی که جانشینی را روشن کرده‌اند."""
    scope: dict[int, set[int]] = {}
    for site_id in await _allowed_site_ids(db, settings_model):
        managers = {m for m, s in (await active_substitute_employees(db, site_id)).items() if s == employee_id}
        if managers:
            scope[site_id] = managers
    return scope


async def substitute_of(db: AsyncSession, settings_model, site_id: int, manager_id: int | None) -> int | None:
    """جانشین فعال این مدیر در کاراوب، اگر جانشینی برای این سایت روشن است."""
    if manager_id is None:
        return None
    setting = (await db.execute(select(settings_model).where(settings_model.site_id == site_id))).scalar_one_or_none()
    if setting is None or not setting.allow_kara_substitute:
        return None
    return (await active_substitute_employees(db, site_id)).get(manager_id)
