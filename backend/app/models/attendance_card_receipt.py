"""
مدل AttendanceCardReceipt (جدول attendance_card_receipts).

برای هر اطلاعیه از نوع «فیش کارکرد»، یک رکورد به‌ازای هر پرسنلی نگه می‌دارد
که کد پرسنلی‌اش در اکسل آپلودشده توسط مدیر منابع انسانی پیدا شده است.

هم‌ساختار با PayrollReceipt است و همان مدل دسترسی را دارد: هیچ Endpoint ای
اجازه‌ی خواندن رکورد یک پرسنل توسط پرسنل دیگر را نمی‌دهد؛ رکورد همیشه با
(notice_id, employee_id == current_user.employee_id) واکشی می‌شود.
fields_json به‌صورت خام و عمومی (لیست {label, value}) ذخیره می‌شود تا
PDF فیش از روی آن ساخته شود.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AttendanceCardReceipt(Base):
    """
    یک فیش کارکرد برای یک پرسنل در یک اطلاعیه.
    هر جفت (notice_id, employee_id) یکتاست؛ با حذف اطلاعیه یا پرسنل، رکورد هم حذف می‌شود.
    """
    __tablename__ = "attendance_card_receipts"
    __table_args__ = (
        UniqueConstraint("notice_id", "employee_id", name="uq_attendance_card_receipt_notice_employee"),  # یک فیش برای هر پرسنل در هر اطلاعیه
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # کد پرسنلی در لحظه‌ی آپلود (Snapshot؛ با تغییر بعدی personnel_code پرسنل عوض نمی‌شود)
    source_personnel_code: Mapped[str] = mapped_column(String(64), nullable=False)

    # JSON از لیست [{"label": "...", "value": "..."}] — فیلدهای فیش کارکرد به ترتیب ستون‌های اکسل
    fields_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # زمان ساخت رکورد (با timezone)

    employee: Mapped["Employee"] = relationship()  # noqa: F821  # رابطه به پرسنل صاحب فیش
