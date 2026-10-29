"""
API ماژول «درخواست مساعده» (پیشوند /advances؛ docs/advances.md).

پرسنل (فقط ورود):
  GET  /advances/me                    تنظیمات مؤثر، سابقه، مبلغ قابل درخواست، امکان ثبت، درخواست‌های من
  POST /advances                       ثبت درخواست (مبلغ از پله‌ی سابقه؛ فقط دلیل اختیاری)
  POST /advances/{id}/cancel           لغو درخواست پرداخت‌نشده
  GET  /advances/inbox ، /advances/inbox/count   کارتابل مدیر واحد / مدیر سایت
  POST /advances/inbox/decide          تأیید/رد گروهی مدیر واحد / مدیر سایت (request_ids)
مدیریت (مجوزهای سایت‌محور advances.policy / advances.finance / advances.view):
  GET  /advances/admin/sites                      سایت‌ها + تنظیمات + دسترسی‌های کاربر
  PUT  /advances/admin/sites/{site_id}            تنظیمات (policy)
  GET  /advances/admin/sites/{site_id}/employees  جست‌وجوی پرسنل سایت برای مدیر سایت (policy)
  GET  /advances/admin/sites/{site_id}/requests   فهرست درخواست‌ها (view یا finance)
  GET  /advances/admin/sites/{site_id}/export     خروجی Excel درخواست‌ها + اطلاعات بانکی پرسنل (view یا finance)
  POST /advances/admin/sites/{site_id}/decide     تأیید/رد گروهی واحد مالی (finance)
  POST /advances/admin/sites/{site_id}/pay        ثبت پرداخت گروهی (finance)
  GET/PUT /advances/admin/sites/{site_id}/notification-templates   متن اعلان‌ها (policy)
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission
from app.core.text_normalize import normalize_search_text
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.services import notification_templates
from app.services.advance_service import AdvanceError, AdvanceService
from app.services.loan_service import employee_label

router = APIRouter()

CODES = ("advances.policy", "advances.finance", "advances.view")


class SubmitIn(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)
    amount: int | None = Field(default=None, gt=0)  # فقط حالت «مبلغ دلخواه» (ریال)


class BulkDecisionIn(BaseModel):
    request_ids: list[int] = Field(min_length=1, max_length=200)
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


class BulkPayIn(BaseModel):
    request_ids: list[int] = Field(min_length=1, max_length=200)
    paid_date: str | None = Field(default=None, max_length=10)  # YYYY/MM/DD شمسی؛ خالی = امروز
    note: str | None = Field(default=None, max_length=500)


class TierIn(BaseModel):
    group: str = Field(default="staff", max_length=20)  # staff | supervisor | manager
    min_months: int = Field(ge=0)
    amount: int = Field(gt=0)  # مبلغ ثابت؛ در حالت دلخواه = سقف پله
    min_amount: int | None = Field(default=None, gt=0)  # حداقل مبلغ دلخواه پله


class MemberIn(BaseModel):
    employee_id: int
    group: str = Field(max_length=20)  # supervisor | manager


class SettingsIn(BaseModel):
    is_enabled: bool
    site_manager_employee_id: int | None = None
    window_from_day: int = Field(ge=1, le=31)
    window_to_day: int = Field(ge=1, le=31)
    max_per_month: int = Field(ge=1, le=31)
    rules_text: str | None = Field(default=None, max_length=4000)
    amount_mode: str = Field(default="fixed", pattern="^(fixed|range)$")
    amount_step: int | None = Field(default=None, ge=0)
    block_hire_month: bool | None = None  # قانون ماه شروع به کار؛ None = بدون تغییر
    allow_kara_substitute: bool | None = None  # جانشین فعال مدیر در کاراوب هم تأیید کند؛ None = بدون تغییر
    tiers: list[TierIn] = Field(default_factory=list, max_length=90)
    members: list[MemberIn] = Field(default_factory=list, max_length=500)  # تعیین دستی مدیر/سرپرست


class TemplatesIn(BaseModel):
    texts: dict[str, str | None]


def _err(e: AdvanceError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=str(e))


async def _require_employee(db: AsyncSession, user: User) -> Employee:
    if user.employee_id is None:
        raise HTTPException(status_code=400, detail="این قابلیت فقط برای حساب‌های متصل به پرسنل در دسترس است")
    employee = await db.get(Employee, user.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="پرسنل موردنظر یافت نشد")
    return employee


async def _access(db: AsyncSession, user: User) -> dict[str, set[int] | None]:
    if user.is_superuser:
        return {c: None for c in CODES}
    return {c: await get_sites_with_permission(db, user, c) for c in CODES}


def _has(sites: set[int] | None, site_id: int) -> bool:
    return sites is None or site_id in sites


async def _require(db: AsyncSession, user: User, site_id: int, *codes: str) -> dict:
    access = await _access(db, user)
    if not any(_has(access[c], site_id) for c in codes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی لازم برای این عملیات را ندارید")
    return access


# ---------- پرسنل ----------


@router.get("/me")
async def me(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _require_employee(db, current_user)
    return await AdvanceService(db).my_overview(employee)


@router.post("")
async def submit(payload: SubmitIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _require_employee(db, current_user)
    try:
        return await AdvanceService(db).submit(employee, current_user, payload.reason, payload.amount)
    except AdvanceError as e:
        raise _err(e) from e


@router.post("/{request_id}/cancel")
async def cancel(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _require_employee(db, current_user)
    try:
        return await AdvanceService(db).cancel(employee, current_user, request_id)
    except AdvanceError as e:
        raise _err(e) from e


@router.get("/inbox")
async def inbox(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.employee_id is None:
        return []
    employee = await _require_employee(db, current_user)
    return await AdvanceService(db).inbox(employee)


@router.get("/inbox/count")
async def inbox_count(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.employee_id is None:
        return {"count": 0}
    employee = await _require_employee(db, current_user)
    return {"count": await AdvanceService(db).inbox_count(employee)}


@router.post("/inbox/decide")
async def inbox_decide(
    payload: BulkDecisionIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """تأیید/رد گروهی مدیر واحد یا مدیر سایت؛ هر درخواست جدا بررسی می‌شود و نتیجه‌ی هر کدام برمی‌گردد."""
    employee = await _require_employee(db, current_user)
    try:
        return await AdvanceService(db).approver_decide(
            employee, current_user, payload.request_ids, payload.approve, payload.note
        )
    except AdvanceError as e:
        raise _err(e) from e


# ---------- مدیریت ----------


@router.get("/admin/sites")
async def admin_sites(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    access = await _access(db, current_user)
    if all(v is None for v in access.values()):
        allowed = None
    else:
        allowed = set()
        for v in access.values():
            if v is None:
                allowed = None
                break
            allowed |= v
    sites = await AdvanceService(db).admin_sites(allowed)
    for site in sites:
        sid = site["site_id"]
        site["can_policy"] = _has(access["advances.policy"], sid)
        site["can_finance"] = _has(access["advances.finance"], sid)
        site["can_view"] = _has(access["advances.view"], sid) or site["can_finance"]
    return sites


@router.put("/admin/sites/{site_id}")
async def update_site(
    site_id: int, payload: SettingsIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _require(db, current_user, site_id, "advances.policy")
    try:
        result = await AdvanceService(db).update_settings(site_id, payload.model_dump())
    except AdvanceError as e:
        raise _err(e) from e
    return {"ok": True, "reassigned": result["changed"], "unresolved": result["unresolved"]}


@router.post("/admin/sites/{site_id}/reassign-approvers")
async def reassign_approvers(site_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """مثل وام: درخواست‌های در حال تأیید مساعده به مدیر واحد (زنجیره‌ی مرخصی) و مدیر سایت امروز منتقل می‌شوند."""
    await _require(db, current_user, site_id, "advances.policy")
    service = AdvanceService(db)
    result = await service.reassign_approvers(
        site_id=site_id, refresh_unit_manager=True, reason="به‌روزرسانی تأییدکننده‌ها توسط مدیر"
    )
    await service._commit()
    return result


@router.get("/admin/sites/{site_id}/employees")
async def site_employees(
    site_id: int,
    q: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """جست‌وجوی پرسنل فعال سایت (نام یا کد پرسنلی) برای انتخاب مدیر سایت مساعده و تعیین مدیران/سرپرستان."""
    await _require(db, current_user, site_id, "advances.policy")
    stmt = select(Employee).where(
        Employee.site_id == site_id, Employee.is_active.is_(True), Employee.is_enabled.is_(True)
    )
    key = normalize_search_text(q or "").strip()
    if key:
        like = f"%{key}%"
        stmt = stmt.where(
            Employee.first_name.ilike(like) | Employee.last_name.ilike(like) | Employee.personnel_code.ilike(like)
        )
    rows = (await db.execute(stmt.order_by(Employee.last_name, Employee.first_name).limit(20))).scalars().all()
    return [{"id": e.id, "label": employee_label(e)} for e in rows]


@router.get("/admin/sites/{site_id}/requests")
async def site_requests(
    site_id: int,
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
    month: str | None = Query(default=None, max_length=7),
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require(db, current_user, site_id, "advances.view", "advances.finance")
    return await AdvanceService(db).list_requests(
        site_id, status_filter, month, normalize_search_text(q or "") or None, page, page_size
    )


@router.get("/admin/sites/{site_id}/export")
async def export_site_requests(
    site_id: int,
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
    month: str | None = Query(default=None, max_length=7),
    q: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """خروجی Excel درخواست‌ها (همان فیلترهای فهرست) همراه با اطلاعات بانکی پرسنل. مجوز: advances.view یا finance."""
    await _require(db, current_user, site_id, "advances.view", "advances.finance")
    content = await AdvanceService(db).export_xlsx(site_id, status_filter, month, normalize_search_text(q or "") or None)
    filename = f"advances_{site_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"  # noqa: DTZ005
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/admin/sites/{site_id}/decide")
async def finance_decide(
    site_id: int,
    payload: BulkDecisionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require(db, current_user, site_id, "advances.finance")
    try:
        return await AdvanceService(db).finance_decide(
            site_id, current_user, payload.request_ids, payload.approve, payload.note
        )
    except AdvanceError as e:
        raise _err(e) from e


@router.post("/admin/sites/{site_id}/pay")
async def finance_pay(
    site_id: int, payload: BulkPayIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _require(db, current_user, site_id, "advances.finance")
    try:
        return await AdvanceService(db).finance_pay(
            site_id, current_user, payload.request_ids, payload.paid_date, payload.note
        )
    except AdvanceError as e:
        raise _err(e) from e


@router.get("/admin/sites/{site_id}/notification-templates")
async def get_templates(site_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _require(db, current_user, site_id, "advances.policy")
    return await notification_templates.list_templates(db, "advance", site_id)


@router.put("/admin/sites/{site_id}/notification-templates")
async def save_templates(
    site_id: int, payload: TemplatesIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _require(db, current_user, site_id, "advances.policy")
    try:
        await notification_templates.save_templates(db, "advance", site_id, payload.texts)
    except notification_templates.TemplateError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}
