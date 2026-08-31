"""
/feedback                      (POST)   ارسال انتقاد/پیشنهاد - هر کاربر لاگین‌شده
/feedback                      (GET)    فهرست پیام‌ها - Admin واقعی، یا دارنده مجوز
                                          feedback.view (سایت‌محور) / feedback.view_all (سراسری)
/feedback/prohibited-phrases   (GET/POST/DELETE) - فقط Admin واقعی (superuser)

امنیتی: فرستنده همیشه از خودِ کاربر لاگین‌شده (سشن) خوانده می‌شود - هرگز
از ورودی درخواست.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_superuser
from app.db.session import get_db
from app.models.user import User
from app.schemas.feedback import FeedbackMessageOut, FeedbackSubmitIn, ProhibitedPhraseIn, ProhibitedPhraseOut
from app.services.feedback_service import FeedbackAccessDenied, FeedbackService

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackSubmitIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await FeedbackService(db).submit_feedback(current_user, payload.message, payload.is_anonymous)
    return {"success": True}


@router.get("", response_model=list[FeedbackMessageOut])
async def list_feedback(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await FeedbackService(db).get_feedback_list(current_user)
    except FeedbackAccessDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


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
