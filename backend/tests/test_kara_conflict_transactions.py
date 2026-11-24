"""Mocked connection tests for conflict-gated insertion and final decisions.

No live SQL Server/PostgreSQL connection is used.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.kara_request_conflicts import RequestConflictError


@pytest.fixture
def svc(monkeypatch):
    for module in ("pymssql", "pymysql", "psycopg2", "jdatetime", "asyncpg", "passlib", "pywebpush"):
        pytest.importorskip(module)
    from cryptography.fernet import Fernet
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("SECRET_KEY", "test-only-not-for-production-" + "x" * 40)
    monkeypatch.setenv("DB_CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.services import leave_request_service
    return leave_request_service


class Connection:
    def __init__(self):
        self.events = []

    def cursor(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params):
        self.events.append(sql.strip().split()[0])

    def fetchone(self):
        return (1351,)

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")

    def close(self):
        self.events.append("close")


@pytest.fixture
def mapping():
    keys = """request_id emp_no submitting_date card_no start_date end_date start_hour end_hour duration
    operations_id description cur_emp_no is_first_time_shift persian_start_date application_id source destination
    action_id is_final_approved approval_by_manager approval_date manager_idea branch_code""".split()
    return SimpleNamespace(**{k + "_column": k for k in keys}, table_name="WF_Requests",
                           branch_code_value=1, application_id_value=4)


@pytest.fixture
def values():
    return dict(emp_no=972199, submitting_date=datetime(2026, 11, 21, 8), card_no=57,
                start_date=datetime(2026, 11, 21), end_date=datetime(2026, 11, 21), duration=1,
                operations_id=5, description="", cur_emp_no=215331, persian_start_date=14050830)


@pytest.mark.parametrize("conflict", [False, True])
def test_insert_checks_and_commits_on_same_connection(svc, monkeypatch, mapping, values, conflict):
    connection = Connection()
    monkeypatch.setattr(svc, "_connect", lambda conn: connection)
    def check(cur, *args):
        assert cur is connection
        connection.events.append("check")
        if conflict:
            raise RequestConflictError("conflict")
    monkeypatch.setattr(svc, "_check_new_kara_request", check)
    conn = SimpleNamespace(db_type=svc.DbType.mssql)
    if conflict:
        with pytest.raises(RequestConflictError):
            svc._insert_request_sync(conn, mapping, values, conflict_names=object())
        assert connection.events == ["check", "rollback", "close"]
    else:
        assert svc._insert_request_sync(conn, mapping, values, conflict_names=object()) == 1351
        assert connection.events == ["check", "INSERT", "commit", "close"]


def decision_setup(svc, monkeypatch, mapping, approved, *, conflict=False, stale=False, fail_apply=False):
    connection = Connection()
    conn = SimpleNamespace(db_type=svc.DbType.mssql)
    expected = dict(RequestId=1350, EmpNo=972199, CurEmpNo=215331, IsFinalApproved=None,
                    AcceptCode=None, StartDate=datetime(2026, 11, 21), EndDate=datetime(2026, 11, 21),
                    StartHour=None, EndHour=None, Duration="1", CardNo=57, OperationsID=5)
    current = dict(expected)
    if stale:
        current["IsFinalApproved"] = True
    updates = {mapping.is_final_approved_column: approved, mapping.approval_by_manager_column: 215331}
    monkeypatch.setattr(svc, "_connect", lambda conn: connection)
    def locked(cur, *args):
        assert cur is connection
        connection.events.append("lock")
        return [current]
    def guard(cur, *args):
        assert cur is connection
        connection.events.append("check")
        if conflict:
            raise RequestConflictError("manual conflict")
    def select(*args, cursor, **kwargs):
        assert cursor is connection
        connection.events.append("verify")
        return [dict(current, IsFinalApproved=approved, ApprovalByManagerEmpNo=215331)]
    def apply(cur, *args):
        assert cur is connection
        connection.events.append("apply")
        if fail_apply:
            raise RuntimeError("write failed")
        return 0
    monkeypatch.setattr(svc, "_locked_request_rows", locked)
    monkeypatch.setattr(svc, "_check_attendance_conflicts", guard)
    monkeypatch.setattr(svc, "_select_requests_sync", select)
    monkeypatch.setattr(svc.kara_wb, "apply_on_approval", apply)
    run = lambda: svc._decide_kara_ordinary_sync(conn, mapping, object(), expected, updates, 215331, approved, set())
    return connection, run


def test_hr_registers_after_submit_approval_does_not_write(svc, monkeypatch, mapping):
    connection, run = decision_setup(svc, monkeypatch, mapping, True, conflict=True)
    with pytest.raises(RequestConflictError):
        run()
    assert connection.events == ["lock", "check", "rollback", "close"]


def test_reject_never_checks_or_writes_attendance(svc, monkeypatch, mapping):
    connection, run = decision_setup(svc, monkeypatch, mapping, False, conflict=True)
    run()
    assert connection.events == ["lock", "UPDATE", "verify", "commit", "close"]


def test_approval_and_effect_commit_together(svc, monkeypatch, mapping):
    connection, run = decision_setup(svc, monkeypatch, mapping, True)
    run()
    assert connection.events == ["lock", "check", "UPDATE", "verify", "apply", "commit", "close"]


def test_writeback_failure_rolls_back_decision(svc, monkeypatch, mapping):
    connection, run = decision_setup(svc, monkeypatch, mapping, True, fail_apply=True)
    with pytest.raises(RuntimeError):
        run()
    assert connection.events == ["lock", "check", "UPDATE", "verify", "apply", "rollback", "close"]


def test_already_decided_row_cannot_be_applied_again(svc, monkeypatch, mapping):
    connection, run = decision_setup(svc, monkeypatch, mapping, True, stale=True)
    with pytest.raises(RequestConflictError):
        run()
    assert connection.events == ["lock", "rollback", "close"]
