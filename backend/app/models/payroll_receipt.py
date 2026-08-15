"""
مدل PayrollReceipt: برای هر اطلاعیه از نوع «فیش حقوقی»، یک رکورد به‌ازای هر
پرسنلی که کدش (Code) در XML آپلودشده پیدا شده است.

نکته امنیتی حیاتی: این جدول به‌گونه‌ای طراحی شده که هیچ Endpoint ای اجازه
لیست‌کردن یا خواندن رکورد یک پرسنل توسط پرسنل دیگر را نمی‌دهد — همیشه با
(notice_id, employee_id == current_user.employee_id) واکشی می‌شود.
fields_json خام و Generic نگه داشته شده (نه ستون‌های ثابت مثل «حقوق پایه») تا
با هر ساختار XML سازگار باشد — هر Tag فرزند مستقیم <SalaryReceiptItem> فقط
به یک ردیف {label, value} تبدیل می‌شود.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PayrollReceipt(Base):
    __tablename__ = "payroll_receipts"
    __table_args__ = (
        UniqueConstraint("notice_id", "employee_id", name="uq_payroll_receipt_notice_employee"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # کد پرسنلی همان لحظه‌ی Upload (Snapshot، مستقل از تغییرات بعدی personnel_code خودِ پرسنل)
    source_personnel_code: Mapped[str] = mapped_column(String(64), nullable=False)

    # JSON از لیست [{"label": "...", "value": "..."}] — همان فیلدهای خام <SalaryReceiptItem>
    # با همان ترتیب اصلی XML، بدون هیچ فرض ساختاری فراتر از وجود Code.
    fields_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    employee: Mapped["Employee"] = relationship()  # noqa: F821
