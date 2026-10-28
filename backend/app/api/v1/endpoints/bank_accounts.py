"""
Endpoint های ماژول «اطلاعات بانکی» پرسنل (پیشوند /bank-accounts؛ docs/bank-accounts.md).

پرسنل:
  GET  /me                       بانک‌های فعال سایت + اطلاعات ثبت‌شده‌ی خودم + وضعیت تکمیل
  PUT  /me/{bank_id}             ثبت/تغییر اطلاعات یک بانک (آزاد؛ در سابقه ثبت می‌شود)
  GET  /me/history               سابقه‌ی تغییرات خودم

مدیریت (محدود به سایت‌های مجاز):
  GET    /admin/sites/{site_id}/banks       بانک‌های سایت (view یا manage)
  POST   /admin/sites/{site_id}/banks       تعریف بانک (manage)
  PUT    /admin/banks/{bank_id}             ویرایش بانک (manage)
  DELETE /admin/banks/{bank_id}             حذف بانکِ بدون اطلاعات (manage)
  GET    /admin/report                      گزارش پرسنل × بانک‌ها (view)
  GET    /admin/export                      خروجی Excel (view)
  GET    /admin/employees/{id}/history      سابقه‌ی تغییرات یک پرسنل (view)
  PUT    /admin/employees/{id}/banks/{bank_id}   اصلاح اطلاعات یک پرسنل (manage)
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.services.bank_account_service import (
    BankAccountError,
    BankAccountService,
    _bank_out,
)

router = APIRouter()

VIEW = "bank_accounts.view"
MANAGE = "bank_accounts.manage"


class AccountIn(BaseModel):
    account_number: str | None = Field(default=None, max_length=40)
    sheba: str | None = Field(default=None, max_length=40)
    card_number: str | None = Field(default=None, max_length=40)
    accept_terms: bool = False  # پذیرش تعهد مالکیت حساب (فقط اولین ثبت خودِ پرسنل)


class BankIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    is_required: bool | None = None
    account_number_mode: str | None = None
    sheba_mode: str | None = None
    card_number_mode: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


def _bad(e: BankAccountError):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def _require_employee(db: AsyncSession, user: User) -> Employee:
    if user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="این قابلیت فقط برای حساب‌های متصل به پرسنل در دسترس است"
        )
    employee = await db.get(Employee, user.employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل موردنظر یافت نشد")
    return employee


async def _sites(db: AsyncSession, user: User, *codes: str) -> set[int] | None:
    """اجتماع سایت‌های مجاز برای یکی از مجوزها؛ None = همه؛ هیچ → ۴۰۳."""
    union: set[int] = set()
    for code in codes:
        sites = await get_sites_with_permission(db, user, code)
        if sites is None:
            return None
        union |= sites
    if not union:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه دسترسی به اطلاعات بانکی پرسنل را ندارید")
    return union


def _check_site(sites: set[int] | None, site_id: int) -> None:
    if sites is not None and site_id not in sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="به اطلاعات این سایت دسترسی ندارید")


# ---------- پرسنل ----------


@router.get("/me")
async def my_bank_info(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _require_employee(db, current_user)
    return await BankAccountService(db).employee_info(employee)


@router.put("/me/{bank_id}")
async def save_my_account(
    bank_id: int,
    payload: AccountIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = await _require_employee(db, current_user)
    try:
        return await BankAccountService(db).save_account(
            employee, bank_id, payload.model_dump(), current_user, accept_terms=payload.accept_terms
        )
    except BankAccountError as e:
        _bad(e)


@router.get("/me/history")
async def my_history(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _require_employee(db, current_user)
    return await BankAccountService(db).history(employee.id, masked=False)


# ---------- مدیریت ----------


@router.get("/admin/sites/{site_id}/banks")
async def list_site_banks(
    site_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _check_site(await _sites(db, current_user, VIEW, MANAGE), site_id)
    return [_bank_out(b) for b in await BankAccountService(db).list_banks(site_id)]


@router.post("/admin/sites/{site_id}/banks")
async def add_bank(
    site_id: int,
    payload: BankIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_site(await _sites(db, current_user, MANAGE), site_id)
    try:
        return await BankAccountService(db).add_bank(site_id, payload.model_dump(exclude_none=True))
    except BankAccountError as e:
        _bad(e)


@router.put("/admin/banks/{bank_id}")
async def update_bank(
    bank_id: int,
    payload: BankIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BankAccountService(db)
    try:
        bank = await service.get_bank(bank_id)
        _check_site(await _sites(db, current_user, MANAGE), bank.site_id)
        return await service.update_bank(bank_id, payload.model_dump(exclude_none=True))
    except BankAccountError as e:
        _bad(e)


@router.delete("/admin/banks/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank(bank_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = BankAccountService(db)
    try:
        bank = await service.get_bank(bank_id)
        _check_site(await _sites(db, current_user, MANAGE), bank.site_id)
        await service.delete_bank(bank_id)
    except BankAccountError as e:
        _bad(e)


@router.get("/admin/report")
async def report(
    site_id: int | None = None,
    search: str | None = Query(default=None, max_length=100),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(complete|missing)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _sites(db, current_user, VIEW)
    if site_id is not None:
        _check_site(sites, site_id)
    return await BankAccountService(db).report(sites, site_id, search, status_filter)


@router.get("/admin/export")
async def export(
    site_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status", pattern="^(complete|missing)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _sites(db, current_user, VIEW)
    if site_id is not None:
        _check_site(sites, site_id)
    content = await BankAccountService(db).export_xlsx(sites, site_id, status_filter)
    filename = f"bank_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _employee_in_sites(db: AsyncSession, employee_id: int, sites: set[int] | None) -> Employee:
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل موردنظر یافت نشد")
    _check_site(sites, employee.site_id)
    return employee


@router.get("/admin/employees/{employee_id}/history")
async def employee_history(
    employee_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _employee_in_sites(db, employee_id, await _sites(db, current_user, VIEW, MANAGE))
    return await BankAccountService(db).history(employee_id, masked=False)


@router.put("/admin/employees/{employee_id}/banks/{bank_id}")
async def admin_save_account(
    employee_id: int,
    bank_id: int,
    payload: AccountIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = await _employee_in_sites(db, employee_id, await _sites(db, current_user, MANAGE))
    try:
        return await BankAccountService(db).save_account(
            employee, bank_id, payload.model_dump(), current_user, by_admin=True
        )
    except BankAccountError as e:
        _bad(e)
