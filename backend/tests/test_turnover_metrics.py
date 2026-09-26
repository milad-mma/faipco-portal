"""تست‌های محاسبه‌ی «گزارش جذب و ترک کار» (app/services/turnover_metrics.py)."""
import ast
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("jdatetime")

from app.services.turnover_metrics import (  # noqa: E402
    Record,
    compute_report,
    jalali_int_to_gregorian,
    monthly_series,
    month_index,
    normalize_reason,
    parse_jalali_int,
    prepare_records,
)

CATEGORIES = [
    {"id": 1, "title": "استعفا", "group": "voluntary", "legal_basis": None},
    {"id": 2, "title": "تعدیل نیرو", "group": "involuntary", "legal_basis": None},
    {"id": 3, "title": "خطای ثبت", "group": "excluded", "legal_basis": None},
]
ALIASES = {"استعفا": 1, "تعدیل": 2, "کدپرسنلی اشتباه": 3}


def rec(hire, term=None, reason="", dept="10", gender=1, birth=None, position="51", education="6"):
    """ردیف نمونه؛ term خالی یعنی شاغل."""
    return Record(
        hire=hire,
        term=term,
        left=term is not None,
        reason_raw=reason,
        reason_norm=normalize_reason(reason),
        dept=dept,
        gender=gender,
        birth=birth,
        position=position,
        education=education,
    )


# نرمال‌سازی علت: همزه‌ی انتهایی، حروف عربی، نیم‌فاصله، علائم
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("استعفاء", "استعفا"),
        ("  استعفا  ", "استعفا"),
        ("ترک‌کار", "ترک کار"),
        ("كدپرسنلي اشتباه", "کدپرسنلی اشتباه"),
        (".", ""),
        (None, ""),
        ("ترک کار-کدپرسنلی صحیح ۲۳۵۲۰۹", "ترک کار-کدپرسنلی صحیح 235209"),
    ],
)
def test_normalize_reason(raw, expected):
    assert normalize_reason(raw) == expected


# متن‌های پیش‌فرض Migration 089 باید دقیقاً خروجی normalize_reason باشند، وگرنه هرگز تطبیق نمی‌خورند
def test_seed_aliases_are_normalized():
    path = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions" / "089_turnover_report.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "_ALIASES"
    )
    for text, _key in aliases:
        assert normalize_reason(text) == text


def test_parse_jalali_int():
    assert parse_jalali_int(14030601) == 14030601
    assert parse_jalali_int("1403/6/1") == 14030601
    assert parse_jalali_int("14030601.0") == 14030601
    assert parse_jalali_int(0) is None
    assert parse_jalali_int(None) is None
    assert parse_jalali_int("14031301") is None


def test_jalali_to_gregorian():
    assert jalali_int_to_gregorian(14030601) == date(2024, 8, 22)
    assert jalali_int_to_gregorian(14050704) == date(2026, 9, 26)
    # روز نامعتبر (۳۰ اسفند سال غیرکبیسه) به آخرین روز ماه برده می‌شود
    assert jalali_int_to_gregorian(14041230) == jalali_int_to_gregorian(14041229)


# پرسنل اول/آخر ماه و رابطه‌ی «آخر = اول + استخدام − ترک»
def test_monthly_headcount_identity():
    records = [
        rec(14020101),  # شاغل قدیمی
        rec(14020101, 14030615, "استعفا"),  # وسط ماه رفته
        rec(14030610),  # وسط ماه آمده
        rec(14030605, 14030620, "استعفا"),  # همان ماه آمده و رفته
        rec(14030701, 14030701, "تعدیل"),  # روز اول ماه بعد آمده و همان روز رفته
    ]
    prepared, _w = prepare_records(records, ALIASES, {c["id"]: c["group"] for c in CATEGORIES})
    series = monthly_series(prepared, month_index(1403, 6), month_index(1403, 7))
    sh, mh = series
    assert (sh["start_headcount"], sh["hires"], sh["separations"], sh["end_headcount"]) == (2, 2, 2, 2)
    assert (mh["start_headcount"], mh["hires"], mh["separations"], mh["end_headcount"]) == (2, 1, 1, 2)
    for row in series:
        assert row["end_headcount"] == row["start_headcount"] + row["hires"] - row["separations"]
    assert sh["avg_headcount"] == 2 and sh["turnover_rate"] == 100.0
    assert sh["by_group"]["voluntary"] == 2 and mh["by_group"]["involuntary"] == 1


# رکورد «خارج از آمار» کلاً حذف می‌شود؛ ترک‌کرده‌ی بی‌تاریخ و بی‌تاریخ استخدام هشدار می‌گیرند
def test_prepare_excludes_and_warns():
    records = [
        rec(14030101, 14030301, "کدپرسنلی اشتباه"),
        Record(None, None, False, "", "", "1", 1, None, None, None),
        Record(14030101, None, True, "", "", "1", 1, None, None, None),
        rec(14030101),
    ]
    prepared, warnings = prepare_records(records, ALIASES, {c["id"]: c["group"] for c in CATEGORIES})
    assert len(prepared) == 1
    assert warnings == {"excluded": 1, "missing_hire": 1, "missing_term": 1}


def test_compute_report_kpis_and_sections():
    today = 14050704
    records = [rec(14010101, dept="10") for _ in range(8)]
    records += [
        rec(14030610, 14030625, "استعفا", dept="10", birth=13800101),  # ۱۵ روز
        rec(14030701, 14031101, "تعدیل", dept="20", gender=2, birth=13700101),  # ~۴ ماه
        rec(14030801, dept="20"),
        rec(14040101, 14040501, "ناشناخته", dept="20"),  # دسته‌بندی نشده
        rec(14020101, 14030801, "کدپرسنلی اشتباه", dept="10"),  # خارج از آمار
    ]
    report = compute_report(
        records,
        alias_category=ALIASES,
        categories=CATEGORIES,
        start_idx=month_index(1403, 6),
        from_idx=None,
        to_idx=None,
        today=today,
        dept_names={"10": "تولید", "20": "اداری"},
    )
    k = report["kpis"]
    assert report["range"] == {"from_month": "1403/06", "to_month": "1405/07", "start_month": "1403/06"}
    assert k["start_headcount"] == 8 and k["end_headcount"] == 9
    assert k["hires"] == 4 and k["separations"] == 3 and k["net"] == 1
    assert k["by_group"]["voluntary"] == 1 and k["by_group"]["involuntary"] == 1 and k["by_group"]["uncategorized"] == 1
    assert k["exit_within_30_share"] == pytest.approx(33.3)
    assert k["replacement_ratio"] == pytest.approx(1.33)
    assert report["warnings"] == {"excluded": 1}
    # علت‌ها: دسته‌بندی نشده با متن خامش
    uncategorized = next(r for r in report["reasons"] if r["group"] == "uncategorized")
    assert uncategorized["texts"] == [{"text": "ناشناخته", "count": 1}]
    # سالانه: سه سال (۱۴۰۳ ناقص از شهریور)
    assert [y["year"] for y in report["yearly"]] == [1403, 1404, 1405]
    assert report["yearly"][0]["months"] == 7
    # واحد «اداری» با میانگین زیر ۵ نفر نرخ ندارد
    admin = next(d for d in report["departments"] if d["code"] == "20")
    assert admin["turnover_rate_annualized"] is None and admin["separations"] == 2
    # ماندگاری: پاییز ۱۴۰۳ دو نفر (یکی بعد از ~۴ ماه رفته)؛ تابستان یک نفر که در ۱۵ روز رفته
    autumn = next(c for c in report["cohorts"] if c["label"] == "پاییز 1403")
    assert autumn["size"] == 2
    assert [p["retention"] for p in autumn["points"]] == [100.0, 100.0, 50.0, 50.0]
    summer = next(c for c in report["cohorts"] if c["label"] == "تابستان 1403")
    assert [p["retention"] for p in summer["points"]] == [0.0, 0.0, 0.0, 0.0]
    # ترکیب جمعیتی
    assert {g["key"]: g["separations"] for g in report["demographics"]["gender"]} == {1: 2, 2: 1}
    assert report["department_options"] == [{"code": "20", "name": "اداری"}, {"code": "10", "name": "تولید"}]


def test_filters_and_range_clamp():
    records = [rec(14030101, dept="10"), rec(14030101, 14030801, "استعفا", dept="20", gender=2)]
    report = compute_report(
        records,
        alias_category=ALIASES,
        categories=CATEGORIES,
        start_idx=month_index(1403, 6),
        from_idx=month_index(1402, 1),  # قبل از شروع → به شروع محدود می‌شود
        to_idx=month_index(1499, 1),  # بعد از امروز → به ماه جاری
        today=14040315,
        gender_filter=2,
    )
    assert report["range"]["from_month"] == "1403/06" and report["range"]["to_month"] == "1404/03"
    assert report["kpis"]["separations"] == 1 and report["kpis"]["start_headcount"] == 1
    # گزینه‌های واحد از کل داده (قبل از فیلتر) ساخته می‌شوند
    assert {d["code"] for d in report["department_options"]} == {"10", "20"}


# ---------- دوره‌های استخدام از تاریخچه (استخدام مجدد در کاراوب) ----------

def _is_left(row):
    return row.get("IsCut") == 1


def _merge(current, history):
    from app.services.turnover_metrics import merge_history

    return merge_history(
        current, history, emp_col="Emp_No", hire_col="Emp_Date", term_col="End_Date", order_col="ChangeDate", is_left=_is_left
    )


def test_merge_history_rehire_like_kara():
    # نمونه‌ی واقعی 225932: تعدیل، برگشت و ترک در همان روز، برگشت دوباره
    history = [
        {"Emp_No": 225932, "Emp_Date": 14010524, "End_Date": None, "IsCut": 0, "ChangeDate": "2024-07-02"},
        {"Emp_No": 225932, "Emp_Date": 14010524, "End_Date": 14050101, "IsCut": 1, "ChangeDate": "2026-04-22"},
        {"Emp_No": 225932, "Emp_Date": 14050216, "End_Date": 14050216, "IsCut": 1, "ChangeDate": "2026-05-05"},
        {"Emp_No": 225932, "Emp_Date": 14050618, "End_Date": None, "IsCut": 0, "ChangeDate": "2026-09-20"},
    ]
    current = [{"Emp_No": 225932, "Emp_Date": 14050618, "End_Date": None, "IsCut": 0}]
    episodes = sorted(_merge(current, history), key=lambda e: e[0]["Emp_Date"])
    assert [(e[0]["Emp_Date"], e[1], e[2]) for e in episodes] == [
        (14010524, False, True),
        (14050216, True, True),
        (14050618, True, False),
    ]


def test_merge_history_ignores_corrections_and_uses_latest_state():
    history = [
        # اصلاح تاریخ استخدام (بدون ترک کار در بین) → دوره‌ی جدا نیست
        {"Emp_No": 1, "Emp_Date": 14030101, "End_Date": None, "IsCut": 0, "ChangeDate": "2024-07-01"},
        # ترک کاری که بعداً لغو شد (همان تاریخ استخدام دوباره فعال) → آخرین وضعیت شاغل است، ولی ردیف فعلی ملاک است
        {"Emp_No": 2, "Emp_Date": 14020101, "End_Date": 14030101, "IsCut": 1, "ChangeDate": "2024-07-01"},
        {"Emp_No": 2, "Emp_Date": 14020101, "End_Date": None, "IsCut": 0, "ChangeDate": "2024-08-01"},
        # تاریخ ترک کار اصلاح شد → آخرین مقدار
        {"Emp_No": 3, "Emp_Date": 14020101, "End_Date": 14030101, "IsCut": 1, "ChangeDate": "2024-07-01"},
        {"Emp_No": 3, "Emp_Date": 14020101, "End_Date": 14030115, "IsCut": 1, "ChangeDate": "2024-07-05"},
    ]
    current = [
        {"Emp_No": 1, "Emp_Date": 14030105, "End_Date": None, "IsCut": 0},
        {"Emp_No": 2, "Emp_Date": 14020101, "End_Date": None, "IsCut": 0},
        {"Emp_No": 3, "Emp_Date": 14020101, "End_Date": 14030120, "IsCut": 1},
    ]
    episodes = _merge(current, history)
    assert len(episodes) == 3
    assert all(not rehire and not from_history for _row, rehire, from_history in episodes)
    assert next(r for r, *_ in episodes if r["Emp_No"] == 3)["End_Date"] == 14030120


def test_rehire_counted_in_report():
    records = [
        rec(14010101, 14040101, "تعدیل"),
        Record(14040301, None, False, "", "", "10", 1, None, "51", "6", rehire=True),
    ]
    report = compute_report(
        records,
        alias_category=ALIASES,
        categories=CATEGORIES,
        start_idx=month_index(1403, 6),
        from_idx=None,
        to_idx=None,
        today=14050101,
    )
    assert report["kpis"]["rehires"] == 1 and report["kpis"]["hires"] == 1
    assert report["kpis"]["rehire_share"] == 100.0
