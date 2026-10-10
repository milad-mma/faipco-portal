"""
API ماژول «درخواست وام» (پیشوند /loans؛ docs/loans.md).

پرسنل (فقط ورود):
  GET  /loans/me                         مقررات جاری سایت، سابقه، انواع قابل درخواست، درخواست‌های من
  GET  /loans/guarantor-candidates?q=    همکاران قابل انتخاب به‌عنوان ضامن
  POST /loans                            ثبت درخواست
  POST /loans/{id}/cancel                لغو درخواست پرداخت‌نشده
  POST /loans/{id}/guarantors/{gid}/replace   جایگزینی ضامنی که نپذیرفته
  GET  /loans/inbox ، /loans/inbox/count کارتابل: ضمانت‌ها و تأییدهای منتظر من
  POST /loans/{id}/guarantee             قبول/رد ضمانت
  POST /loans/{id}/decide                تأیید/رد مدیر واحد یا مدیر سایت
مدیریت (مجوزهای سایت‌محور loans.policy / loans.finance / loans.view):
  GET  /loans/admin/sites                سایت‌ها + دسترسی‌های کاربر در هر سایت
  PUT  /loans/admin/sites/{site_id}      فعال‌سازی و مدیر سایت (policy)
  GET/POST /loans/admin/sites/{site_id}/policies ، PUT/DELETE /loans/admin/policies/{id} (policy)
  GET  /loans/admin/sites/{site_id}/requests ، GET /loans/admin/requests/{id}   (view یا finance)
  POST /loans/admin/requests/{id}/pay|reject|queue|settle ، /loans/admin/installments/{id}/toggle (finance)
  POST /loans/admin/sites/{site_id}/manual ، سابقه‌ی اصلاحی /loans/admin/sites/{site_id}/service-overrides (finance)
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.services.loan_service import LoanError, LoanService

router = APIRouter()

CODES = ("loans.policy", "loans.finance", "loans.view")


# ---------- ورودی‌ها ----------


class LoanSubmitIn(BaseModel):
    loan_type_id: int
    amount: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=2000)
    guarantor_ids: list[int] = Field(default_factory=list, max_length=10)


class DecisionIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


class ReplaceGuarantorIn(BaseModel):
    employee_id: int


class SiteSettingsIn(BaseModel):
    is_enabled: bool
    site_manager_employee_id: int | None = None


class LoanTypeIn(BaseModel):
    id: int | None = None
    title: str = Field(max_length=200)
    max_amount: int = Field(gt=0)
    min_service_months: int = Field(default=0, ge=0, le=600)
    guarantor_count: int = Field(default=0, ge=0, le=10)
    extra_requirement: str | None = Field(default=None, max_length=500)
    out_of_queue: bool = False
    is_active: bool = True


class PolicyIn(BaseModel):
    title: str = Field(max_length=200)
    effective_from: str = Field(max_length=10)
    rules_text: str | None = Field(default=None, max_length=20000)
    block_if_unsettled: bool = True
    approval_steps: list[str] | None = Field(default=None, max_length=10)
    guarantor_max_active: int | None = Field(default=None, ge=0, le=1000)
    guarantor_min_service_months: int | None = Field(default=None, ge=0, le=1000)
    guarantor_no_active_loan: bool = False
    types: list[LoanTypeIn] = Field(default_factory=list, max_length=50)


class PolicyCreateIn(PolicyIn):
    copy_from_policy_id: int | None = None


class PayIn(BaseModel):
    amount_approved: int = Field(gt=0)
    installment_count: int | None = Field(default=None, ge=1, le=120)
    installment_amount: int | None = Field(default=None, gt=0)
    first_month: str = Field(max_length=7)
    extra_confirmed: bool = False
    note: str | None = Field(default=None, max_length=2000)


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class QueueIn(BaseModel):
    queue_seq: int = Field(ge=1, le=1_000_000)


class ManualIn(BaseModel):
    employee_id: int
    loan_type_id: int | None = None
    type_title: str | None = Field(default=None, max_length=200)
    amount: int = Field(gt=0)
    queue_seq: int | None = Field(default=None, ge=1, le=1_000_000)
    out_of_queue: bool = False  # فقط وقتی نوع وام انتخاب نشده (عنوان آزاد)
    note: str | None = Field(default=None, max_length=2000)


class OverrideIn(BaseModel):
    start_date: str = Field(max_length=10)
    note: str = Field(max_length=2000)


# ---------- کمکی ----------


def _err(e: LoanError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=str(e))


async def _require_employee(db: AsyncSession, user: User) -> Employee:
    if user.employee_id is None:
        raise HTTPException(status_code=400, detail="این قابلیت فقط برای حساب‌های متصل به پرسنل در دسترس است")
    employee = await db.get(Employee, user.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="پرسنل موردنظر یافت نشد")
    return employee


async def _access(db: AsyncSession, user: User) -> dict[str, set[int] | None]:
    """سایت‌های هر مجوز وام برای کاربر (None = همه‌ی سایت‌ها)."""
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
async def my_loans(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _require_employee(db, current_user)
    return await LoanService(db).my_overview(employee)


@router.get("/guarantor-candidates")
async def guarantor_candidates(
    q: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = await _require_employee(db, current_user)
    return await LoanService(db).guarantor_candidates(employee, q)


@router.post("")
async def submit_loan(
    payload: LoanSubmitIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    employee = await _require_employee(db, current_user)
    try:
        return await LoanService(db).submit(employee, current_user, payload.model_dump())
    except LoanError as e:
        raise _err(e) from e


@router.get("/inbox")
async def inbox(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.employee_id is None:
        return {"guarantee": [], "approvals": []}
    employee = await _require_employee(db, current_user)
    return await LoanService(db).inbox(employee)


@router.get("/inbox/count")
async def inbox_count(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.employee_id is None:
        return {"count": 0}
    employee = await _require_employee(db, current_user)
    return {"count": await LoanService(db).inbox_count(employee)}


@router.post("/{request_id}/cancel")
async def cancel_loan(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _require_employee(db, current_user)
    try:
        return await LoanService(db).cancel(employee, current_user, request_id)
    except LoanError as e:
        raise _err(e) from e


@router.post("/{request_id}/guarantors/{guarantor_id}/replace")
async def replace_guarantor(
    request_id: int,
    guarantor_id: int,
    payload: ReplaceGuarantorIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = await _require_employee(db, current_user)
    try:
        return await LoanService(db).replace_guarantor(
            employee, current_user, request_id, guarantor_id, payload.employee_id
        )
    except LoanError as e:
        raise _err(e) from e


@router.post("/{request_id}/guarantee")
async def guarantee(
    request_id: int, payload: DecisionIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    employee = await _require_employee(db, current_user)
    try:
        return await LoanService(db).guarantee_decide(employee, current_user, request_id, payload.approve, payload.note)
    except LoanError as e:
        raise _err(e) from e


@router.post("/{request_id}/decide")
async def decide(
    request_id: int, payload: DecisionIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    employee = await _require_employee(db, current_user)
    try:
        return await LoanService(db).approver_decide(employee, current_user, request_id, payload.approve, payload.note)
    except LoanError as e:
        raise _err(e) from e


# ---------- مدیریت: سایت‌ها و مقررات ----------


@router.get("/admin/sites")
async def admin_sites(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    access = await _access(db, current_user)
    if all(v is not None and not v for v in access.values()):
        raise HTTPException(status_code=403, detail="دسترسی لازم برای مدیریت وام را ندارید")
    union: set[int] | None = set()
    for v in access.values():
        if v is None:
            union = None
            break
        union |= v
    sites = await LoanService(db).admin_sites(union)
    for s in sites:
        s["can_policy"] = _has(access["loans.policy"], s["site_id"])
        s["can_finance"] = _has(access["loans.finance"], s["site_id"])
        s["can_view"] = s["can_finance"] or _has(access["loans.view"], s["site_id"])
    return sites


@router.put("/admin/sites/{site_id}")
async def update_site(
    site_id: int, payload: SiteSettingsIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _require(db, current_user, site_id, "loans.policy")
    service = LoanService(db)
    try:
        await service.update_site_settings(site_id, payload.is_enabled, payload.site_manager_employee_id)
    except LoanError as e:
        raise _err(e) from e
    return {"ok": True}


@router.get("/admin/sites/{site_id}/employees")
async def site_employees(
    site_id: int,
    q: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require(db, current_user, site_id, *CODES)
    return await LoanService(db).search_site_employees(site_id, q)


@router.get("/admin/sites/{site_id}/policies")
async def list_policies(site_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _require(db, current_user, site_id, *CODES)
    return await LoanService(db).list_policies(site_id)


@router.post("/admin/sites/{site_id}/policies")
async def create_policy(
    site_id: int, payload: PolicyCreateIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    access = await _require(db, current_user, site_id, "loans.policy")
    service = LoanService(db)
    copy_from = None
    if payload.copy_from_policy_id:
        try:
            copy_from = await service.get_policy(payload.copy_from_policy_id)
        except LoanError as e:
            raise _err(e) from e
        # کپی از سایت دیگر فقط وقتی کاربر مقررات آن سایت را هم می‌تواند ببیند
        if not any(_has(access[c], copy_from.site_id) for c in CODES):
            raise HTTPException(status_code=403, detail="به مقررات سایت مبدأ دسترسی ندارید")
    data = payload.model_dump(exclude={"copy_from_policy_id"})
    try:
        return await service.create_policy(site_id, data, copy_from)
    except LoanError as e:
        raise _err(e) from e


async def _policy_for(db: AsyncSession, user: User, policy_id: int, *codes: str):
    service = LoanService(db)
    try:
        policy = await service.get_policy(policy_id)
    except LoanError as e:
        raise _err(e) from e
    await _require(db, user, policy.site_id, *codes)
    return service, policy


@router.put("/admin/policies/{policy_id}")
async def update_policy(
    policy_id: int, payload: PolicyIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    service, policy = await _policy_for(db, current_user, policy_id, "loans.policy")
    try:
        return await service.update_policy(policy, payload.model_dump())
    except LoanError as e:
        raise _err(e) from e


@router.delete("/admin/policies/{policy_id}")
async def delete_policy(policy_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    service, policy = await _policy_for(db, current_user, policy_id, "loans.policy")
    await service.delete_policy(policy)
    return {"ok": True}


# ---------- مدیریت: درخواست‌ها و مالی ----------


@router.get("/admin/sites/{site_id}/requests")
async def admin_requests(
    site_id: int,
    status_filter: Literal["open", "in_review", "waiting_finance", "active", "settled", "rejected", "cancelled"]
    | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require(db, current_user, site_id, "loans.view", "loans.finance")
    return await LoanService(db).admin_list(site_id, status_filter)


async def _request_for(db: AsyncSession, user: User, request_id: int, *codes: str):
    service = LoanService(db)
    try:
        req = await service._load_request(request_id)
        await _require(db, user, req.site_id, *codes)
        # عملیات مالی: قفل ردیف فقط بعد از بررسی دسترسی (و خواندن تازه زیر قفل)
        if codes == ("loans.finance",):
            req = await service._load_request(request_id, lock=True)
    except LoanError as e:
        raise _err(e) from e
    return service, req


@router.get("/admin/requests/{request_id}")
async def admin_request(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    service, req = await _request_for(db, current_user, request_id, "loans.view", "loans.finance")
    return await service.serialize(req, detail=True)


@router.post("/admin/requests/{request_id}/pay")
async def pay(
    request_id: int, payload: PayIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    service, req = await _request_for(db, current_user, request_id, "loans.finance")
    try:
        return await service.finance_pay(req, current_user, payload.model_dump())
    except LoanError as e:
        raise _err(e) from e


@router.post("/admin/requests/{request_id}/reject")
async def reject(
    request_id: int, payload: NoteIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    service, req = await _request_for(db, current_user, request_id, "loans.finance")
    try:
        return await service.finance_reject(req, current_user, payload.note)
    except LoanError as e:
        raise _err(e) from e


@router.post("/admin/requests/{request_id}/queue")
async def set_queue(
    request_id: int, payload: QueueIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    service, req = await _request_for(db, current_user, request_id, "loans.finance")
    try:
        return await service.finance_set_queue(req, current_user, payload.queue_seq)
    except LoanError as e:
        raise _err(e) from e


@router.post("/admin/requests/{request_id}/settle")
async def settle(
    request_id: int, payload: NoteIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    service, req = await _request_for(db, current_user, request_id, "loans.finance")
    try:
        return await service.finance_settle(req, current_user, payload.note)
    except LoanError as e:
        raise _err(e) from e


@router.post("/admin/installments/{installment_id}/toggle")
async def toggle_installment(
    installment_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    access = await _access(db, current_user)
    sites = access["loans.finance"]
    if sites is not None and not sites:
        raise HTTPException(status_code=403, detail="دسترسی لازم برای این عملیات را ندارید")
    try:
        return await LoanService(db).finance_toggle_installment(installment_id, current_user, sites)
    except LoanError as e:
        raise _err(e) from e


@router.post("/admin/sites/{site_id}/manual")
async def manual_entry(
    site_id: int, payload: ManualIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _require(db, current_user, site_id, "loans.finance")
    try:
        return await LoanService(db).finance_manual(site_id, current_user, payload.model_dump())
    except LoanError as e:
        raise _err(e) from e


@router.get("/admin/sites/{site_id}/service-overrides")
async def list_overrides(site_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _require(db, current_user, site_id, "loans.finance")
    return await LoanService(db).list_overrides(site_id)


@router.get("/admin/employees/{employee_id}/service")
async def employee_service(employee_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="پرسنل موردنظر یافت نشد")
    await _require(db, current_user, employee.site_id, "loans.finance")
    return await LoanService(db).service_info(employee)


@router.put("/admin/employees/{employee_id}/service")
async def set_override(
    employee_id: int, payload: OverrideIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="پرسنل موردنظر یافت نشد")
    await _require(db, current_user, employee.site_id, "loans.finance")
    try:
        await LoanService(db).set_override(employee, current_user, payload.start_date, payload.note)
    except LoanError as e:
        raise _err(e) from e
    return {"ok": True}


@router.delete("/admin/employees/{employee_id}/service")
async def delete_override(employee_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="پرسنل موردنظر یافت نشد")
    await _require(db, current_user, employee.site_id, "loans.finance")
    await LoanService(db).delete_override(employee_id)
    return {"ok": True}
