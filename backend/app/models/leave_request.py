"""
مدل‌های SQLAlchemy ماژول «درخواست مرخصی/ماموریت» (جدول‌های پورتال، نه کاراوب).

خودِ درخواست‌ها در جدول خام WF_Requests دیتابیس کاراوب (SiteConnection هر سایت)
خوانده و نوشته می‌شوند؛ این ماژول فقط پیکربندی و ساختار سمت پورتال را نگه می‌دارد:
    - LeaveRequestMapping: نام جدول/ستون‌های کاراوب برای هر سایت (مثل AttendanceMapping)؛
      وجود این رکورد یعنی ماژول برای آن سایت فعال است. با BranchCode اختیاری،
      نصب‌های چندشعبه‌ای با جدول مشترک هم پشتیبانی می‌شوند.
    - LeaveRequestType: نوع‌های درخواست قابل‌تعریف توسط ادمین (زیرنوع فقط سمت پورتال است).
    - LeaveRequestHrOfficer: مسئول نیروی انسانی سایت (تأییدکننده نهایی تردد فراموش‌شده).
    - LeaveRequestApprover: تأییدکننده دستی هر واحد (Fallback زنجیره مدیر بخش کاراوب).
"""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class LeaveRequestMapping(Base, TimestampMixin):
    """
    نگاشت نام جدول/ستون‌های کاراوب برای درخواست‌های مرخصی/ماموریت یک سایت.
    هر سایت حداکثر یک Mapping دارد (site_id یکتا)؛ وجود این رکورد یعنی ماژول برای
    سایت فعال است. ستون‌هایی از WF_Requests که اینجا نگاشت نشده‌اند، هنگام نوشتن NULL می‌مانند.
    """

    __tablename__ = "leave_request_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False)

    table_name: Mapped[str] = mapped_column(String(128), nullable=False, default="WF_Requests")  # جدول اصلی درخواست‌ها

    # ستون‌های جدول WF_Requests (نام پیش‌فرض کاراوب؛ برای هر نصب قابل‌تغییر)
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

    # غیرفعال‌سازی موقت ماژول برای سایت از صفحه تنظیمات (جدا از فرم نگاشت؛ upsert_mapping
    # آن را تغییر نمی‌دهد). تا True است، فرم درخواست پرسنل بسته و کارت داشبورد «غیرفعال» است.
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # ستون ActionId در WF_Requests؛ مقدار آن از LeaveRequestType.action_id می‌آید.
    # اگر خالی باشد، این ستون اصلاً نوشته نمی‌شود.
    action_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="ActionId")

    # جدول مرجع WF_Action (ActionId + عنوان فارسی) برای فهرست کمکی فرم «افزودن نوع درخواست».
    # اختیاری؛ اگر table_name خالی باشد، فهرست کمکی نمایش داده نمی‌شود.
    action_lookup_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="WF_Action")
    action_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="ActionId")
    action_lookup_desc_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Fdesc")

    # جدول مرجع WF_OperationTypes: فهرست رسمی OperationsID ها (منبع مقدار operation_id هر نوع)
    operation_lookup_table_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="WF_OperationTypes"
    )
    operation_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="OperationId")
    operation_lookup_desc_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Name")

    # جدول مرجع کارت‌ها (منبع مقدار Card_No هر نوع). WF_Cards.Title عنوان سفارشی هر شعبه است؛
    # Cards.DefaultTitle فقط عنوان پیش‌فرض سراسری.
    card_lookup_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="WF_Cards")
    card_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Card_No")
    card_lookup_desc_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Title")
    # ستون WF_ActionID در جدول کارت‌ها: ActionId هر درخواست همیشه برابر ActionId کارتِ انتخاب‌شده است؛
    # با انتخاب کارت در پنل ادمین، action_id نوع به‌صورت خودکار از همین ستون پر می‌شود.
    card_lookup_action_id_column: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="WF_ActionID"
    )

    # جدول‌های Employee و Sections کاراوب برای یافتن تأییدکننده (CurEmp_NO) از زنجیره
    # Employee.Sec_No -> Sections.Sec_No -> Sections.ManagerEmp_No.
    # این زنجیره بر تخصیص دستی LeaveRequestApprover اولویت دارد؛ آن جدول فقط Fallback است.
    employee_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Employee")
    employee_emp_no_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Emp_No")
    employee_sec_no_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Sec_No")
    section_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Sections")
    section_sec_no_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Sec_No")
    section_manager_emp_no_column: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="ManagerEmp_No"
    )
    # ستون بخش پدر در Sections: اگر مدیرِ به‌دست‌آمده خودِ درخواست‌دهنده باشد (کسی تأییدکننده
    # خودش نیست)، جست‌وجو از طریق این ستون به بخش بالادستی ادامه می‌یابد تا مدیر متفاوتی پیدا شود.
    section_parent_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="TFather")

    # جدول WF_Reviews: نظر واقعی تأییدکننده اینجا ذخیره می‌شود (یک ردیف به‌ازای هر تصمیم)،
    # نه در WF_Requests.ManagerIdea. اختیاری؛ اگر خالی باشد فقط ManagerIdea استفاده می‌شود.
    wf_reviews_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="WF_Reviews")
    # جدول‌های فرزند WF_Requests با FK بدون CASCADE (پیوست، صعود خودکار، تأیید موازی):
    # هنگام حذف مدیریتی یک درخواست باید ردیف‌های این‌ها هم پاک شوند وگرنه حذف با خطای FK می‌شکند.
    wf_attachment_table_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="WF_Attachment"
    )
    wf_moveup_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="WF_MoveUp")
    wf_parallel_approval_table_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="WF_RequestParallelApproval"
    )
    # ستون‌های جدول WF_Reviews
    wf_reviews_request_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="RequestId")
    wf_reviews_reviewed_emp_no_column: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="ReviewedEmp_No"
    )
    wf_reviews_description_column: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="Description"
    )
    wf_reviews_type_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="ReviewType")
    wf_reviews_date_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="ReviewDate")
    wf_reviews_show_to_personal_column: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="ShowToPersonal"
    )
    # مقدار ReviewType که در WF_Reviews برای «تأیید» و «رد» نوشته می‌شود (قابل‌تنظیم برای هر نصب)
    wf_reviews_approved_type_value: Mapped[int | None] = mapped_column(Integer, nullable=True, default=4)
    wf_reviews_rejected_type_value: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3)

    # فیلتر شعبه برای نصب‌هایی که یک جدول مشترک بین چند سایت دارند: هر خواندن/نوشتن فقط
    # ردیف‌های با همین branch_code_value را می‌بیند. اگر branch_code_column خالی باشد، فیلتری اعمال نمی‌شود.
    branch_code_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="BranchCode")
    branch_code_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # مقدار ثابتی که در ستون ApplicationId هر درخواست جدید نوشته می‌شود
    application_id_value: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    # نگاشت جدول/ستون‌های کاراوب به شکل JSON با کلید «گروه.نقش» (اعتبارسنجی در kara_schema)
    kara_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    site: Mapped["Site"] = relationship()  # noqa: F821


class LeaveRequestType(Base, TimestampMixin):
    """
    نوع درخواست قابل‌تعریف توسط ادمین برای هر سایت (مثلاً «مرخصی روزانه استحقاقی»).
    جدول WF_Requests ستونی برای زیرنوع ندارد؛ تفکیک زیرنوع فقط در همین جدول پورتال
    نگه‌داری می‌شود و مقادیر کاراوب (ActionId/OperationsID/Card_No) از روی نوع نوشته می‌شوند.
    """

    __tablename__ = "leave_request_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)  # عنوان نمایشی؛ مبنای کد مجوز مشاهده
    is_mission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # False=مرخصی، True=مأموریت
    is_hourly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # False=روزانه، True=ساعتی
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # فقط نوع‌های فعال در فرم پرسنل می‌آیند
    # مقدار ActionId کاراوب برای این نوع (به ترکیب مرخصی/مأموریت × ساعتی/روزانه بستگی دارد).
    # فرانت‌اند مقدار پیشنهادی می‌دهد ولی قابل‌ویرایش است؛ اگر خالی بماند، ستون نوشته نمی‌شود.
    action_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # مقدار OperationsID از جدول WF_OperationTypes؛ اگر خالی بماند، سرویس ۵ (مرخصی) یا ۳ (مأموریت) می‌نویسد
    operation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # مقدار Card_No از جدول کارت‌های کاراوب؛ اگر خالی بماند، سرویس ۰ می‌نویسد
    card_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # نوع «تردد فراموش‌شده»: به‌جای بازه زمانی، یک یا دو تردد (ورود/خروج با تاریخ جداگانه) ثبت می‌شود؛
    # اول سرپرست و بعد مسئول نیروی انسانی تأیید می‌کند و در پایان تردد در کاراوب درج می‌شود.
    is_forgotten_punch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    site: Mapped["Site"] = relationship()  # noqa: F821


class LeaveRequestHrOfficer(Base, TimestampMixin):
    """
    مسئول نیروی انسانی هر سایت: تأییدکننده نهایی درخواست‌های «تردد فراموش‌شده»
    (بعد از تأیید سرپرست). هر سایت حداکثر یک نفر (site_id یکتا).
    """

    __tablename__ = "leave_request_hr_officers"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)

    employee: Mapped["Employee"] = relationship()  # noqa: F821


class LeaveRequestApprover(Base, TimestampMixin):
    """
    تأییدکننده دستی مرخصی/ماموریت برای یک واحد سازمانی (Fallback وقتی زنجیره مدیر بخش
    کاراوب جواب ندهد). مستقل از سرپرست اطلاعیه‌ها (Department.supervisor_user_id) و
    سرپرست ارزیابی عملکرد (EvaluationDepartmentSupervisor). هر واحد حداکثر یک تأییدکننده دارد.
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

