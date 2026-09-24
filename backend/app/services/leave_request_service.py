"""
سرویس «درخواست مرخصی/ماموریت» - روی جدول خام WF_Requests در دیتابیس منبع
سایت (کاراوب) هم می‌خواند و هم می‌نویسد (INSERT/UPDATE/DELETE)، با همان الگوی
اتصال و Quote کردن نام جدول/ستون که در گزارش تردد ماهانه استفاده می‌شود.

بخش‌های فایل:
    - توابع همگام (sync) سطح ماژول: اتصال به دیتابیس منبع، خواندن/درج/به‌روزرسانی/حذف
      درخواست، خواندن جدول‌های مرجع (WF_Action، Cards، WF_OperationTypes)،
      نظرهای تأییدکننده در WF_Reviews و پیدا کردن مدیر از زنجیره سازمانی.
      این‌ها همیشه با asyncio.to_thread از سرویس فراخوانی می‌شوند.
    - ارسال اعلان Push در پس‌زمینه به درخواست‌دهنده/تأییدکننده.
    - کلاس LeaveRequestService: ثبت درخواست (ساعتی، روزانه، تردد فراموش‌شده)،
      حذف، لیست‌ها (خودم / کارتابل تأییدکننده / همه‌ی سایت)، تصمیم‌گیری،
      ویرایش مدیریتی و Lookupهای پنل ادمین؛ همراه با اعمال اثر تأیید در کارکرد
      کاراوب از طریق kara_attendance_writeback.
    - _normalize_row: تبدیل ردیف خام دیتابیس به دیکشنری پایدار برای Schemaها.

امنیت: نام جدول/ستون فقط از LeaveRequestMapping (تنظیم‌شده توسط Admin با
مجوز sites.manage) می‌آید و با _quote مخصوص نوع دیتابیس احاطه می‌شود؛
مقادیر واقعی همیشه Parameterized هستند.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import pymssql
import pymysql
import pymysql.cursors
import psycopg2
import psycopg2.extras
import jdatetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.leave_request_rules import (
    LeaveRequestRulesError,
    compute_daily_duration,
    compute_hourly_duration,
    jalali_date_to_compact,
)
from app.core.security import decrypt_secret
from app.models.employee import Employee
from app.models.leave_request import (
    LeaveRequestApprover,
    LeaveRequestHrOfficer,
    LeaveRequestMapping,
    LeaveRequestType,
)
from app.models.site import AttendanceMapping, DbType, SiteConnection
from app.models.user import User
from app.services import kara_attendance_writeback as kara_wb
from app.services import site_branch
from app.services.kara_schema import KaraNames
from app.services.push_service import PushService

logger = logging.getLogger(__name__)


class LeaveRequestError(Exception):
    """خطای قابل نمایش به کاربر در عملیات درخواست مرخصی/ماموریت؛ در لایه API به پاسخ 400 تبدیل می‌شود."""
    pass


# تردد فراموش‌شده: حداکثر چند روز گذشته قابل‌ثبت است (مثل WF_Action.RequestValidDays کاراوب)
FORGOTTEN_PUNCH_MAX_PAST_DAYS = 31
# حداکثر فاصله ورود تا خروج در یک درخواست (شیفت شب ۱۲ ساعته + حاشیه)
FORGOTTEN_PUNCH_MAX_SPAN_HOURS = 24
_PUNCH_LABELS = {"in": "ورود", "out": "خروج"}  # برچسب فارسی نوع تردد برای پیام‌ها و توضیحات


def _quote(db_type: DbType, name: str) -> str:
    """نام جدول/ستون را با علامت Quote مخصوص همان نوع دیتابیس احاطه می‌کند (` برای MySQL، " برای PostgreSQL، [] برای SQL Server)."""
    if db_type == DbType.mysql:
        return f"`{name}`"
    if db_type == DbType.postgresql:
        return f'"{name}"'
    return f"[{name}]"  # mssql


def _connect(conn: SiteConnection):
    """
    ورودی: رکورد اتصال سایت. یک اتصال همگام به دیتابیس منبع (SQL Server /
    MySQL / PostgreSQL) با Timeout ده ثانیه باز می‌کند و شیء اتصال درایور را برمی‌گرداند.
    """
    password = decrypt_secret(conn.password_encrypted)  # رمز در دیتابیس پورتال رمزنگاری‌شده است
    # انتخاب درایور بر اساس نوع دیتابیس
    if conn.db_type == DbType.mssql:
        return pymssql.connect(
            server=conn.host,
            port=str(conn.port),
            database=conn.database_name,
            user=conn.username,
            password=password,
            timeout=10,
            login_timeout=10,
        )
    if conn.db_type == DbType.mysql:
        return pymysql.connect(
            host=conn.host,
            port=conn.port,
            database=conn.database_name,
            user=conn.username,
            password=password,
            connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,  # تا ردیف‌ها دیکشنری باشند
        )
    if conn.db_type == DbType.postgresql:
        return psycopg2.connect(
            host=conn.host,
            port=conn.port,
            dbname=conn.database_name,
            user=conn.username,
            password=password,
            connect_timeout=10,
        )
    raise LeaveRequestError(f"نوع اتصال «{conn.db_type.value}» برای درخواست مرخصی/ماموریت پشتیبانی نمی‌شود")


def _dict_cursor(connection, db_type: DbType):
    """یک Cursor می‌سازد که ردیف‌ها را به‌صورت دیکشنری (نام ستون -> مقدار) برگرداند؛ روش هر درایور متفاوت است."""
    if db_type == DbType.mssql:
        return connection.cursor(as_dict=True)
    if db_type == DbType.postgresql:
        return connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return connection.cursor()  # MySQL: خودِ اتصال با DictCursor ساخته شده


def _effective_branch(mapping: LeaveRequestMapping) -> int | None:
    """
    کد شعبه مؤثر: مقدار خودِ نگاشت مرخصی/ماموریت، و اگر خالی است «کد شعبه این
    سایت» از نگاشت پرسنل (در _get_mapping_and_connection روی نمونه گذاشته می‌شود).
    """
    if mapping.branch_code_value is not None:
        return mapping.branch_code_value
    return getattr(mapping, "_site_branch", None)


def _branch_filter_sql(q, mapping: LeaveRequestMapping) -> tuple[str, dict]:
    """
    ورودی: تابع Quote و نگاشت. تکه‌ی «AND ستون_شعبه = %(branch_code)s» و پارامترش را
    برمی‌گرداند تا به WHERE کوئری‌های WF_Requests اضافه شود؛ اگر شعبه نگاشت نشده، رشته خالی.
    """
    branch = _effective_branch(mapping)
    # فقط وقتی هم ستون شعبه نگاشت شده و هم مقداری برای این سایت داریم
    if mapping.branch_code_column and branch is not None:
        return f" AND {q(mapping.branch_code_column)} = %(branch_code)s", {"branch_code": branch}
    return "", {}


def _resolve_manager_emp_no_sync(conn: SiteConnection, mapping: LeaveRequestMapping, emp_no: int) -> int | None:
    """
    ورودی: اتصال، نگاشت و کد پرسنلی درخواست‌دهنده. کد پرسنلی مدیرِ او را از
    زنجیره سازمانی کاراوب پیدا می‌کند: Employee.Sec_No -> Sections.Sec_No ->
    Sections.ManagerEmp_No (فقط‌خواندنی).

    اگر مدیرِ به‌دست‌آمده خودِ همان درخواست‌دهنده باشد (فرد، مدیر بخش خودش
    است)، از طریق ستون section_parent_column به بخش بالادستی صعود می‌کند و
    دوباره بررسی می‌کند، تا مدیرِ متفاوتی پیدا شود یا به ریشه سلسله‌مراتب برسد.

    خروجی None یعنی: جدول‌های زنجیره تنظیم نشده‌اند، پرسنل/بخش پیدا نشد، یا تا
    ریشه هم مدیرِ متفاوتی پیدا نشد - تا سرویس به تخصیص دستی (LeaveRequestApprover) برگردد.
    """
    # بدون نگاشت جدول پرسنل و بخش‌ها، زنجیره قابل پیمایش نیست
    if not (mapping.employee_table_name and mapping.section_table_name):
        return None
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        with _dict_cursor(connection, conn.db_type) as cur:
            # کد بخش (Sec_No) پرسنل درخواست‌دهنده
            employee_query = f"""
                SELECT {q(mapping.employee_sec_no_column)} AS {q("SecNo")}
                FROM {q(mapping.employee_table_name)}
                WHERE {q(mapping.employee_emp_no_column)} = %(emp_no)s
            """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
            cur.execute(employee_query, {"emp_no": emp_no})
            row = cur.fetchone()
            if not row or row.get("SecNo") is None:
                return None
            current_sec_no = row["SecNo"]

            # صعود در سلسله‌مراتب بخش‌ها تا پیدا شدن مدیری غیر از خودِ درخواست‌دهنده؛
            # سقف ۱۰ سطح فقط محافظ در برابر داده حلقه‌ای است.
            for _ in range(10):
                # مدیر و بخش والدِ بخش فعلی
                section_query = f"""
                    SELECT
                        {q(mapping.section_manager_emp_no_column)} AS {q("ManagerEmpNo")},
                        {q(mapping.section_parent_column)} AS {q("ParentSecNo")}
                    FROM {q(mapping.section_table_name)}
                    WHERE {q(mapping.section_sec_no_column)} = %(sec_no)s
                """  # noqa: S608
                cur.execute(section_query, {"sec_no": current_sec_no})
                section_row = cur.fetchone()
                if not section_row or section_row.get("ManagerEmpNo") is None:
                    return None
                manager_emp_no = int(section_row["ManagerEmpNo"])
                # هیچ‌کس تأییدکننده خودش نیست؛ مدیر متفاوت یعنی جواب پیدا شد
                if manager_emp_no != emp_no:
                    return manager_emp_no
                parent_sec_no = section_row.get("ParentSecNo")
                if parent_sec_no is None:
                    return None  # به ریشه رسیدیم و هنوز مدیرِ متفاوتی پیدا نشد
                current_sec_no = parent_sec_no  # یک سطح بالاتر
            return None  # سقف صعود پر شد (داده حلقه‌ای)
    finally:
        connection.close()


def _select_lookup_sync(conn: SiteConnection, table_name: str, id_column: str, desc_column: str) -> list[dict]:
    """
    ورودی: اتصال، نام جدول مرجع و نام ستون شناسه/عنوان. همه ردیف‌های یک جدول
    مرجعِ ساده (شناسه عددی + عنوان فارسی، مثل WF_Action و WF_OperationTypes) را
    فقط‌خواندنی می‌خواند و به‌صورت لیست دیکشنری با کلیدهای LookupId/LookupTitle برمی‌گرداند.
    برای پرکردن فرم «افزودن نوع درخواست» در پنل ادمین استفاده می‌شود.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        # همه ردیف‌ها، مرتب بر اساس شناسه
        query = f"""
            SELECT {q(id_column)} AS {q("LookupId")}, {q(desc_column)} AS {q("LookupTitle")}
            FROM {q(table_name)}
            ORDER BY {q(id_column)} ASC
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with _dict_cursor(connection, conn.db_type) as cur:
            cur.execute(query)
            return list(cur.fetchall())
    finally:
        connection.close()


def _select_card_lookup_sync(conn: SiteConnection, mapping: LeaveRequestMapping) -> list[dict]:
    """
    ورودی: اتصال و نگاشت. فهرست کارت‌های جدول Cards را فقط‌خواندنی می‌خواند و
    به‌صورت لیست دیکشنری با کلیدهای LookupId/LookupTitle/LinkedActionId برمی‌گرداند.
    ستون سوم (ActionId مرتبط با هر کارت) باعث می‌شود انتخاب یک کارت در پنل ادمین،
    ActionId را هم خودکار پر کند - چون ActionId همیشه از خودِ کارت مشتق می‌شود.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    # Card_No در چند شعبه تکرار می‌شود (عنوان سفارشی هر شعبه) - فقط کارت‌های شعبه همین سایت
    names = KaraNames(mapping)
    where_sql, params = "", {}
    branch = getattr(mapping, "_site_branch", None)
    if names.has("cards", "branch_code") and branch is not None:
        where_sql = f"WHERE {q(names.raw('cards', 'branch_code'))} = %(branch)s"
        params["branch"] = branch
    connection = _connect(conn)
    try:
        # کارت‌ها به همراه ActionId مرتبط، مرتب بر اساس Card_No
        query = f"""
            SELECT
                {q(mapping.card_lookup_id_column)} AS {q("LookupId")},
                {q(mapping.card_lookup_desc_column)} AS {q("LookupTitle")},
                {q(mapping.card_lookup_action_id_column)} AS {q("LinkedActionId")}
            FROM {q(mapping.card_lookup_table_name)}
            {where_sql}
            ORDER BY {q(mapping.card_lookup_id_column)} ASC
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with _dict_cursor(connection, conn.db_type) as cur:
            cur.execute(query, params)
            return list(cur.fetchall())
    finally:
        connection.close()


def _select_requests_sync(conn: SiteConnection, mapping: LeaveRequestMapping, where_sql: str, params: dict) -> list[dict]:
    """
    ورودی: اتصال، نگاشت، شرط WHERE (با نام ستون‌های Quote‌شده) و پارامترهایش.
    ردیف‌های WF_Requests مطابق شرط (به‌علاوه فیلتر شعبه سایت) را می‌خواند و با
    نام‌های ثابت (RequestId، EmpNo، StartDate، ...) مستقل از نگاشت برمی‌گرداند، جدیدترین اول.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    branch_sql, branch_params = _branch_filter_sql(q, mapping)
    # ستون AcceptCode (وضعیت اعمال در کاراوب؛ ۲۲ = ابطال‌شده) فقط اگر نگاشت شده باشد خوانده می‌شود
    names = KaraNames(mapping)
    accept_sql = (
        f"{q(names.raw('wf_requests', 'accept_code'))} AS {q('AcceptCode')}, "
        if names.has("wf_requests", "accept_code")
        else ""
    )
    connection = _connect(conn)
    try:
        # همه ستون‌های درخواست با نام مستعار ثابت؛ ActionId فقط اگر نگاشت شده باشد
        query = f"""
            SELECT
                {accept_sql}{q(mapping.request_id_column)} AS {q("RequestId")},
                {q(mapping.emp_no_column)} AS {q("EmpNo")},
                {q(mapping.submitting_date_column)} AS {q("SubmittingDate")},
                {q(mapping.start_date_column)} AS {q("StartDate")},
                {q(mapping.end_date_column)} AS {q("EndDate")},
                {q(mapping.start_hour_column)} AS {q("StartHour")},
                {q(mapping.end_hour_column)} AS {q("EndHour")},
                {q(mapping.duration_column)} AS {q("Duration")},
                {q(mapping.is_final_approved_column)} AS {q("IsFinalApproved")},
                {q(mapping.approval_by_manager_column)} AS {q("ApprovalByManagerEmpNo")},
                {q(mapping.approval_date_column)} AS {q("ApprovalDate")},
                {q(mapping.operations_id_column)} AS {q("OperationsID")},
                {q(mapping.description_column)} AS {q("Description")},
                {q(mapping.cur_emp_no_column)} AS {q("CurEmpNo")},
                {q(mapping.manager_idea_column)} AS {q("ManagerIdea")},
                {q(mapping.source_column)} AS {q("Source")},
                {q(mapping.destination_column)} AS {q("Distination")},
                {q(mapping.card_no_column)} AS {q("CardNo")}{(", " + q(mapping.action_id_column) + " AS " + q("ActionId")) if mapping.action_id_column else ""}
            FROM {q(mapping.table_name)}
            WHERE {where_sql} {branch_sql}
            ORDER BY {q(mapping.request_id_column)} DESC
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with _dict_cursor(connection, conn.db_type) as cur:
            cur.execute(query, {**params, **branch_params})
            return list(cur.fetchall())
    finally:
        connection.close()


def _insert_review_sync(
    conn: SiteConnection,
    mapping: LeaveRequestMapping,
    request_id: int,
    reviewed_emp_no: int,
    description: str,
    review_type: int,
) -> None:
    """
    ورودی: اتصال، نگاشت، شناسه درخواست، کد پرسنلی تأییدکننده، متن نظر و نوع Review.
    یک ردیف در WF_Reviews درج می‌کند - نظر واقعی تأییدکننده آنجا ذخیره می‌شود،
    نه در WF_Requests.ManagerIdea (یک ردیف به‌ازای هر تصمیم).
    اگر جدول WF_Reviews برای این سایت نگاشت نشده باشد، بدون خطا کاری نمی‌کند.
    """
    if not mapping.wf_reviews_table_name:
        return
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            # ستون‌های WF_Reviews به ترتیبی که مقادیر پایین ساخته می‌شوند
            columns = [
                mapping.wf_reviews_request_id_column,
                mapping.wf_reviews_reviewed_emp_no_column,
                mapping.wf_reviews_description_column,
                mapping.wf_reviews_type_column,
                mapping.wf_reviews_date_column,
                mapping.wf_reviews_show_to_personal_column,
            ]
            # ReviewDate فقط تاریخ است (ساعت 00:00:00) - مثل رکوردهایی که خودِ کاراوب می‌سازد
            today = kara_wb.kara_now()
            review_date = datetime(today.year, today.month, today.day)
            values = [request_id, reviewed_emp_no, description, review_type, review_date, True]  # آخری: ShowToPersonal
            columns_sql = ", ".join(q(c) for c in columns)
            placeholders = ", ".join(f"%({i})s" for i in range(len(columns)))
            params = {str(i): v for i, v in enumerate(values)}
            query = f"INSERT INTO {q(mapping.wf_reviews_table_name)} ({columns_sql}) VALUES ({placeholders})"  # noqa: S608
            cur.execute(query, params)
            connection.commit()
    finally:
        connection.close()


def _update_review_description_sync(
    conn: SiteConnection, mapping: LeaveRequestMapping, request_id: int, description: str
) -> bool:
    """
    ورودی: اتصال، نگاشت، شناسه درخواست و متن جدید نظر. متن Description آخرین
    ردیف WF_Reviews همان درخواست را به‌روز می‌کند (همان ردیفی که برای نمایش خوانده می‌شود).
    خروجی True یعنی ردیفی به‌روز شد؛ False یعنی Review ای وجود نداشت یا جدول نگاشت نشده
    (فراخوان در این حالت باید یک ردیف جدید درج کند).
    """
    if not mapping.wf_reviews_table_name:
        return False
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            # فقط آخرین Review به‌روز می‌شود - نه همه‌ی تاریخچه تصمیم‌ها
            names = KaraNames(mapping)
            if names.has("wf_reviews", "id"):
                # ستون شناسه نگاشت شده: ردیف با بیشترین شناسه برای این درخواست
                id_col = q(names.raw("wf_reviews", "id"))
                query = f"""
                    UPDATE {q(mapping.wf_reviews_table_name)}
                    SET {q(mapping.wf_reviews_description_column)} = %(description)s
                    WHERE {id_col} = (
                        SELECT MAX({id_col}) FROM {q(mapping.wf_reviews_table_name)}
                        WHERE {q(mapping.wf_reviews_request_id_column)} = %(request_id)s
                    )
                """  # noqa: S608
            else:
                # ستون شناسه نظر نگاشت نشده: همه نظرهای همین درخواست به‌روز می‌شوند
                query = f"""
                    UPDATE {q(mapping.wf_reviews_table_name)}
                    SET {q(mapping.wf_reviews_description_column)} = %(description)s
                    WHERE {q(mapping.wf_reviews_request_id_column)} = %(request_id)s
                """  # noqa: S608
            cur.execute(query, {"description": description, "request_id": request_id})
            updated = cur.rowcount  # تعداد ردیف‌های تغییرکرده
            connection.commit()
            return updated > 0
    finally:
        connection.close()


def _select_latest_reviews_sync(
    conn: SiteConnection, mapping: LeaveRequestMapping, request_ids: list[int]
) -> dict[int, str]:
    """
    ورودی: اتصال، نگاشت و لیست شناسه درخواست‌ها. آخرین نظر ثبت‌شده در WF_Reviews
    برای هر درخواست را می‌خواند و دیکشنری {RequestId: Description} برمی‌گرداند
    (ممکن است چند نظر پشت‌سرهم ثبت شده باشد؛ فقط آخرین مهم است).
    اگر جدول نگاشت نشده یا لیست خالی باشد، دیکشنری خالی - تا سرویس به ManagerIdea خام برگردد.
    """
    if not mapping.wf_reviews_table_name or not request_ids:
        return {}
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        with _dict_cursor(connection, conn.db_type) as cur:
            # یک placeholder نام‌دار به‌ازای هر شناسه برای عبارت IN
            id_placeholders = ", ".join(f"%(id{i})s" for i in range(len(request_ids)))
            params = {f"id{i}": rid for i, rid in enumerate(request_ids)}
            # همه نظرهای این درخواست‌ها (انتخاب آخرین نظر در پایتون انجام می‌شود)
            query = f"""
                SELECT
                    {q(mapping.wf_reviews_request_id_column)} AS {q("RequestId")},
                    {q(mapping.wf_reviews_description_column)} AS {q("Description")},
                    {q(mapping.wf_reviews_date_column)} AS {q("ReviewDate")}
                FROM {q(mapping.wf_reviews_table_name)}
                WHERE {q(mapping.wf_reviews_request_id_column)} IN ({id_placeholders})
            """  # noqa: S608
            cur.execute(query, params)
            rows = list(cur.fetchall())
    finally:
        connection.close()

    # برای هر درخواست، نظری با جدیدترین ReviewDate نگه داشته می‌شود (تاریخ تساوی یا خالی: ردیف بعدی برنده است)
    latest: dict[int, tuple] = {}
    for row in rows:
        rid = row.get("RequestId")
        review_date = row.get("ReviewDate")
        if rid is None:
            continue
        if rid not in latest or (review_date or datetime.min) >= (latest[rid][1] or datetime.min):
            latest[rid] = (row.get("Description"), review_date)
    return {rid: desc for rid, (desc, _) in latest.items() if desc is not None}  # نظرهای خالی حذف می‌شوند


def _insert_request_sync(conn: SiteConnection, mapping: LeaveRequestMapping, values: dict) -> int:
    """
    ورودی: اتصال، نگاشت و دیکشنری مقادیر با کلیدهای منطقی (emp_no، start_date، duration، ...).
    یک ردیف جدید در WF_Requests درج می‌کند و شناسه (RequestId) ردیف جدید را برمی‌گرداند؛
    روش گرفتن شناسه برای هر نوع دیتابیس متفاوت است.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    # نگاشت نام ستون واقعی -> مقدار؛ ستون‌های اختیاری پایین‌تر اضافه می‌شوند
    column_map = {
        mapping.emp_no_column: values["emp_no"],
        mapping.submitting_date_column: values["submitting_date"],
        mapping.card_no_column: values.get("card_no", 0),  # Card_No از جدول Cards؛ پیش‌فرض ۰ اگر نوع درخواست مقداری نداشته باشد
        mapping.start_date_column: values["start_date"],
        mapping.end_date_column: values.get("end_date"),
        mapping.start_hour_column: values.get("start_hour"),
        mapping.end_hour_column: values.get("end_hour"),
        mapping.duration_column: str(values["duration"]),
        mapping.operations_id_column: values["operations_id"],
        mapping.description_column: values["description"],
        mapping.cur_emp_no_column: values["cur_emp_no"],
        mapping.is_first_time_shift_column: False,  # همیشه False نوشته می‌شود
        mapping.persian_start_date_column: values["persian_start_date"],
        mapping.application_id_column: mapping.application_id_value,
    }
    # کد شعبه فقط اگر ستونش نگاشت شده و مقداری برای این سایت داریم
    if mapping.branch_code_column and _effective_branch(mapping) is not None:
        column_map[mapping.branch_code_column] = _effective_branch(mapping)
    # مبدأ/مقصد فقط برای ماموریت
    if values.get("source") is not None:
        column_map[mapping.source_column] = values["source"]
    if values.get("destination") is not None:
        column_map[mapping.destination_column] = values["destination"]
    # ActionId اختیاری است: فقط اگر هم ستونش نگاشت شده و هم نوع درخواست مقداری داشته باشد
    if mapping.action_id_column and values.get("action_id") is not None:
        column_map[mapping.action_id_column] = values["action_id"]
    # ستون‌هایی که خودِ کاراوب هنگام ثبت پر می‌کند (از kara_attendance_writeback.submit_extra_columns)
    for extra_column, extra_value in (values.get("extra_columns") or {}).items():
        column_map[extra_column] = extra_value

    # ساخت بخش ستون‌ها و placeholderهای نام‌دار (0، 1، 2، ...)
    columns_sql = ", ".join(q(col) for col in column_map)
    placeholders = ", ".join(f"%({i})s" for i in range(len(column_map)))
    params = {str(i): val for i, val in enumerate(column_map.values())}

    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            # درج و گرفتن شناسه ردیف جدید، به روش مخصوص هر دیتابیس
            if conn.db_type == DbType.postgresql:
                query = (
                    f"INSERT INTO {q(mapping.table_name)} ({columns_sql}) VALUES ({placeholders}) "
                    f"RETURNING {q(mapping.request_id_column)}"
                )  # noqa: S608
                cur.execute(query, params)
                new_id = cur.fetchone()[0]
            elif conn.db_type == DbType.mssql:
                query = (
                    f"INSERT INTO {q(mapping.table_name)} ({columns_sql}) "
                    f"OUTPUT INSERTED.{q(mapping.request_id_column)} VALUES ({placeholders})"
                )  # noqa: S608
                cur.execute(query, params)
                new_id = cur.fetchone()[0]
            else:  # mysql
                query = f"INSERT INTO {q(mapping.table_name)} ({columns_sql}) VALUES ({placeholders})"  # noqa: S608
                cur.execute(query, params)
                new_id = cur.lastrowid  # شناسه AUTO_INCREMENT آخرین درج
            connection.commit()
            return int(new_id)
    finally:
        connection.close()


def _update_request_sync(
    conn: SiteConnection, mapping: LeaveRequestMapping, request_id: int, updates: dict
) -> None:
    """
    ورودی: اتصال، نگاشت، شناسه درخواست و دیکشنری {نام ستون واقعی: مقدار جدید}.
    ستون‌های داده‌شده‌ی همان ردیف WF_Requests را (محدود به شعبه سایت) به‌روز می‌کند.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    branch_sql, branch_params = _branch_filter_sql(q, mapping)
    # ساخت بخش SET با placeholderهای شماره‌ای
    set_clauses = ", ".join(f"{q(col)} = %({i})s" for i, col in enumerate(updates))
    params = {str(i): val for i, val in enumerate(updates.values())}
    params["request_id"] = request_id
    params.update(branch_params)

    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            # به‌روزرسانی فقط ردیف با این شناسه (و شعبه)
            query = (
                f"UPDATE {q(mapping.table_name)} SET {set_clauses} "
                f"WHERE {q(mapping.request_id_column)} = %(request_id)s {branch_sql}"
            )  # noqa: S608
            cur.execute(query, params)
            connection.commit()
    finally:
        connection.close()


def _delete_dependent_rows_sync(conn: SiteConnection, mapping: LeaveRequestMapping, request_id: int) -> None:
    """
    ورودی: اتصال، نگاشت و شناسه درخواست. همه ردیف‌های وابسته به این درخواست را
    در چهار جدول فرزند حذف می‌کند تا حذف خودِ درخواست با خطای Foreign Key
    (ON DELETE NO_ACTION) شکست نخورد:

        WF_Reviews                  (نظر تأییدکننده)
        WF_Attachment               (پیوست فایل)
        WF_MoveUp                   (صعود خودکار زمانی / ارجاع)
        WF_RequestParallelApproval  (تأیید موازی)

    هر جدولی که نامش نگاشت نشده باشد بدون خطا رد می‌شود (نصب‌های بدون آن جدول).
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    names = KaraNames(mapping)
    # (نام جدول، ستون شناسه درخواست) برای هر جدول فرزند؛ مقدار False یعنی ستون نگاشت نشده
    targets = [
        (mapping.wf_reviews_table_name, mapping.wf_reviews_request_id_column),
        (mapping.wf_attachment_table_name, names.has("wf_attachment", "request_id") and names.raw("wf_attachment", "request_id")),
        (mapping.wf_moveup_table_name, names.has("wf_moveup", "request_id") and names.raw("wf_moveup", "request_id")),
        (
            mapping.wf_parallel_approval_table_name,
            names.has("wf_parallel", "request_id") and names.raw("wf_parallel", "request_id"),
        ),
    ]
    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            # حذف ردیف‌های این درخواست از هر جدول فرزندِ نگاشت‌شده، همه در یک تراکنش
            for table_name, id_column in targets:
                if not table_name or not id_column:
                    continue  # جدول یا ستون نگاشت نشده
                query = (
                    f"DELETE FROM {q(table_name)} WHERE {q(id_column)} = %(request_id)s"
                )  # noqa: S608
                cur.execute(query, {"request_id": request_id})
            connection.commit()
    finally:
        connection.close()


def _delete_request_sync(conn: SiteConnection, mapping: LeaveRequestMapping, request_id: int) -> None:
    """ورودی: اتصال، نگاشت و شناسه درخواست. خودِ ردیف WF_Requests را (محدود به شعبه سایت) حذف می‌کند؛ بررسی مجوز حذف در لایه سرویس انجام شده است."""
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    branch_sql, branch_params = _branch_filter_sql(q, mapping)
    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            # حذف ردیف با این شناسه (و شعبه)
            query = (
                f"DELETE FROM {q(mapping.table_name)} "
                f"WHERE {q(mapping.request_id_column)} = %(request_id)s {branch_sql}"
            )  # noqa: S608
            cur.execute(query, {"request_id": request_id, **branch_params})
            connection.commit()
    finally:
        connection.close()


def _run_kara_writeback_sync(conn: SiteConnection, names: KaraNames, fn, *args):
    """
    ورودی: اتصال، نام‌های کاراوب، یک تابع از kara_attendance_writeback و آرگومان‌هایش.
    تابع را با یک Cursor دیکشنری (فقط SQL Server) در یک تراکنش واحد اجرا می‌کند
    (همه یا هیچ) و نتیجه‌اش را برمی‌گرداند؛ در صورت خطا Rollback می‌کند و خطا را بالا می‌فرستد.
    """
    connection = _connect(conn)
    try:
        with connection.cursor(as_dict=True) as cur:
            result = fn(cur, names, *args)
        connection.commit()
        return result
    except Exception:
        connection.rollback()  # هیچ تغییر نیمه‌کاره‌ای در کاراوب نماند
        raise
    finally:
        connection.close()


def _to_personnel_code_int(employee: Employee) -> int:
    """کد پرسنلی (رشته) پرسنل را به عدد Emp_No کاراوب تبدیل می‌کند؛ اگر عددی نباشد خطای قابل نمایش می‌دهد."""
    try:
        return int(employee.personnel_code)
    except (TypeError, ValueError) as e:
        raise LeaveRequestError("کد پرسنلی این کارمند عددی نیست - ثبت درخواست مرخصی/ماموریت برایش ممکن نیست") from e


# اعلان Push در پس‌زمینه و با Session جداگانه ارسال می‌شود تا پاسخ HTTP منتظر
# سرویس Push مرورگر (که ممکن است کند یا در دسترس نباشد) نماند.
# نگه‌داشتن ارجاع Taskها تا قبل از اتمام توسط GC جمع نشوند.
_background_push_tasks: set = set()


def _schedule_push(site_id: int, emp_no: int, url: str, body: str) -> None:
    """ورودی: سایت، کد پرسنلی گیرنده، آدرس مقصد و متن. ارسال Push را به‌صورت Task پس‌زمینه زمان‌بندی می‌کند و فوراً برمی‌گردد."""
    task = asyncio.create_task(_send_push_to_emp_no(site_id, emp_no, url, body))
    _background_push_tasks.add(task)
    task.add_done_callback(_background_push_tasks.discard)  # پس از اتمام، از مجموعه حذف شود


async def _send_push_to_emp_no(site_id: int, emp_no: int, url: str, body: str) -> None:
    """
    ورودی: سایت، کد پرسنلی، آدرس و متن. کاربر پورتال متناظر با این کد پرسنلی را
    پیدا می‌کند و اعلان Push را با حداکثر ۶۰ ثانیه انتظار می‌فرستد.
    هر خطایی فقط لاگ می‌شود؛ اگر کاربری با این کد نباشد، کاری نمی‌کند.
    """
    from app.db.session import AsyncSessionLocal  # import محلی برای جلوگیری از import حلقه‌ای

    try:
        async with AsyncSessionLocal() as db:
            # کاربر متصل به پرسنلی با این کد در همین سایت
            result = await db.execute(
                select(User)
                .join(Employee, Employee.id == User.employee_id)
                .where(Employee.site_id == site_id, Employee.personnel_code == str(emp_no))
            )
            user = result.scalar_one_or_none()
            if user is None:
                return  # پرسنل حساب کاربری ندارد
            # سقف زمانی، چون webpush خودش Timeout ندارد
            await asyncio.wait_for(
                PushService(db).notify_users({user.id}, url=url, priority="normal", body=body),
                timeout=60,
            )
    except Exception:
        logger.exception("ارسال Push درخواست مرخصی/ماموریت با خطا مواجه شد")


MODULE_DISABLED_MESSAGE = "درخواست مرخصی/ماموریت در حال حاضر غیرفعال است"


class LeaveRequestService:
    """
    سرویس اصلی درخواست مرخصی/ماموریت. ورودی: Session دیتابیس پورتال.
    نگاشت و اتصال هر سایت را از پورتال می‌خواند و عملیات روی WF_Requests کاراوب
    را از طریق توابع همگام سطح ماژول (در Thread جداگانه) انجام می‌دهد.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_mapping_and_connection(
        self, site_id: int, *, user_facing: bool = False
    ) -> tuple[LeaveRequestMapping, SiteConnection]:
        """
        ورودی: شناسه سایت. نگاشت مرخصی/ماموریت و اتصال فعال دیتابیس منبع سایت را
        برمی‌گرداند؛ اگر هرکدام تنظیم نباشد خطا می‌دهد.
        user_facing=True برای عملیات پرسنل/سرپرست (ثبت، حذف، لیست‌ها، تصمیم) -
        اگر ماژول برای این سایت از پنل ادمین غیرفعال شده باشد خطا می‌دهد؛
        عملیات مدیریتی (لیست همه، ویرایش ادمین، Lookupها) با غیرفعال بودن هم کار می‌کنند.
        """
        # نگاشت جدول WF_Requests این سایت
        mapping_result = await self.db.execute(select(LeaveRequestMapping).where(LeaveRequestMapping.site_id == site_id))
        mapping = mapping_result.scalar_one_or_none()
        if mapping is None:
            raise LeaveRequestError("قابلیت درخواست مرخصی/ماموریت برای این سایت هنوز تنظیم نشده است")
        if user_facing and mapping.is_disabled:
            raise LeaveRequestError(MODULE_DISABLED_MESSAGE)

        # اتصال دیتابیس منبع سایت (باید فعال باشد)
        conn_result = await self.db.execute(select(SiteConnection).where(SiteConnection.site_id == site_id))
        site_connection = conn_result.scalar_one_or_none()
        if site_connection is None or not site_connection.is_active:
            raise LeaveRequestError("اتصال دیتابیس این سایت تنظیم یا فعال نیست")
        # چند سایت روی یک کاراوب: «کد شعبه این سایت» از نگاشت پرسنل روی نمونه گذاشته می‌شود
        # (ویژگی غیرنگاشت‌شده، ذخیره نمی‌شود) تا هر سایت فقط درخواست‌های شعبه خودش را ببیند
        # و درخواست/کارکردش با شعبه درست ثبت شود؛ _effective_branch از آن استفاده می‌کند.
        mapping._site_branch = site_branch.as_int(await site_branch.get_site_branch_value(self.db, site_id))
        return mapping, site_connection

    async def _get_kara_names(self, site_id: int, mapping: LeaveRequestMapping, site_connection) -> KaraNames | None:
        """
        ورودی: شناسه سایت، نگاشت مرخصی و اتصال. نام‌های جدول/ستون کاراوب را از دو
        نگاشت همین سایت (مرخصی/ماموریت + تردد) به‌صورت KaraNames برمی‌گرداند.
        فقط برای SQL Server؛ در غیر این صورت None (هیچ اثری در کارکرد کاراوب اعمال نمی‌شود).
        اینکه کدام بخش واقعاً اجرا شود را خودِ KaraNames بر اساس نگاشت‌شدن جدول‌ها تعیین می‌کند.
        """
        if site_connection.db_type != DbType.mssql:
            return None
        # نگاشت تردد همین سایت (ممکن است نباشد)
        attendance = (
            await self.db.execute(select(AttendanceMapping).where(AttendanceMapping.site_id == site_id))
        ).scalar_one_or_none()
        return KaraNames(mapping, attendance)

    async def _get_approver_employee_id(self, department_id: int | None) -> int | None:
        """ورودی: شناسه واحد. شناسه پرسنلِ تأییدکننده‌ی دستی آن واحد (LeaveRequestApprover) را برمی‌گرداند؛ اگر تعیین نشده None."""
        if department_id is None:
            return None
        # تخصیص دستی تأییدکننده به واحد
        result = await self.db.execute(
            select(LeaveRequestApprover.approver_employee_id).where(
                LeaveRequestApprover.department_id == department_id
            )
        )
        return result.scalar_one_or_none()

    async def _resolve_approver_emp_no(self, employee: Employee, mapping, site_connection) -> int:
        """
        ورودی: پرسنل درخواست‌دهنده، نگاشت و اتصال. کد پرسنلی سرپرست (تأییدکننده اول)
        را برمی‌گرداند: اول از زنجیره سازمانی کاراوب (Employee.Sec_No -> Sections.ManagerEmp_No)؛
        اگر جواب نداد (جدول‌ها تنظیم نشده، پرسنل/بخش پیدا نشد یا خطای دیتابیس)،
        از تخصیص دستی LeaveRequestApprover. اگر هیچ‌کدام نبود خطا می‌دهد.
        """
        # روش اول: زنجیره سازمانی کاراوب؛ هر خطایی به Fallback می‌رسد
        try:
            cur_emp_no = await asyncio.to_thread(
                _resolve_manager_emp_no_sync, site_connection, mapping, _to_personnel_code_int(employee)
            )
        except Exception:
            cur_emp_no = None
        if cur_emp_no is not None:
            return cur_emp_no
        # روش دوم: تأییدکننده دستی واحد پرسنل
        approver_employee_id = await self._get_approver_employee_id(employee.department_id)
        if approver_employee_id is None:
            raise LeaveRequestError(
                "نتوانستیم تأییدکننده این پرسنل را (نه از زنجیره سازمانی، نه از تخصیص دستی) پیدا کنیم - "
                "لطفاً با منابع انسانی هماهنگ کنید"
            )
        approver = await self.db.get(Employee, approver_employee_id)
        if approver is None:
            raise LeaveRequestError("تأییدکننده این واحد یافت نشد")
        return _to_personnel_code_int(approver)

    async def _get_hr_officer_emp_no(self, site_id: int) -> int | None:
        """ورودی: شناسه سایت. کد پرسنلی (عددی) مسئول نیروی انسانی سایت (LeaveRequestHrOfficer) را برمی‌گرداند؛ اگر تعیین نشده یا عددی نیست None."""
        # کد پرسنلی مسئول نیروی انسانی این سایت
        result = await self.db.execute(
            select(Employee.personnel_code)
            .join(LeaveRequestHrOfficer, LeaveRequestHrOfficer.employee_id == Employee.id)
            .where(LeaveRequestHrOfficer.site_id == site_id)
        )
        code = result.scalar_one_or_none()
        return int(code) if code and str(code).isdigit() else None

    async def _get_forgotten_context(self, site_id: int) -> tuple[set, int | None]:
        """ورودی: شناسه سایت. خروجی: (مجموعه Card_No های نوع‌های «تردد فراموش‌شده»، کد پرسنلی مسئول نیروی انسانی)."""
        # Card_No نوع‌های تردد فراموش‌شده - برای تشخیص این نوع از روی ردیف خام
        result = await self.db.execute(
            select(LeaveRequestType.card_no).where(
                LeaveRequestType.site_id == site_id,
                LeaveRequestType.is_forgotten_punch.is_(True),
                LeaveRequestType.card_no.is_not(None),
            )
        )
        cards = {int(c) for c in result.scalars().all()}
        return cards, await self._get_hr_officer_emp_no(site_id)

    @staticmethod
    def _annotate_stage(items: list[dict], hr_emp_no: int | None) -> None:
        """ورودی: لیست درخواست‌های نرمال‌شده و کد پرسنلی مسئول نیروی انسانی. کلید awaiting_hr را روی هر مورد می‌گذارد (درجا): تردد فراموش‌شده‌ی در انتظار تأیید نهایی منابع انسانی."""
        # در انتظار منابع انسانی = تردد فراموش‌شده، هنوز pending و تأییدکننده فعلی همان مسئول HR
        for item in items:
            item["awaiting_hr"] = bool(
                item.get("is_forgotten_punch")
                and item.get("status") == "pending"
                and hr_emp_no is not None
                and item.get("current_approver_emp_no") == hr_emp_no
            )

    async def _submit_forgotten_punches(
        self, employee: Employee, leave_type: LeaveRequestType, punches: list, description: str
    ) -> dict:
        """
        ورودی: پرسنل، نوع درخواست (از نوع تردد فراموش‌شده)، لیست ترددها (هر کدام
        kind ورود/خروج، punch_date و time فشرده) و توضیحات.
        به‌ازای هر تردد یک ردیف درخواست جداگانه در WF_Requests ثبت می‌کند (مثل کاراوب)
        و به سرپرست اعلان می‌دهد؛ خروجی {"request_id": اولی, "request_ids": همه}.
        گردش کار: اول سرپرست تأیید می‌کند، بعد مسئول نیروی انسانی؛ در پایان تردد در کاراوب درج می‌شود.
        """
        # اعتبارسنجی ساختار ورودی: یک یا دو تردد، حداکثر یک ورود و یک خروج
        if not punches:
            raise LeaveRequestError("حداقل یکی از ترددهای ورود یا خروج را وارد کنید")
        if len(punches) > 2:
            raise LeaveRequestError("در هر درخواست حداکثر یک ورود و یک خروج قابل‌ثبت است")
        kinds = [p.kind for p in punches if p.kind]
        if any(k not in _PUNCH_LABELS for k in kinds) or len(set(kinds)) != len(kinds):
            raise LeaveRequestError("نوع تردد نامعتبر است (فقط یک ورود و یک خروج)")
        if len(punches) > 1 and len(kinds) != len(punches):
            raise LeaveRequestError("برای هر تردد فراموش‌شده باید یک درخواست جداگانه ثبت شود")

        # پیش‌نیازهای سایت: نگاشت ستون‌های نوشتن تردد در کاراوب و تعیین مسئول نیروی انسانی
        mapping, site_connection = await self._get_mapping_and_connection(employee.site_id, user_facing=True)
        kara_names = await self._get_kara_names(employee.site_id, mapping, site_connection)
        if kara_names is None or not kara_names.can_write_punch:
            raise LeaveRequestError(
                "ثبت تردد فراموش‌شده برای این سایت فعال نیست - ستون‌های تکمیلی جدول تردد و جدول کاربران "
                "باید در تنظیمات سایت نگاشت شوند"
            )
        if await self._get_hr_officer_emp_no(employee.site_id) is None:
            raise LeaveRequestError("مسئول نیروی انسانی این سایت هنوز تعیین نشده - لطفاً با منابع انسانی هماهنگ کنید")

        # اعتبارسنجی زمان هر تردد: ساعت معتبر، نه در آینده، نه قدیمی‌تر از سقف مجاز
        now = kara_wb.kara_now()
        parsed: list[tuple] = []  # (تردد، لحظه datetime، برچسب فارسی)
        for p in punches:
            hour, minute = divmod(int(p.time), 100)  # ساعت فشرده HHMM
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise LeaveRequestError("ساعت تردد نامعتبر است")
            moment = datetime(p.punch_date.year, p.punch_date.month, p.punch_date.day, hour, minute)
            label = _PUNCH_LABELS.get(p.kind or "", "تردد")
            if moment > now:
                raise LeaveRequestError(f"زمان {label} نمی‌تواند در آینده باشد")
            if (now.date() - p.punch_date).days > FORGOTTEN_PUNCH_MAX_PAST_DAYS:
                raise LeaveRequestError(
                    f"ثبت تردد فراموش‌شده فقط تا {FORGOTTEN_PUNCH_MAX_PAST_DAYS} روز گذشته امکان‌پذیر است"
                )
            parsed.append((p, moment, label))
        # اگر هم ورود و هم خروج داده شده، ترتیب و فاصله‌شان بررسی می‌شود
        by_kind = {p.kind: moment for p, moment, _ in parsed if p.kind}
        if "in" in by_kind and "out" in by_kind:
            if by_kind["out"] <= by_kind["in"]:
                raise LeaveRequestError("زمان خروج باید بعد از زمان ورود باشد")
            if (by_kind["out"] - by_kind["in"]).total_seconds() > FORGOTTEN_PUNCH_MAX_SPAN_HOURS * 3600:
                raise LeaveRequestError(f"فاصله ورود تا خروج نمی‌تواند بیش از {FORGOTTEN_PUNCH_MAX_SPAN_HOURS} ساعت باشد")

        # جلوگیری از تکرار: همه درخواست‌های قبلی این پرسنل برای مقایسه
        emp_no = _to_personnel_code_int(employee)
        forgotten_cards, _ = await self._get_forgotten_context(employee.site_id)
        existing = await asyncio.to_thread(
            _select_requests_sync,
            site_connection,
            mapping,
            f"{_quote(site_connection.db_type, mapping.emp_no_column)} = %(emp_no)s",
            {"emp_no": emp_no},
        )
        for p, _, label in parsed:
            jalali = jdatetime.date.fromgregorian(date=p.punch_date)
            date_int = jalali_date_to_compact(jalali.year, jalali.month, jalali.day)
            # تردد با همین تاریخ و ساعت از قبل در جدول تردد کاراوب هست؟
            if await asyncio.to_thread(
                _run_kara_writeback_sync, site_connection, kara_names, kara_wb.punch_exists, emp_no, date_int, int(p.time)
            ):
                raise LeaveRequestError(f"تردد {label} در همین تاریخ و ساعت از قبل در سیستم ثبت شده است")
            # درخواست تردد فراموش‌شده‌ی فعال (در بررسی یا تأییدشده) با همین تاریخ و ساعت هست؟
            for row in existing:
                if (
                    row.get("CardNo") not in forgotten_cards
                    or row.get("IsFinalApproved") is False
                    or row.get("AcceptCode") == kara_wb.ACCEPT_CANCELLED
                ):
                    continue  # نوع دیگر، ردشده یا ابطال‌شده - مانع نیست
                row_date = row.get("StartDate")
                row_date = row_date.date() if hasattr(row_date, "date") else row_date  # datetime -> date
                if row_date == p.punch_date and row.get("StartHour") == int(p.time):
                    raise LeaveRequestError(f"برای تردد {label} در همین تاریخ و ساعت از قبل درخواست ثبت کرده‌اید")

        # تأییدکننده اول (سرپرست) و ستون‌های تکمیلی که کاراوب هنگام ثبت پر می‌کند
        cur_emp_no = await self._resolve_approver_emp_no(employee, mapping, site_connection)
        try:
            extra_columns = await asyncio.to_thread(
                _run_kara_writeback_sync, site_connection, kara_names, kara_wb.submit_extra_columns, emp_no, cur_emp_no, 0
            )
        except Exception as e:
            raise LeaveRequestError(f"خواندن اطلاعات تکمیلی از کاراوب با خطا مواجه شد: {e}") from e

        # درج یک ردیف درخواست به‌ازای هر تردد، به ترتیب زمانی
        request_ids: list[int] = []
        for p, _, label in sorted(parsed, key=lambda item: item[1]):
            jalali = jdatetime.date.fromgregorian(date=p.punch_date)
            text = (description or "").strip()
            values = {
                "emp_no": emp_no,
                "submitting_date": kara_wb.kara_now(),
                "start_date": datetime(p.punch_date.year, p.punch_date.month, p.punch_date.day),
                "end_date": None,  # تردد بازه ندارد
                "start_hour": int(p.time),  # ساعت خودِ تردد
                "end_hour": 0,  # مثل کاراوب
                "duration": 0,
                "operations_id": leave_type.operation_id if leave_type.operation_id is not None else 2,
                # ورود/خروج در خودِ جدول تردد کاراوب ذخیره نمی‌شود - برای تأییدکننده در توضیحات می‌آید
                "description": (f"{label} - {text}" if text else label) if p.kind else text,
                "cur_emp_no": cur_emp_no,
                "persian_start_date": jalali_date_to_compact(jalali.year, jalali.month, jalali.day),
                "action_id": leave_type.action_id,
                "card_no": leave_type.card_no,
                "extra_columns": extra_columns,
            }
            try:
                request_ids.append(await asyncio.to_thread(_insert_request_sync, site_connection, mapping, values))
            except Exception as e:
                raise LeaveRequestError(f"ثبت درخواست در دیتابیس منبع با خطا مواجه شد: {e}") from e

        # یک اعلان به سرپرست برای همه ترددهای این درخواست
        await self._notify_approver_of_new_request(employee.site_id, cur_emp_no)
        return {"request_id": request_ids[0], "request_ids": request_ids}

    async def submit_request(
        self,
        employee: Employee,
        leave_type_id: int,
        start_date: date,
        end_date: date | None,
        start_hour: int | None,
        end_hour: int | None,
        description: str,
        source: str | None = None,
        destination: str | None = None,
        punches: list | None = None,
    ) -> dict:
        """
        ورودی: پرسنل، شناسه نوع درخواست، تاریخ/ساعت شروع و پایان، توضیحات، مبدأ/مقصد
        (ماموریت) و لیست ترددها (تردد فراموش‌شده).
        اعتبارسنجی می‌کند، مدت را محاسبه می‌کند، تداخل با درخواست‌های قبلی را بررسی
        می‌کند، یک ردیف در WF_Requests درج می‌کند و به سرپرست اعلان می‌دهد.
        خروجی: {"request_id": شناسه ردیف جدید}.
        """
        # نوع درخواست باید فعال و متعلق به همین سایت باشد
        leave_type = await self.db.get(LeaveRequestType, leave_type_id)
        if leave_type is None or not leave_type.is_active or leave_type.site_id != employee.site_id:
            raise LeaveRequestError("نوع درخواست موردنظر یافت نشد")
        # Card_No در WF_Requests کلید خارجی به جدول Cards است و مقدار ۰ آنجا وجود ندارد -
        # به‌جای درج مقدار نامعتبر، خطای روشن تا ادمین این نوع را کامل کند
        if leave_type.card_no is None:
            raise LeaveRequestError(
                f"برای نوع «{leave_type.title}» هنوز Card_No تنظیم نشده - لطفاً از تنظیمات "
                "درخواست مرخصی/ماموریت، یک کارت از فهرست رسمی Cards برای این نوع انتخاب کنید"
            )

        # تردد فراموش‌شده گردش کار جداگانه دارد
        if leave_type.is_forgotten_punch:
            return await self._submit_forgotten_punches(employee, leave_type, punches or [], description)

        mapping, site_connection = await self._get_mapping_and_connection(employee.site_id, user_facing=True)
        cur_emp_no = await self._resolve_approver_emp_no(employee, mapping, site_connection)

        # محاسبه مدت: ساعتی (فرمت فشرده HHMM، بدون تاریخ پایان) یا روزانه (تعداد روز)
        try:
            if leave_type.is_hourly:
                if start_hour is None or end_hour is None:
                    raise LeaveRequestRulesError("ساعت شروع و پایان الزامی است")
                duration = compute_hourly_duration(start_hour, end_hour)
                effective_end_date = None
            else:
                if end_date is None:
                    raise LeaveRequestRulesError("تاریخ پایان الزامی است")
                duration = compute_daily_duration(start_date, end_date)
                effective_end_date = end_date
        except LeaveRequestRulesError as e:
            raise LeaveRequestError(str(e)) from e  # تبدیل به خطای قابل نمایش سرویس

        # نباید با درخواست در بررسی/تأییدشده‌ی قبلی هم‌پوشانی داشته باشد
        await self._ensure_no_overlap(
            site_connection, mapping, employee, start_date, effective_end_date, start_hour, end_hour
        )

        # تاریخ شمسی شروع به فرمت عددی YYYYMMDD
        jalali_start = jdatetime.date.fromgregorian(date=start_date)
        persian_start_date = jalali_date_to_compact(jalali_start.year, jalali_start.month, jalali_start.day)

        # مقادیر منطقی ردیف جدید (نگاشت به ستون واقعی در _insert_request_sync)
        values = {
            "emp_no": _to_personnel_code_int(employee),
            "submitting_date": kara_wb.kara_now(),
            "start_date": datetime(start_date.year, start_date.month, start_date.day),
            "end_date": datetime(effective_end_date.year, effective_end_date.month, effective_end_date.day)
            if effective_end_date
            else None,
            "start_hour": start_hour if leave_type.is_hourly else None,  # ساعت‌ها فقط برای نوع ساعتی
            "end_hour": end_hour if leave_type.is_hourly else None,
            "duration": duration,
            "operations_id": leave_type.operation_id if leave_type.operation_id is not None else (3 if leave_type.is_mission else 5),  # پیش‌فرض: ۳ ماموریت، ۵ مرخصی
            "description": description or "",
            "cur_emp_no": cur_emp_no,  # تأییدکننده فعلی
            "persian_start_date": persian_start_date,
            "source": source if leave_type.is_mission else None,  # مبدأ/مقصد فقط برای ماموریت
            "destination": destination if leave_type.is_mission else None,
            "action_id": leave_type.action_id,
            "card_no": leave_type.card_no,  # بالاتر تضمین شد که None نیست
        }

        # ستون‌هایی که کاراوب هنگام ثبت پر می‌کند (SubmittedByEmployeeID، Requested_Time،
        # DutyTools/DutyTamin و CurSection) - فقط برای SQL Server
        kara_names = await self._get_kara_names(employee.site_id, mapping, site_connection)
        if kara_names is not None:
            try:
                values["extra_columns"] = await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_names,
                    kara_wb.submit_extra_columns,
                    values["emp_no"],
                    cur_emp_no,
                    duration,
                )
            except Exception as e:
                raise LeaveRequestError(f"خواندن اطلاعات تکمیلی از کاراوب با خطا مواجه شد: {e}") from e

        # درج ردیف در WF_Requests
        try:
            new_request_id = await asyncio.to_thread(_insert_request_sync, site_connection, mapping, values)
        except LeaveRequestError:
            raise
        except Exception as e:
            # متن خطای خام درایور/Trigger (معمولاً شامل نام ستون یا محدودیت مشکل‌دار) نمایش داده می‌شود تا قابل عیب‌یابی باشد
            raise LeaveRequestError(f"ثبت درخواست در دیتابیس منبع با خطا مواجه شد: {e}") from e

        # اطلاع‌رسانی به تأییدکننده در پس‌زمینه - خطای Push هرگز ثبت درخواست را متوقف نمی‌کند
        await self._notify_approver_of_new_request(employee.site_id, cur_emp_no)

        return {"request_id": new_request_id}

    async def _notify_approver_of_new_request(self, site_id: int, cur_emp_no: int) -> None:
        """ورودی: سایت و کد پرسنلی تأییدکننده. اعلان Push «درخواست در انتظار تصمیم شما» را با لینک به تب کارتابل زمان‌بندی می‌کند."""
        _schedule_push(
            site_id,
            cur_emp_no,
            "/leave-requests?tab=pending",
            "یک درخواست مرخصی/ماموریت در انتظار تصمیم شماست.\n"
            "جهت بررسی روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید.",
        )

    async def _notify_requester_of_forgotten_punch(self, site_id: int, emp_no: int, stage: str) -> None:
        """ورودی: سایت، کد پرسنلی درخواست‌دهنده و مرحله (supervisor / approved / rejected). اعلان Push مرحله‌ی تردد فراموش‌شده را با لینک به تب «درخواست‌های من» زمان‌بندی می‌کند."""
        # متن اعلان هر مرحله
        texts = {
            "supervisor": "درخواست تردد فراموش‌شده شما توسط سرپرست تأیید شد و برای تأیید نهایی به منابع انسانی ارسال شد.",
            "approved": "درخواست تردد فراموش‌شده شما توسط منابع انسانی تأیید و در سیستم حضور و غیاب ثبت شد.",
            "rejected": "درخواست تردد فراموش‌شده شما رد شد.",
        }
        _schedule_push(
            site_id,
            emp_no,
            "/leave-requests?tab=my-requests",
            texts[stage] + "\nجهت مشاهده جزئیات روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید.",
        )

    async def _notify_requester_of_decision(self, site_id: int, emp_no: int) -> None:
        """ورودی: سایت و کد پرسنلی درخواست‌دهنده. اعلان Push «درخواست شما بررسی شد» را با لینک به تب «درخواست‌های من» زمان‌بندی می‌کند."""
        _schedule_push(
            site_id,
            emp_no,
            "/leave-requests?tab=my-requests",
            "درخواست مرخصی/ماموریت شما بررسی شد.\n"
            "جهت مشاهده نتیجه روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید.",
        )

    # ---------- خواندن/نمایش ----------

    async def _get_type_lookup(self, site_id: int) -> dict:
        """
        ورودی: شناسه سایت. دیکشنری {(OperationsID, ActionId, Card_No): (شناسه نوع، عنوان، تردد فراموش‌شده؟)}
        برای همه نوع‌های این سایت برمی‌گرداند. چون WF_Requests شناسه نوع پورتال را ذخیره
        نمی‌کند، تطبیق این سه ستون تنها راه بازشناسی نوع یک درخواست موجود است.
        """
        # همه نوع‌های درخواست این سایت (فعال و غیرفعال، تا درخواست‌های قدیمی هم بازشناسی شوند)
        result = await self.db.execute(select(LeaveRequestType).where(LeaveRequestType.site_id == site_id))
        types = result.scalars().all()
        return {(t.operation_id, t.action_id, t.card_no): (t.id, t.title, t.is_forgotten_punch) for t in types}

    async def _get_requester_info(self, site_id: int, emp_nos: list) -> dict:
        """
        ورودی: شناسه سایت و لیست کدهای پرسنلی (Emp_No خام). دیکشنری
        {کد پرسنلی: {"name": نام کامل, "department": نام واحد}} را از جدول پرسنل پورتال برمی‌گرداند.
        """
        emp_no_strings = [str(e) for e in emp_nos if e is not None]  # personnel_code رشته است
        if not emp_no_strings:
            return {}
        # پرسنل این سایت با این کدها، همراه با واحدشان
        result = await self.db.execute(
            select(Employee)
            .options(selectinload(Employee.department))
            .where(Employee.site_id == site_id, Employee.personnel_code.in_(emp_no_strings))
        )
        employees = result.scalars().all()
        return {
            int(e.personnel_code): {
                "name": f"{e.first_name} {e.last_name}",
                "department": e.department.name if e.department else None,
            }
            for e in employees
            if e.personnel_code.isdigit()  # کد غیرعددی با Emp_No کاراوب تطبیق ندارد
        }

    async def _ensure_no_overlap(
        self,
        site_connection,
        mapping: LeaveRequestMapping,
        employee: Employee,
        start_date: date,
        end_date: date | None,
        start_hour: int | None,
        end_hour: int | None,
    ) -> None:
        """
        ورودی: اتصال، نگاشت، پرسنل و تاریخ/ساعت شروع و پایان درخواست جدید.
        اگر با یکی از درخواست‌های «در حال بررسی» یا «تأییدشده»ی همین فرد هم‌پوشانی
        داشته باشد خطا می‌دهد؛ درخواست ردشده/ابطال‌شده مانع نیست.
        ساعتی: همان روز و هم‌پوشانی بازه ساعت‌ها؛ روزانه: هم‌پوشانی بازه روزها؛
        یک ساعتی و یک روزانه در همان روز هم تداخل محسوب می‌شوند.
        """
        # همه درخواست‌های قبلی این پرسنل
        emp_no = _to_personnel_code_int(employee)
        col = _quote(site_connection.db_type, mapping.emp_no_column)
        rows = await asyncio.to_thread(
            _select_requests_sync, site_connection, mapping, f"{col} = %(emp_no)s", {"emp_no": emp_no}
        )
        new_start = start_date
        new_end = end_date or start_date  # ساعتی: همان یک روز
        forgotten_cards, _ = await self._get_forgotten_context(employee.site_id)

        # مقایسه بازه درخواست جدید با هر درخواست فعال قبلی
        for row in rows:
            if row.get("IsFinalApproved") is False or row.get("AcceptCode") == kara_wb.ACCEPT_CANCELLED:
                continue  # ردشده یا ابطال‌شده - مانع نیست
            if row.get("CardNo") in forgotten_cards:
                continue  # تردد فراموش‌شده بازه زمانی ندارد - با مرخصی/ماموریت تداخل نمی‌کند
            existing_start_raw = row.get("StartDate")
            if not existing_start_raw:
                continue
            existing_start = existing_start_raw.date() if hasattr(existing_start_raw, "date") else existing_start_raw  # datetime -> date
            existing_end_raw = row.get("EndDate")
            existing_end = (  # بدون تاریخ پایان (ساعتی) = همان روز شروع
                (existing_end_raw.date() if hasattr(existing_end_raw, "date") else existing_end_raw)
                if existing_end_raw
                else existing_start
            )
            if new_end < existing_start or new_start > existing_end:
                continue  # هیچ روز مشترکی ندارند

            existing_start_hour = row.get("StartHour")
            # اگر هر دو ساعتی‌اند، فقط وقتی تداخل است که بازه ساعت‌ها هم بریده شوند
            if start_hour is not None and existing_start_hour is not None:
                existing_end_hour = row.get("EndHour")
                if existing_end_hour is None or end_hour is None:
                    raise LeaveRequestError("برای همین بازه زمانی از قبل درخواستی ثبت کرده‌اید")
                if end_hour <= existing_start_hour or start_hour >= existing_end_hour:
                    continue  # بازه ساعت‌ها جدا هستند
            # روز مشترک دارند و (حداقل یکی روزانه است یا ساعت‌ها هم‌پوشانی دارند)
            raise LeaveRequestError("برای همین بازه زمانی از قبل درخواستی ثبت کرده‌اید")

    async def get_pending_count_for_approver(self, approver_employee: Employee) -> int:
        """ورودی: پرسنل تأییدکننده. تعداد درخواست‌های در انتظار تصمیم او را برای شمارنده کارت داشبورد برمی‌گرداند؛ اگر ماژول برای سایت تنظیم نیست، صفر."""
        try:
            pending = await self.list_pending_for_approver(approver_employee)
        except LeaveRequestError:
            # اگر این سایت اصلاً نگاشت مرخصی/ماموریت ندارد، شمارنده صفر است - نه خطا
            return 0
        return len(pending)

    async def delete_request(self, request_id: int, employee: Employee) -> None:
        """
        ورودی: شناسه درخواست و پرسنل. درخواست را حذف می‌کند - فقط اگر متعلق به
        خودِ همین فرد باشد و هنوز تصمیم‌گیری نشده باشد (IsFinalApproved هنوز NULL)؛
        در غیر این صورت خطا می‌دهد.
        """
        # خواندن ردیف درخواست
        mapping, site_connection = await self._get_mapping_and_connection(employee.site_id, user_facing=True)
        request_id_col = _quote(site_connection.db_type, mapping.request_id_column)
        rows = await asyncio.to_thread(
            _select_requests_sync,
            site_connection,
            mapping,
            f"{request_id_col} = %(request_id)s",
            {"request_id": request_id},
        )
        if not rows:
            raise LeaveRequestError("درخواست موردنظر یافت نشد")
        request_row = rows[0]
        # بررسی مالکیت و وضعیت
        emp_no = _to_personnel_code_int(employee)
        if request_row.get("EmpNo") != emp_no:
            raise LeaveRequestError("شما مجاز به حذف این درخواست نیستید")
        if request_row.get("IsFinalApproved") is not None:
            raise LeaveRequestError("این درخواست قبلاً تصمیم‌گیری شده - دیگر قابل‌حذف نیست")
        # اول ردیف‌های وابسته (مثلاً ردیف ارجاع و نظر سرپرستِ یک تردد فراموش‌شده‌ی
        # هنوز در بررسی) حذف می‌شوند، وگرنه کلید خارجی جلوی حذف درخواست را می‌گیرد
        await asyncio.to_thread(_delete_dependent_rows_sync, site_connection, mapping, request_id)
        await asyncio.to_thread(_delete_request_sync, site_connection, mapping, request_id)

    async def admin_delete_request(self, site_id: int, request_id: int) -> None:
        """
        ورودی: شناسه سایت و شناسه درخواست. حذف مدیریتی (مجوز leave_requests.manage):
        هر درخواستی در هر مرحله‌ای (در بررسی، تأییدشده، ردشده) حذف می‌شود.
        اگر تأییدشده بود، اثرش در کارکرد کاراوب هم برداشته می‌شود؛ سپس ردیف‌های
        جدول‌های وابسته و در پایان خودِ درخواست حذف می‌شوند.
        """
        # خواندن ردیف درخواست
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        request_id_col = _quote(site_connection.db_type, mapping.request_id_column)
        rows = await asyncio.to_thread(
            _select_requests_sync,
            site_connection,
            mapping,
            f"{request_id_col} = %(request_id)s",
            {"request_id": request_id},
        )
        if not rows:
            raise LeaveRequestError("درخواست موردنظر یافت نشد")

        # برداشتن اثر تأیید در کارکرد کاراوب (تردد علامت‌خورده یا ردیف Mor_Mam)
        # و پاک کردن WF_RequestState (که کلید خارجی ندارد و باید دستی حذف شود)
        kara_names = await self._get_kara_names(site_id, mapping, site_connection)
        if kara_names is not None:
            # ابطال‌شده در کاراوب: اثرش را خودِ کاراوب برداشته است
            if rows[0].get("IsFinalApproved") and rows[0].get("AcceptCode") != kara_wb.ACCEPT_CANCELLED:
                forgotten_cards, _ = await self._get_forgotten_context(site_id)
                await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_names,
                    kara_wb.revert_forgotten_punch if rows[0].get("CardNo") in forgotten_cards else kara_wb.revert_effects,  # تابع برگشت بر اساس نوع
                    rows[0],
                    None,
                    mapping.application_id_value,
                )
            await asyncio.to_thread(
                _run_kara_writeback_sync, site_connection, kara_names, kara_wb.delete_request_state_rows, request_id
            )

        # اول وابسته‌ها، بعد خودِ درخواست (کلیدهای خارجی NO_ACTION)
        await asyncio.to_thread(_delete_dependent_rows_sync, site_connection, mapping, request_id)
        await asyncio.to_thread(_delete_request_sync, site_connection, mapping, request_id)

    async def list_my_requests(self, employee: Employee) -> list[dict]:
        """ورودی: پرسنل. همه درخواست‌های خودِ او را (جدیدترین اول) به‌صورت نرمال‌شده، با نظر واقعی تأییدکننده و پرچم awaiting_hr برمی‌گرداند."""
        # درخواست‌های این پرسنل از WF_Requests
        mapping, site_connection = await self._get_mapping_and_connection(employee.site_id, user_facing=True)
        emp_no = _to_personnel_code_int(employee)
        col = _quote(site_connection.db_type, mapping.emp_no_column)
        rows = await asyncio.to_thread(
            _select_requests_sync, site_connection, mapping, f"{col} = %(emp_no)s", {"emp_no": emp_no}
        )
        # نرمال‌سازی و تکمیل با نوع، نظر واقعی و مرحله
        type_lookup = await self._get_type_lookup(employee.site_id)
        normalized = [_normalize_row(row, type_lookup) for row in rows]
        await self._apply_real_reviews(site_connection, mapping, normalized)
        self._annotate_stage(normalized, await self._get_hr_officer_emp_no(employee.site_id))
        return normalized

    async def _apply_real_reviews(self, site_connection, mapping, normalized: list[dict]) -> None:
        """
        ورودی: اتصال، نگاشت و لیست درخواست‌های نرمال‌شده. مقدار manager_idea
        درخواست‌های تصمیم‌گرفته‌شده را (درجا) با آخرین نظر واقعی از WF_Reviews جایگزین می‌کند.
        اگر جدول نگاشت نشده یا نظری ثبت نشده باشد، مقدار خام ManagerIdea دست‌نخورده می‌ماند.
        """
        # فقط درخواست‌های تصمیم‌گرفته‌شده نظر دارند
        request_ids = [item["request_id"] for item in normalized if item.get("status") != "pending"]
        if not request_ids:
            return
        reviews = await asyncio.to_thread(_select_latest_reviews_sync, site_connection, mapping, request_ids)
        # جایگزینی نظر خام با نظر واقعی، هرجا که وجود دارد
        for item in normalized:
            real_comment = reviews.get(item["request_id"])
            if real_comment is not None:
                item["manager_idea"] = real_comment

    async def list_pending_for_approver(self, approver_employee: Employee) -> list[dict]:
        """ورودی: پرسنل تأییدکننده. درخواست‌های در انتظار تصمیم او (CurEmpNo = او و بدون تصمیم) را نرمال‌شده، با نام/واحد درخواست‌دهنده و پرچم awaiting_hr برمی‌گرداند."""
        # درخواست‌هایی که تأییدکننده فعلی‌شان این فرد است و هنوز تصمیم ندارند
        mapping, site_connection = await self._get_mapping_and_connection(approver_employee.site_id, user_facing=True)
        cur_emp_no = _to_personnel_code_int(approver_employee)
        cur_col = _quote(site_connection.db_type, mapping.cur_emp_no_column)
        approved_col = _quote(site_connection.db_type, mapping.is_final_approved_column)
        where_sql = f"{cur_col} = %(cur_emp_no)s AND {approved_col} IS NULL"
        rows = await asyncio.to_thread(
            _select_requests_sync, site_connection, mapping, where_sql, {"cur_emp_no": cur_emp_no}
        )
        # نرمال‌سازی با نام/واحد/نوع از سایت خودِ درخواست‌دهنده (ممکن است سایت دیگری هم‌منبع باشد)
        normalized = await self._normalize_for_approver(approver_employee, rows)
        await self._annotate_stage_by_requester_site(normalized, approver_employee.site_id)
        return normalized

    async def _same_source_site_ids(self, site_id: int) -> list[int]:
        """
        شناسه‌ی این سایت و همه‌ی سایت‌هایی که به همان دیتابیس منبع وصل‌اند (این سایت اول).
        کارتابل تأییدکننده از همان دیتابیس خوانده می‌شود، پس درخواست‌دهنده ممکن است در یکی از این سایت‌ها باشد.
        """
        from app.sync_engine.sync_service import SyncService  # جلوگیری از import حلقه‌ای

        own = (await self.db.execute(select(SiteConnection).where(SiteConnection.site_id == site_id))).scalar_one_or_none()
        if own is None:
            return [site_id]
        others = (await self.db.execute(select(SiteConnection).where(SiteConnection.site_id != site_id))).scalars().all()
        return [site_id] + [c.site_id for c in others if SyncService.same_source(own, c)]

    async def _normalize_for_approver(self, approver_employee: Employee, rows: list[dict]) -> list[dict]:
        """
        ردیف‌های خام کارتابل تأییدکننده را نرمال می‌کند و نام، واحد و سایت درخواست‌دهنده را اضافه می‌کند.
        درخواست‌دهنده اول در سایت تأییدکننده و بعد در سایت‌های هم‌منبع جست‌وجو می‌شود؛ عنوان نوع درخواست
        از نوع‌های سایت خودِ درخواست‌دهنده خوانده می‌شود. خروجی: لیست dict با کلید requester_site_id.
        """
        site_ids = await self._same_source_site_ids(approver_employee.site_id)
        emp_nos = [str(row.get("EmpNo")) for row in rows if row.get("EmpNo") is not None]
        info_by_code: dict[int, dict] = {}
        if emp_nos:
            result = await self.db.execute(
                select(Employee)
                .options(selectinload(Employee.department))
                .where(Employee.site_id.in_(site_ids), Employee.personnel_code.in_(emp_nos))
            )
            # ترتیب اولویت: سایت تأییدکننده، سپس بقیه به ترتیب site_ids
            rank = {sid: i for i, sid in enumerate(site_ids)}
            for e in sorted(result.scalars().all(), key=lambda x: rank.get(x.site_id, 99)):
                if not e.personnel_code.isdigit():
                    continue
                info_by_code.setdefault(
                    int(e.personnel_code),
                    {
                        "name": f"{e.first_name} {e.last_name}",
                        "department": e.department.name if e.department else None,
                        "site_id": e.site_id,
                    },
                )
        type_lookups: dict[int, dict] = {}  # site_id -> نگاشت نوع‌های همان سایت (کش در همین فراخوانی)
        items = []
        for row in rows:
            emp_no = row.get("EmpNo")
            info = info_by_code.get(int(emp_no)) if isinstance(emp_no, int) or str(emp_no).isdigit() else None
            info = info or {}
            requester_site = info.get("site_id", approver_employee.site_id)
            if requester_site not in type_lookups:
                type_lookups[requester_site] = await self._get_type_lookup(requester_site)
            item = _normalize_row(row, type_lookups[requester_site])
            item["requester_name"] = info.get("name")
            item["requester_department"] = info.get("department")
            item["requester_site_id"] = requester_site
            items.append(item)
        return items

    async def _requester_site_id(self, site_id: int, emp_no) -> int:
        """
        سایت پرتالِ درخواست‌دهنده را از روی Emp_No پیدا می‌کند: اول همین سایت، بعد سایت‌های هم‌منبع.
        اگر پیدا نشد همان site_id برمی‌گردد.
        """
        if emp_no is None:
            return site_id
        site_ids = await self._same_source_site_ids(site_id)
        result = await self.db.execute(
            select(Employee.site_id).where(Employee.site_id.in_(site_ids), Employee.personnel_code == str(emp_no))
        )
        found = {row[0] for row in result.all()}
        if site_id in found or not found:
            return site_id
        return next(sid for sid in site_ids if sid in found)

    async def _annotate_stage_by_requester_site(self, items: list[dict], default_site_id: int) -> None:
        """پرچم awaiting_hr را برای هر درخواست با مسئول نیروی انسانیِ سایت خودِ درخواست‌دهنده تعیین می‌کند (درجا)."""
        by_site: dict[int, list[dict]] = {}
        for item in items:
            by_site.setdefault(item.get("requester_site_id") or default_site_id, []).append(item)
        for site_id, group in by_site.items():
            self._annotate_stage(group, await self._get_hr_officer_emp_no(site_id))

    async def list_decided_by_approver(
        self, approver_employee: Employee, page: int = 0, page_size: int = 10
    ) -> dict:
        """
        ورودی: پرسنل تأییدکننده، شماره صفحه (از صفر) و اندازه صفحه (۱ تا ۱۰۰).
        سوابق درخواست‌هایی که این فرد قبلاً تأیید/رد کرده (به‌علاوه تردد فراموش‌شده‌هایی
        که به منابع انسانی ارجاع داده) را جدیدترین اول و صفحه‌بندی‌شده برمی‌گرداند.
        خروجی: {"items": لیست نرمال‌شده صفحه, "total": تعداد کل}.
        """
        # درخواست‌هایی که تصمیم نهایی‌شان توسط این فرد ثبت شده
        mapping, site_connection = await self._get_mapping_and_connection(approver_employee.site_id, user_facing=True)
        approver_emp_no = _to_personnel_code_int(approver_employee)
        approver_col = _quote(site_connection.db_type, mapping.approval_by_manager_column)
        approved_col = _quote(site_connection.db_type, mapping.is_final_approved_column)
        where_sql = f"{approver_col} = %(approver)s AND {approved_col} IS NOT NULL"
        rows = await asyncio.to_thread(
            _select_requests_sync, site_connection, mapping, where_sql, {"approver": approver_emp_no}
        )
        # تردد فراموش‌شده‌هایی که این فرد به‌عنوان سرپرست تأیید و به مسئول
        # نیروی انسانی ارجاع داده (تصمیم نهایی با او نبوده) - از WF_MoveUp
        kara_names = await self._get_kara_names(approver_employee.site_id, mapping, site_connection)
        if kara_names is not None and kara_names.can_write_moveup:
            try:
                moved_ids = await asyncio.to_thread(
                    _run_kara_writeback_sync, site_connection, kara_names, kara_wb.request_ids_moved_by, approver_emp_no
                )
            except Exception:
                logger.exception("خواندن ارجاع‌های کاراوب با خطا مواجه شد")
                moved_ids = []  # خطای خواندن ارجاع‌ها فهرست اصلی را از کار نمی‌اندازد
            # فقط آن‌هایی که قبلاً در فهرست نیستند اضافه می‌شوند
            known = {r.get("RequestId") for r in rows}
            moved_ids = [rid for rid in moved_ids if rid not in known]
            if moved_ids:
                id_col = _quote(site_connection.db_type, mapping.request_id_column)
                placeholders = ", ".join(f"%(m{i})s" for i in range(len(moved_ids)))
                rows += await asyncio.to_thread(
                    _select_requests_sync,
                    site_connection,
                    mapping,
                    f"{id_col} IN ({placeholders})",
                    {f"m{i}": rid for i, rid in enumerate(moved_ids)},
                )
        # مرتب‌سازی: جدیدترین تصمیم (یا ثبت) اول
        rows.sort(
            key=lambda r: (r.get("ApprovalDate") or r.get("SubmittingDate") or datetime.min, r.get("RequestId") or 0),
            reverse=True,
        )
        # صفحه‌بندی در حافظه
        total = len(rows)
        page = max(page, 0)
        page_size = min(max(page_size, 1), 100)
        page_rows = rows[page * page_size : (page + 1) * page_size]

        # نرمال‌سازی فقط ردیف‌های همین صفحه، با نام/واحد/نوع از سایت خودِ درخواست‌دهنده
        items = await self._normalize_for_approver(approver_employee, page_rows)
        await self._apply_real_reviews(site_connection, mapping, items)
        await self._annotate_stage_by_requester_site(items, approver_employee.site_id)
        return {"items": items, "total": total}

    async def list_all_for_site(
        self,
        site_id: int,
        allowed_type_ids: list | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        status_filter: str | None = None,
        type_id_filter: int | None = None,
        department_filter: str | None = None,
    ) -> list[dict]:
        """
        ورودی: شناسه سایت، لیست نوع‌های مجاز (None = همه) و فیلترهای گزارشی
        (بازه تاریخی، وضعیت، نوع، نام واحد).
        همه درخواست‌های سایت را می‌خواند، در حافظه فیلتر می‌کند و نرمال‌شده با
        نام/واحد درخواست‌دهنده برمی‌گرداند. برای مجوز leave_requests.view/manage
        یا مجوز محدود به نوع (LeaveRequestTypeViewer، از طریق allowed_type_ids).
        بازه تاریخی بر اساس تاریخ خودِ مرخصی/ماموریت است، نه تاریخ ثبت.
        """
        # همه درخواست‌های سایت (فیلترها در پایتون اعمال می‌شوند)
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        rows = await asyncio.to_thread(_select_requests_sync, site_connection, mapping, "1 = 1", {})
        type_lookup = await self._get_type_lookup(site_id)
        requester_info = await self._get_requester_info(site_id, [row.get("EmpNo") for row in rows])
        normalized = []
        # نرمال‌سازی و اعمال فیلترها روی هر ردیف
        for row in rows:
            item = _normalize_row(row, type_lookup)
            # محدودیت مجوز به نوع‌های خاص
            if allowed_type_ids is not None and item["type_id"] not in allowed_type_ids:
                continue
            if type_id_filter is not None and item["type_id"] != type_id_filter:
                continue
            if status_filter and item["status"] != status_filter:
                continue
            # فیلتر بازه تاریخی: بازه درخواست باید با بازه فیلتر هم‌پوشانی داشته باشد
            if date_from or date_to:
                item_start = item["start_date"]
                if item_start is None:
                    continue
                item_start = item_start.date() if hasattr(item_start, "date") else item_start  # datetime -> date
                item_end = item["end_date"] or item["start_date"]  # ساعتی: همان یک روز
                item_end = item_end.date() if hasattr(item_end, "date") else item_end
                if date_to and item_start > date_to:
                    continue
                if date_from and item_end < date_from:
                    continue
            # فیلتر واحد بر اساس واحد فعلی پرسنل در پورتال
            info = requester_info.get(item["emp_no"], {})
            if department_filter and info.get("department") != department_filter:
                continue
            item["requester_name"] = info.get("name")
            item["requester_department"] = info.get("department")
            normalized.append(item)
        await self._apply_real_reviews(site_connection, mapping, normalized)
        self._annotate_stage(normalized, await self._get_hr_officer_emp_no(site_id))
        return normalized

    async def _list_lookup(
        self, site_id: int, table_name: str | None, id_column: str | None, desc_column: str | None
    ) -> list[dict]:
        """
        ورودی: شناسه سایت و نام جدول مرجع/ستون شناسه/ستون عنوان (از نگاشت).
        ردیف‌های یک جدول مرجع ساده (شناسه + عنوان) را به‌صورت [{"lookup_id", "title"}] برمی‌گرداند.
        اگر نام جدول خالی باشد (تنظیم نشده)، فهرست خالی - نه خطا.
        """
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        if not table_name:
            return []
        rows = await asyncio.to_thread(_select_lookup_sync, site_connection, table_name, id_column, desc_column)
        # ردیف‌های بدون شناسه حذف می‌شوند
        return [
            {"lookup_id": row.get("LookupId"), "title": row.get("LookupTitle")}
            for row in rows
            if row.get("LookupId") is not None
        ]

    async def list_action_lookup(self, site_id: int) -> list[dict]:
        """ورودی: شناسه سایت. فهرست رسمی WF_Action را به‌صورت [{"action_id", "title"}] برمی‌گرداند - برای پنل ادمین هنگام ساخت «نوع درخواست» جدید."""
        mapping, _ = await self._get_mapping_and_connection(site_id)
        items = await self._list_lookup(
            site_id, mapping.action_lookup_table_name, mapping.action_lookup_id_column, mapping.action_lookup_desc_column
        )
        return [{"action_id": item["lookup_id"], "title": item["title"]} for item in items]

    async def list_operation_lookup(self, site_id: int) -> list[dict]:
        """ورودی: شناسه سایت. فهرست رسمی WF_OperationTypes را به‌صورت [{"operation_id", "title"}] برمی‌گرداند."""
        mapping, _ = await self._get_mapping_and_connection(site_id)
        items = await self._list_lookup(
            site_id,
            mapping.operation_lookup_table_name,
            mapping.operation_lookup_id_column,
            mapping.operation_lookup_desc_column,
        )
        return [{"operation_id": item["lookup_id"], "title": item["title"]} for item in items]

    async def list_card_lookup(self, site_id: int) -> list[dict]:
        """
        ورودی: شناسه سایت. فهرست رسمی Cards را به‌صورت [{"card_no", "title", "action_id"}]
        برمی‌گرداند. برخلاف دو Lookup دیگر، از _select_card_lookup_sync اختصاصی استفاده
        می‌کند تا ActionId مرتبط با هر کارت هم برگردد (ActionId همیشه از کارت مشتق می‌شود).
        اگر جدول Cards نگاشت نشده باشد، فهرست خالی.
        """
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        if not mapping.card_lookup_table_name:
            return []
        rows = await asyncio.to_thread(_select_card_lookup_sync, site_connection, mapping)
        # ردیف‌های بدون شناسه حذف می‌شوند
        return [
            {"card_no": row.get("LookupId"), "title": row.get("LookupTitle"), "action_id": row.get("LinkedActionId")}
            for row in rows
            if row.get("LookupId") is not None
        ]

    # ---------- تصمیم‌گیری (تأییدکننده) ----------

    async def decide_request(
        self, site_id: int, request_id: int, approver_employee: Employee, approved: bool, manager_idea: str
    ) -> None:
        """
        ورودی: سایت، شناسه درخواست، پرسنل تأییدکننده، تصمیم (تأیید/رد) و نظر.
        تصمیم را روی WF_Requests ثبت می‌کند، در صورت تأیید اثرش را در کارکرد کاراوب
        اعمال می‌کند، نظر را در WF_Reviews می‌نویسد و به درخواست‌دهنده اعلان می‌دهد.
        تردد فراموش‌شده: تأیید سرپرست نهایی نیست و درخواست به مسئول نیروی انسانی ارجاع می‌شود.
        """
        # خواندن ردیف درخواست
        mapping, site_connection = await self._get_mapping_and_connection(site_id, user_facing=True)
        request_id_col = _quote(site_connection.db_type, mapping.request_id_column)
        rows = await asyncio.to_thread(
            _select_requests_sync,
            site_connection,
            mapping,
            f"{request_id_col} = %(request_id)s",
            {"request_id": request_id},
        )
        if not rows:
            raise LeaveRequestError("درخواست موردنظر یافت نشد")
        request_row = rows[0]

        # فقط تأییدکننده فعلی و فقط روی درخواست بدون تصمیم
        approver_emp_no = _to_personnel_code_int(approver_employee)
        if request_row.get("CurEmpNo") != approver_emp_no:
            raise LeaveRequestError("شما مجاز به تصمیم‌گیری روی این درخواست نیستید")
        if request_row.get("IsFinalApproved") is not None:
            raise LeaveRequestError("این درخواست قبلاً تصمیم‌گیری شده است")

        # سایت خودِ درخواست‌دهنده (ممکن است سایت هم‌منبع دیگری باشد): مسئول نیروی انسانی،
        # کارت‌های تردد فراموش‌شده و اعلان‌ها از همان سایت خوانده می‌شوند
        requester_site_id = await self._requester_site_id(site_id, request_row.get("EmpNo"))

        # تردد فراموش‌شده: تأیید سرپرست نهایی نیست - درخواست به مسئول نیروی انسانی
        # ارجاع می‌شود و فقط تأیید او تردد را در کاراوب درج می‌کند. رد در هر مرحله نهایی است.
        forgotten_cards, hr_emp_no = await self._get_forgotten_context(requester_site_id)
        is_forgotten = request_row.get("CardNo") in forgotten_cards
        kara_names = await self._get_kara_names(site_id, mapping, site_connection)
        if is_forgotten and approved:
            if hr_emp_no is None:
                raise LeaveRequestError("مسئول نیروی انسانی این سایت تعیین نشده - تأیید تردد فراموش‌شده ممکن نیست")
            if kara_names is None or not kara_names.can_write_punch:
                raise LeaveRequestError("ستون‌های لازم جدول تردد برای ثبت تردد فراموش‌شده در تنظیمات سایت نگاشت نشده‌اند")
            # اگر تأییدکننده خودِ مسئول HR است یا مسئول HR خودش درخواست‌دهنده است، تأیید فعلی نهایی است
            if approver_emp_no != hr_emp_no and request_row.get("EmpNo") != hr_emp_no:
                # ارجاع به مسئول نیروی انسانی (CurEmpNo عوض می‌شود و ردیف WF_MoveUp ثبت می‌شود)
                try:
                    await asyncio.to_thread(
                        _run_kara_writeback_sync,
                        site_connection,
                        kara_names,
                        kara_wb.move_up_to,
                        request_row,
                        approver_emp_no,
                        hr_emp_no,
                    )
                except Exception as e:
                    logger.exception("ارجاع درخواست %s به مسئول نیروی انسانی شکست خورد", request_id)
                    raise LeaveRequestError(f"ارجاع درخواست به مسئول نیروی انسانی با خطا مواجه شد: {e}") from e
                # نظر سرپرست (اگر نوشته) در WF_Reviews ثبت می‌شود
                if mapping.wf_reviews_approved_type_value is not None and (manager_idea or "").strip():
                    await asyncio.to_thread(
                        _insert_review_sync,
                        site_connection,
                        mapping,
                        request_id,
                        approver_emp_no,
                        manager_idea,
                        mapping.wf_reviews_approved_type_value,
                    )
                # اعلان به درخواست‌دهنده (مرحله سرپرست) و به مسئول نیروی انسانی
                if request_row.get("EmpNo") is not None:
                    await self._notify_requester_of_forgotten_punch(
                        requester_site_id, request_row["EmpNo"], "supervisor"
                    )
                _schedule_push(
                    requester_site_id,
                    hr_emp_no,
                    "/leave-requests?tab=pending",
                    "یک درخواست تردد فراموش‌شده (تأییدشده توسط سرپرست) در انتظار تأیید شماست.\n"
                    "جهت بررسی روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید.",
                )
                return  # تصمیم نهایی هنوز ثبت نمی‌شود

        # ثبت تصمیم نهایی روی WF_Requests. ManagerIdea عمداً خالی نوشته می‌شود (مثل
        # کاراوب) - نظر واقعی فقط در WF_Reviews.Description است تا دو منبع حقیقت واگرا نشوند.
        updates = {
            mapping.is_final_approved_column: approved,
            mapping.approval_by_manager_column: approver_emp_no,
            mapping.approval_date_column: kara_wb.kara_now(),
            mapping.manager_idea_column: "",
        }
        await asyncio.to_thread(_update_request_sync, site_connection, mapping, request_id, updates)

        # اعمال اثر تأیید در کارکرد کاراوب: ساعتی روی تردد مطابق (یا AcceptCode=8 اگر ترددی
        # نیست)، روزانه در Mor_Mam، تردد فراموش‌شده درج تردد. اگر شکست بخورد، خودِ تأیید هم
        # برگردانده می‌شود تا درخواستی «تأییدشده ولی بی‌اثر» باقی نماند.
        if approved and kara_names is not None:
            try:
                await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_names,
                    kara_wb.apply_forgotten_punch if is_forgotten else kara_wb.apply_on_approval,  # تابع اعمال بر اساس نوع
                    request_row,
                    approver_emp_no,
                    mapping.application_id_value,
                    _effective_branch(mapping) or 1,
                )
            except Exception as e:
                logger.exception("اعمال تأیید درخواست %s در کارکرد کاراوب شکست خورد", request_id)
                # برگرداندن تصمیم به حالت «در حال بررسی»
                rollback = {
                    mapping.is_final_approved_column: None,
                    mapping.approval_by_manager_column: None,
                    mapping.approval_date_column: None,
                }
                await asyncio.to_thread(_update_request_sync, site_connection, mapping, request_id, rollback)
                raise LeaveRequestError(f"ثبت این تأیید در کارکرد کاراوب با خطا مواجه شد: {e}") from e

        # ثبت نظر تأییدکننده در WF_Reviews (فقط اگر متنی نوشته باشد - مثل کاراوب).
        # ReviewType برای تأیید و رد یکسان است؛ تصمیم واقعی فقط در IsFinalApproved ذخیره می‌شود.
        review_type = mapping.wf_reviews_approved_type_value
        if review_type is not None and (manager_idea or "").strip():
            await asyncio.to_thread(
                _insert_review_sync,
                site_connection,
                mapping,
                request_id,
                approver_emp_no,
                manager_idea or "",
                review_type,
            )

        # اطلاع‌رسانی به درخواست‌دهنده در پس‌زمینه - خطای Push تصمیم را متوقف نمی‌کند
        requester_emp_no = request_row.get("EmpNo")
        if requester_emp_no is not None:
            if is_forgotten:
                await self._notify_requester_of_forgotten_punch(
                    requester_site_id, requester_emp_no, "approved" if approved else "rejected"
                )
            else:
                await self._notify_requester_of_decision(requester_site_id, requester_emp_no)

    # ---------- ویرایش مدیریتی (فقط leave_requests.manage) ----------

    async def admin_update_request(self, site_id: int, request_id: int, updates: dict) -> None:
        """
        ورودی: سایت، شناسه درخواست و دیکشنری updates با کلیدهای مجاز: is_final_approved،
        start_date، end_date، start_hour، end_hour، leave_type_id، manager_idea، description.
        ویرایش مدیریتی (مجوز leave_requests.manage): ستون‌های داده‌شده را در WF_Requests
        به‌روز می‌کند، اثر قبلی در کارکرد کاراوب را برمی‌دارد و اثر جدید را اعمال می‌کند،
        و نظر تأییدکننده را در WF_Reviews می‌نویسد.

        «مدت» مستقیماً ویرایش نمی‌شود: اگر هر دو ساعت شروع/پایان داده شوند، از رویشان
        (فرمت HHMM) و اگر هر دو تاریخ داده شوند، از رویشان (تعداد روز) محاسبه می‌شود -
        همان قانون submit_request.
        leave_type_id ستون مستقیم نیست: نوع موردنظر پیدا شده و سه ستون
        OperationsID / ActionId / Card_No از روی آن به‌روز می‌شوند.
        """
        # خواندن ردیف فعلی درخواست
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        request_id_col = _quote(site_connection.db_type, mapping.request_id_column)
        current_rows = await asyncio.to_thread(
            _select_requests_sync,
            site_connection,
            mapping,
            f"{request_id_col} = %(request_id)s",
            {"request_id": request_id},
        )
        if not current_rows:
            raise LeaveRequestError("درخواست موردنظر یافت نشد")
        forgotten_cards, _ = await self._get_forgotten_context(site_id)
        updates = dict(updates)  # کپی، چون پایین تغییر می‌کند
        # Card_No نهایی درخواست (اگر نوع عوض می‌شود، Card_No نوع جدید) برای تشخیص تردد فراموش‌شده
        target_card = current_rows[0].get("CardNo")
        if updates.get("leave_type_id") is not None:
            new_type = await self.db.get(LeaveRequestType, updates["leave_type_id"])
            if new_type is not None:
                target_card = new_type.card_no
        if target_card in forgotten_cards:
            # تردد فراموش‌شده بازه ندارد: فقط تاریخ و ساعت خودِ تردد (مثل کاراوب)
            updates.pop("end_date", None)
            if "start_hour" in updates:
                updates["end_hour"] = 0
            else:
                updates.pop("end_hour", None)
        # نگاشت کلیدهای منطقی به ستون واقعی WF_Requests
        column_updates: dict = {}
        key_to_column = {
            "is_final_approved": mapping.is_final_approved_column,
            "start_date": mapping.start_date_column,
            "end_date": mapping.end_date_column,
            "start_hour": mapping.start_hour_column,
            "end_hour": mapping.end_hour_column,
            "description": mapping.description_column,
        }
        for key, column in key_to_column.items():
            if key in updates:
                column_updates[column] = updates[key]

        # محاسبه خودکار مدت از روی ساعت‌ها (HHMM) یا تاریخ‌ها (تعداد روز)
        try:
            if target_card in forgotten_cards:
                pass  # مدت همیشه '0'
            elif updates.get("start_hour") is not None and updates.get("end_hour") is not None:
                column_updates[mapping.duration_column] = str(
                    compute_hourly_duration(updates["start_hour"], updates["end_hour"])
                )
            elif updates.get("start_date") is not None and updates.get("end_date") is not None:
                start_date_only = updates["start_date"].date() if hasattr(updates["start_date"], "date") else updates["start_date"]  # datetime -> date
                end_date_only = updates["end_date"].date() if hasattr(updates["end_date"], "date") else updates["end_date"]
                column_updates[mapping.duration_column] = str(compute_daily_duration(start_date_only, end_date_only))
        except LeaveRequestRulesError as e:
            raise LeaveRequestError(str(e)) from e

        # تغییر نوع: سه ستون OperationsID / ActionId / Card_No از روی نوع جدید (مثل submit_request)
        if "leave_type_id" in updates and updates["leave_type_id"] is not None:
            leave_type = await self.db.get(LeaveRequestType, updates["leave_type_id"])
            if leave_type is None or leave_type.site_id != site_id:
                raise LeaveRequestError("نوع درخواست موردنظر یافت نشد")
            column_updates[mapping.operations_id_column] = (
                leave_type.operation_id if leave_type.operation_id is not None else (3 if leave_type.is_mission else 5)  # پیش‌فرض: ۳ ماموریت، ۵ مرخصی
            )
            if mapping.action_id_column and leave_type.action_id is not None:
                column_updates[mapping.action_id_column] = leave_type.action_id
            column_updates[mapping.card_no_column] = leave_type.card_no if leave_type.card_no is not None else 0

        # «نظر تأییدکننده» فقط در WF_Reviews.Description نوشته می‌شود، نه در ManagerIdea
        # (مثل کاراوب، تا دو منبع حقیقت واگرا نشوند)؛ ثبت آن در انتهای تابع انجام می‌شود
        new_manager_idea = updates.get("manager_idea")

        # اثر در کارکرد کاراوب: تغییر وضعیت/تاریخ/ساعت/نوع روی کارکرد اثر دارد - اثر قبلی
        # (اگر تأییدشده بود) برداشته و بعد از ویرایش، اگر همچنان/تازه تأییدشده است، دوباره اعمال می‌شود
        kara_names = await self._get_kara_names(site_id, mapping, site_connection)
        writeback = kara_names is not None and bool(
            {"is_final_approved", "start_date", "end_date", "start_hour", "end_hour", "leave_type_id"}
            & set(updates)
        )  # فقط اگر یکی از کلیدهای مؤثر بر کارکرد تغییر کرده باشد
        old_row = None
        if writeback:
            old_row = current_rows[0]
            # برداشتن اثر قبلی (ابطال‌شده در کاراوب اثری ندارد)
            if old_row.get("IsFinalApproved") and old_row.get("AcceptCode") != kara_wb.ACCEPT_CANCELLED:
                await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_names,
                    kara_wb.revert_forgotten_punch
                    if old_row.get("CardNo") in forgotten_cards
                    else kara_wb.revert_effects,
                    old_row,
                    None,
                    mapping.application_id_value,
                )

        # به‌روزرسانی ستون‌های WF_Requests
        if column_updates:
            await asyncio.to_thread(_update_request_sync, site_connection, mapping, request_id, column_updates)

        # اعمال اثر جدید بر اساس ردیف به‌روزشده
        if writeback and old_row is not None:
            new_rows = await asyncio.to_thread(
                _select_requests_sync,
                site_connection,
                mapping,
                f"{request_id_col} = %(request_id)s",
                {"request_id": request_id},
            )
            new_row = new_rows[0] if new_rows else None
            if new_row and new_row.get("IsFinalApproved"):
                # تأییدشده: اعمال اثر با تأییدکننده ثبت‌شده (یا تأییدکننده فعلی اگر خالی است)
                approver = new_row.get("ApprovalByManagerEmpNo") or new_row.get("CurEmpNo")
                await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_names,
                    kara_wb.apply_forgotten_punch
                    if new_row.get("CardNo") in forgotten_cards
                    else kara_wb.apply_on_approval,
                    new_row,
                    approver,
                    mapping.application_id_value,
                    _effective_branch(mapping) or 1,
                )
            elif new_row:
                # دیگر تأییدشده نیست: پاک کردن AcceptCode
                await asyncio.to_thread(_run_kara_writeback_sync, site_connection, kara_names, kara_wb.clear_accept_code, request_id)

        # ثبت نظر تأییدکننده: به‌روزرسانی آخرین Review، و اگر Review ای وجود نداشت
        # (مثلاً مدیر بدون نوشتن نظر تصمیم گرفته بود)، درج ردیف جدید
        if "manager_idea" in updates and mapping.wf_reviews_table_name:
            updated = await asyncio.to_thread(
                _update_review_description_sync,
                site_connection,
                mapping,
                request_id,
                new_manager_idea or "",
            )
            if not updated and mapping.wf_reviews_approved_type_value is not None:
                # تأییدکننده‌ی ثبت‌شده‌ی خودِ درخواست را می‌خوانیم تا ردیف
                # جدید Review به نام همان فرد ثبت شود، نه یک مقدار ساختگی.
                request_id_col = _quote(site_connection.db_type, mapping.request_id_column)
                rows = await asyncio.to_thread(
                    _select_requests_sync,
                    site_connection,
                    mapping,
                    f"{request_id_col} = %(request_id)s",
                    {"request_id": request_id},
                )
                approver_emp_no = rows[0].get("ApprovalByManagerEmpNo") if rows else None
                await asyncio.to_thread(
                    _insert_review_sync,
                    site_connection,
                    mapping,
                    request_id,
                    approver_emp_no or 0,  # اگر تأییدکننده‌ای ثبت نشده، صفر
                    new_manager_idea or "",
                    mapping.wf_reviews_approved_type_value,
                )


def _normalize_row(row: dict, type_lookup: dict | None = None) -> dict:
    """
    ورودی: یک ردیف خام WF_Requests (با نام‌های مستعار _select_requests_sync) و
    نگاشت نوع از _get_type_lookup. دیکشنری پایدار و مستقل از نوع دیتابیس برای
    Schemaهای Pydantic برمی‌گرداند: وضعیت متنی (pending/approved/rejected/cancelled)،
    فیلدهای درخواست و نوع بازشناسی‌شده از ترکیب (OperationsID, ActionId, Card_No).
    اگر type_lookup داده نشود یا تطبیقی نباشد، type_id/type_title خالی می‌مانند (نه خطا).
    """
    # وضعیت: ابطال‌شده در خودِ کاراوب (IsFinalApproved همان ۱ می‌ماند، فقط AcceptCode = ۲۲)،
    # بدون تصمیم = در بررسی، True = تأیید، False = رد
    is_final_approved = row.get("IsFinalApproved")
    if row.get("AcceptCode") == kara_wb.ACCEPT_CANCELLED:
        status = "cancelled"
    elif is_final_approved is None:
        status = "pending"
    elif is_final_approved:
        status = "approved"
    else:
        status = "rejected"

    # بازشناسی نوع درخواست از سه ستون
    operations_id = row.get("OperationsID")
    action_id = row.get("ActionId")
    card_no = row.get("CardNo")
    type_key = (operations_id, action_id, card_no)
    matched_type = (type_lookup or {}).get(type_key)  # (شناسه، عنوان، تردد فراموش‌شده؟) یا None

    return {
        "request_id": row.get("RequestId"),
        "emp_no": row.get("EmpNo"),
        "submitted_at": row.get("SubmittingDate"),
        "start_date": row.get("StartDate"),
        "end_date": row.get("EndDate"),
        "start_hour": row.get("StartHour"),
        "end_hour": row.get("EndHour"),
        "duration": row.get("Duration"),
        "status": status,
        "approved_by_emp_no": row.get("ApprovalByManagerEmpNo"),
        "approved_at": row.get("ApprovalDate"),
        "is_mission": operations_id == 3,  # OperationsID=3 یعنی ماموریت
        "description": row.get("Description"),
        "current_approver_emp_no": row.get("CurEmpNo"),
        "manager_idea": row.get("ManagerIdea"),
        "source": row.get("Source"),
        "destination": row.get("Distination"),  # املای ستون در کاراوب همین است
        "type_id": matched_type[0] if matched_type else None,
        "type_title": matched_type[1] if matched_type else None,
        "is_forgotten_punch": bool(matched_type[2]) if matched_type and len(matched_type) > 2 else False,
    }
