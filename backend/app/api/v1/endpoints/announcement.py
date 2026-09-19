"""
Endpoint های «اعلان تغییرات پرتال» — دیالوگی که هنگام ورود به کاربر
نمایش داده می‌شود.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_superuser
from app.db.session import get_db
from app.models.user import User
from app.services.system_settings_service import SystemSettingsService

router = APIRouter()


class AnnouncementIn(BaseModel):
    enabled: bool
    title: str
    body: str


@router.get("/current")
async def get_current_announcement(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    اعلان فعلی + اینکه آیا برای **این کاربر** باید نمایش داده شود.

    ⚠️ تصمیم نمایش سمت سرور گرفته می‌شود، نه کلاینت - تا منطق «نسخه‌ای
    که کاربر رد کرده» در یک جا بماند و با دستکاری سمت کلاینت دور زدنی
    نباشد.
    """
    announcement = await SystemSettingsService(db).get_announcement()
    should_show = (
        announcement["enabled"]
        and bool(announcement["body"].strip())
        # ⚠️ اگر کاربر نسخه فعلی (یا بالاتر) را رد کرده، نمایش داده
        # نمی‌شود؛ ولی با انتشار نسخه جدید دوباره ظاهر می‌شود.
        and current_user.dismissed_announcement_version < announcement["version"]
    )
    return {**announcement, "should_show": should_show}


@router.post("/dismiss")
async def dismiss_announcement(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ⚠️ «دیگر نمایش نده» - فقط برای **همین نسخه**. دکمه «بستن» اصلاً این
    Endpoint را صدا نمی‌زند، پس دفعه بعد دوباره نمایش داده می‌شود.
    """
    announcement = await SystemSettingsService(db).get_announcement()
    current_user.dismissed_announcement_version = announcement["version"]
    await db.commit()
    return {"ok": True, "dismissed_version": announcement["version"]}


@router.get("/settings")
async def get_announcement_settings(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    return await SystemSettingsService(db).get_announcement()


@router.put("/settings")
async def update_announcement_settings(
    payload: AnnouncementIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    """⚠️ اگر متن یا عنوان عوض شود، نسخه خودکار بالا می‌رود و همه کاربران دوباره آن را می‌بینند."""
    return await SystemSettingsService(db).set_announcement(
        payload.enabled, payload.title, payload.body
    )
