"""
سرویس «درخواست مرخصی/ماموریت» - برخلاف گزارش تردد ماهانه (فقط خواندنی)،
این سرویس هم می‌خواند هم می‌نویسد (INSERT/UPDATE) روی جدول خام WF_Requests
در دیتابیس منبع همان سایت - دقیقاً همان الگوی اتصال/Quote کردن نام
جدول/ستون (app/services/monthly_attendance_service.py).

⚠️ طبق تأیید صریح کاربر: این قابلیت خاص توسط نرم‌افزار ورود و خروج
فعلی سایت استفاده نمی‌شود - پورتال تنها نویسنده فعال این بخش از جدول
است؛ آن نرم‌افزار فقط می‌تواند این رکوردها را (در صورت تمایل) ببیند.

⚠️ امنیتی: نام جدول/ستون فقط از LeaveRequestMapping (تنظیم‌شده توسط
Admin با مجوز sites.manage) می‌آید و با _quote مخصوص نوع دیتابیس احاطه
می‌شود؛ مقادیر واقعی همیشه Parameterized هستند - همان الگوی امنیتی
Sync Engine/گزارش تردد ماهانه.
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
from app.models.leave_request import LeaveRequestApprover, LeaveRequestMapping, LeaveRequestType
from app.models.site import DbType, SiteConnection
from app.models.user import User
from app.services import kara_attendance_writeback as kara_wb
from app.services.push_service import PushService

logger = logging.getLogger(__name__)


class LeaveRequestError(Exception):
    pass


def _quote(db_type: DbType, name: str) -> str:
    if db_type == DbType.mysql:
        return f"`{name}`"
    if db_type == DbType.postgresql:
        return f'"{name}"'
    return f"[{name}]"  # mssql


def _connect(conn: SiteConnection):
    password = decrypt_secret(conn.password_encrypted)
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
            cursorclass=pymysql.cursors.DictCursor,
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
    if db_type == DbType.mssql:
        return connection.cursor(as_dict=True)
    if db_type == DbType.postgresql:
        return connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return connection.cursor()


def _branch_filter_sql(q, mapping: LeaveRequestMapping) -> tuple[str, dict]:
    if mapping.branch_code_column and mapping.branch_code_value is not None:
        return f" AND {q(mapping.branch_code_column)} = %(branch_code)s", {"branch_code": mapping.branch_code_value}
    return "", {}


def _resolve_manager_emp_no_sync(conn: SiteConnection, mapping: LeaveRequestMapping, emp_no: int) -> int | None:
    """
    ⚠️ فقط‌خواندنی - زنجیره واقعی نرم‌افزار ورود/خروج برای تعیین
    تأییدکننده: Employee.Sec_No -> Sections.Sec_No -> Sections.ManagerEmp_No.

    ⚠️ کشف حیاتی (تأییدشده با مقایسه مستقیم با نتیجه واقعی کاراوب): اگر
    مدیرِ به‌دست‌آمده خودِ همان درخواست‌دهنده باشد (یعنی فرد، مدیر بخش
    خودش است - مثلاً سرپرست/رئیس همان واحد)، هیچ‌کس نمی‌تواند تأییدکننده
    خودش باشد - باید از طریق ستون section_parent_column (TFather) به
    بخش بالادستی صعود کرد و دوباره همین بررسی را تکرار کرد، تا مدیرِ
    متفاوتی پیدا شود یا به ریشه سلسله‌مراتب برسیم.

    اگر هرکدام از جدول‌های این زنجیره تنظیم نشده باشند، یا پرسنل/بخش
    موردنظر پیدا نشود، یا حتی در ریشه سلسله‌مراتب هم مدیرِ متفاوتی پیدا
    نشود، None برمی‌گرداند - تا سرویس بتواند به Fallback دستی
    (LeaveRequestApprover) برگردد.
    """
    if not (mapping.employee_table_name and mapping.section_table_name):
        return None
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        with _dict_cursor(connection, conn.db_type) as cur:
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

            # ⚠️ سقف ۱۰ سطح صعود - صرفاً محافظتی در برابر داده حلقه‌ای
            # نادرست (Sec_No که به خودش یا حلقه‌ای برمی‌گردد)؛ سلسله‌مراتب
            # واقعی سازمانی هیچ‌وقت این‌قدر عمیق نیست.
            for _ in range(10):
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
                if manager_emp_no != emp_no:
                    return manager_emp_no
                parent_sec_no = section_row.get("ParentSecNo")
                if parent_sec_no is None:
                    return None  # به ریشه رسیدیم و هنوز مدیرِ متفاوتی پیدا نشد
                current_sec_no = parent_sec_no
            return None
    finally:
        connection.close()


def _select_lookup_sync(conn: SiteConnection, table_name: str, id_column: str, desc_column: str) -> list[dict]:
    """
    ⚠️ فقط‌خواندنی - یک تابع عمومی برای خواندن هر جدول مرجعِ ساده (یک
    ستون شناسه عددی + یک ستون عنوان فارسی) در دیتابیس منبع سایت - طبق
    درخواست صریح کاربر، سه جدول این الگو را دارند: WF_Action، Cards،
    WF_OperationTypes. کاملاً مستقل از جدول اصلی WF_Requests - فقط برای
    کمک به پرکردن فرم «افزودن نوع درخواست» در پنل ادمین استفاده می‌شود.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
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
    ⚠️ فقط‌خواندنی - کشف حیاتی تأییدشده با بررسی مستقیم دیتابیس Kara:
    ActionId هیچ‌وقت مستقل انتخاب نمی‌شود - همیشه دقیقاً برابر
    Cards.WF_ActionID همان کارتی است که Card_No به آن اشاره می‌کند. این
    تابع (برخلاف _select_lookup_sync عمومی) همین ستون سوم (ActionId
    مرتبط) را هم برمی‌گرداند - تا انتخاب یک کارت در پنل ادمین، ActionId
    را هم خودکار و درست پر کند.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        query = f"""
            SELECT
                {q(mapping.card_lookup_id_column)} AS {q("LookupId")},
                {q(mapping.card_lookup_desc_column)} AS {q("LookupTitle")},
                {q(mapping.card_lookup_action_id_column)} AS {q("LinkedActionId")}
            FROM {q(mapping.card_lookup_table_name)}
            ORDER BY {q(mapping.card_lookup_id_column)} ASC
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with _dict_cursor(connection, conn.db_type) as cur:
            cur.execute(query)
            return list(cur.fetchall())
    finally:
        connection.close()


def _select_requests_sync(conn: SiteConnection, mapping: LeaveRequestMapping, where_sql: str, params: dict) -> list[dict]:
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    branch_sql, branch_params = _branch_filter_sql(q, mapping)
    connection = _connect(conn)
    try:
        query = f"""
            SELECT
                {q(mapping.request_id_column)} AS {q("RequestId")},
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
    ⚠️ کشف حیاتی (تأییدشده با داده واقعی): نظر واقعی تأییدکننده در
    WF_Requests.ManagerIdea ذخیره نمی‌شود - در جدول جداگانه WF_Reviews
    (یک ردیف به‌ازای هر تصمیم) ذخیره می‌شود. اگر برای این سایت تنظیم
    نشده باشد (wf_reviews_table_name خالی)، کاری انجام نمی‌دهد - نه
    خطا؛ چون کاملاً اختیاری است (سازگاری با نصب‌های بدون این جدول).
    """
    if not mapping.wf_reviews_table_name:
        return
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            columns = [
                mapping.wf_reviews_request_id_column,
                mapping.wf_reviews_reviewed_emp_no_column,
                mapping.wf_reviews_description_column,
                mapping.wf_reviews_type_column,
                mapping.wf_reviews_date_column,
                mapping.wf_reviews_show_to_personal_column,
            ]
            # ⚠️ طبق تصمیم صریح کاربر (هم‌راستا با رفتار واقعی کاراوب):
            # ReviewDate فقط تاریخ است، بدون ساعت. رکوردهای ساخته‌شده توسط
            # خودِ کاراوب همگی ساعت 00:00:00 دارند - اگر ساعت هم بنویسیم،
            # ممکن است در گزارش‌های خودِ کاراوب رفتار متفاوتی ایجاد کند.
            today = datetime.now()
            review_date = datetime(today.year, today.month, today.day)
            values = [request_id, reviewed_emp_no, description, review_type, review_date, True]
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
    ⚠️ رفع ناسازگاری واقعی (گزارش کاربر): ویرایش مدیریتیِ «نظر تأییدکننده»
    قبلاً فقط ManagerIdea را به‌روز می‌کرد - در حالی که نظر واقعی در
    WF_Reviews.Description است و پرتال هم همان را برای نمایش می‌خواند.
    نتیجه: ادمین نظر را ویرایش می‌کرد ولی هیچ تغییری در نمایش نمی‌دید.

    این تابع آخرین ردیف Review همان درخواست را به‌روز می‌کند. خروجی
    True یعنی ردیفی به‌روز شد؛ False یعنی اصلاً Review ای وجود نداشت
    (در این حالت فراخوان باید یک ردیف جدید درج کند).
    """
    if not mapping.wf_reviews_table_name:
        return False
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            # فقط آخرین Review به‌روز می‌شود (همان که _select_latest_reviews_sync
            # برای نمایش انتخاب می‌کند) - نه همه‌ی تاریخچه تصمیم‌ها.
            id_col = q("Id")
            query = f"""
                UPDATE {q(mapping.wf_reviews_table_name)}
                SET {q(mapping.wf_reviews_description_column)} = %(description)s
                WHERE {id_col} = (
                    SELECT MAX({id_col}) FROM {q(mapping.wf_reviews_table_name)}
                    WHERE {q(mapping.wf_reviews_request_id_column)} = %(request_id)s
                )
            """  # noqa: S608
            cur.execute(query, {"description": description, "request_id": request_id})
            updated = cur.rowcount
            connection.commit()
            return updated > 0
    finally:
        connection.close()


def _select_latest_reviews_sync(
    conn: SiteConnection, mapping: LeaveRequestMapping, request_ids: list[int]
) -> dict[int, str]:
    """
    ⚠️ برای نمایش «نظر تأییدکننده» واقعی - آخرین ردیف WF_Reviews به‌ازای
    هر RequestId (ممکن است چند تصمیم/نظر پشت‌سرهم برای یک درخواست ثبت
    شده باشد، فقط آخرین مهم است). اگر تنظیم نشده یا لیست خالی باشد،
    دیکشنری خالی برمی‌گرداند - تا سرویس به ManagerIdea خام برگردد.
    """
    if not mapping.wf_reviews_table_name or not request_ids:
        return {}
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        with _dict_cursor(connection, conn.db_type) as cur:
            id_placeholders = ", ".join(f"%(id{i})s" for i in range(len(request_ids)))
            params = {f"id{i}": rid for i, rid in enumerate(request_ids)}
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

    latest: dict[int, tuple] = {}
    for row in rows:
        rid = row.get("RequestId")
        review_date = row.get("ReviewDate")
        if rid is None:
            continue
        if rid not in latest or (review_date or datetime.min) >= (latest[rid][1] or datetime.min):
            latest[rid] = (row.get("Description"), review_date)
    return {rid: desc for rid, (desc, _) in latest.items() if desc is not None}


def _insert_request_sync(conn: SiteConnection, mapping: LeaveRequestMapping, values: dict) -> int:
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    column_map = {
        mapping.emp_no_column: values["emp_no"],
        mapping.submitting_date_column: values["submitting_date"],
        mapping.card_no_column: values.get("card_no", 0),  # ⚠️ طبق تأیید کاربر از جدول Cards می‌آید - پیش‌فرض ۰ اگر نوع درخواست مقداری تعیین نکرده باشد
        mapping.start_date_column: values["start_date"],
        mapping.end_date_column: values.get("end_date"),
        mapping.start_hour_column: values.get("start_hour"),
        mapping.end_hour_column: values.get("end_hour"),
        mapping.duration_column: str(values["duration"]),
        mapping.operations_id_column: values["operations_id"],
        mapping.description_column: values["description"],
        mapping.cur_emp_no_column: values["cur_emp_no"],
        mapping.is_first_time_shift_column: False,  # ⚠️ طبق داده واقعی، همیشه False بوده
        mapping.persian_start_date_column: values["persian_start_date"],
        mapping.application_id_column: mapping.application_id_value,
    }
    if mapping.branch_code_column and mapping.branch_code_value is not None:
        column_map[mapping.branch_code_column] = mapping.branch_code_value
    if values.get("source") is not None:
        column_map[mapping.source_column] = values["source"]
    if values.get("destination") is not None:
        column_map[mapping.destination_column] = values["destination"]
    # ⚠️ اختیاری - طبق تحلیل داده واقعی، فقط اگر هم ستونش نگاشت شده باشد
    # و هم خودِ نوع درخواست مقداری برایش تعیین کرده باشد، نوشته می‌شود.
    if mapping.action_id_column and values.get("action_id") is not None:
        column_map[mapping.action_id_column] = values["action_id"]
    # ⚠️ ستون‌هایی که خودِ کاراوب هنگام ثبت پر می‌کند (kara_attendance_writeback)
    for extra_column, extra_value in (values.get("extra_columns") or {}).items():
        column_map[extra_column] = extra_value

    columns_sql = ", ".join(q(col) for col in column_map)
    placeholders = ", ".join(f"%({i})s" for i in range(len(column_map)))
    params = {str(i): val for i, val in enumerate(column_map.values())}

    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
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
                new_id = cur.lastrowid
            connection.commit()
            return int(new_id)
    finally:
        connection.close()


def _update_request_sync(
    conn: SiteConnection, mapping: LeaveRequestMapping, request_id: int, updates: dict
) -> None:
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    branch_sql, branch_params = _branch_filter_sql(q, mapping)
    set_clauses = ", ".join(f"{q(col)} = %({i})s" for i, col in enumerate(updates))
    params = {str(i): val for i, val in enumerate(updates.values())}
    params["request_id"] = request_id
    params.update(branch_params)

    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
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
    ⚠️ حذف همه ردیف‌های وابسته به یک درخواست، قبل از حذف خودِ درخواست.

    تأییدشده با بررسی مستقیم Foreign Key های دیتابیس Kara: چهار جدول
    فرزند به WF_Requests وابسته‌اند و همگی ON DELETE NO_ACTION هستند -
    یعنی دیتابیس خودش پاکشان نمی‌کند و اگر ردیفی داشته باشند، حذف خودِ
    درخواست با خطای Foreign Key **شکست می‌خورد**:

        WF_Reviews                  (نظر تأییدکننده)
        WF_Attachment               (پیوست فایل)
        WF_MoveUp                   (صعود خودکار زمانی)
        WF_RequestParallelApproval  (تأیید موازی)

    سه تای آخر در نصب فعلی خالی‌اند، ولی کاراوب می‌تواند پرشان کند - پس
    نادیده گرفتنشان یعنی یک باگ خفته که فقط وقتی ظاهر می‌شود که کاربر
    درخواستی با پیوست را حذف کند.

    نام هر جدول اگر تنظیم نشده باشد، آن جدول رد می‌شود (نه خطا) - برای
    نصب‌هایی که آن جدول را ندارند.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    targets = [
        (mapping.wf_reviews_table_name, mapping.wf_reviews_request_id_column or "RequestId"),
        (mapping.wf_attachment_table_name, "RequestId"),
        (mapping.wf_moveup_table_name, "RequestId"),
        (mapping.wf_parallel_approval_table_name, "RequestId"),
    ]
    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            for table_name, id_column in targets:
                if not table_name:
                    continue
                query = (
                    f"DELETE FROM {q(table_name)} WHERE {q(id_column)} = %(request_id)s"
                )  # noqa: S608
                cur.execute(query, {"request_id": request_id})
            connection.commit()
    finally:
        connection.close()


def _delete_request_sync(conn: SiteConnection, mapping: LeaveRequestMapping, request_id: int) -> None:
    """⚠️ حذف واقعی ردیف - فقط برای درخواست‌های خودِ کاربر و هنوز درحال‌بررسی (بررسی در لایه سرویس، قبل از فراخوانی این تابع)."""
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    branch_sql, branch_params = _branch_filter_sql(q, mapping)
    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            query = (
                f"DELETE FROM {q(mapping.table_name)} "
                f"WHERE {q(mapping.request_id_column)} = %(request_id)s {branch_sql}"
            )  # noqa: S608
            cur.execute(query, {"request_id": request_id, **branch_params})
            connection.commit()
    finally:
        connection.close()


def _kara_writeback_enabled(conn: SiteConnection, mapping: LeaveRequestMapping) -> bool:
    """هم‌رفتاری با کاراوب (Mor_Mam/DataFile/...) فقط روی SQL Server و وقتی در تنظیمات سایت فعال باشد."""
    return bool(getattr(mapping, "kara_writeback_enabled", False)) and conn.db_type == DbType.mssql


def _run_kara_writeback_sync(conn: SiteConnection, fn, *args):
    """یک تابع kara_attendance_writeback را در یک تراکنش واحد اجرا می‌کند (همه یا هیچ)."""
    connection = _connect(conn)
    try:
        with connection.cursor(as_dict=True) as cur:
            result = fn(cur, *args)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _to_personnel_code_int(employee: Employee) -> int:
    try:
        return int(employee.personnel_code)
    except (TypeError, ValueError) as e:
        raise LeaveRequestError("کد پرسنلی این کارمند عددی نیست - ثبت درخواست مرخصی/ماموریت برایش ممکن نیست") from e


class LeaveRequestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_mapping_and_connection(self, site_id: int) -> tuple[LeaveRequestMapping, SiteConnection]:
        mapping_result = await self.db.execute(select(LeaveRequestMapping).where(LeaveRequestMapping.site_id == site_id))
        mapping = mapping_result.scalar_one_or_none()
        if mapping is None:
            raise LeaveRequestError("قابلیت درخواست مرخصی/ماموریت برای این سایت هنوز تنظیم نشده است")

        conn_result = await self.db.execute(select(SiteConnection).where(SiteConnection.site_id == site_id))
        site_connection = conn_result.scalar_one_or_none()
        if site_connection is None or not site_connection.is_active:
            raise LeaveRequestError("اتصال دیتابیس این سایت تنظیم یا فعال نیست")
        return mapping, site_connection

    async def _get_approver_employee_id(self, department_id: int | None) -> int | None:
        if department_id is None:
            return None
        result = await self.db.execute(
            select(LeaveRequestApprover.approver_employee_id).where(
                LeaveRequestApprover.department_id == department_id
            )
        )
        return result.scalar_one_or_none()

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
    ) -> dict:
        leave_type = await self.db.get(LeaveRequestType, leave_type_id)
        if leave_type is None or not leave_type.is_active or leave_type.site_id != employee.site_id:
            raise LeaveRequestError("نوع درخواست موردنظر یافت نشد")
        # ⚠️ رفع باگ واقعی گزارش‌شده: قبلاً وقتی card_no این نوع تنظیم نشده
        # بود، مقدار پیش‌فرض ۰ نوشته می‌شد - اما Card_No در WF_Requests یک
        # محدودیت Foreign Key واقعی به جدول Cards دارد (تأییدشده با بررسی
        # مستقیم دیتابیس) و مقدار ۰ در آن جدول وجود ندارد - هر INSERT با
        # آن شکست می‌خورد. حالا به‌جای نوشتن یک مقدار نامعتبر، خطای روشن
        # می‌دهیم تا ادمین این نوع را کامل کند.
        if leave_type.card_no is None:
            raise LeaveRequestError(
                f"برای نوع «{leave_type.title}» هنوز Card_No تنظیم نشده - لطفاً از تنظیمات "
                "درخواست مرخصی/ماموریت، یک کارت از فهرست رسمی Cards برای این نوع انتخاب کنید"
            )

        mapping, site_connection = await self._get_mapping_and_connection(employee.site_id)

        # ⚠️ طبق تأیید صریح کاربر: روش اول، همان زنجیره واقعی نرم‌افزار
        # ورود/خروج است (Employee.Sec_No -> Sections.ManagerEmp_No) -
        # اگر جواب نداد (جدول‌ها تنظیم نشده یا پرسنل/بخش پیدا نشد)،
        # Fallback به تخصیص دستی LeaveRequestApprover.
        # ⚠️ اگر خودِ این زنجیره به خطای دیتابیس بخورد (مثلاً نام جدول/ستون
        # اشتباه تنظیم شده)، آن را هم به‌جای ۵۰۰ عمومی، Fallback در نظر
        # می‌گیریم - نه اینکه کل ثبت درخواست را متوقف کند.
        try:
            cur_emp_no = await asyncio.to_thread(
                _resolve_manager_emp_no_sync, site_connection, mapping, _to_personnel_code_int(employee)
            )
        except Exception:
            cur_emp_no = None
        if cur_emp_no is None:
            approver_employee_id = await self._get_approver_employee_id(employee.department_id)
            if approver_employee_id is None:
                raise LeaveRequestError(
                    "نتوانستیم تأییدکننده این پرسنل را (نه از زنجیره سازمانی، نه از تخصیص دستی) پیدا کنیم - "
                    "لطفاً با منابع انسانی هماهنگ کنید"
                )
            approver = await self.db.get(Employee, approver_employee_id)
            if approver is None:
                raise LeaveRequestError("تأییدکننده این واحد یافت نشد")
            cur_emp_no = _to_personnel_code_int(approver)

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
            raise LeaveRequestError(str(e)) from e

        await self._ensure_no_overlap(
            site_connection, mapping, employee, start_date, effective_end_date, start_hour, end_hour
        )

        jalali_start = jdatetime.date.fromgregorian(date=start_date)
        persian_start_date = jalali_date_to_compact(jalali_start.year, jalali_start.month, jalali_start.day)

        values = {
            "emp_no": _to_personnel_code_int(employee),
            "submitting_date": datetime.now(),
            "start_date": datetime(start_date.year, start_date.month, start_date.day),
            "end_date": datetime(effective_end_date.year, effective_end_date.month, effective_end_date.day)
            if effective_end_date
            else None,
            "start_hour": start_hour if leave_type.is_hourly else None,
            "end_hour": end_hour if leave_type.is_hourly else None,
            "duration": duration,
            "operations_id": leave_type.operation_id if leave_type.operation_id is not None else (3 if leave_type.is_mission else 5),
            "description": description or "",
            "cur_emp_no": cur_emp_no,
            "persian_start_date": persian_start_date,
            "source": source if leave_type.is_mission else None,
            "destination": destination if leave_type.is_mission else None,
            "action_id": leave_type.action_id,
            "card_no": leave_type.card_no,  # ⚠️ همیشه معتبر است - بالاتر تضمین شد (None بودن آن خطا می‌دهد)
        }

        # ⚠️ هم‌رفتاری با کاراوب: SubmittedByEmployeeID، Requested_Time،
        # DutyTools/DutyTamin و CurSection را کاراوب هنگام ثبت پر می‌کند.
        if _kara_writeback_enabled(site_connection, mapping):
            try:
                values["extra_columns"] = await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_wb.submit_extra_columns,
                    values["emp_no"],
                    cur_emp_no,
                    duration,
                )
            except Exception as e:
                raise LeaveRequestError(f"خواندن اطلاعات تکمیلی از کاراوب با خطا مواجه شد: {e}") from e

        try:
            new_request_id = await asyncio.to_thread(_insert_request_sync, site_connection, mapping, values)
        except LeaveRequestError:
            raise
        except Exception as e:
            # ⚠️ طبق گزارش کاربر: قبلاً هر خطای غیرمنتظره (مثلاً خطای خام
            # درایور دیتابیس، یا خطای Trigger روی خودِ جدول WF_Requests)
            # به‌صورت ۵۰۰ عمومی و بدون پیام مشخص برمی‌گشت - غیرقابل‌عیب‌یابی.
            # حالا متن خطای خام (که معمولاً شامل نام ستون/محدودیت مشکل‌دار
            # است) مستقیماً نمایش داده می‌شود تا علت واقعی مشخص شود.
            raise LeaveRequestError(f"ثبت درخواست در دیتابیس منبع با خطا مواجه شد: {e}") from e

        # ⚠️ اطلاع‌رسانی به تأییدکننده - هرگز نباید خودِ ثبت درخواست را
        # متوقف کند (اگر Push پیکربندی نشده یا خطا داد، درخواست همچنان
        # با موفقیت ثبت شده است).
        await self._notify_approver_of_new_request(employee.site_id, cur_emp_no)

        return {"request_id": new_request_id}

    async def _notify_approver_of_new_request(self, site_id: int, cur_emp_no: int) -> None:
        try:
            result = await self.db.execute(
                select(User)
                .join(Employee, Employee.id == User.employee_id)
                .where(Employee.site_id == site_id, Employee.personnel_code == str(cur_emp_no))
            )
            approver_user = result.scalar_one_or_none()
            if approver_user is None:
                return
            await PushService(self.db).notify_users(
                {approver_user.id},
                url="/leave-requests?tab=pending",
                priority="normal",
                body=(
                    "یک درخواست مرخصی/ماموریت در انتظار تصمیم شماست.\n"
                    "جهت بررسی روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
                ),
            )
        except Exception:
            logger.exception("ارسال Push برای درخواست مرخصی/ماموریت جدید با خطا مواجه شد")

    async def _notify_requester_of_decision(self, site_id: int, emp_no: int) -> None:
        try:
            result = await self.db.execute(
                select(User)
                .join(Employee, Employee.id == User.employee_id)
                .where(Employee.site_id == site_id, Employee.personnel_code == str(emp_no))
            )
            requester_user = result.scalar_one_or_none()
            if requester_user is None:
                return
            await PushService(self.db).notify_users(
                {requester_user.id},
                url="/leave-requests?tab=my-requests",
                priority="normal",
                body=(
                    "درخواست مرخصی/ماموریت شما بررسی شد.\n"
                    "جهت مشاهده نتیجه روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
                ),
            )
        except Exception:
            logger.exception("ارسال Push برای تصمیم درخواست مرخصی/ماموریت با خطا مواجه شد")

    # ---------- خواندن/نمایش ----------

    async def _get_type_lookup(self, site_id: int) -> dict:
        """
        ⚠️ برای نمایش «نوع درخواست» جداگانه از توضیحات - نگاشت ترکیب
        (OperationsID, ActionId, Card_No) هر نوع فعلی این سایت به
        (شناسه، عنوان) آن. چون WF_Requests شناسه نوع پورتال را ذخیره
        نمی‌کند، این تنها راه بازشناسی نوع یک درخواست موجود است.
        """
        result = await self.db.execute(select(LeaveRequestType).where(LeaveRequestType.site_id == site_id))
        types = result.scalars().all()
        return {(t.operation_id, t.action_id, t.card_no): (t.id, t.title) for t in types}

    async def _get_requester_info(self, site_id: int, emp_nos: list) -> dict:
        """
        ⚠️ برای نمایش «نام و نام خانوادگی» و «واحد» درخواست‌دهنده - نگاشت
        کد پرسنلی (Emp_No خام) به {name, department}، از جدول خودِ پورتال.
        """
        emp_no_strings = [str(e) for e in emp_nos if e is not None]
        if not emp_no_strings:
            return {}
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
            if e.personnel_code.isdigit()
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
        ⚠️ طبق درخواست صریح کاربر: جلوگیری از ثبت دو درخواست هم‌پوشان برای
        یک نفر. فقط درخواست‌های «در حال بررسی» و «تأییدشده» مانع می‌شوند -
        درخواست ردشده هیچ تداخلی ایجاد نمی‌کند.

        برای نوع ساعتی، تداخل یعنی همان روز و هم‌پوشانی بازه ساعت‌ها؛ برای
        نوع روزانه، تداخل یعنی هم‌پوشانی بازه‌ی روزها. یک درخواست ساعتی و
        یک درخواست روزانه در همان روز هم تداخل محسوب می‌شوند.
        """
        emp_no = _to_personnel_code_int(employee)
        col = _quote(site_connection.db_type, mapping.emp_no_column)
        rows = await asyncio.to_thread(
            _select_requests_sync, site_connection, mapping, f"{col} = %(emp_no)s", {"emp_no": emp_no}
        )
        new_start = start_date
        new_end = end_date or start_date

        for row in rows:
            if row.get("IsFinalApproved") is False:
                continue  # ردشده - مانع نیست
            existing_start_raw = row.get("StartDate")
            if not existing_start_raw:
                continue
            existing_start = existing_start_raw.date() if hasattr(existing_start_raw, "date") else existing_start_raw
            existing_end_raw = row.get("EndDate")
            existing_end = (
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
                    continue
            raise LeaveRequestError("برای همین بازه زمانی از قبل درخواستی ثبت کرده‌اید")

    async def get_pending_count_for_approver(self, approver_employee: Employee) -> int:
        """⚠️ برای شمارنده روی کارت داشبورد پرسنل (مثل شمارنده ارزیابی عملکرد) - تعداد درخواست‌های در انتظار تصمیم این فرد."""
        try:
            pending = await self.list_pending_for_approver(approver_employee)
        except LeaveRequestError:
            # اگر این سایت اصلاً نگاشت مرخصی/ماموریت ندارد، شمارنده صفر است - نه خطا
            return 0
        return len(pending)

    async def delete_request(self, request_id: int, employee: Employee) -> None:
        """
        ⚠️ طبق درخواست صریح کاربر - فقط درخواست‌های خودِ فرد، و فقط تا
        وقتی هنوز تصمیم‌گیری نشده (IsFinalApproved هنوز NULL است) قابل
        حذف هستند - نه یک درخواستِ از قبل تائید/ردشده.
        """
        mapping, site_connection = await self._get_mapping_and_connection(employee.site_id)
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
        emp_no = _to_personnel_code_int(employee)
        if request_row.get("EmpNo") != emp_no:
            raise LeaveRequestError("شما مجاز به حذف این درخواست نیستید")
        if request_row.get("IsFinalApproved") is not None:
            raise LeaveRequestError("این درخواست قبلاً تصمیم‌گیری شده - دیگر قابل‌حذف نیست")
        await asyncio.to_thread(_delete_request_sync, site_connection, mapping, request_id)

    async def admin_delete_request(self, site_id: int, request_id: int) -> None:
        """
        ⚠️ طبق درخواست صریح کاربر: حذف مدیریتی - برخلاف delete_request که
        فقط درخواست خودِ فرد و فقط تا قبل از تصمیم‌گیری را حذف می‌کند،
        اینجا دارنده مجوز leave_requests.manage می‌تواند **هر** درخواستی
        را در **هر مرحله‌ای** (در حال بررسی، تأییدشده، ردشده) حذف کند.

        ⚠️ ردیف‌های همه جدول‌های وابسته هم حذف می‌شوند (WF_Reviews،
        WF_Attachment، WF_MoveUp، WF_RequestParallelApproval) - چون هر
        چهار Foreign Key در دیتابیس Kara از نوع NO_ACTION هستند و اگر
        ردیفی داشته باشند، حذف خودِ درخواست شکست می‌خورد. ترتیب عمداً اول
        وابسته‌ها بعد خودِ درخواست است.
        """
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

        # ⚠️ هم‌رفتاری با کاراوب: اگر درخواست تأییدشده بود، اثرش در کارکرد
        # (تردد علامت‌خورده یا ردیف Mor_Mam) هم باید برداشته شود؛ و
        # WF_RequestState (بدون کلید خارجی) هم باید دستی پاک شود.
        if _kara_writeback_enabled(site_connection, mapping):
            if rows[0].get("IsFinalApproved"):
                await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_wb.revert_effects,
                    rows[0],
                    None,
                    mapping.application_id_value,
                )
            await asyncio.to_thread(
                _run_kara_writeback_sync, site_connection, kara_wb.delete_request_state_rows, request_id
            )

        await asyncio.to_thread(_delete_dependent_rows_sync, site_connection, mapping, request_id)
        await asyncio.to_thread(_delete_request_sync, site_connection, mapping, request_id)

    async def list_my_requests(self, employee: Employee) -> list[dict]:
        mapping, site_connection = await self._get_mapping_and_connection(employee.site_id)
        emp_no = _to_personnel_code_int(employee)
        col = _quote(site_connection.db_type, mapping.emp_no_column)
        rows = await asyncio.to_thread(
            _select_requests_sync, site_connection, mapping, f"{col} = %(emp_no)s", {"emp_no": emp_no}
        )
        type_lookup = await self._get_type_lookup(employee.site_id)
        normalized = [_normalize_row(row, type_lookup) for row in rows]
        await self._apply_real_reviews(site_connection, mapping, normalized)
        return normalized

    async def _apply_real_reviews(self, site_connection, mapping, normalized: list[dict]) -> None:
        """
        ⚠️ کشف حیاتی (تأییدشده با داده واقعی): نظر واقعی تأییدکننده در
        ManagerIdea نیست، در WF_Reviews است. اگر برای این سایت تنظیم
        نشده یا نظری ثبت نشده باشد، همان مقدار خامِ ManagerIdea که
        _normalize_row قبلاً گذاشته دست‌نخورده باقی می‌ماند.
        """
        request_ids = [item["request_id"] for item in normalized if item.get("status") != "pending"]
        if not request_ids:
            return
        reviews = await asyncio.to_thread(_select_latest_reviews_sync, site_connection, mapping, request_ids)
        for item in normalized:
            real_comment = reviews.get(item["request_id"])
            if real_comment is not None:
                item["manager_idea"] = real_comment

    async def list_pending_for_approver(self, approver_employee: Employee) -> list[dict]:
        mapping, site_connection = await self._get_mapping_and_connection(approver_employee.site_id)
        cur_emp_no = _to_personnel_code_int(approver_employee)
        cur_col = _quote(site_connection.db_type, mapping.cur_emp_no_column)
        approved_col = _quote(site_connection.db_type, mapping.is_final_approved_column)
        where_sql = f"{cur_col} = %(cur_emp_no)s AND {approved_col} IS NULL"
        rows = await asyncio.to_thread(
            _select_requests_sync, site_connection, mapping, where_sql, {"cur_emp_no": cur_emp_no}
        )
        type_lookup = await self._get_type_lookup(approver_employee.site_id)
        requester_info = await self._get_requester_info(
            approver_employee.site_id, [row.get("EmpNo") for row in rows]
        )
        normalized = []
        for row in rows:
            item = _normalize_row(row, type_lookup)
            info = requester_info.get(item["emp_no"], {})
            item["requester_name"] = info.get("name")
            item["requester_department"] = info.get("department")
            normalized.append(item)
        return normalized

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
        ⚠️ فقط برای دارندگان مجوز leave_requests.view/leave_requests.manage
        (یا مجوز محدود به تفکیک نوع - LeaveRequestTypeViewer).

        ⚠️ طبق درخواست صریح کاربر: اگر allowed_type_ids داده شود (یعنی
        کاربر مجوز سراسری ندارد، فقط به چند نوع خاص دسترسی دارد)، فقط
        درخواست‌هایی که با یکی از آن نوع‌ها تطبیق دارند برگردانده می‌شوند
        - نه همه‌ی درخواست‌های سایت.

        ⚠️ فیلترهای گزارشی (بازه تاریخی، وضعیت، نوع، واحد) - بازه تاریخی
        بر اساس تاریخ خودِ مرخصی/ماموریت است (نه تاریخ ثبت)، چون گزارش‌گیری
        واقعی همیشه «چه کسانی در فلان بازه مرخصی بودند» است.
        """
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        rows = await asyncio.to_thread(_select_requests_sync, site_connection, mapping, "1 = 1", {})
        type_lookup = await self._get_type_lookup(site_id)
        requester_info = await self._get_requester_info(site_id, [row.get("EmpNo") for row in rows])
        normalized = []
        for row in rows:
            item = _normalize_row(row, type_lookup)
            if allowed_type_ids is not None and item["type_id"] not in allowed_type_ids:
                continue
            if type_id_filter is not None and item["type_id"] != type_id_filter:
                continue
            if status_filter and item["status"] != status_filter:
                continue
            if date_from or date_to:
                item_start = item["start_date"]
                if item_start is None:
                    continue
                item_start = item_start.date() if hasattr(item_start, "date") else item_start
                item_end = item["end_date"] or item["start_date"]
                item_end = item_end.date() if hasattr(item_end, "date") else item_end
                if date_to and item_start > date_to:
                    continue
                if date_from and item_end < date_from:
                    continue
            info = requester_info.get(item["emp_no"], {})
            if department_filter and info.get("department") != department_filter:
                continue
            item["requester_name"] = info.get("name")
            item["requester_department"] = info.get("department")
            normalized.append(item)
        await self._apply_real_reviews(site_connection, mapping, normalized)
        return normalized

    async def _list_lookup(
        self, site_id: int, table_name: str | None, id_column: str | None, desc_column: str | None
    ) -> list[dict]:
        """
        ⚠️ تابع کمکی عمومی - طبق درخواست صریح کاربر، سه جدول مرجع
        (WF_Action، WF_OperationTypes، Cards) دقیقاً همین الگو را دارند:
        یک ستون شناسه + یک ستون عنوان فارسی. اگر برای این سایت تنظیم
        نشده باشد (نام جدول خالی)، فهرست خالی برمی‌گرداند - نه خطا؛ چون
        کاملاً اختیاری است.
        """
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        if not table_name:
            return []
        rows = await asyncio.to_thread(_select_lookup_sync, site_connection, table_name, id_column, desc_column)
        return [
            {"lookup_id": row.get("LookupId"), "title": row.get("LookupTitle")}
            for row in rows
            if row.get("LookupId") is not None
        ]

    async def list_action_lookup(self, site_id: int) -> list[dict]:
        """فهرست رسمی WF_Action (ActionId + عنوان فارسی) - برای کمک به پنل ادمین هنگام ساخت «نوع درخواست» جدید."""
        mapping, _ = await self._get_mapping_and_connection(site_id)
        items = await self._list_lookup(
            site_id, mapping.action_lookup_table_name, mapping.action_lookup_id_column, mapping.action_lookup_desc_column
        )
        return [{"action_id": item["lookup_id"], "title": item["title"]} for item in items]

    async def list_operation_lookup(self, site_id: int) -> list[dict]:
        """فهرست رسمی WF_OperationTypes (OperationId + عنوان فارسی)."""
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
        فهرست رسمی Cards (Card_No + عنوان فارسی + ActionId مرتبط). برخلاف
        list_action_lookup/list_operation_lookup (که از تابع عمومی
        _list_lookup استفاده می‌کنند)، این یکی از _select_card_lookup_sync
        اختصاصی استفاده می‌کند - چون کشف شد ActionId همیشه از همین کارت
        مشتق می‌شود، نه مستقل.
        """
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        if not mapping.card_lookup_table_name:
            return []
        rows = await asyncio.to_thread(_select_card_lookup_sync, site_connection, mapping)
        return [
            {"card_no": row.get("LookupId"), "title": row.get("LookupTitle"), "action_id": row.get("LinkedActionId")}
            for row in rows
            if row.get("LookupId") is not None
        ]

    # ---------- تصمیم‌گیری (تأییدکننده) ----------

    async def decide_request(
        self, site_id: int, request_id: int, approver_employee: Employee, approved: bool, manager_idea: str
    ) -> None:
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
        request_row = rows[0]

        approver_emp_no = _to_personnel_code_int(approver_employee)
        if request_row.get("CurEmpNo") != approver_emp_no:
            raise LeaveRequestError("شما مجاز به تصمیم‌گیری روی این درخواست نیستید")
        if request_row.get("IsFinalApproved") is not None:
            raise LeaveRequestError("این درخواست قبلاً تصمیم‌گیری شده است")

        # ⚠️ طبق تصمیم صریح کاربر (هم‌راستا با رفتار واقعی کاراوب):
        # ManagerIdea عمداً خالی نوشته می‌شود. بررسی رکوردهای واقعیِ
        # ساخته‌شده توسط خودِ کاراوب نشان داد این ستون همیشه خالی است و
        # نظر واقعی فقط در WF_Reviews.Description ذخیره می‌شود - پس
        # نوشتن همزمان در هر دو جا، دو منبع حقیقت می‌ساخت که می‌توانستند
        # از هم واگرا شوند (دقیقاً همان باگی که در ویرایش مدیریتی دیدیم).
        updates = {
            mapping.is_final_approved_column: approved,
            mapping.approval_by_manager_column: approver_emp_no,
            mapping.approval_date_column: datetime.now(),
            mapping.manager_idea_column: "",
        }
        await asyncio.to_thread(_update_request_sync, site_connection, mapping, request_id, updates)

        # ⚠️ هم‌رفتاری با کاراوب: تأیید نهایی باید در کارکرد هم اثر کند -
        # ساعتی روی تردد مطابق (یا AcceptCode=8 اگر ترددی نیست)، روزانه در
        # Mor_Mam. اگر این مرحله شکست بخورد، خودِ تأیید هم برگردانده می‌شود
        # تا درخواستی «تأییدشده ولی بی‌اثر» باقی نماند.
        if approved and _kara_writeback_enabled(site_connection, mapping):
            try:
                await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_wb.apply_on_approval,
                    request_row,
                    approver_emp_no,
                    mapping.application_id_value,
                    mapping.branch_code_value or 1,
                )
            except Exception as e:
                logger.exception("اعمال تأیید درخواست %s در کارکرد کاراوب شکست خورد", request_id)
                rollback = {
                    mapping.is_final_approved_column: None,
                    mapping.approval_by_manager_column: None,
                    mapping.approval_date_column: None,
                }
                await asyncio.to_thread(_update_request_sync, site_connection, mapping, request_id, rollback)
                raise LeaveRequestError(f"ثبت این تأیید در کارکرد کاراوب با خطا مواجه شد: {e}") from e

        # ⚠️ کشف حیاتی (تأییدشده با داده واقعی): نظر واقعی تأییدکننده در
        # ManagerIdea ذخیره نمی‌شود - باید در WF_Reviews هم ثبت شود تا هم
        # در خودِ کاراوب صحیح دیده شود، هم توسط پورتال به‌درستی خوانده شود.
        #
        # ⚠️ تصحیح مهم (با داده واقعیِ یک رد‌شده از خودِ کاراوب تأیید شد):
        # ReviewType اصلاً «تأیید/رد» را نشان نمی‌دهد - کاراوب برای هر دو
        # حالت مقدار یکسانی (۴) می‌نویسد؛ تصمیم واقعی فقط در
        # WF_Requests.IsFinalApproved ذخیره می‌شود. فرض قبلی (مقدار
        # متفاوت برای رد) اشتباه بود و باعث می‌شد رد‌کردن از پورتال، مقداری
        # در WF_Reviews بنویسد که کاراوب هرگز تولید نمی‌کند. حالا همیشه
        # همان مقدار استانداردِ کاراوب نوشته می‌شود.
        # ⚠️ طبق تصمیم صریح کاربر: وقتی مدیر اصلاً نظری ننوشته، هیچ ردیف
        # Review ساخته نمی‌شود - دقیقاً مثل کاراوب (رکورد تأییدشده‌ای در
        # دیتابیس بود که هیچ Review نداشت، چون مدیر متنی ننوشته بود).
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

        # ⚠️ اطلاع‌رسانی به درخواست‌دهنده - هرگز نباید خودِ تصمیم را متوقف کند.
        requester_emp_no = request_row.get("EmpNo")
        if requester_emp_no is not None:
            await self._notify_requester_of_decision(approver_employee.site_id, requester_emp_no)

    # ---------- ویرایش مدیریتی (فقط leave_requests.manage) ----------

    async def admin_update_request(self, site_id: int, request_id: int, updates: dict) -> None:
        """
        ⚠️ فقط برای دارندگان مجوز leave_requests.manage - طبق درخواست
        صریح: می‌تواند تصمیم (تأیید/رد)، نوع درخواست، و تاریخ/ساعت
        درخواست را هم ویرایش کند. کلیدهای مجاز updates: is_final_approved،
        start_date، end_date، start_hour، end_hour، leave_type_id،
        manager_idea، description.

        ⚠️ طبق درخواست صریح کاربر: «مدت» دیگر یک فیلد خام و مستقیماً
        قابل‌ویرایش نیست - چون کاربر معنایش را نمی‌فهمید. هرگاه هر دو
        ساعت شروع/پایان با هم داده شوند، مدت به‌صورت خودکار از رویشان
        محاسبه می‌شود (فرمت فشرده HHMM)؛ هرگاه هر دو تاریخ شروع/پایان با
        هم داده شوند، مدت به‌صورت خودکار از رویشان محاسبه می‌شود (تعداد
        روز) - دقیقاً همان قانونی که submit_request هنگام ثبت اولیه
        به‌کار می‌برد.

        ⚠️ leave_type_id ویژه است - یک ستون مستقیم در WF_Requests نیست؛
        وقتی داده شود، نوع موردنظر در LeaveRequestType این سایت پیدا شده
        و سه ستون واقعی مرتبط (OperationsID, ActionId, Card_No) بر همان
        اساس به‌روزرسانی می‌شوند - دقیقاً همان چیزی که submit_request هنگام
        ثبت اولیه می‌نویسد.
        """
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
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

        try:
            if updates.get("start_hour") is not None and updates.get("end_hour") is not None:
                column_updates[mapping.duration_column] = str(
                    compute_hourly_duration(updates["start_hour"], updates["end_hour"])
                )
            elif updates.get("start_date") is not None and updates.get("end_date") is not None:
                start_date_only = updates["start_date"].date() if hasattr(updates["start_date"], "date") else updates["start_date"]
                end_date_only = updates["end_date"].date() if hasattr(updates["end_date"], "date") else updates["end_date"]
                column_updates[mapping.duration_column] = str(compute_daily_duration(start_date_only, end_date_only))
        except LeaveRequestRulesError as e:
            raise LeaveRequestError(str(e)) from e

        if "leave_type_id" in updates and updates["leave_type_id"] is not None:
            leave_type = await self.db.get(LeaveRequestType, updates["leave_type_id"])
            if leave_type is None or leave_type.site_id != site_id:
                raise LeaveRequestError("نوع درخواست موردنظر یافت نشد")
            column_updates[mapping.operations_id_column] = (
                leave_type.operation_id if leave_type.operation_id is not None else (3 if leave_type.is_mission else 5)
            )
            if mapping.action_id_column and leave_type.action_id is not None:
                column_updates[mapping.action_id_column] = leave_type.action_id
            column_updates[mapping.card_no_column] = leave_type.card_no if leave_type.card_no is not None else 0

        # ⚠️ «نظر تأییدکننده» فقط در WF_Reviews.Description نوشته می‌شود -
        # نه در ManagerIdea. این هم‌راستا با رفتار واقعی کاراوب است (که
        # ManagerIdea را همیشه خالی می‌گذارد) و از داشتن دو منبع حقیقت که
        # می‌توانند واگرا شوند جلوگیری می‌کند - دقیقاً همان باگی که باعث شد
        # ویرایش ادمین در نمایش دیده نشود.
        #
        # اگر هنوز هیچ Review ای برای این درخواست ثبت نشده باشد (مثلاً
        # مدیر بدون نوشتن نظر تصمیم گرفته بود)، یک ردیف جدید درج می‌شود.
        new_manager_idea = updates.get("manager_idea")

        # ⚠️ هم‌رفتاری با کاراوب: تغییر وضعیت/تاریخ/ساعت/نوع یک درخواست
        # روی کارکرد اثر دارد - اثر قبلی (اگر تأییدشده بود) برداشته و بعد
        # از ویرایش، اگر همچنان/تازه تأییدشده است، دوباره اعمال می‌شود.
        writeback = _kara_writeback_enabled(site_connection, mapping) and bool(
            {"is_final_approved", "start_date", "end_date", "start_hour", "end_hour", "leave_type_id"}
            & set(updates)
        )
        request_id_col = _quote(site_connection.db_type, mapping.request_id_column)
        old_row = None
        if writeback:
            old_rows = await asyncio.to_thread(
                _select_requests_sync,
                site_connection,
                mapping,
                f"{request_id_col} = %(request_id)s",
                {"request_id": request_id},
            )
            old_row = old_rows[0] if old_rows else None
            if old_row and old_row.get("IsFinalApproved"):
                await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_wb.revert_effects,
                    old_row,
                    None,
                    mapping.application_id_value,
                )

        if column_updates:
            await asyncio.to_thread(_update_request_sync, site_connection, mapping, request_id, column_updates)

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
                approver = new_row.get("ApprovalByManagerEmpNo") or new_row.get("CurEmpNo")
                await asyncio.to_thread(
                    _run_kara_writeback_sync,
                    site_connection,
                    kara_wb.apply_on_approval,
                    new_row,
                    approver,
                    mapping.application_id_value,
                    mapping.branch_code_value or 1,
                )
            elif new_row:
                await asyncio.to_thread(_run_kara_writeback_sync, site_connection, kara_wb.clear_accept_code, request_id)

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
                    approver_emp_no or 0,
                    new_manager_idea or "",
                    mapping.wf_reviews_approved_type_value,
                )


def _normalize_row(row: dict, type_lookup: dict | None = None) -> dict:
    """
    یک ردیف خام WF_Requests را به شکل پایدار و مستقل از نوع دیتابیس منبع
    برای استفاده در Schema های Pydantic درمی‌آورد.

    ⚠️ طبق درخواست صریح کاربر: توضیحات کاربر (Description) دیگر شامل
    عنوان نوع نیست (آن دو جدا شدند) - عنوان نوع («نوع درخواست») اینجا با
    تطبیق ترکیب (OperationsID, ActionId, Card_No) این ردیف با
    LeaveRequestType های همان سایت به‌دست می‌آید؛ اگر type_lookup داده
    نشود یا تطبیقی پیدا نشود، type_id/type_title خالی می‌مانند (نه خطا -
    یک درخواست قدیمی‌تر ممکن است دیگر با هیچ نوع فعلی تطبیق نداشته باشد).
    """
    is_final_approved = row.get("IsFinalApproved")
    if is_final_approved is None:
        status = "pending"
    elif is_final_approved:
        status = "approved"
    else:
        status = "rejected"

    operations_id = row.get("OperationsID")
    action_id = row.get("ActionId")
    card_no = row.get("CardNo")
    type_key = (operations_id, action_id, card_no)
    matched_type = (type_lookup or {}).get(type_key)

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
        "is_mission": operations_id == 3,
        "description": row.get("Description"),
        "current_approver_emp_no": row.get("CurEmpNo"),
        "manager_idea": row.get("ManagerIdea"),
        "source": row.get("Source"),
        "destination": row.get("Distination"),
        "type_id": matched_type[0] if matched_type else None,
        "type_title": matched_type[1] if matched_type else None,
    }
