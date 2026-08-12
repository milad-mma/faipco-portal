"""
مدل AttendanceCardReceipt: برای هر اطلاعیه از نوع «فیش کارکرد»، یک رکورد
به‌ازای هر پرسنلی که کدش در اکسل آپلودشده (توسط مدیر منابع انسانی) پیدا
شده است.

دقیقاً هم‌ساختار با PayrollReceipt — همان مدل دسترسی ساختاری: هیچ Endpoint ای
اجازه لیست‌کردن یا خواندن رکورد یک پرسنل توسط پرسنل دیگر را نمی‌دهد؛ همیشه
با (notice_id, employee_id == current_user.employee_id) واکشی می‌شود.
fields_json خام و Generic نگه داشته شده (لیست {label, value}) تا PDF از
رویش ساخته شود.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AttendanceCardReceipt(Base):
    __tablename__ = "attendance_card_receipts"
    __table_args__ = (
        UniqueConstraint("notice_id", "employee_id", name="uq_attendance_card_receipt_notice_employee"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # کد پرسنلی همان لحظه‌ی Upload (Snapshot، مستقل از تغییرات بعدی personnel_code خودِ پرسنل)
    source_personnel_code: Mapped[str] = mapped_column(String(64), nullable=False)

    # JSON از لیست [{"label": "...", "value": "..."}] — همان ۱۶ فیلد فیش کارکرد
    fields_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    employee: Mapped["Employee"] = relationship()  # noqa: F821
