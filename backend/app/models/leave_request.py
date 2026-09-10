"""
مدل‌های «درخواست مرخصی/ماموریت» - این ماژول برخلاف بقیه پروژه، به یک
جدول خام (WF_Requests) در همان دیتابیس منبع سایت (SiteConnection - از
قبل برای Sync پرسنل/گزارش تردد موجود است) هم می‌خواند و هم می‌نویسد -
نه فقط می‌خواند. این جدول متعلق به نرم‌افزار ورود و خروج فعلی سایت است،
اما طبق تأیید صریح کاربر، این قابلیت خاص (درخواست مرخصی/ماموریت) توسط
آن نرم‌افزار استفاده نمی‌شود - فقط قابل‌مشاهده خواهد بود؛ یعنی پورتال
تنها نویسنده فعال این بخش از جدول است.

⚠️ نام جدول/ستون‌ها هاردکد نیستند - دقیقاً همان الگوی AttendanceMapping/
EmployeeMapping: چون نصب‌های مختلف ممکن است نام‌گذاری متفاوتی داشته
باشند، از پنل تنظیمات سایت قابل‌تنظیم‌اند (LeaveRequestMapping).

⚠️ چون بعضی نصب‌ها یک دیتابیس/جدول مشترک بین چند سایت (شعبه) دارند، یک
ستون BranchCode اختیاری هم پشتیبانی می‌شود - اگر تنظیم شود، هر
خواندن/نوشتن فقط همان مقدار شعبه را می‌بیند/می‌نویسد.
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class LeaveRequestMapping(Base, TimestampMixin):
    """
    نگاشت ستون‌های جدول خام WF_Requests این سایت. هر سایت حداکثر یک
    Mapping دارد (site_id یکتا) - وجود یا نبود این رکورد، خودِ «آیا این
    قابلیت برای این سایت فعال است؟» را هم مشخص می‌کند.

    ⚠️ ستون‌هایی که معنایشان هنوز کاملاً روشن نیست یا برای این نسخه لازم
    نیستند (RequestStatus، IOStatus، DeviceWent/Back، LocationStatus،
    TransferCost، IOTime، Tolerance، ActionId، MoveUpCnt، Requested_Time،
    IsWardenCheck، DutyTools، DutyTamin، Taker*، ezReasonId، ReserveText1،
    MamCntr1/2، AcceptCode، CurSection) عمداً اینجا نگاشت نشده‌اند - در
    نوشتن، خالی (NULL) گذاشته می‌شوند؛ هروقت معنایشان روشن‌تر شد، قابل‌
    اضافه‌شدن هستند.
    """

    __tablename__ = "leave_request_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False)

    table_name: Mapped[str] = mapped_column(String(128), nullable=False, default="WF_Requests")

    request_id_column: Mapped[str] = mapped_column(String(128), nullable=False, default="RequestId")
    emp_no_column: Mapped[str] = mapped_column(String(128), nullable=False, default="Emp_No")
    submitting_date_column: Mapped[str] = mapped_column(String(128), nullable=False, default="SubmittingDate")
    card_no_column: Mapped[str] = mapped_column(String(128), nullable=False, default="Card_No")
    start_date_column: Mapped[str] = mapped_column(String(128), nullable=False, default="StartDate")
    end_date_column: Mapped[str] = mapped_column(String(128), nullable=False, default="EndDate")
    start_hour_column: Mapped[str] = mapped_column(String(128), nullable=False, default="StartHour")
    end_hour_column: Mapped[str] = mapped_column(String(128), nullable=False, default="EndHour")
    duration_column: Mapped[str] = mapped_column(String(128), nullable=False, default="Duration")
    is_final_approved_column: Mapped[str] = mapped_column(String(128), nullable=False, default="IsFinalApproved")
    approval_by_manager_column: Mapped[str] = mapped_column(
        String(128), nullable=False, default="ApprovalByManagerEmp_No"
    )
    approval_date_column: Mapped[str] = mapped_column(String(128), nullable=False, default="ApprovalDate")
    operations_id_column: Mapped[str] = mapped_column(String(128), nullable=False, default="OperationsID")
    description_column: Mapped[str] = mapped_column(String(128), nullable=False, default="Description")
    cur_emp_no_column: Mapped[str] = mapped_column(String(128), nullable=False, default="CurEmp_NO")
    manager_idea_column: Mapped[str] = mapped_column(String(128), nullable=False, default="ManagerIdea")
    is_first_time_shift_column: Mapped[str] = mapped_column(
        String(128), nullable=False, default="IsFirstTimeShift"
    )
    persian_start_date_column: Mapped[str] = mapped_column(
        String(128), nullable=False, default="PersianStartDate"
    )
    application_id_column: Mapped[str] = mapped_column(String(128), nullable=False, default="ApplicationId")
    source_column: Mapped[str] = mapped_column(String(128), nullable=False, default="Source")
    destination_column: Mapped[str] = mapped_column(String(128), nullable=False, default="Distination")
    # ⚠️ اختیاری - طبق تحلیل داده واقعی، ActionId با ترکیب مرخصی/مأموریت
    # × ساعتی/روزانه مرتبط است (نه با زیرنوع دقیق) - مقدار هر ترکیب روی
    # خودِ LeaveRequestType تنظیم می‌شود؛ اگر ستون آن ناشناخته/غیرلازم
    # است، این فیلد را خالی بگذارید تا اصلاً نوشته نشود.
    action_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="ActionId")

    # ⚠️ اختیاری - فقط برای نصب‌هایی که یک دیتابیس/جدول مشترک بین چند
    # سایت (شعبه) دارند. اگر branch_code_column خالی باشد، یعنی این سایت
    # جدول اختصاصی خودش را دارد و فیلتر شعبه‌ای اعمال نمی‌شود.
    branch_code_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="BranchCode")
    branch_code_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # مقداری که همیشه در ApplicationId نوشته می‌شود - طبق مشاهده داده
    # واقعی، در تمام ردیف‌ها همیشه ۴ بوده است؛ قابل‌تغییر برای نصب‌های دیگر.
    application_id_value: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    site: Mapped["Site"] = relationship()  # noqa: F821


class LeaveRequestType(Base, TimestampMixin):
    """
    نوع‌های قابل‌تعریف توسط ادمین (مثلاً «مرخصی استحقاقی روزانه»، «مرخصی
    استعلاجی ساعتی»، «مأموریت روزانه») - طبق داده واقعی مشاهده‌شده، خودِ
    جدول WF_Requests فقط دو مقدار OperationsID دارد (۵=مرخصی، ۳=مأموریت)
    و زیرنوع دقیق (استعلاجی/استحقاقی/شرکتی) هیچ ستون اختصاصی ندارد - فقط
    در متن آزاد Description نوشته می‌شود. برای همین، تفکیک زیرنوع کاملاً
    سمت پورتال (همین جدول) نگه‌داری می‌شود - نه در جدول خام.
    """

    __tablename__ = "leave_request_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_mission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # False=مرخصی، True=مأموریت
    is_hourly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # False=روزانه، True=ساعتی
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # ⚠️ طبق تحلیل داده واقعی WF_Requests: ActionId فقط به ترکیب
    # مرخصی/مأموریت × ساعتی/روزانه بستگی دارد (نه زیرنوع دقیق) - مقدار
    # پیشنهادی خودکار در فرانت‌اند محاسبه می‌شود (۱=مرخصی‌روزانه،
    # ۲=مأموریت‌روزانه، ۳=مرخصی‌ساعتی، ۹=مأموریت‌ساعتی) ولی کاملاً
    # قابل‌ویرایش دستی است - چون ممکن است نصب‌های دیگر کدهای متفاوتی
    # داشته باشند. اگر خالی بماند، اصلاً نوشته نمی‌شود.
    action_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    site: Mapped["Site"] = relationship()  # noqa: F821


class LeaveRequestApprover(Base, TimestampMixin):
    """
    تخصیص «تأییدکننده مرخصی/ماموریت» یک واحد سازمانی - طبق تصمیم صریح
    کاربر، کاملاً مستقل از سرپرستِ اطلاعیه‌ها (Department.supervisor_user_id)
    و مستقل از مدیر/سرپرستِ ارزیابی عملکرد (EvaluationDepartmentSupervisor)
    - این‌ها سه مفهوم کاملاً جدا هستند، حتی اگر در عمل یک نفر باشند. هر
    واحد حداکثر یک تأییدکننده مرخصی/ماموریت دارد (department_id یکتا).
    """

    __tablename__ = "leave_request_approvers"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    approver_employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )

    department: Mapped["Department"] = relationship()  # noqa: F821
    approver_employee: Mapped["Employee"] = relationship()  # noqa: F821
