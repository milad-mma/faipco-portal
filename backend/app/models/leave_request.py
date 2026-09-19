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

    # ⚠️ جدول مرجع WF_Action - فهرست رسمی ActionId ها به‌همراه عنوان
    # فارسی‌شان (Fdesc)؛ برای این‌که هنگام ساخت «نوع درخواست» جدید، ادمین
    # از بین همین فهرست واقعی انتخاب کند - نه حدس بزند. کاملاً اختیاری و
    # مستقل از Mapping اصلی بالا؛ اگر table_name خالی باشد، این قابلیت
    # غیرفعال است (فرم افزودن نوع، عادی و بدون فهرست کمکی نمایش داده می‌شود).
    action_lookup_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="WF_Action")
    action_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="ActionId")
    action_lookup_desc_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Fdesc")

    # ⚠️ طبق تأیید صریح کاربر: OperationsID واقعاً از جدول WF_OperationTypes
    # می‌آید (نه فقط دو مقدار ثابت ۵/۳ که قبلاً حدس زده بودیم) - این جدول
    # مرجع، فهرست رسمی و کامل انواع عملیات را نگه می‌دارد.
    operation_lookup_table_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="WF_OperationTypes"
    )
    operation_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="OperationId")
    operation_lookup_desc_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Name")

    # ⚠️ طبق تأیید صریح کاربر: Card_No واقعاً از جدول Cards می‌آید (نه یک
    # مقدار ثابت ۰ که قبلاً به‌عنوان جایگزین موقت نوشته می‌شد).
    card_lookup_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Cards")
    card_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Card_No")
    card_lookup_desc_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="DefaultTitle")
    # ⚠️ کشف حیاتی (تأییدشده با بررسی مستقیم دیتابیس Kara): ActionId هیچ‌وقت
    # مستقل انتخاب نمی‌شود - همیشه دقیقاً برابر Cards.WF_ActionID همان
    # کارتی است که Card_No به آن اشاره می‌کند (تأییدشده با تطبیق کامل هر
    # ۷ رکورد واقعی WF_Requests). این ستون برای همین لینک استفاده می‌شود -
    # تا هنگام انتخاب یک کارت در پنل ادمین، ActionId خودکار و درست پر شود.
    card_lookup_action_id_column: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="WF_ActionID"
    )

    # ⚠️ طبق تأیید صریح کاربر: تأییدکننده واقعی (CurEmp_NO) از زنجیره
    # Employee.Sec_No -> Sections.Sec_No -> Sections.ManagerEmp_No در
    # همان دیتابیس منبع به‌دست می‌آید - این همان منطق واقعی نرم‌افزار
    # ورود/خروج است (تأییدشده با داده واقعی: پرسنل ۳۰۷۴۱۳ در بخش ۴، مدیر
    # بخش=۲۹۲۹۹۴ -> CurEmp_NO=۲۹۲۹۹۴). این روش نسبت به تخصیص دستی
    # LeaveRequestApprover اولویت دارد - آن جدول فقط برای مواردی که این
    # زنجیره جواب ندهد (Fallback دستی)، همچنان نگه داشته شده است.
    employee_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Employee")
    employee_emp_no_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Emp_No")
    employee_sec_no_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Sec_No")
    section_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Sections")
    section_sec_no_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="Sec_No")
    section_manager_emp_no_column: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="ManagerEmp_No"
    )
    # ⚠️ کشف حیاتی (تأییدشده با بررسی مستقیم دیتابیس Kara و مقایسه با
    # نتیجه واقعی کاراوب): وقتی یک نفر خودش مدیر بخش خودش است (مثلاً
    # سرپرست/رئیس همان واحد)، هیچ‌کس نمی‌تواند تأییدکننده خودش باشد - در
    # این حالت، نرم‌افزار واقعی به مدیرِ واحدِ بالادستی (پدر این بخش در
    # سلسله‌مراتب) صعود می‌کند. این ستون همان بخش پدر را مشخص می‌کند - اگر
    # مدیرِ به‌دست‌آمده همان درخواست‌دهنده باشد، زنجیره از طریق همین ستون
    # به بالا ادامه پیدا می‌کند تا یک مدیرِ متفاوت پیدا شود.
    section_parent_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="TFather")

    # ⚠️ کشف حیاتی (تأییدشده با بررسی مستقیم دیتابیس Kara): نظر واقعی
    # تأییدکننده در ستون WF_Requests.ManagerIdea ذخیره نمی‌شود (آن ستون
    # همیشه خالی/"" باقی می‌ماند حتی وقتی نظر واقعی وجود دارد) - نظر
    # واقعی در جدول جداگانه WF_Reviews ذخیره می‌شود (یک ردیف به‌ازای هر
    # تصمیم، نه فقط یک ستون تکی). این فیلدها کاملاً اختیاری‌اند - اگر
    # نصبی این جدول را نداشت، به رفتار قبلی (فقط ManagerIdea) برمی‌گردد.
    wf_reviews_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="WF_Reviews")
    # ⚠️ جدول‌های وابسته دیگر (تأییدشده با بررسی Foreign Key های واقعی
    # دیتابیس Kara): WF_Requests سه جدول فرزند دیگر هم دارد که همگی
    # ON DELETE NO_ACTION هستند - یعنی دیتابیس خودش پاکشان نمی‌کند و اگر
    # ردیفی داشته باشند، حذف خودِ درخواست با خطای FK شکست می‌خورد.
    # این‌ها در نصب فعلی خالی‌اند، ولی کاراوب می‌تواند پرشان کند (پیوست
    # فایل، صعود خودکار، تأیید موازی) - پس هنگام حذف مدیریتی باید پاک شوند.
    wf_attachment_table_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="WF_Attachment"
    )
    wf_moveup_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="WF_MoveUp")
    wf_parallel_approval_table_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="WF_RequestParallelApproval"
    )
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
    # ⚠️ فقط مقدار «تأیید» با داده واقعی تأیید شد (۴). مقدار «رد» هنوز
    # حدسی است (هیچ نمونه واقعی رد‌شده از طریق خودِ کاراوب در دیتابیس
    # موجود نبود) - اگر اشتباه بود، همین‌جا در تنظیمات سایت اصلاح کنید.
    wf_reviews_approved_type_value: Mapped[int | None] = mapped_column(Integer, nullable=True, default=4)
    wf_reviews_rejected_type_value: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3)

    # ⚠️ اختیاری - فقط برای نصب‌هایی که یک دیتابیس/جدول مشترک بین چند
    # سایت (شعبه) دارند. اگر branch_code_column خالی باشد، یعنی این سایت
    # جدول اختصاصی خودش را دارد و فیلتر شعبه‌ای اعمال نمی‌شود.
    branch_code_column: Mapped[str | None] = mapped_column(String(128), nullable=True, default="BranchCode")
    branch_code_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # مقداری که همیشه در ApplicationId نوشته می‌شود - طبق مشاهده داده
    # واقعی، در تمام ردیف‌ها همیشه ۴ بوده است؛ قابل‌تغییر برای نصب‌های دیگر.
    application_id_value: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    # ⚠️ هم‌رفتاری با کاراوب (app/services/kara_attendance_writeback.py):
    # تأیید نهایی در کارکرد هم اثر می‌کند (ساعتی روی تردد مطابق، روزانه در
    # Mor_Mam) و فیلدهای تکمیلی WF_Requests مثل خودِ کاراوب پر می‌شوند.
    kara_writeback_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
    # ⚠️ طبق تأیید صریح کاربر: OperationsID واقعی از WF_OperationTypes
    # انتخاب می‌شود (نه فرض ثابت ۵=مرخصی/۳=ماموریت) - اگر خالی بماند،
    # سرویس برای سازگاری با نصب‌های قدیمی‌تر، همان فرض قبلی (۵/۳ بر
    # اساس is_mission) را به‌کار می‌برد.
    operation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ⚠️ طبق تأیید صریح کاربر: Card_No واقعی از جدول Cards انتخاب
    # می‌شود - اگر خالی بماند، سرویس مقدار پیش‌فرض ۰ را می‌نویسد (رفتار قبلی).
    card_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

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

