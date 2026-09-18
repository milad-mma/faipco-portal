"""
Endpoint های «پیش‌نیازهای دسترسی» — وضعیت قفل برای کاربر جاری، و
تنظیمات فعال/غیرفعال‌سازی برای Admin.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_superuser
from app.db.session import get_db
from app.models.user import User
from app.services.access_gate_service import (
    ALL_FEATURES,
    ALL_GATES,
    AccessGateService,
    setting_key,
)
from app.services.system_settings_service import SystemSettingsService

router = APIRouter()


class AccessGateSettingIn(BaseModel):
    gate: str
    feature: str
    enabled: bool


@router.get("/my-status")
async def my_access_gate_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ⚠️ وضعیت قفل کاربر جاری - یک درخواست، همه‌چیز. فرانت‌اند با این
    می‌تواند **قبل از** کلیک هشدار نشان دهد، نه اینکه کاربر کلیک کند و
    ۴۰۳ بگیرد.
    """
    return await AccessGateService(db).get_status(current_user)


@router.get("/settings")
async def list_access_gate_settings(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    """⚠️ فقط Admin واقعی - فهرست وضعیت همه ترکیب‌های (نوع اجبار × قابلیت)."""
    settings = SystemSettingsService(db)
    out = []
    for gate in ALL_GATES:
        for feature in ALL_FEATURES:
            out.append(
                {
                    "gate": gate,
                    "feature": feature,
                    "enabled": await settings.get_access_gate(setting_key(gate, feature)),
                }
            )
    return out


@router.put("/settings")
async def update_access_gate_setting(
    payload: AccessGateSettingIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    await SystemSettingsService(db).set_access_gate(
        setting_key(payload.gate, payload.feature), payload.enabled
    )
    return {"ok": True}
