"""
تست منطق خالص امنیت نام جدول/ستون (H5): اعتبارسنجی مشترک validate_sql_identifier، escape جداکننده‌ی
پایانی در توابع _quote/_q هر نوع دیتابیس، KaraNames و سقف حجم Zip اکسل (M9) و فیلدهای SMB (M8).
"""
import sys
import types

import pytest


def _stub_missing(*names: str) -> None:
    """ماژول‌های درایور دیتابیس را اگر نصب نیستند با ماژول خالی جایگزین می‌کند (فقط برای import شدن adapter)."""
    for name in names:
        try:
            __import__(name)
        except ImportError:
            mod = types.ModuleType(name)
            sys.modules[name] = mod
            if "." in name:
                parent, child = name.rsplit(".", 1)
                setattr(sys.modules[parent], child, mod)


# ---------- validate_sql_identifier ----------


def test_identifier_accepts_safe_names_and_empty():
    from app.services.kara_schema import validate_sql_identifier as v

    assert v("Emp_No") == "Emp_No"
    assert v("  Card No 1 ") == "Card No 1"
    assert v(None) is None and v("") is None and v("   ") is None
    assert v("dbo.Employee", allow_schema=True) == "dbo.Employee"


@pytest.mark.parametrize(
    "bad",
    ["Emp]; DROP TABLE x--", "a`b", 'a"b', "1abc", "dbo.a.b", "a..b", "x" * 129, "نام", "a;b", "a-b"],
)
def test_identifier_rejects_unsafe_names(bad):
    from app.services.kara_schema import validate_sql_identifier as v

    with pytest.raises(ValueError, match="حرف، عدد، زیرخط و فاصله"):
        v(bad, allow_schema=True)


def test_identifier_without_schema_rejects_dot():
    from app.services.kara_schema import validate_sql_identifier as v

    with pytest.raises(ValueError):
        v("dbo.Employee")


# ---------- escape جداکننده در quote ها ----------


def test_quote_mssql_escapes_bracket_and_splits_schema():
    from app.services.kara_schema import quote_mssql

    assert quote_mssql("Emp_No") == "[Emp_No]"
    assert quote_mssql("dbo.Employee") == "[dbo].[Employee]"
    assert quote_mssql("x]; DROP TABLE t--") == "[x]]; DROP TABLE t--]"


def test_kara_names_quote_escapes():
    from app.services.kara_schema import KaraNames

    leave = types.SimpleNamespace(kara_schema={"wf_moveup.table": "WF]MoveUp", "wf_moveup.request_id": "Req]Id"})
    n = KaraNames(leave_mapping=leave)
    assert n.t("wf_moveup") == "[WF]]MoveUp]"
    assert n.c("wf_moveup", "request_id") == "[Req]]Id]"
    assert KaraNames._q("dbo.WF_Requests", "x") == "[dbo].[WF_Requests]"


def test_adapter_quote_helpers_escape_closing_delimiter():
    _stub_missing("pymssql", "pymysql", "pymysql.cursors", "psycopg2", "psycopg2.extras")
    from app.sync_engine.adapters.mssql_adapter import _q as q_mssql
    from app.sync_engine.adapters.mysql_adapter import _q as q_mysql
    from app.sync_engine.adapters.postgresql_adapter import _q as q_pg

    assert q_mssql("a]b") == "[a]]b]" and q_mssql("dbo.T") == "[dbo].[T]"
    assert q_mysql("a`b") == "`a``b`" and q_mysql("s.T") == "`s`.`T`"
    assert q_pg('a"b') == '"a""b"' and q_pg("s.T") == '"s"."T"'


def test_service_quote_helpers_escape_closing_delimiter():
    pytest.importorskip("sqlalchemy")
    _stub_missing("pymssql", "pymysql", "pymysql.cursors", "psycopg2", "psycopg2.extras")
    from app.models.site import DbType
    from app.services.kara_attendance_overlay import _quote as q_overlay
    from app.services.leave_request_service import _quote as q_leave
    from app.services.monthly_attendance_service import _quote as q_month

    for q in (q_leave, q_month):
        assert q(DbType.mssql, "a]b") == "[a]]b]"
        assert q(DbType.mysql, "a`b") == "`a``b`"
        assert q(DbType.postgresql, 'a"b') == '"a""b"'
        assert q(DbType.mssql, "dbo.T") == "[dbo].[T]"
    assert q_overlay("Card]1") == "[Card]]1]"


# ---------- Schema های نگاشت (نیاز به pydantic و مدل‌ها) ----------


def test_mapping_schemas_reject_unsafe_identifiers():
    pytest.importorskip("sqlalchemy")
    pydantic = pytest.importorskip("pydantic")
    from app.schemas.leave_request import LeaveRequestMappingIn
    from app.schemas.site import AttendanceMappingIn, EmployeeMappingIn

    base = dict(table_name="dbo.Employee", personnel_code_column="Emp No", first_name_column="F", last_name_column="L")
    ok = EmployeeMappingIn(**base, photo_table="  ")
    assert ok.table_name == "dbo.Employee" and ok.photo_table is None

    with pytest.raises(pydantic.ValidationError):
        EmployeeMappingIn(**{**base, "table_name": "Emp]; DROP--"})
    with pytest.raises(pydantic.ValidationError):
        EmployeeMappingIn(**{**base, "personnel_code_column": "a.b"})  # ستون: نقطه مجاز نیست
    with pytest.raises(pydantic.ValidationError):
        LeaveRequestMappingIn(wf_moveup_table_name="x`y")
    with pytest.raises(pydantic.ValidationError):
        AttendanceMappingIn(
            table_name="T", personnel_code_column="P", date_column="d", time_column="t", calendar_day_column_prefix="Day]"
        )


def test_backup_smb_fields_reject_injection_chars():
    pytest.importorskip("sqlalchemy")
    from app.schemas.backup import _clean_smb_field

    assert _clean_smb_field(" backups/faipco ", "smb_path") == "backups/faipco"
    for bad in ['a"b', "a;b", "a`b", "a\nb", "a$(id)b"]:
        with pytest.raises(ValueError):
            _clean_smb_field(bad, "smb_path")


# ---------- سقف حجم Zip اکسل (M9) ----------


def test_xlsx_size_cap():
    import io
    import zipfile

    pytest.importorskip("openpyxl")
    from app.services.payroll_common import PayrollParseError
    from app.services.payroll_xlsx import check_xlsx_size

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/sheet1.xml", b"0" * 1024)
    data = buf.getvalue()
    check_xlsx_size(data)  # زیر سقف
    with pytest.raises(PayrollParseError):
        check_xlsx_size(data, max_bytes=100)
    with pytest.raises(PayrollParseError):
        check_xlsx_size(b"not a zip")
