"""
Endpoint های سیستم اطلاعیه سازمانی.

/notices                      (POST)  ایجاد اطلاعیه — مجوز هر Target جداگانه بررسی می‌شود
/notices/{id}/publish          (POST)  انتشار اطلاعیه
/notices                      (GET)   لیست کامل همه اطلاعیه‌ها — نیازمند notices.view (پنل Admin)
/notices/me                   (GET)   اطلاعیه‌های قابل‌مشاهده برای کاربر جاری
/notices/{id}/read             (POST)  ثبت این‌که کاربر جاری این اطلاعیه را باز/مشاهده کرد
/notices/sent-by-me            (GET)   گزارش «چه چیزهایی به چه کسانی فرستادم» برای فرستنده
/notices/admin-report          (GET)   گزارش کامل همه اطلاعیه‌ها با فرستنده و آمار بازدید — Admin
/notices/{id}/readers          (GET)   چه کسانی این اطلاعیه را دیدند (فرستنده خودش یا Admin)
/notices/available-targets     (GET)   برای فرم «اطلاعیه جدید» — Target های مجاز کاربر جاری
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.notice import Notice
from app.models.user import User
from app.schemas.notice import NoticeCreate, NoticeDetailOut, NoticeOut, NoticeReaderOut
from app.services.notice_service import NoticePermissionError, NoticeService, send_publish_notifications

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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    notice = await NoticeService(db).publish_notice(notice_id)
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="اطلاعیه یافت نشد")
    # ارسال Push به Background منتقل می‌شود تا پاسخ فوراً برگردد (بدون مکث شبکه)
    background_tasks.add_task(send_publish_notifications, notice.id)
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


@router.post("/{notice_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notice_read(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """وقتی کاربر یک اطلاعیه بسته/Preview‌شده را باز می‌کند، از فرانت‌اند صدا زده می‌شود."""
    await NoticeService(db).mark_as_read(notice_id, current_user.id)


@router.get("/sent-by-me", response_model=list[NoticeDetailOut])
async def sent_by_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """گزارش شخصی فرستنده: چه چیزهایی به چه کسانی/واحدهایی فرستاده و چند نفر دیده‌اند."""
    return await NoticeService(db).get_detailed_notices(sender_id=current_user.id)


@router.get("/admin-report", response_model=list[NoticeDetailOut])
async def admin_report(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("notices.view")),
):
    """گزارش کامل Admin: همه اطلاعیه‌های سیستم، فرستنده هرکدام، و آمار بازدید."""
    return await NoticeService(db).get_detailed_notices(sender_id=None)


@router.get("/{notice_id}/readers", response_model=list[NoticeReaderOut])
async def notice_readers(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    چه کسانی این اطلاعیه را دیده‌اند — فقط خودِ فرستنده یا Admin (notices.view) اجازه دارد.
    """
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="اطلاعیه یافت نشد")

    if notice.sender_id != current_user.id and not current_user.is_superuser:
        # بررسی مجوز notices.view برای Adminهای غیر superuser (در حال حاضر فقط superuser دارد)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه مشاهده این گزارش را ندارید")

    return await NoticeService(db).get_notice_readers(notice_id)


@router.get("/available-targets")
async def available_targets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await NoticeService(db).get_available_targets(current_user)
