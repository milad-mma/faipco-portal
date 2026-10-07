"""تست منطق خالص «گزارش خطاها»: حذف اطلاعات حساس، گروه‌بندی خطاهای یکسان، دسته و راهنما."""
import pytest


def _svc():
    pytest.importorskip("sqlalchemy")
    import app.services.error_log_service as svc

    return svc


def test_redact_removes_secrets():
    svc = _svc()
    text = "connect failed password=Sup3r! token: abc.def Authorization: Bearer xyz postgresql://u:pw@h/db"
    out = svc.redact(text)
    assert "Sup3r" not in out and "pw@" not in out and "Bearer xyz" not in out
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0abcdefgh.abcdefghijklmnop"
    assert "eyJ" not in svc.redact(f"ws?token={jwt}")
    # قالب دیکشنری پایتون (پارامترهای SQLAlchemy)، مقدار کوتیشن‌دار با فاصله، و Basic
    out = svc.redact("{'hashed_password': '$2b$12$abc', 'name': 'ali'} password = \"a b\" Authorization: Basic dXNlcjpw")
    assert "$2b$" not in out and '"a b"' not in out and "dXNlcjpw" not in out and "'ali'" in out
    assert svc.redact("tokenize step failed") == "tokenize step failed"


def test_nul_bytes_are_removed():
    svc = _svc()
    assert svc._clean("a\x00b") == "ab"
    assert svc._clean_context({"page": "/x\x00"}) == {"page": "/x"}


def test_same_error_with_different_numbers_is_one_group():
    svc = _svc()
    a = svc._fingerprint("error", "kara", "x", "Emp_No=225735 failed after 10s")
    b = svc._fingerprint("error", "kara", "x", "Emp_No=235508 failed after 12s")
    c = svc._fingerprint("error", "kara", "x", "Invalid column name 'BranchCode'")
    assert a == b and a != c


def test_category_and_hint():
    svc = _svc()
    msg = 'pymssql.exceptions.ProgrammingError: (207, b"Invalid column name \'BranchCode\'.")'
    assert svc._category_for("app.services.monthly_attendance_service", msg) == "kara"
    assert "BranchCode" in svc.hint_for("error", "kara", "Invalid column name 'BranchCode'.")
    assert svc.hint_for("slow", "slow", "x")
    assert svc.hint_for("error", "server", "something unknown") is None
