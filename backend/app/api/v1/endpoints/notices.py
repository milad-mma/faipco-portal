"""
Endpoint های سیستم اطلاعیه سازمانی.

/notices                    (POST)  ایجاد اطلاعیه — مجوز هر Target جداگانه بررسی می‌شود
/notices/{id}/publish        (POST)  انتشار اطلاعیه
/notices                    (GET)   لیست کامل همه اطلاعیه‌ها — نیازمند notices.view (پنل Admin)
/notices/me                 (GET)   اطلاعیه‌های قابل‌مشاهده برای کاربر جاری
/notices/available-targets   (GET)   برای فرم «اطلاعیه جدید» — Target های مجاز کاربر جاری
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.notice import NoticeCreate, NoticeOut
from app.services.notice_service import NoticePermissionError, NoticeService

router = APIRouter()


@router.post("", response_model=NoticeOut)
async def create_notice(
    payload: NoticeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await NoticeService(db).create_notice(current_user, payload)
    except NoticePermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{notice_id}/publish", response_model=NoticeOut)
async def publish_notice(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    notice = await NoticeService(db).publish_notice(notice_id)
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="اطلاعیه یافت نشد")
    return notice


@router.get("", response_model=list[NoticeOut])
async def list_notices(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("notices.view")),
):
    return await NoticeService(db).list_all()


@router.get("/me", response_model=list[NoticeOut])
async def my_notices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await NoticeService(db).list_for_user(current_user)


@router.get("/available-targets")
async def available_targets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await NoticeService(db).get_available_targets(current_user)
