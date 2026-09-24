"""
مدل PayrollReceipt: فیش حقوقی ذخیره‌شده‌ی یک پرسنل برای یک اطلاعیه از نوع «فیش حقوقی».

به‌ازای هر پرسنلی که کدش (Code) در فایل آپلودشده پیدا شود یک رکورد ساخته می‌شود.
دسترسی: رکورد همیشه با (notice_id, employee_id == current_user.employee_id) واکشی می‌شود
تا هیچ پرسنلی نتواند فیش پرسنل دیگر را لیست کند یا بخواند.
fields_json به‌صورت عمومی (Generic) ذخیره می‌شود، نه ستون‌های ثابت مثل «حقوق پایه»،
تا با هر ساختار فایل ورودی سازگار باشد؛ هر فیلد فقط یک ردیف {label, value} است.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PayrollReceipt(Base):
    """
    یک فیش حقوقی: اتصال یک اطلاعیه به یک پرسنل همراه با فیلدهای خام فیش.
    برای هر (notice_id, employee_id) فقط یک رکورد مجاز است.
    """
    __tablename__ = "payroll_receipts"
    __table_args__ = (
        UniqueConstraint("notice_id", "employee_id", name="uq_payroll_receipt_notice_employee"),  # هر پرسنل در هر اطلاعیه یک فیش
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), nullable=False)  # با حذف اطلاعیه فیش‌ها هم حذف می‌شوند
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # کد پرسنلی در لحظه‌ی آپلود (Snapshot، مستقل از تغییرات بعدی personnel_code خودِ پرسنل)
    source_personnel_code: Mapped[str] = mapped_column(String(64), nullable=False)

    # JSON از لیست [{"label": "...", "value": "...", "section": "..."}] — فیلدهای خام فیش
    # با همان ترتیب فایل اصلی، بدون هیچ فرض ساختاری فراتر از وجود Code.
    fields_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    employee: Mapped["Employee"] = relationship()  # noqa: F821
