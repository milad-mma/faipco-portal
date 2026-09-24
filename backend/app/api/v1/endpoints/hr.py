"""
Endpoint های منابع انسانی برای پیام تبریک تولد:
/hr/birthday-templates      (GET/POST/DELETE) مجموعه متن‌های تبریک تولد
/hr/birthday-send-time      (GET/PUT)         ساعت ارسال روزانه
/hr/birthday-enabled        (GET/PUT)         فعال/غیرفعال کلی قابلیت
/hr/birthday-send-now       (POST)            ارسال فوری پیام‌های امروز
همه با مجوز hr.birthday_messages؛ Admin و hr-manager هر دو روی همان داده مشترک کار می‌کنند.
چون این تنظیمات و ارسال فوری روی پرسنل همه‌ی سایت‌ها اثر دارند، تغییر آن‌ها (POST/PUT/DELETE)
فقط با انتصاب سراسری این مجوز (یا superuser) مجاز است؛ خواندن با انتصاب سایتی هم ممکن است.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.birthday_greetings import (
    BirthdayEnabledIn,
    BirthdayEnabledOut,
    BirthdaySendTimeIn,
    BirthdaySendTimeOut,
    BirthdayTemplateIn,
    BirthdayTemplateOut,
)
from app.services.birthday_greetings_service import BirthdayGreetingsService

router = APIRouter()


async def require_org_wide_birthday_manager(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("hr.birthday_messages")),
) -> User:
    """
    Dependency: کاربر باید hr.birthday_messages را به‌صورت سراسری (یا superuser) داشته باشد؛
    انتصاب سایتی کافی نیست چون متن‌ها، ساعت ارسال و ارسال فوری برای همه‌ی سایت‌ها مشترک‌اند. در غیر این صورت 403.
    """
    if await get_sites_with_permission(db, user, "hr.birthday_messages") is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="تنظیمات پیام تبریک تولد برای همه‌ی سایت‌ها مشترک است و فقط با مجوز برای همه‌ی سایت‌ها قابل تغییر است",
        )
    return user


@router.get("/birthday-templates", response_model=list[BirthdayTemplateOut])
async def list_birthday_templates(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("hr.birthday_messages")),
):
    """فهرست همه متن‌های تبریک تولد را برمی‌گرداند. مجوز: hr.birthday_messages."""
    return await BirthdayGreetingsService(db).list_templates()


@router.post("/birthday-templates", response_model=BirthdayTemplateOut, status_code=status.HTTP_201_CREATED)
async def add_birthday_template(
    payload: BirthdayTemplateIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_org_wide_birthday_manager),
):
    """یک متن تبریک جدید اضافه می‌کند و آن را برمی‌گرداند. مجوز: hr.birthday_messages؛ خطای 400 برای متن نامعتبر."""
    try:
        return await BirthdayGreetingsService(db).add_template(payload.text)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/birthday-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_birthday_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_org_wide_birthday_manager),
):
    """یک متن تبریک را حذف می‌کند. مجوز: hr.birthday_messages؛ خطای 404 اگر پیدا نشود."""
    deleted = await BirthdayGreetingsService(db).delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پیام یافت نشد")


@router.get("/birthday-send-time", response_model=BirthdaySendTimeOut)
async def get_birthday_send_time(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("hr.birthday_messages")),
):
    """ساعت و دقیقه ارسال روزانه پیام تبریک را برمی‌گرداند. مجوز: hr.birthday_messages."""
    hour, minute = await BirthdayGreetingsService(db).get_send_time()
    return BirthdaySendTimeOut(hour=hour, minute=minute)


@router.put("/birthday-send-time", response_model=BirthdaySendTimeOut)
async def update_birthday_send_time(
    payload: BirthdaySendTimeIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_org_wide_birthday_manager),
):
    """
    ساعت ارسال روزانه را ذخیره و زمان‌بند را فوراً به‌روز می‌کند.
    مجوز: hr.birthday_messages؛ خطای 400 برای ساعت/دقیقه نامعتبر.
    """
    from app.core.scheduler import reschedule_birthday_send_time

    try:
        hour, minute = await BirthdayGreetingsService(db).set_send_time(payload.hour, payload.minute)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # بدون Restart سرور، همان لحظه روی Job در حال اجرا اعمال می‌شود
    reschedule_birthday_send_time(hour, minute)
    return BirthdaySendTimeOut(hour=hour, minute=minute)


@router.get("/birthday-enabled", response_model=BirthdayEnabledOut)
async def get_birthday_enabled(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("hr.birthday_messages")),
):
    """وضعیت فعال/غیرفعال بودن ارسال خودکار تبریک تولد را برمی‌گرداند. مجوز: hr.birthday_messages."""
    enabled = await BirthdayGreetingsService(db).get_enabled()
    return BirthdayEnabledOut(enabled=enabled)


@router.put("/birthday-enabled", response_model=BirthdayEnabledOut)
async def update_birthday_enabled(
    payload: BirthdayEnabledIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_org_wide_birthday_manager),
):
    """ارسال خودکار تبریک تولد را فعال/غیرفعال می‌کند و وضعیت جدید را برمی‌گرداند. مجوز: hr.birthday_messages."""
    enabled = await BirthdayGreetingsService(db).set_enabled(payload.enabled)
    return BirthdayEnabledOut(enabled=enabled)


@router.post("/birthday-send-now")
async def send_birthday_greetings_now(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_org_wide_birthday_manager),
):
    """
    پیام‌های تبریک تولد امروز را فوراً و بدون صبر تا ساعت زمان‌بندی‌شده ارسال می‌کند (مثلاً برای تست).
    مجوز: hr.birthday_messages. خروجی: تعداد پیام‌های ارسال‌شده + پیام متنی برای نمایش.
    """
    sent_count = await BirthdayGreetingsService(db).send_todays_birthday_greetings()
    return {
        "sent_count": sent_count,
        "message": f"{sent_count} پیام تبریک تولد فرستاده شد." if sent_count else "هیچ پیامی فرستاده نشد (یا امروز کسی تولد ندارد، یا فهرست خالی است، یا ارسال خودکار غیرفعال است).",
    }
