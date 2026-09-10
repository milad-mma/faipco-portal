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
from datetime import date, datetime

import pymssql
import pymysql
import pymysql.cursors
import psycopg2
import psycopg2.extras
import jdatetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
                {q(mapping.destination_column)} AS {q("Distination")}
            FROM {q(mapping.table_name)}
            WHERE {where_sql} {branch_sql}
            ORDER BY {q(mapping.request_id_column)} DESC
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with _dict_cursor(connection, conn.db_type) as cur:
            cur.execute(query, {**params, **branch_params})
            return list(cur.fetchall())
    finally:
        connection.close()


def _insert_request_sync(conn: SiteConnection, mapping: LeaveRequestMapping, values: dict) -> int:
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    column_map = {
        mapping.emp_no_column: values["emp_no"],
        mapping.submitting_date_column: values["submitting_date"],
        mapping.card_no_column: 0,  # ⚠️ معنای دقیق نامشخص - طبق تصمیم صریح همیشه ۰
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

        mapping, site_connection = await self._get_mapping_and_connection(employee.site_id)

        approver_employee_id = await self._get_approver_employee_id(employee.department_id)
        if approver_employee_id is None:
            raise LeaveRequestError(
                "برای واحد سازمانی شما هنوز تأییدکننده مرخصی/ماموریت تعیین نشده - لطفاً با منابع انسانی هماهنگ کنید"
            )
        approver = await self.db.get(Employee, approver_employee_id)
        if approver is None:
            raise LeaveRequestError("تأییدکننده این واحد یافت نشد")

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
            "operations_id": 3 if leave_type.is_mission else 5,
            "description": f"{leave_type.title} — {description}" if description else leave_type.title,
            "cur_emp_no": _to_personnel_code_int(approver),
            "persian_start_date": persian_start_date,
            "source": source if leave_type.is_mission else None,
            "destination": destination if leave_type.is_mission else None,
        }

        new_request_id = await asyncio.to_thread(_insert_request_sync, site_connection, mapping, values)
        return {"request_id": new_request_id}

    # ---------- خواندن/نمایش ----------

    async def list_my_requests(self, employee: Employee) -> list[dict]:
        mapping, site_connection = await self._get_mapping_and_connection(employee.site_id)
        emp_no = _to_personnel_code_int(employee)
        col = _quote(site_connection.db_type, mapping.emp_no_column)
        rows = await asyncio.to_thread(
            _select_requests_sync, site_connection, mapping, f"{col} = %(emp_no)s", {"emp_no": emp_no}
        )
        return [_normalize_row(row) for row in rows]

    async def list_pending_for_approver(self, approver_employee: Employee) -> list[dict]:
        mapping, site_connection = await self._get_mapping_and_connection(approver_employee.site_id)
        cur_emp_no = _to_personnel_code_int(approver_employee)
        cur_col = _quote(site_connection.db_type, mapping.cur_emp_no_column)
        approved_col = _quote(site_connection.db_type, mapping.is_final_approved_column)
        where_sql = f"{cur_col} = %(cur_emp_no)s AND {approved_col} IS NULL"
        rows = await asyncio.to_thread(
            _select_requests_sync, site_connection, mapping, where_sql, {"cur_emp_no": cur_emp_no}
        )
        return [_normalize_row(row) for row in rows]

    async def list_all_for_site(self, site_id: int) -> list[dict]:
        """⚠️ فقط برای دارندگان مجوز leave_requests.view/leave_requests.manage - همه درخواست‌های این سایت، بدون فیلتر."""
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        rows = await asyncio.to_thread(_select_requests_sync, site_connection, mapping, "1 = 1", {})
        return [_normalize_row(row) for row in rows]

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

        updates = {
            mapping.is_final_approved_column: approved,
            mapping.approval_by_manager_column: approver_emp_no,
            mapping.approval_date_column: datetime.now(),
            mapping.manager_idea_column: manager_idea or "",
        }
        await asyncio.to_thread(_update_request_sync, site_connection, mapping, request_id, updates)

    # ---------- ویرایش مدیریتی (فقط leave_requests.manage) ----------

    async def admin_update_request(self, site_id: int, request_id: int, updates: dict) -> None:
        """
        ⚠️ فقط برای دارندگان مجوز leave_requests.manage - طبق درخواست
        صریح: می‌تواند تصمیم (تأیید/رد) و تاریخ/ساعت درخواست را هم ویرایش
        کند. کلیدهای مجاز updates: is_final_approved، start_date، end_date،
        start_hour، end_hour، manager_idea، description.
        """
        mapping, site_connection = await self._get_mapping_and_connection(site_id)
        column_updates: dict = {}
        key_to_column = {
            "is_final_approved": mapping.is_final_approved_column,
            "start_date": mapping.start_date_column,
            "end_date": mapping.end_date_column,
            "start_hour": mapping.start_hour_column,
            "end_hour": mapping.end_hour_column,
            "manager_idea": mapping.manager_idea_column,
            "description": mapping.description_column,
        }
        for key, column in key_to_column.items():
            if key in updates:
                column_updates[column] = updates[key]
        if not column_updates:
            return
        await asyncio.to_thread(_update_request_sync, site_connection, mapping, request_id, column_updates)


def _normalize_row(row: dict) -> dict:
    """
    یک ردیف خام WF_Requests را به شکل پایدار و مستقل از نوع دیتابیس منبع
    برای استفاده در Schema های Pydantic درمی‌آورد.
    """
    is_final_approved = row.get("IsFinalApproved")
    if is_final_approved is None:
        status = "pending"
    elif is_final_approved:
        status = "approved"
    else:
        status = "rejected"

    operations_id = row.get("OperationsID")

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
    }
