"""
متن اعلان‌ها و اطلاعیه‌های خودکار ماژول‌های سراسری (اطلاعیه‌ها، ارزیابی عملکرد، تبریک تولد، انتقادات و پیشنهادات،
امنیت ورود، مشخصات خانوادگی). مرخصی و وام متن جدا برای هر سایت دارند و endpoint خودشان را.

  GET /notification-templates/{module}   فهرست متن‌ها (پیش‌فرض یا تغییرداده‌شده)
  PUT /notification-templates/{module}   ذخیره؛ متن خالی = پیش‌فرض
مجوز: مجوز مدیریت همان ماژول برای همه‌ی سایت‌ها (notification_templates.GLOBAL_MODULES).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.user import User
from app.services import notification_templates

router = APIRouter()


class TemplatesIn(BaseModel):
    texts: dict[str, str | None] = Field(default_factory=dict)


async def _require(db: AsyncSession, user: User, module: str) -> None:
    code = notification_templates.GLOBAL_MODULES.get(module)
    if code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ماژول پیدا نشد")
    if user.is_superuser:
        return
    if await get_sites_with_permission(db, user, code) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"متن اعلان‌های این بخش بین همه‌ی سایت‌ها مشترک است و فقط با مجوز {code} برای همه‌ی سایت‌ها قابل تغییر است",
        )


@router.get("/{module}")
async def get_templates(module: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _require(db, current_user, module)
    return await notification_templates.list_templates(db, module, None)


@router.put("/{module}")
async def put_templates(
    module: str, payload: TemplatesIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _require(db, current_user, module)
    try:
        return await notification_templates.save_templates(db, module, None, payload.texts)
    except notification_templates.TemplateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
