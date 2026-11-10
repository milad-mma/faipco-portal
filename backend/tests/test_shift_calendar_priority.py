"""Regression: a stale DailyWork shift must never replace the current group calendar.

Real-world incident: employee 225886, 1405/08/17-19; GrpShift=14 (06:30-14:30),
DailyWork=2 (07:00-15:00).  Only read-only cursor fakes are used here.
"""
from datetime import date
from types import SimpleNamespace

from app.services.kara_attendance_writeback import _day_deduction_minutes, shift_window_sync
from app.services.kara_schema import ATTENDANCE_SCHEMA_DEFAULTS, KaraNames


class Cursor:
    def __init__(self, group, daily):
        self.group = group
        self.daily = daily
        self.queries = []
        self.last = None

    def execute(self, sql, params=None):
        self.queries.append(sql)
        self.last = self.group if 'FROM [GrpShift] g' in sql else self.daily

    def fetchone(self):
        return self.last


def names():
    return KaraNames(attendance_mapping=SimpleNamespace(kara_schema=ATTENDANCE_SCHEMA_DEFAULTS))


def window_row(shift_no, start, end, kasr=800):
    return {'ShiftNo': shift_no, 'Found': shift_no, 'StartT': start,
            'EndT': end, 'Added': 0, 'Kasr': kasr}


def deduction_row(shift_no, kasr):
    return {'ShiftNo': shift_no, 'KasrGh': kasr, 'KasrGh5': kasr}


def test_current_group_calendar_wins_over_stale_dailywork():
    cursor = Cursor(window_row(14, 630, 1430), window_row(2, 700, 1500))
    result = shift_window_sync(cursor, names(), 225886, date(2026, 11, 10))
    assert result['shift_no'] == 14
    assert (result['start'], result['end']) == (630, 1430)
    assert len(cursor.queries) == 1  # no read from stale DailyWork


def test_dailywork_fallback_only_without_group_calendar():
    cursor = Cursor(None, window_row(2, 700, 1500))
    result = shift_window_sync(cursor, names(), 225886, date(2026, 11, 10))
    assert result['shift_no'] == 2
    assert len(cursor.queries) == 2


def test_group_off_day_not_overridden_by_stale_dailywork():
    cursor = Cursor({'ShiftNo': 501, 'Found': None}, window_row(2, 700, 1500))
    result = shift_window_sync(cursor, names(), 225886, date(2026, 11, 10))
    assert result == {'off_day': True, 'shift_no': 501}
    assert len(cursor.queries) == 1


def test_daily_deduction_uses_current_group_calendar():
    cursor = Cursor(deduction_row(14, 700), deduction_row(2, 800))
    assert _day_deduction_minutes(cursor, names(), 225886, date(2026, 11, 10)) == 420
    assert len(cursor.queries) == 1


def test_daily_deduction_fallback_without_calendar():
    cursor = Cursor(None, deduction_row(2, 800))
    assert _day_deduction_minutes(cursor, names(), 225886, date(2026, 11, 10)) == 480
    assert len(cursor.queries) == 2
