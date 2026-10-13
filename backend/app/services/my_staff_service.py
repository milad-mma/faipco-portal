"""
سرویس «پرسنل من» برای سرپرست‌ها (صفحه‌ی «تردد پرسنل من»).

«پرسنل من» یعنی همه‌ی پرسنلی که سرپرست (به همان معنای تأییدکننده‌ی مرخصی) بالای سرشان است —
شامل واحدهای زیرمجموعه تا پایین درخت سازمانی (سرپرستِ سرپرست، همه‌ی زیرمجموعه‌هایش را می‌بیند).

ریشه‌های درخت یک سرپرست از دو جا جمع می‌شود (همان دو منبعی که تأییدکننده‌ی مرخصی از آن‌ها پیدا می‌شود):
1. زنجیره‌ی سازمانی کاراوب (فقط‌خواندنی): واحدهایی که Sections.ManagerEmp_No آن‌ها کد پرسنلی این فرد است.
2. تخصیص دستی پرتال: ردیف‌های LeaveRequestApprover که approver_employee_id این فرد است.
سپس با ستون «واحد بالادست» (Sections.TFather) همه‌ی زیرواحدها اضافه می‌شوند و پرسنل فعال این واحدها
(در این سایت و سایت‌های هم‌منبع) برگردانده می‌شود. خودِ سرپرست در فهرست نیست.

اگر نگاشت مرخصی یا اتصال کاراوب تنظیم نباشد یا کوئری خطا بدهد، فقط تخصیص دستی حساب می‌شود (بدون خطا).
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.org_tree import build_parent_map, normalize_code, subtree_codes
from app.models.employee import Department, Employee
from app.models.leave_request import LeaveRequestApprover, LeaveRequestMapping
from app.models.site import SiteConnection
from app.models.user import User
from app.services.leave_request_service import LeaveRequestError, LeaveRequestService, _connect, _dict_cursor, _quote

logger = logging.getLogger(__name__)


def _code_key(value) -> str | None:
    """کد پرسنلی را برای مقایسه یکسان می‌کند: «0123»، 123 و 123.0 همه → «123»؛ خالی → None."""
    text = normalize_code(value)
    if text is None:
        return None
    return str(int(text)) if text.isdigit() else text


def _fetch_sections_sync(conn: SiteConnection, mapping: LeaveRequestMapping) -> list[dict]:
    """همه‌ی ردیف‌های جدول واحدهای کاراوب را (کد، کد مدیر، کد بالادست) فقط‌خواندنی می‌خواند."""
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        with _dict_cursor(connection, conn.db_type) as cur:
            query = f"""
                SELECT
                    {q(mapping.section_sec_no_column)} AS {q("SecNo")},
                    {q(mapping.section_manager_emp_no_column)} AS {q("ManagerEmpNo")},
                    {q(mapping.section_parent_column)} AS {q("ParentSecNo")}
                FROM {q(mapping.section_table_name)}
            """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
            cur.execute(query)
            return list(cur.fetchall())
    finally:
        connection.close()


async def _kara_sections(db: AsyncSession, site_id: int) -> list[dict]:
    """ردیف‌های واحدهای کاراوب برای این سایت؛ اگر نگاشت/اتصال نباشد یا خطا بدهد، لیست خالی."""
    try:
        mapping, conn = await LeaveRequestService(db)._get_mapping_and_connection(site_id)
    except LeaveRequestError:
        return []
    if not mapping.section_table_name:
        return []
    try:
        return await asyncio.to_thread(_fetch_sections_sync, conn, mapping)
    except Exception:  # noqa: BLE001 - خطای کاراوب نباید صفحه را از کار بیندازد
        logger.exception("خواندن جدول واحدهای کاراوب برای «پرسنل من» ناموفق بود (site_id=%s)", site_id)
        return []


async def list_my_staff(db: AsyncSession, user: User) -> list[Employee]:
    """
    ورودی: کاربر لاگین‌شده. خروجی: پرسنل فعال زیر نظر او (مستقیم و غیرمستقیم)، مرتب بر اساس نام خانوادگی.
    کاربر بدون پرسنل یا بدون زیرمجموعه → لیست خالی.
    """
    if user.employee_id is None:
        return []
    me = await db.get(Employee, user.employee_id)
    if me is None:
        return []

    # ۱) واحدهایی که در کاراوب مدیرشان این فرد است + نقشه‌ی بالادست برای پیمایش زیرمجموعه‌ها
    sections = await _kara_sections(db, me.site_id)
    parents = build_parent_map(sections, "SecNo", "ParentSecNo")
    roots: set[str] = set()
    my_code = _code_key(me.personnel_code)
    for row in sections:
        manager = _code_key(row.get("ManagerEmpNo"))
        sec_no = normalize_code(row.get("SecNo"))
        if manager is not None and manager == my_code and sec_no is not None:
            roots.add(sec_no)

    # ۲) تخصیص دستی تأییدکننده (LeaveRequestApprover) در پرتال
    manual_codes = (
        await db.execute(
            select(Department.code)
            .join(LeaveRequestApprover, LeaveRequestApprover.department_id == Department.id)
            .where(LeaveRequestApprover.approver_employee_id == me.id)
        )
    ).scalars().all()
    roots.update(c for c in (normalize_code(code) for code in manual_codes) if c is not None)
    if not roots:
        return []

    # ۳) همه‌ی زیرواحدها + پرسنل فعال آن‌ها در این سایت و سایت‌های هم‌منبع (کد واحد در چند سایت یکسان است)
    codes = subtree_codes(parents, roots)
    site_ids = await LeaveRequestService(db)._same_source_site_ids(me.site_id)
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.department))
        .join(Department, Employee.department_id == Department.id)
        .where(
            Department.site_id.in_(site_ids),
            Department.code.in_(codes),
            Employee.is_active.is_(True),
            Employee.id != me.id,
        )
        .order_by(Employee.last_name, Employee.first_name)
    )
    return list(result.scalars().all())


def staff_to_dict(employee: Employee) -> dict:
    """شکل خروجی API برای یک نفر از «پرسنل من» (بدون اطلاعات حساس مثل کد ملی/موبایل)."""
    return {
        "id": employee.id,
        "personnel_code": employee.personnel_code,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "department_name": employee.department.name if employee.department else None,
    }
