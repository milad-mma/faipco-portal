"""
Endpointهای «پیش‌نیازهای دسترسی» (access gate).
- my-status: وضعیت قفل قابلیت‌ها برای کاربر جاری.
- settings (GET/PUT): فهرست و تغییر فعال/غیرفعال بودن هر ترکیب «نوع پیش‌نیاز × قابلیت»، فقط برای Admin.
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
    """بدنه‌ی درخواست PUT /settings: نوع پیش‌نیاز، قابلیت و وضعیت فعال بودن."""
    gate: str
    feature: str
    enabled: bool


@router.get("/my-status")
async def my_access_gate_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    وضعیت قفل همه‌ی قابلیت‌ها برای کاربر جاری را در یک درخواست برمی‌گرداند.
    دسترسی: هر کاربر واردشده. فرانت‌اند با آن پیش از کلیک کاربر، هشدار قفل را نشان می‌دهد.
    """
    return await AccessGateService(db).get_status(current_user)


@router.get("/settings")
async def list_access_gate_settings(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    """
    فهرست وضعیت فعال/غیرفعال همه‌ی ترکیب‌های (نوع پیش‌نیاز × قابلیت) را برمی‌گرداند.
    دسترسی: فقط superuser (در غیر این صورت 403).
    """
    settings = SystemSettingsService(db)
    out = []
    # برای هر ترکیب gate × feature مقدار تنظیم ذخیره‌شده خوانده می‌شود
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
    """
    فعال/غیرفعال بودن یک ترکیب (نوع پیش‌نیاز × قابلیت) را ذخیره می‌کند و {"ok": True} برمی‌گرداند.
    دسترسی: فقط superuser (در غیر این صورت 403).
    """
    await SystemSettingsService(db).set_access_gate(
        setting_key(payload.gate, payload.feature), payload.enabled
    )
    return {"ok": True}
