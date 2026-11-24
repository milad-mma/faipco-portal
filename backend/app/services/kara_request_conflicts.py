"""Read-only conflict checks for ordinary KaraWeb leave/mission requests.

The caller supplies a SQL Server transaction cursor. UPDLOCK/HOLDLOCK keep
checked rows/ranges stable until the request insert or final approval commits.
Do not infer manual absence from the absence of punches or DailyWork totals.
Only the mapped sources supported by the portal are checked here.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.leave_request_rules import compact_time_to_minutes


class RequestConflictError(Exception):
    """A user-facing conflict or unavailable conflict check; no write is allowed."""


def as_day(value) -> date:
    return value.date() if hasattr(value, "date") else value


def active_request(row: dict) -> bool:
    # SQL Server bit values may be bool or int. NULL means pending.
    return row.get("IsFinalApproved") != 0 and row.get("AcceptCode") != 22


def request_interval(start_date, end_date=None, start_hour=None, end_hour=None):
    """Half-open interval in absolute minutes; daily end dates are inclusive."""
    start_date = as_day(start_date)
    end_date = as_day(end_date) or start_date
    base = start_date.toordinal() * 1440
    if start_hour is None:
        return base, (end_date.toordinal() + 1) * 1440
    if end_hour is None:
        # A malformed legacy hourly request cannot be safely assumed disjoint.
        return base, (end_date.toordinal() + 1) * 1440
    a = base + compact_time_to_minutes(int(start_hour))
    b = base + compact_time_to_minutes(int(end_hour))
    if b < a:
        b += 1440
    return a, b


def overlaps(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def is_exit_permit(row):
    start, end = row.get("StartHour"), row.get("EndHour")
    return start is not None and start == end and str(row.get("Duration") or "0").strip() in ("0", "")


def assert_no_request_overlap(rows, candidate, forgotten_cards=(), *, exclude_id=None):
    """Prevent overlapping pending/applied requests; do not block rejected/cancelled rows."""
    target = request_interval(candidate["StartDate"], candidate.get("EndDate"), candidate.get("StartHour"), candidate.get("EndHour"))
    for row in rows:
        if exclude_id is not None and row.get("RequestId") == exclude_id:
            continue
        if not active_request(row) or row.get("CardNo") in forgotten_cards or is_exit_permit(row):
            continue
        if not row.get("StartDate"):
            continue
        old = request_interval(row["StartDate"], row.get("EndDate"), row.get("StartHour"), row.get("EndHour"))
        if overlaps(target, old):
            raise RequestConflictError("برای همین بازه زمانی از قبل درخواستی ثبت شده است.")


def _date_label(number):
    text = f"{int(number):08d}"
    return f"{text[:4]}/{text[4:6]}/{text[6:]}".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _marked_interval(times, index, bounds):
    """Like the portal's attendance overlay: entry ends a gap, exit starts it."""
    t = times[index]
    if index % 2 == 0:
        return (times[index - 1] if index else (bounds[0] if bounds else None), t)
    return (t, times[index + 1] if index + 1 < len(times) else (bounds[1] if bounds else None))


def marked_hourly_conflict(punches, target, bounds=None):
    """Find an incompatible explicit mark in a shift's ordered raw punches.

    Times and bounds use absolute minutes. When an edge of a marked interval
    is unknown, conservatively reject only if it could overlap the candidate.
    A zero Status is a normal punch, not a manual leave/absence record.
    """
    ordered = sorted(punches, key=lambda p: p[0])
    times = [p[0] for p in ordered]
    for i, (_, row) in enumerate(ordered):
        if not int(row.get("Status") or 0):
            continue
        lo, hi = _marked_interval(times, i, bounds)
        if lo is not None and hi is not None and lo >= hi:
            # A malformed/edge mark has no provable interval. Do not assume it is safe.
            lo = hi = None
        if (lo is None or lo < target[1]) and (hi is None or hi > target[0]):
            return row
    return None


def assert_no_attendance_conflict(cur, n, candidate, *, jalali_int, shift_ref=None, match_punch=None,
                                  for_approval=False):
    """Check live Mor_Mam and DataFile, not derived absence in DailyWork.

    jalali_int and shift/match helpers come from kara_attendance_writeback.
    This function never modifies records. Missing mappings fail closed for an
    ordinary KaraWeb request rather than silently allowing duplicate writeback.
    """
    if not n.can_read_daily_marks or not n.can_read_hourly_marks or not n.has("wf_requests", "accept_code"):
        raise RequestConflictError(
            "امکان بررسی کامل سوابق کارکرد وجود ندارد. لطفاً با منابع انسانی برای بررسی نگاشت کاراوب هماهنگ کنید."
        )
    start = as_day(candidate["StartDate"])
    end = as_day(candidate.get("EndDate")) or start
    sh, eh = candidate.get("StartHour"), candidate.get("EndHour")
    target = request_interval(start, end, sh, eh)
    if target[1] <= target[0]:
        raise RequestConflictError("بازه زمانی درخواست معتبر نیست.")
    last = date.fromordinal((target[1] - 1) // 1440)
    emp = int(candidate["EmpNo"])
    base = start.toordinal() * 1440
    s, e = target[0] - base, target[1] - base
    ref = shift_ref(cur, n, emp, start, s, e) if sh is not None and shift_ref else None
    # A post-midnight hourly request can belong to the previous day's shift.
    # Check that shift date as well as the actual dates written to WF_Requests.
    first = start - timedelta(days=1) if isinstance(ref, tuple) and ref[0] < 0 and min(e, ref[1]) > max(s, ref[0]) else start
    first_j, last_j = jalali_int(first), jalali_int(last)
    M = lambda role: n.c("mor_mam", role)
    # Match the existing attendance overlay's effective daily marks, not
    # accrual (Inc_Type=6) or monthly hourly deductions (Inc_Type=2).
    # Also catch the identical card even if its day flag is misconfigured.
    # Emp_No is unique within a shared KaraWeb database; don't hide an existing
    # record from another branch after an employee transfer.
    # The existing overlay also recognizes day cards by code without a
    # branch join. WF_Cards may contain the same code in multiple branches;
    # EXISTS avoids duplicates and does not miss a record after a transfer.
    # Resolve the existing record's display title from the mapped card table,
    # using its own branch (not the requester's current branch). A missing or
    # ambiguous title must not make an otherwise valid conflict disappear.
    title_sql = "NULL"
    if getattr(n.leave, "card_lookup_desc_column", None):
        title = f"NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(4000), c.{n.cards_title}))), N'')"
        title_branch = ""
        if n.has("cards", "branch_code") and n.has("mor_mam", "branch_code"):
            title_branch = f" AND c.{n.c('cards', 'branch_code')} = m.{M('branch_code')}"
        title_sql = (
            f"(SELECT CASE WHEN COUNT(DISTINCT {title}) = 1 THEN MIN({title}) END "
            f"FROM {n.cards_table} c WHERE c.{n.cards_no} = m.{M('type')}{title_branch})"
        )
    cur.execute(
        f"SELECT TOP 1 m.{M('s_date')} AS SDate, ISNULL(m.{M('e_date')}, m.{M('s_date')}) AS EDate, "
        f"{title_sql} AS CardTitle "
        f"FROM {n.t('mor_mam')} m WITH (UPDLOCK, HOLDLOCK) "
        f"WHERE m.{M('emp_no')} = %(e)s AND m.{M('s_date')} <= %(t)s "
        f"AND ISNULL(m.{M('e_date')}, m.{M('s_date')}) >= %(f)s "
        f"AND (m.{M('inc_type')} = 0 OR m.{M('inc_type')} IS NULL) "
        f"AND (m.{M('type')} = %(card)s OR EXISTS (SELECT 1 FROM {n.cards_table} c "
        f"WHERE c.{n.cards_no} = m.{M('type')} AND c.{n.c('cards', 'is_day')} = 1)) "
        f"ORDER BY m.{M('s_date')}",
        {"e": emp, "f": first_j, "t": last_j, "card": candidate.get("CardNo")},
    )
    daily = cur.fetchone()
    if daily:
        day = max(first_j, int(daily["SDate"]))
        title = " ".join(str(daily.get("CardTitle") or "").split())
        label = f"«{title}»" if title else "وضعیت روزانه‌ای در کارکرد"
        if for_approval:
            raise RequestConflictError(
                f"در تاریخ {_date_label(day)} برای درخواست‌دهنده {label} ثبت شده است. "
                "امکان تأیید درخواست وجود ندارد. لطفاً با واحد منابع انسانی هماهنگ کنید."
            )
        raise RequestConflictError(
            f"در تاریخ {_date_label(day)} برای شما {label} ثبت شده است. "
            "امکان ثبت درخواست وجود ندارد. لطفاً به واحد منابع انسانی مراجعه نمائید."
        )

    # Raw marks only. Include neighbouring dates for night shifts, but decide
    # overlap on the actual time interval, not merely on the date.
    # The lock covers the same neighbour dates that the writeback matcher can read.
    # Only convert dates actually returned, avoiding expanding large daily ranges.
    scan_first, scan_last = start - timedelta(days=1), last + timedelta(days=1)
    date_cache = {}
    def actual_day(jday):
        # Binary search the date range with the same monotonic calendar converter.
        # Usually only one or two days per request are read; cache repeated punches.
        if jday not in date_cache:
            left, right = scan_first.toordinal(), scan_last.toordinal()
            while left <= right:
                middle = (left + right) // 2
                d = date.fromordinal(middle)
                value = jalali_int(d)
                if value == jday:
                    date_cache[jday] = d
                    break
                if value < jday:
                    left = middle + 1
                else:
                    right = middle - 1
            else:
                raise RequestConflictError("تاریخ یکی از ترددهای کاراوب نامعتبر است؛ با منابع انسانی هماهنگ کنید.")
        return date_cache[jday]
    cur.execute(
        f"SELECT {n.df_date} AS DateInt, {n.df_time} AS Time, {n.c('datafile', 'status')} AS Status "
        f"FROM {n.df_table} WITH (UPDLOCK, HOLDLOCK) "
        f"WHERE {n.df_emp_no} = %(e)s AND {n.df_date} BETWEEN %(f)s AND %(t)s "
        f"ORDER BY {n.df_date}, {n.df_time}",
        {"e": emp, "f": jalali_int(scan_first), "t": jalali_int(scan_last)},
    )
    punches = []
    for row in cur.fetchall():
        day = actual_day(int(row["DateInt"]))
        punches.append((day.toordinal() * 1440 + compact_time_to_minutes(int(row["Time"])), row))
    if not any(int(row.get("Status") or 0) for _, row in punches):
        return  # Ordinary attendance/absence inferred from missing punches is not a conflict.
    conflict = None
    if sh is None:
        # A daily request overlaps every explicit hourly mark on the covered
        # calendar days. Normal attendance does not count as a conflict.
        conflict = next((row for t, row in punches if target[0] <= t < target[1] and int(row.get("Status") or 0)), None)
        if conflict is None and shift_ref:
            # A marked punch in the early hours of the following date can be
            # the end of the last requested night's shift.
            next_marks = [(t, row) for t, row in punches if t >= target[1] and int(row.get("Status") or 0)]
            if next_marks:
                last_base = last.toordinal() * 1440
                last_ref = shift_ref(cur, n, emp, last, 0, 1440)
                if isinstance(last_ref, tuple) and last_ref[1] > 1440:
                    conflict = next((row for t, row in next_marks if t <= last_base + last_ref[1]), None)
    else:
        bounds = (base + ref[0], base + ref[1]) if isinstance(ref, tuple) else None
        # Use the same window as the existing writeback matcher; if no shift
        # is known, only the candidate's calendar dates are considered.
        lo, hi = (bounds[0] - 180, bounds[1] + 360) if bounds else (base, (last.toordinal() + 1) * 1440 - 1)
        relevant = [(t, row) for t, row in punches if lo <= t <= hi]
        conflict = marked_hourly_conflict(relevant, target, bounds)
        if not conflict and match_punch and n.can_write_hourly:
            # Also prevent two otherwise disjoint requests sharing the same
            # marked punch because of matching tolerance.
            matched, matched_day = match_punch(cur, n, emp, start, s, e, ref)
            if matched and int(matched.get("Status") or 0):
                conflict = {"DateInt": jalali_int(matched_day)}
    if conflict:
        raise RequestConflictError(
            f"در تاریخ {_date_label(conflict['DateInt'])} قبلاً علامت مؤثر کارکرد ثبت شده است. "
            "بازه درخواست با ثبت موجود تداخل دارد یا قابل تطبیق قطعی نیست؛ با منابع انسانی هماهنگ کنید."
        )
