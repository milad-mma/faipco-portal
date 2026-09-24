"""
Endpoint های «اعلان تغییرات پرتال» — دیالوگی که هنگام ورود به کاربر
نمایش داده می‌شود.

/announcement/current   (GET)  اعلان فعلی و این‌که برای کاربر جاری نمایش داده شود یا نه
/announcement/dismiss   (POST) «دیگر نمایش نده» برای نسخه فعلی
/announcement/settings  (GET/PUT) خواندن/ویرایش اعلان - فقط superuser
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
    """ورودی PUT /announcement/settings."""
    enabled: bool
    title: str
    body: str


@router.get("/current")
async def get_current_announcement(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    اعلان فعلی را همراه با فیلد should_show (آیا برای این کاربر نمایش داده شود) برمی‌گرداند.
    دسترسی: هر کاربر لاگین‌شده. تصمیم نمایش سمت سرور گرفته می‌شود تا منطق
    «نسخه ردشده توسط کاربر» یک‌جا بماند و از سمت کلاینت قابل دور زدن نباشد.
    """
    announcement = await SystemSettingsService(db).get_announcement()
    # نمایش فقط وقتی: اعلان فعال است، متن خالی نیست و کاربر این نسخه را رد نکرده
    should_show = (
        announcement["enabled"]
        and bool(announcement["body"].strip())
        # اگر کاربر نسخه فعلی (یا بالاتر) را رد کرده، نمایش داده
        # نمی‌شود؛ با انتشار نسخه جدید دوباره ظاهر می‌شود.
        and current_user.dismissed_announcement_version < announcement["version"]
    )
    return {**announcement, "should_show": should_show}


@router.post("/dismiss")
async def dismiss_announcement(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    «دیگر نمایش نده» برای نسخه فعلی اعلان؛ نسخه ردشده روی کاربر ذخیره می‌شود.
    دسترسی: هر کاربر لاگین‌شده. دکمه «بستن» این Endpoint را صدا نمی‌زند،
    پس با بستن ساده، اعلان دفعه بعد دوباره نمایش داده می‌شود.
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
    """تنظیمات کامل اعلان (فعال بودن، عنوان، متن، نسخه) را برمی‌گرداند. دسترسی: فقط superuser."""
    return await SystemSettingsService(db).get_announcement()


@router.put("/settings")
async def update_announcement_settings(
    payload: AnnouncementIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    """
    اعلان را ذخیره می‌کند و تنظیمات جدید را برمی‌گرداند. دسترسی: فقط superuser.
    اگر متن یا عنوان عوض شود، نسخه خودکار بالا می‌رود و همه کاربران دوباره آن را می‌بینند.
    """
    return await SystemSettingsService(db).set_announcement(
        payload.enabled, payload.title, payload.body
    )
