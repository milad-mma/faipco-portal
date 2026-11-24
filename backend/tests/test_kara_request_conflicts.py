"""KaraWeb conflict rules with a fake read cursor; no live DB writes."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.kara_request_conflicts import (
    RequestConflictError, assert_no_request_overlap, assert_no_attendance_conflict,
    marked_hourly_conflict, request_interval,
)
from app.services.kara_schema import KaraNames, LEAVE_SCHEMA_DEFAULTS, ATTENDANCE_SCHEMA_DEFAULTS

DAY = date(2026, 11, 21)


def request(day=DAY, end=None, start_hour=None, end_hour=None, **extra):
    return {
        "RequestId": 1350, "EmpNo": 972199, "CardNo": 57,
        "StartDate": day, "EndDate": end,
        "StartHour": start_hour, "EndHour": end_hour,
        "Duration": 1 if start_hour is None else 100,
        "IsFinalApproved": None, "AcceptCode": None, **extra,
    }


def fake_jalali(d):
    # Fixed, monotonic fixture around 1405/08/30, including the month boundary.
    # Calendar conversion itself is supplied by the existing code in production.
    days = (d - DAY).days
    return 14050830 + days if days <= 0 else 14050900 + days


@pytest.fixture
def names():
    leave = SimpleNamespace(
        kara_schema=dict(LEAVE_SCHEMA_DEFAULTS), card_lookup_table_name="WF_Cards",
        card_lookup_id_column="Card_No", card_lookup_desc_column="Title",
    )
    attendance = SimpleNamespace(kara_schema=dict(ATTENDANCE_SCHEMA_DEFAULTS),
        mapping_mode="single_column", table_name="DataFile", personnel_code_column="Emp_No",
        date_column="IoDate", time_column="IoTime")
    return KaraNames(leave, attendance)


class Cursor:
    def __init__(self, daily=None, punches=(), failure=None):
        self.daily = daily
        self.punches = list(punches)
        self.calls = []
        self.failure = failure

    def execute(self, sql, params):
        self.calls.append((sql, params))
        assert sql.lstrip().startswith("SELECT")
        if self.failure:
            raise self.failure

    def fetchone(self):
        assert "AS SDate" in self.calls[-1][0]
        return self.daily

    def fetchall(self):
        assert "DataFile" in self.calls[-1][0]
        return self.punches


def check(cur, names, row=None, **kwargs):
    return assert_no_attendance_conflict(cur, names, row or request(), jalali_int=fake_jalali, **kwargs)


def punch(hour, status=0, day=DAY):
    return {"DateInt": fake_jalali(day), "Time": hour, "Status": status}


@pytest.mark.parametrize("state", [None, True, 1])
def test_pending_or_approved_request_conflicts(state):
    old = request(RequestId=1273, IsFinalApproved=state)
    with pytest.raises(RequestConflictError, match="درخواستی"):
        assert_no_request_overlap([old], request())


@pytest.mark.parametrize("old", [
    request(IsFinalApproved=False), request(IsFinalApproved=0),
    request(IsFinalApproved=True, AcceptCode=22),
    request(CardNo=99), request(start_hour=1200, end_hour=1200, Duration=0),
])
def test_rejected_cancelled_forgotten_or_exit_is_not_a_leave_conflict(old):
    assert_no_request_overlap([old], request(), {99})


def test_exclude_only_same_request_at_approval():
    assert_no_request_overlap([request()], request(), exclude_id=1350)
    with pytest.raises(RequestConflictError):
        assert_no_request_overlap([request(RequestId=1273), request()], request(), exclude_id=1350)


def test_partial_multiday_and_daily_hourly_overlap():
    with pytest.raises(RequestConflictError):
        assert_no_request_overlap([request(DAY - timedelta(days=2), DAY)], request(DAY, DAY + timedelta(days=2)))
    with pytest.raises(RequestConflictError):
        assert_no_request_overlap([request(start_hour=900, end_hour=1000)], request())
    assert_no_request_overlap([request(DAY - timedelta(days=1))], request())


def test_hourly_intervals_touch_but_do_not_overlap():
    assert_no_request_overlap([request(start_hour=800, end_hour=1000)], request(start_hour=1000, end_hour=1100))
    with pytest.raises(RequestConflictError):
        assert_no_request_overlap([request(start_hour=800, end_hour=1000)], request(start_hour=930, end_hour=1100))


def test_overnight_request_overlap_next_calendar_day():
    overnight = request(start_hour=2300, end_hour=200)
    with pytest.raises(RequestConflictError):
        assert_no_request_overlap([overnight], request(DAY + timedelta(days=1), start_hour=100, end_hour=300))
    assert_no_request_overlap([overnight], request(DAY + timedelta(days=1), start_hour=200, end_hour=300))


def test_manual_daily_record_is_detected_before_any_write(names):
    # The supplied case: HR record 612500 in Mor_Mam on 1405/08/30.
    cur = Cursor(daily={"SDate": 14050830, "EDate": 14050830})
    with pytest.raises(RequestConflictError, match="۱۴۰۵/۰۸/۳۰"):
        check(cur, names)
    assert len(cur.calls) == 1
    sql, params = cur.calls[0]
    assert "[Mor_Mam]" in sql and "WITH (UPDLOCK, HOLDLOCK)" in sql
    assert "[Inc_Type] = 0" in sql and "[Inc_Type] IS NULL" in sql
    assert "[IsDay] = 1" in sql
    assert "[S_Date] <= %(t)s" in sql and "[E_Date]" in sql and ">= %(f)s" in sql
    assert params == {"e": 972199, "f": 14050830, "t": 14050830, "card": 57}


def test_day_range_checks_all_days_including_end_date(names):
    cur = Cursor(daily={"SDate": 14050901, "EDate": 14050901})
    with pytest.raises(RequestConflictError, match="۱۴۰۵/۰۹/۰۱"):
        check(cur, names, request(DAY - timedelta(days=1), DAY + timedelta(days=1)))
    assert cur.calls[0][1]["f"] == 14050829
    assert cur.calls[0][1]["t"] == 14050901


@pytest.mark.parametrize("punches", [[], [punch(730), punch(1430)]])
def test_normal_punch_or_derived_absence_does_not_block(names, punches):
    cur = Cursor(punches=punches)
    check(cur, names)
    assert len(cur.calls) == 2
    assert all("WITH (UPDLOCK, HOLDLOCK)" in sql for sql, _ in cur.calls)
    assert all("DailyWork" not in sql for sql, _ in cur.calls)


def test_daily_request_conflicts_with_explicit_hourly_mark(names):
    with pytest.raises(RequestConflictError, match="علامت مؤثر"):
        check(Cursor(punches=[punch(800), punch(1000, 17), punch(1100), punch(1500)]), names)


def test_hourly_marks_overlap_only_same_interval(names):
    punches = [punch(800), punch(1000, 17), punch(1100), punch(1500)]
    shift = lambda *a: (8 * 60, 15 * 60)
    with pytest.raises(RequestConflictError):
        check(Cursor(punches=punches), names, request(start_hour=1030, end_hour=1130), shift_ref=shift)
    check(Cursor(punches=punches), names, request(start_hour=1100, end_hour=1200), shift_ref=shift)


def test_missing_bound_for_mark_is_conservative():
    # First marked punch is entry: until the punch, not after it.
    assert marked_hourly_conflict([(600, {"Status": 17})], (500, 590))
    assert not marked_hourly_conflict([(600, {"Status": 17})], (600, 700))


def test_matching_tolerance_cannot_reuse_existing_mark(names):
    punches = [punch(800), punch(1000, 17), punch(1100), punch(1500)]
    with pytest.raises(RequestConflictError):
        check(Cursor(punches=punches), names, request(start_hour=1100, end_hour=1200),
              shift_ref=lambda *a: (480, 900),
              match_punch=lambda *a: ({"Status": 17}, DAY))


def test_post_midnight_hourly_checks_previous_shift_daily_record(names):
    cur = Cursor(daily={"SDate": 14050829, "EDate": 14050829})
    with pytest.raises(RequestConflictError, match="۱۴۰۵/۰۸/۲۹"):
        check(cur, names, request(start_hour=100, end_hour=200), shift_ref=lambda *a: (-330, 150))
    assert cur.calls[0][1]["f"] == 14050829


def test_daily_night_shift_checks_following_morning_mark(names):
    with pytest.raises(RequestConflictError, match="۱۴۰۵/۰۹/۰۱"):
        check(Cursor(punches=[punch(1830), punch(230, 17, DAY + timedelta(days=1))]), names,
              shift_ref=lambda *a: (1110, 1590))


def test_missing_mapping_fails_closed(names):
    del names._names["mor_mam.table"]
    cur = Cursor()
    with pytest.raises(RequestConflictError, match="نگاشت"):
        check(cur, names)
    assert not cur.calls


def test_source_read_failure_never_means_no_conflict(names):
    with pytest.raises(RuntimeError, match="offline"):
        check(Cursor(failure=RuntimeError("offline")), names)


def test_custom_names_are_quoted_not_hardcoded(names):
    names._names["mor_mam.table"] = "dbo.CustomLeave"
    names._names["mor_mam.emp_no"] = "WorkerId"
    cur = Cursor()
    check(cur, names)
    assert "[dbo].[CustomLeave]" in cur.calls[0][0]
    assert "m.[WorkerId] = %(e)s" in cur.calls[0][0]


@pytest.mark.parametrize("title", ["غیبت", "مرخصی روزانه استحقاقی", "ماموریت  روزانه"])
def test_daily_conflict_uses_actual_card_title(names, title):
    day = date(2026, 11, 25)
    cur = Cursor(daily={"SDate": 14050904, "EDate": 14050904, "CardTitle": title})
    with pytest.raises(RequestConflictError) as exc:
        check(cur, names, request(day, EmpNo=225735))
    normalized = " ".join(title.split())
    assert str(exc.value) == (
        f"در تاریخ ۱۴۰۵/۰۹/۰۴ برای شما «{normalized}» ثبت شده است. "
        "امکان ثبت درخواست وجود ندارد. لطفاً به واحد منابع انسانی مراجعه نمائید."
    )
    sql = cur.calls[0][0]
    assert "c.[Title]" in sql and "AS CardTitle" in sql
    assert "c.[BranchCode] = m.[BranchCode]" in sql
    assert "DefaultTitle" not in sql
    assert len(cur.calls) == 1


def test_daily_conflict_without_title_still_blocks(names):
    names.leave.card_lookup_desc_column = None
    cur = Cursor(daily={"SDate": 14050830, "EDate": 14050830, "CardTitle": None})
    with pytest.raises(RequestConflictError, match="امکان ثبت درخواست وجود ندارد"):
        check(cur, names)
    assert "NULL AS CardTitle" in cur.calls[0][0]


def test_approval_conflict_identifies_requester_not_supervisor(names):
    cur = Cursor(daily={"SDate": 14050904, "EDate": 14050904, "CardTitle": "غیبت"})
    with pytest.raises(RequestConflictError) as exc:
        check(cur, names, request(date(2026, 11, 25)), for_approval=True)
    assert str(exc.value) == (
        "در تاریخ ۱۴۰۵/۰۹/۰۴ برای درخواست‌دهنده «غیبت» ثبت شده است. "
        "امکان تأیید درخواست وجود ندارد. لطفاً با واحد منابع انسانی هماهنگ کنید."
    )
