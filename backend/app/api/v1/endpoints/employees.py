"""
Endpoint نمونه برای پرسنل — فقط GET (لیست).
CRUD کامل و فیلترها در مراحل بعدی (بعد از تکمیل Sync Engine) اضافه می‌شود.
هدف این Endpoint در این مرحله، نمایش عملی کارکرد require_permission است.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.employee import EmployeeOut

router = APIRouter()


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    site_id: int | None = Query(default=None, description="فیلتر بر اساس Site"),
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(require_permission("employees.view")),
):
    stmt = select(Employee).where(Employee.is_active.is_(True)).limit(200)
    if site_id is not None:
        stmt = stmt.where(Employee.site_id == site_id)
    result = await db.execute(stmt)
    return result.scalars().all()
