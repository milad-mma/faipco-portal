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
/notices/{id}                  (DELETE) حذف اطلاعیه — Soft-Delete، فقط فرستنده خودش یا Admin
/notices/payroll               (POST)  آپلود XML فیش حقوقی و ارسال خودکار — فقط notices.payroll
/notices/{id}/payroll/mine     (GET)   دانلود PDF فیش حقوقی خودِ کاربر جاری برای این اطلاعیه (و فقط خودش)
/notices/attendance-card               (POST)  آپلود اکسل فیش کارکرد و ارسال خودکار — فقط notices.attendance_card
/notices/{id}/attendance-card/mine     (GET)   دانلود PDF فیش کارکرد خودِ کاربر جاری برای این اطلاعیه (و فقط خودش)
"""
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

import json

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.employee import Employee
from app.models.notice import Notice, NoticePriority
from app.models.user import User
from app.schemas.notice import (
    AttendanceCardResultOut,
    NoticeCreate,
    NoticeDetailPageOut,
    NoticeOut,
    NoticePageOut,
    NoticeReaderOut,
    PayrollNoticeResultOut,
)
from app.services.notice_service import NoticePermissionError, NoticeService, send_publish_notifications
from app.services.payroll_pdf import render_payroll_receipt_pdf
from app.services.payroll_service import PayrollNoticeService
from app.services.payroll_common import PayrollParseError
from app.services.attendance_card_pdf import render_attendance_card_pdf
from app.services.attendance_card_service import AttendanceCardNoticeService

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


@router.get("/me", response_model=NoticePageOut)
async def my_notices(
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = await NoticeService(db).list_for_user(current_user, page=page, page_size=page_size)
    return NoticePageOut(items=items, total=total)


@router.post("/{notice_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notice_read(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """وقتی کاربر یک اطلاعیه بسته/Preview‌شده را باز می‌کند، از فرانت‌اند صدا زده می‌شود."""
    await NoticeService(db).mark_as_read(notice_id, current_user.id)


@router.get("/sent-by-me", response_model=NoticeDetailPageOut)
async def sent_by_me(
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """گزارش شخصی فرستنده: چه چیزهایی به چه کسانی/واحدهایی فرستاده و چند نفر دیده‌اند (صفحه‌بندی‌شده)."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    items, total = await NoticeService(db).get_detailed_notices(
        sender_id=current_user.id, limit=page_size, offset=(page - 1) * page_size
    )
    return NoticeDetailPageOut(items=items, total=total)


@router.get("/admin-report", response_model=NoticeDetailPageOut)
async def admin_report(
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("notices.view")),
):
    """گزارش کامل Admin: همه اطلاعیه‌های سیستم، فرستنده هرکدام، و آمار بازدید (صفحه‌بندی‌شده)."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    items, total = await NoticeService(db).get_detailed_notices(
        sender_id=None, limit=page_size, offset=(page - 1) * page_size
    )
    return NoticeDetailPageOut(items=items, total=total)


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


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    حذف اطلاعیه (Soft-Delete): فقط فرستنده خودش یا Admin. بلافاصله از پنل همه
    مخاطبانی که آن را دریافت کرده بودند کنار می‌رود، ولی رکورد در گزارش «ارسالی
    من» و گزارش کامل Admin با برچسب «حذف شده» باقی می‌ماند (حذف فیزیکی نمی‌شود).
    """
    try:
        await NoticeService(db).delete_notice(notice_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except NoticePermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/stats-summary")
async def notices_stats_summary(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("notices.view")),
):
    """تعداد اطلاعیه‌های منتشرشده کل سیستم در ۷ روز اخیر — برای کارت آمار داشبورد Admin."""
    count = await NoticeService(db).count_published_this_week()
    return {"published_this_week": count}


@router.get("/available-targets")
async def available_targets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await NoticeService(db).get_available_targets(current_user)


# ---------- اطلاعیه فیش حقوقی (Payroll Notice) ----------


@router.post("/payroll", response_model=PayrollNoticeResultOut)
async def create_payroll_notice(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    body: str = Form(""),
    priority: NoticePriority = Form(NoticePriority.normal),
    file: UploadFile = File(
        ...,
        description="فایل فیش حقوقی — XML (ساختار SalaryReceiptItem) یا XLSX (خروجی Excel همان گزارش)، با هر نامی",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("notices.payroll")),
):
    """
    فایل آپلود می‌شود (XML یا XLSX — بر اساس پسوند تشخیص داده می‌شود)، کد هر
    رکورد با Employee.personnel_code تطبیق داده می‌شود، و اطلاعیه بلافاصله
    فقط برای پرسنل منطبق منتشر می‌شود. کدهای پیدا نشده در پاسخ گزارش می‌شوند
    (ارسال نمی‌شوند).
    """
    file_bytes = await file.read()
    try:
        result = await PayrollNoticeService(db).create_payroll_notice(
            sender=current_user,
            title=title,
            body=body,
            priority=priority,
            file_bytes=file_bytes,
            filename=file.filename or "",
        )
    except PayrollParseError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    background_tasks.add_task(send_publish_notifications, result.notice.id)

    return PayrollNoticeResultOut(
        notice_id=result.notice.id,
        matched_employee_count=result.matched_employee_count,
        missing_codes=result.missing_codes,
        invalid_row_count=result.invalid_row_count,
    )


@router.get("/{notice_id}/payroll/mine")
async def download_my_payroll_receipt(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    PDF فیش حقوقی خودِ کاربر جاری برای این اطلاعیه — و *فقط* خودش. هیچ
    پارامتری برای انتخاب employee_id دیگری در این Endpoint وجود ندارد؛ همیشه
    از روی current_user.employee_id خوانده می‌شود، پس دسترسی به فیش دیگران
    از این مسیر ساختاراً غیرممکن است.
    """
    notice = await db.get(Notice, notice_id)
    if notice is None or notice.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="اطلاعیه یافت نشد")

    if current_user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="فیشی برای شما یافت نشد")

    receipt = await PayrollNoticeService(db).get_my_receipt(notice_id, current_user.employee_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="فیشی برای شما یافت نشد")

    employee = await db.get(Employee, current_user.employee_id)
    from app.models.site import Site  # پرهیز از Circular Import

    site = await db.get(Site, employee.site_id) if employee else None

    fields = json.loads(receipt.fields_json)
    pdf_bytes = render_payroll_receipt_pdf(
        notice_title=notice.title,
        employee_name=f"{employee.first_name} {employee.last_name}" if employee else "",
        personnel_code=receipt.source_personnel_code,
        site_name=site.name if site else None,
        fields=fields,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="payroll-{notice_id}.pdf"'},
    )


# ---------- اطلاعیه فیش کارکرد (Attendance Card Notice) ----------


@router.post("/attendance-card", response_model=AttendanceCardResultOut)
async def create_attendance_card_notice(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    body: str = Form(""),
    priority: NoticePriority = Form(NoticePriority.normal),
    card_subtitle: str = Form(..., description="زیرعنوان ماه/سال که روی خودِ کارت چاپ می‌شود، مثلاً «تیر ماه 1405»"),
    file: UploadFile = File(..., description="فایل اکسل فیش کارکرد پرسنل"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("notices.attendance_card")),
):
    """
    فایل اکسل آپلود می‌شود، کد هر رکورد با Employee.personnel_code تطبیق
    داده می‌شود، و اطلاعیه بلافاصله فقط برای پرسنل منطبق منتشر می‌شود.
    کدهای پیدا نشده در پاسخ گزارش می‌شوند (ارسال نمی‌شوند). تعداد سطرهای
    سرستون فایل به‌صورت خودکار تشخیص داده می‌شود (نیازی به ورودی دستی نیست).
    """
    file_bytes = await file.read()
    try:
        result = await AttendanceCardNoticeService(db).create_attendance_card_notice(
            sender=current_user,
            title=title,
            body=body,
            priority=priority,
            file_bytes=file_bytes,
            card_subtitle=card_subtitle,
        )
    except PayrollParseError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    background_tasks.add_task(send_publish_notifications, result.notice.id)

    return AttendanceCardResultOut(
        notice_id=result.notice.id,
        matched_employee_count=result.matched_employee_count,
        missing_codes=result.missing_codes,
        invalid_row_count=result.invalid_row_count,
    )


@router.get("/{notice_id}/attendance-card/mine")
async def download_my_attendance_card(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    PDF فیش کارکرد خودِ کاربر جاری برای این اطلاعیه — و *فقط* خودش. دقیقاً
    همان مدل دسترسی ساختاری فیش حقوقی: همیشه از روی current_user.employee_id،
    هیچ پارامتری برای انتخاب employee_id دیگری وجود ندارد.
    """
    notice = await db.get(Notice, notice_id)
    if notice is None or notice.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="اطلاعیه یافت نشد")

    if current_user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کارتی برای شما یافت نشد")

    receipt = await AttendanceCardNoticeService(db).get_my_receipt(notice_id, current_user.employee_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کارتی برای شما یافت نشد")

    employee = await db.get(Employee, current_user.employee_id)
    fields = json.loads(receipt.fields_json)
    pdf_bytes = render_attendance_card_pdf(
        employee_name=f"{employee.first_name} {employee.last_name}" if employee else "",
        month_year=notice.card_subtitle or notice.title,
        fields=fields,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="attendance-card-{notice_id}.pdf"'},
    )
