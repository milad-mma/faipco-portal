"""
/feedback                      (POST)   ارسال انتقاد/پیشنهاد - هر کاربر لاگین‌شده (۱ پیام در دقیقه)
/feedback                      (GET)    فهرست پیام‌ها - Admin واقعی، یا دارنده مجوز
                                          feedback.view (سایت‌محور) / feedback.view_all (سراسری)
                                          قابل‌فیلتر بر اساس فرستنده، سایت، و بازه تاریخ
/feedback/{id}                 (DELETE) حذف یک پیام - فقط Admin واقعی
/feedback/prohibited-phrases   (GET/POST/DELETE) - فقط Admin واقعی (superuser)

امنیتی: فرستنده همیشه از خودِ کاربر لاگین‌شده (سشن) خوانده می‌شود - هرگز
از ورودی درخواست. تشخیص الفاظ نامناسب کاملاً در Backend انجام می‌شود -
غیرقابل‌دورزدن با تغییر Frontend.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_superuser
from app.db.session import get_db
from app.models.feedback import FeedbackCategory
from app.models.user import User
from app.schemas.feedback import FeedbackMessageOut, FeedbackSubmitIn, ProhibitedPhraseIn, ProhibitedPhraseOut
from app.services.feedback_service import FeedbackAccessDenied, FeedbackRateLimitExceeded, FeedbackService

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackSubmitIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await FeedbackService(db).submit_feedback(
            current_user, payload.category, payload.title, payload.message, payload.is_anonymous
        )
    except FeedbackRateLimitExceeded as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    return {"success": True}


@router.get("", response_model=list[FeedbackMessageOut])
async def list_feedback(
    sender_id: int | None = Query(default=None),
    site_id: int | None = Query(default=None),
    category: FeedbackCategory | None = Query(default=None),
    is_anonymous: bool | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await FeedbackService(db).get_feedback_list(
            current_user,
            sender_id=sender_id,
            site_id=site_id,
            category=category,
            is_anonymous=is_anonymous,
            date_from=date_from,
            date_to=date_to,
        )
    except FeedbackAccessDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    deleted = await FeedbackService(db).delete_feedback(feedback_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="یافت نشد")


@router.get("/prohibited-phrases", response_model=list[ProhibitedPhraseOut])
async def list_prohibited_phrases(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    return await FeedbackService(db).list_prohibited_phrases()


@router.post("/prohibited-phrases", response_model=ProhibitedPhraseOut)
async def add_prohibited_phrase(
    payload: ProhibitedPhraseIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    try:
        return await FeedbackService(db).add_prohibited_phrase(payload.phrase)
    except Exception as e:  # noqa: BLE001 - محتمل‌ترین خطا، تکراری‌بودن عبارت (Unique Constraint) است
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="این عبارت قبلاً اضافه شده است") from e


@router.delete("/prohibited-phrases/{phrase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prohibited_phrase(
    phrase_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_superuser),
):
    deleted = await FeedbackService(db).delete_prohibited_phrase(phrase_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="یافت نشد")
