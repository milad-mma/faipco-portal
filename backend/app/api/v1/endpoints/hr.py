"""
/hr/birthday-templates      (GET/POST/DELETE) پول متن‌های تبریک تولد
/hr/birthday-send-time      (GET/PUT)         ساعت ارسال روزانه
/hr/birthday-enabled        (GET/PUT)         فعال/غیرفعال کلی قابلیت
همه با مجوز hr.birthday_messages — بین Admin و hr-manager یکپارچه (هر دو
می‌توانند مدیریت کنند، همان داده مشترک).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
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


@router.get("/birthday-templates", response_model=list[BirthdayTemplateOut])
async def list_birthday_templates(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("hr.birthday_messages")),
):
    return await BirthdayGreetingsService(db).list_templates()


@router.post("/birthday-templates", response_model=BirthdayTemplateOut, status_code=status.HTTP_201_CREATED)
async def add_birthday_template(
    payload: BirthdayTemplateIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("hr.birthday_messages")),
):
    try:
        return await BirthdayGreetingsService(db).add_template(payload.text)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/birthday-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_birthday_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("hr.birthday_messages")),
):
    deleted = await BirthdayGreetingsService(db).delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پیام یافت نشد")


@router.get("/birthday-send-time", response_model=BirthdaySendTimeOut)
async def get_birthday_send_time(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("hr.birthday_messages")),
):
    hour, minute = await BirthdayGreetingsService(db).get_send_time()
    return BirthdaySendTimeOut(hour=hour, minute=minute)


@router.put("/birthday-send-time", response_model=BirthdaySendTimeOut)
async def update_birthday_send_time(
    payload: BirthdaySendTimeIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("hr.birthday_messages")),
):
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
    enabled = await BirthdayGreetingsService(db).get_enabled()
    return BirthdayEnabledOut(enabled=enabled)


@router.put("/birthday-enabled", response_model=BirthdayEnabledOut)
async def update_birthday_enabled(
    payload: BirthdayEnabledIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("hr.birthday_messages")),
):
    enabled = await BirthdayGreetingsService(db).set_enabled(payload.enabled)
    return BirthdayEnabledOut(enabled=enabled)
