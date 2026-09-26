"""
محاسبه‌ی خالص شاخص‌های «گزارش جذب و ترک کار» (بدون دسترسی به دیتابیس؛ قابل تست).

تعریف‌ها (استاندارد SHRM / BLS-JOLTS، دسته‌ها بر اساس قانون کار ایران):
- پرسنل اول ماه: استخدام قبل از روز اول ماه و (شاغل یا ترک کار از روز اول ماه به بعد)
- پرسنل آخر ماه: استخدام تا آخر ماه و (شاغل یا ترک کار بعد از آخر ماه)
- میانگین پرسنل ماه = (اول ماه + آخر ماه) ÷ ۲
- نرخ ترک ماهانه = ترک کار ماه ÷ میانگین پرسنل ماه × ۱۰۰؛ نرخ یک دوره = جمع نرخ‌های ماهانه؛
  نرخ سالانه‌شده = میانگین نرخ ماهانه × ۱۲
- رکوردی که علتش در گروه «خارج از آمار» (مثل کد پرسنلی اشتباه) است کلاً حذف می‌شود
  (نه استخدام حساب می‌شود، نه ترک کار، نه در تعداد پرسنل).
- واحد، سمت و مدرک هر نفر آخرین مقدار ثبت‌شده در منبع است (سابقه‌ی جابه‌جایی در دسترس نیست).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

import jdatetime

GROUP_LABELS = {
    "voluntary": "به خواست کارگر",
    "involuntary": "به خواست کارفرما",
    "probation": "فسخ در دوره‌ی آزمایشی",
    "other": "سایر",
    "excluded": "خارج از آمار",
    "uncategorized": "دسته‌بندی نشده",
}
MIN_GROUP_FOR_RATE = 5  # برای گروه‌های کوچک‌تر (مثلاً یک واحد کوچک) نرخ درصدی نمایش داده نمی‌شود
RETENTION_POINTS = (30, 90, 180, 365)  # روزهای منحنی ماندگاری گروه‌های استخدامی
TENURE_BUCKETS = (
    ("lt1m", "کمتر از ۱ ماه", 0, 30),
    ("1to3m", "۱ تا ۳ ماه", 31, 90),
    ("3to6m", "۳ تا ۶ ماه", 91, 182),
    ("6to12m", "۶ تا ۱۲ ماه", 183, 365),
    ("1to3y", "۱ تا ۳ سال", 366, 1095),
    ("gt3y", "بیش از ۳ سال", 1096, None),
)
AGE_BANDS = (("lt25", "زیر ۲۵", 0, 24), ("25to34", "۲۵ تا ۳۴", 25, 34), ("35to44", "۳۵ تا ۴۴", 35, 44),
             ("45to54", "۴۵ تا ۵۴", 45, 54), ("55p", "۵۵ و بالاتر", 55, 200))
SEASONS = ("بهار", "تابستان", "پاییز", "زمستان")


# ---------- نرمال‌سازی علت ترک کار ----------

_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "ـ": None, "ٔ": None})
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_reason(raw) -> str:
    """
    متن آزاد علت ترک کار را برای تطبیق یکسان می‌کند: حروف عربی → فارسی، نیم‌فاصله و فاصله‌های
    تکراری → یک فاصله، حذف «ء» انتهای کلمه (استعفاء = استعفا)، ارقام انگلیسی و حذف علائم ابتدا/انتها.
    متن خالی → رشته‌ی خالی.
    """
    if raw is None:
        return ""
    text = str(raw).translate(_ARABIC_TO_PERSIAN).translate(_DIGITS)
    text = text.replace("‌", " ").replace("‏", "").replace("‎", "")
    text = re.sub(r"\s+", " ", text).strip(" .,-_/،؛:")
    text = re.sub(r"ء(?=\s|$)", "", text)  # همزه‌ی انتهای کلمه
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()[:400]


# ---------- تاریخ ----------

def parse_jalali_int(raw) -> int | None:
    """تاریخ شمسی خام (13700521، 1370/5/21، ...) → عدد YYYYMMDD؛ نامعتبر یا صفر → None."""
    if raw is None:
        return None
    text = str(raw).strip().translate(_DIGITS)
    if text.endswith(".0"):
        text = text[:-2]
    if not text or text == "0":
        return None
    parts: list[str] | None = None
    for sep in ("/", "-", "."):
        if sep in text:
            parts = text.split(sep)
            break
    if parts is None and text.isdigit() and len(text) == 8:
        parts = [text[:4], text[4:6], text[6:8]]
    if not parts or len(parts) != 3:
        return None
    try:
        y, m, d = (int(p) for p in parts)
    except ValueError:
        return None
    if not (1300 <= y <= 1500 and 1 <= m <= 12 and 1 <= d <= 31):
        return None
    return y * 10000 + m * 100 + d


def jalali_int_to_gregorian(value: int) -> date:
    """YYYYMMDD شمسی → تاریخ میلادی؛ روز نامعتبر (مثل ۳۱ مهر) به آخرین روز معتبر ماه برده می‌شود."""
    y, m, d = value // 10000, (value // 100) % 100, value % 100
    for day in range(d, 0, -1):
        try:
            return jdatetime.date(y, m, day).togregorian()
        except ValueError:
            continue
    return jdatetime.date(y, m, 1).togregorian()


def days_between(start: int, end: int) -> int:
    """فاصله‌ی دو تاریخ شمسی YYYYMMDD به روز."""
    return (jalali_int_to_gregorian(end) - jalali_int_to_gregorian(start)).days


def month_index(year: int, month: int) -> int:
    """شماره‌ی پیوسته‌ی ماه برای پیمایش (سال×۱۲ + ماه-۱)."""
    return year * 12 + (month - 1)


def index_to_month(idx: int) -> tuple[int, int]:
    return idx // 12, idx % 12 + 1


def month_label(idx: int) -> str:
    y, m = index_to_month(idx)
    return f"{y:04d}/{m:02d}"


def parse_month(text: str | None) -> int | None:
    """«1403/06» → شماره‌ی ماه؛ خالی/نامعتبر → None."""
    if not text:
        return None
    t = str(text).strip().translate(_DIGITS).replace("-", "/")
    parts = t.split("/")
    try:
        y, m = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None
    if not (1300 <= y <= 1500 and 1 <= m <= 12):
        return None
    return month_index(y, m)


def age_at(birth: int | None, on: int | None) -> int | None:
    """سن کامل (سال) در تاریخ on از روی تاریخ تولد شمسی YYYYMMDD."""
    if not birth or not on or birth >= on:
        return None
    age = on // 10000 - birth // 10000 - (1 if on % 10000 < birth % 10000 else 0)
    return age if 10 <= age <= 100 else None


# ---------- مدل داده‌ی سبک ----------

@dataclass
class Record:
    """یک ردیف پرسنل منبع بدون هیچ شناسه‌ی شخصی."""

    hire: int | None
    term: int | None
    left: bool
    reason_raw: str
    reason_norm: str
    dept: str | None
    gender: int | None
    birth: int | None
    position: str | None
    education: str | None
    rehire: bool = False  # این دوره‌ی استخدام، برگشت همان شخص بعد از یک ترک کار قبلی است


# ---------- ساخت دوره‌های استخدام از تاریخچه ----------

def merge_history(
    current_rows: list[dict],
    history_rows: list[dict],
    *,
    emp_col: str,
    hire_col: str,
    term_col: str,
    order_col: str,
    is_left,
) -> list[tuple[dict, bool, bool]]:
    """
    کاراوب برای استخدام مجدد رکورد جدید نمی‌سازد: همان رکورد پرسنل دوباره فعال و تاریخ استخدام عوض
    می‌شود، پس دوره‌های قبلی فقط در جدول تاریخچه (LogEmployee، یک ردیف به ازای هر تغییر) می‌مانند.
    این تابع از تاریخچه و ردیف‌های فعلی، «دوره‌های استخدام» را می‌سازد:
    - هر (شخص، تاریخ استخدام) یک دوره است و آخرین وضعیت آن دوره ملاک است (ردیف فعلی بر تاریخچه مقدم است)؛
    - دوره‌ی تاریخچه فقط اگر آخرین وضعیتش «ترک کار با تاریخ» باشد نگه داشته می‌شود؛ دوره‌ی بدون ترک کار
      در تاریخچه یعنی اصلاح تاریخ استخدام (نه دوره‌ی واقعی) و کنار گذاشته می‌شود؛
    - دوره‌ای که قبلش همان شخص یک دوره‌ی خاتمه‌یافته دارد «استخدام مجدد» است.
    خروجی: [(ردیف، استخدام مجدد؟، از تاریخچه؟)]؛ ردیف فعلی بدون کد پرسنلی بدون تغییر برمی‌گردد.
    is_left(row): آیا وضعیت این ردیف «قطع همکاری» است.
    """
    groups: dict[tuple[str, int], tuple[tuple, dict, bool]] = {}
    passthrough: list[tuple[dict, bool, bool]] = []

    def _key(row):
        raw = row.get(emp_col)
        emp = str(raw).strip() if raw is not None else ""
        if emp.endswith(".0") and emp[:-2].isdigit():
            emp = emp[:-2]
        return emp, parse_jalali_int(row.get(hire_col))

    for row in history_rows:
        emp, hire = _key(row)
        if not emp or hire is None:
            continue
        order = row.get(order_col)
        rank = (0, order is not None, str(order) if order is not None else "")
        current = groups.get((emp, hire))
        if current is None or rank >= current[0]:
            groups[(emp, hire)] = (rank, row, False)
    for row in current_rows:
        emp, hire = _key(row)
        if not emp or hire is None:
            passthrough.append((row, False, False))
            continue
        groups[(emp, hire)] = ((1, True, ""), row, True)

    by_emp: dict[str, list[tuple[int, dict, bool]]] = defaultdict(list)
    for (emp, hire), (_rank, row, is_current) in groups.items():
        if is_current or (is_left(row) and parse_jalali_int(row.get(term_col)) is not None):
            by_emp[emp].append((hire, row, is_current))

    result = list(passthrough)
    for episodes in by_emp.values():
        episodes.sort(key=lambda e: e[0])
        ended_before = False
        for hire, row, is_current in episodes:
            result.append((row, ended_before, not is_current))
            term = parse_jalali_int(row.get(term_col))
            if is_left(row) and term is not None:
                ended_before = True
    return result


def _pct(num: float, den: float) -> float | None:
    return round(num * 100.0 / den, 1) if den else None


def _mean(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _round(v: float | None, digits: int = 1) -> float | None:
    return round(v, digits) if v is not None else None


def _annualized(monthly_rates: list) -> float | None:
    """میانگین نرخ‌های ماهانه × ۱۲؛ اگر هیچ ماهی نرخ نداشت (پرسنل صفر) None."""
    mean = _mean(monthly_rates)
    return _round(mean * 12) if mean is not None else None


# ---------- محاسبه‌ی خالص (بدون دیتابیس؛ قابل تست) ----------

def prepare_records(
    records: list[Record], alias_category: dict[str, int | None], category_group: dict[int, str]
) -> tuple[list[tuple[Record, int | None, str]], dict[str, int]]:
    """
    ردیف‌ها را برای محاسبه آماده می‌کند و خروجی (فهرست (رکورد، شناسه دسته، گروه)، شمارنده‌ی هشدارها) می‌دهد.
    - رکورد بدون تاریخ استخدام کنار گذاشته می‌شود؛
    - ترک‌کرده‌ی بدون تاریخ ترک کار کنار گذاشته می‌شود (در هیچ ماهی قابل جایگذاری نیست)؛
    - رکورد «خارج از آمار» کلاً حذف می‌شود؛ تاریخ ترک کار قبل از استخدام به تاریخ استخدام اصلاح می‌شود.
    """
    warnings = Counter()
    prepared: list[tuple[Record, int | None, str]] = []
    for rec in records:
        if rec.hire is None:
            warnings["missing_hire"] += 1
            continue
        if rec.left and rec.term is None:
            warnings["missing_term"] += 1
            continue
        cat_id = alias_category.get(rec.reason_norm) if rec.left else None
        group = category_group.get(cat_id, "uncategorized") if rec.left else ""
        if rec.left and group == "excluded":
            warnings["excluded"] += 1
            continue
        if rec.left and rec.term < rec.hire:
            warnings["term_before_hire"] += 1
            rec.term = rec.hire
        prepared.append((rec, cat_id, group))
    return prepared, dict(warnings)


def monthly_series(prepared: list[tuple[Record, int | None, str]], first_idx: int, last_idx: int) -> list[dict]:
    """
    سری ماهانه از first_idx تا last_idx: پرسنل اول/آخر ماه، میانگین، استخدام، ترک کار به تفکیک گروه و دسته،
    نرخ‌ها و نرخ متحرک ۱۲ماهه (جمع ۱۲ نرخ ماهانه‌ی اخیر، وقتی ۱۲ ماه داده باشد).
    """
    series: list[dict] = []
    for idx in range(first_idx, last_idx + 1):
        y, m = index_to_month(idx)
        ms, me = y * 10000 + m * 100 + 1, y * 10000 + m * 100 + 31
        start = end = hires = seps = rehires = 0
        by_group: Counter = Counter()
        by_category: Counter = Counter()
        for rec, cat_id, group in prepared:
            if rec.hire < ms and (not rec.left or rec.term >= ms):
                start += 1
            if rec.hire <= me and (not rec.left or rec.term > me):
                end += 1
            if ms <= rec.hire <= me:
                hires += 1
                if rec.rehire:
                    rehires += 1
            if rec.left and ms <= rec.term <= me:
                seps += 1
                by_group[group] += 1
                by_category[cat_id if cat_id is not None else 0] += 1
        avg = (start + end) / 2
        row = {
            "idx": idx,
            "month": month_label(idx),
            "start_headcount": start,
            "end_headcount": end,
            "avg_headcount": avg,
            "hires": hires,
            "rehires": rehires,
            "separations": seps,
            "net": hires - seps,
            "by_group": {g: by_group.get(g, 0) for g in ("voluntary", "involuntary", "probation", "other", "uncategorized")},
            "by_category": {str(k): v for k, v in by_category.items()},
            "turnover_rate": _pct(seps, avg),
            "voluntary_rate": _pct(by_group.get("voluntary", 0), avg),
            "involuntary_rate": _pct(by_group.get("involuntary", 0), avg),
            "hire_rate": _pct(hires, avg),
        }
        series.append(row)
    for i, row in enumerate(series):
        window = [r["turnover_rate"] for r in series[max(0, i - 11): i + 1]]
        row["rolling12_rate"] = round(sum(v or 0 for v in window), 1) if i >= 11 else None
    return series


def compute_report(
    records: list[Record],
    *,
    alias_category: dict[str, int | None],
    categories: list[dict],
    start_idx: int | None,
    from_idx: int | None,
    to_idx: int | None,
    today: int,
    dept_names: dict[str, str] | None = None,
    position_names: dict[str, str] | None = None,
    education_names: dict[str, str] | None = None,
    dept_filter: str | None = None,
    gender_filter: int | None = None,
) -> dict:
    """
    کل گزارش را از روی ردیف‌های منبع می‌سازد (بدون دسترسی به دیتابیس).
    start_idx: ماه شروع آمار سایت؛ from_idx/to_idx: بازه‌ی نمایش (به بازه‌ی [شروع، ماه جاری] محدود می‌شود).
    """
    dept_names = dept_names or {}
    position_names = position_names or {}
    education_names = education_names or {}
    category_group = {c["id"]: c["group"] for c in categories}
    category_title = {c["id"]: c["title"] for c in categories}

    department_options = sorted(
        {r.dept for r in records if r.dept}, key=lambda code: (dept_names.get(code, code), code)
    )
    if dept_filter:
        records = [r for r in records if r.dept == dept_filter]
    if gender_filter:
        records = [r for r in records if r.gender == gender_filter]

    prepared, warnings = prepare_records(records, alias_category, category_group)
    today_idx = month_index(today // 10000, (today // 100) % 100)
    if start_idx is None:
        dates = [rec.hire for rec, _c, _g in prepared] + [rec.term for rec, _c, _g in prepared if rec.left]
        start_idx = month_index(min(dates) // 10000, (min(dates) // 100) % 100) if dates else today_idx
        start_idx = max(start_idx, today_idx - 120)  # حداکثر ۱۰ سال
    to_idx = min(to_idx if to_idx is not None else today_idx, today_idx)
    from_idx = max(from_idx if from_idx is not None else start_idx, start_idx)
    to_idx = max(to_idx, start_idx)
    if from_idx > to_idx:
        from_idx = to_idx

    full = monthly_series(prepared, start_idx, to_idx)
    months = [r for r in full if r["idx"] >= from_idx]
    ms_from = index_to_month(from_idx)
    ms_to = index_to_month(to_idx)
    period_start = ms_from[0] * 10000 + ms_from[1] * 100 + 1
    period_end = ms_to[0] * 10000 + ms_to[1] * 100 + 31

    period_seps = [(r, c, g) for r, c, g in prepared if r.left and period_start <= r.term <= period_end]
    period_hires = [(r, c, g) for r, c, g in prepared if period_start <= r.hire <= period_end]
    tenures = [days_between(r.hire, r.term) for r, _c, _g in period_seps]

    # ---- شاخص‌های اصلی ----
    rates = [m["turnover_rate"] for m in months]
    total_seps = sum(m["separations"] for m in months)
    total_hires = sum(m["hires"] for m in months)
    group_totals = {g: sum(m["by_group"][g] for m in months) for g in ("voluntary", "involuntary", "probation", "other", "uncategorized")}

    def _new_hire_attrition(days: int) -> tuple[float | None, int]:
        """از استخدام‌های دوره که حداقل days روز از استخدامشان گذشته، چند درصد در همان days روز رفته‌اند."""
        eligible = [r for r, _c, _g in period_hires if days_between(r.hire, today) >= days]
        gone = [r for r in eligible if r.left and days_between(r.hire, r.term) <= days]
        return _pct(len(gone), len(eligible)), len(eligible)

    attr90, attr90_n = _new_hire_attrition(90)
    attr365, attr365_n = _new_hire_attrition(365)
    kpis = {
        "months": len(months),
        "start_headcount": months[0]["start_headcount"] if months else 0,
        "end_headcount": months[-1]["end_headcount"] if months else 0,
        "avg_headcount": _round(_mean([m["avg_headcount"] for m in months])),
        "hires": total_hires,
        "rehires": sum(m["rehires"] for m in months),
        "rehire_share": _pct(sum(m["rehires"] for m in months), total_hires),
        "separations": total_seps,
        "net": total_hires - total_seps,
        "by_group": group_totals,
        "turnover_rate_period": _round(sum(v for v in rates if v is not None)) if months else None,
        "turnover_rate_annualized": _annualized(rates),
        "voluntary_rate_annualized": _annualized([m["voluntary_rate"] for m in months]),
        "involuntary_rate_annualized": _annualized([m["involuntary_rate"] for m in months]),
        "hire_rate_annualized": _annualized([m["hire_rate"] for m in months]),
        "replacement_ratio": round(total_hires / total_seps, 2) if total_seps else None,
        "exit_within_30_share": _pct(sum(1 for t in tenures if t <= 30), len(tenures)),
        "exit_within_90_share": _pct(sum(1 for t in tenures if t <= 90), len(tenures)),
        "exit_within_365_share": _pct(sum(1 for t in tenures if t <= 365), len(tenures)),
        "avg_tenure_at_exit_months": _round(sum(tenures) / len(tenures) / 30.44) if tenures else None,
        "new_hire_90d_attrition": attr90,
        "new_hire_90d_base": attr90_n,
        "first_year_retention": _round(100 - attr365) if attr365 is not None else None,
        "first_year_base": attr365_n,
    }

    # ---- سالانه ----
    yearly_map: dict[int, list[dict]] = defaultdict(list)
    for m in months:
        yearly_map[index_to_month(m["idx"])[0]].append(m)
    yearly = []
    for year, rows in sorted(yearly_map.items()):
        y_rates = [r["turnover_rate"] for r in rows]
        yearly.append({
            "year": year,
            "months": len(rows),
            "hires": sum(r["hires"] for r in rows),
            "rehires": sum(r["rehires"] for r in rows),
            "separations": sum(r["separations"] for r in rows),
            "net": sum(r["net"] for r in rows),
            "by_group": {g: sum(r["by_group"][g] for r in rows) for g in group_totals},
            "start_headcount": rows[0]["start_headcount"],
            "end_headcount": rows[-1]["end_headcount"],
            "turnover_rate": _round(sum(v for v in y_rates if v is not None)),
            "turnover_rate_annualized": _annualized(y_rates),
        })

    # ---- علت‌ها ----
    cat_counts = Counter(c if c is not None else 0 for _r, c, _g in period_seps)
    texts_by_cat: dict[int, Counter] = defaultdict(Counter)
    for r, c, _g in period_seps:
        texts_by_cat[c if c is not None else 0][r.reason_raw.strip() or "(بدون علت)"] += 1
    reasons = [
        {
            "category_id": c["id"],
            "title": c["title"],
            "group": c["group"],
            "legal_basis": c.get("legal_basis"),
            "count": cat_counts.get(c["id"], 0),
            "share": _pct(cat_counts.get(c["id"], 0), total_seps),
            "texts": [{"text": t, "count": n} for t, n in texts_by_cat[c["id"]].most_common()],
        }
        for c in categories
        if c["group"] != "excluded" and cat_counts.get(c["id"], 0)
    ]
    if cat_counts.get(0):
        reasons.append({
            "category_id": None,
            "title": GROUP_LABELS["uncategorized"],
            "group": "uncategorized",
            "legal_basis": None,
            "count": cat_counts[0],
            "share": _pct(cat_counts[0], total_seps),
            "texts": [{"text": t, "count": n} for t, n in texts_by_cat[0].most_common()],
        })
    reasons.sort(key=lambda r: -r["count"])

    # ---- مدت خدمت هنگام ترک ----
    tenure_buckets = []
    for key, label, lo, hi in TENURE_BUCKETS:
        n = sum(1 for t in tenures if t >= lo and (hi is None or t <= hi))
        tenure_buckets.append({"key": key, "label": label, "count": n, "share": _pct(n, len(tenures))})

    # ---- ماندگاری گروه‌های استخدامی (فصل استخدام) ----
    cohorts_map: dict[tuple[int, int], list[Record]] = defaultdict(list)
    for r, _c, _g in period_hires:
        y, m = r.hire // 10000, (r.hire // 100) % 100
        cohorts_map[(y, (m - 1) // 3)].append(r)
    cohorts = []
    for (y, q), members in sorted(cohorts_map.items()):
        points = []
        for days in RETENTION_POINTS:
            if all(days_between(r.hire, today) >= days for r in members):
                stayed = sum(1 for r in members if not r.left or days_between(r.hire, r.term) > days)
                points.append({"days": days, "retention": _pct(stayed, len(members))})
            else:
                points.append({"days": days, "retention": None})
        cohorts.append({"label": f"{SEASONS[q]} {y}", "size": len(members), "points": points})

    # ---- واحدها ----
    dept_rows = []
    prepared_by_dept: dict[str, list] = defaultdict(list)
    for item in prepared:
        prepared_by_dept[item[0].dept or ""].append(item)
    for code, items in prepared_by_dept.items():
        series = [r for r in monthly_series(items, from_idx, to_idx)]
        hires = sum(r["hires"] for r in series)
        seps = sum(r["separations"] for r in series)
        avg = _mean([r["avg_headcount"] for r in series]) or 0
        if not hires and not seps and not avg:
            continue
        dept_rate = _annualized([r["turnover_rate"] for r in series]) if avg >= MIN_GROUP_FOR_RATE else None
        dept_rows.append({
            "code": code or None,
            "name": dept_names.get(code, code) if code else "بدون واحد",
            "hires": hires,
            "separations": seps,
            "voluntary": sum(r["by_group"]["voluntary"] for r in series),
            "involuntary": sum(r["by_group"]["involuntary"] for r in series),
            "avg_headcount": _round(avg),
            "end_headcount": series[-1]["end_headcount"] if series else 0,
            "turnover_rate_annualized": dept_rate,
            "monthly_separations": [r["separations"] for r in series],
        })
    dept_rows.sort(key=lambda d: (-d["separations"], -d["hires"], d["name"]))
    heatmap = {
        "months": [m["month"] for m in months],
        "rows": [{"code": d["code"], "name": d["name"], "values": d["monthly_separations"]} for d in dept_rows[:15] if d["separations"]],
    }
    for d in dept_rows:
        d.pop("monthly_separations", None)

    # ---- ترکیب جمعیتی ----
    def _dimension(key_fn, label_fn, order: list | None = None) -> list[dict]:
        hires_c = Counter(key_fn(r) for r, _c, _g in period_hires)
        seps_c = Counter(key_fn(r) for r, _c, _g in period_seps)
        keys = order if order is not None else sorted(set(hires_c) | set(seps_c), key=lambda k: -seps_c.get(k, 0))
        return [
            {"key": k, "label": label_fn(k), "hires": hires_c.get(k, 0), "separations": seps_c.get(k, 0)}
            for k in keys
            if hires_c.get(k, 0) or seps_c.get(k, 0)
        ]

    def _age_band(r: Record, on_hire: bool = False):
        age = age_at(r.birth, r.hire if on_hire else (r.term if r.left else None))
        if age is None:
            return None
        return next(k for k, _l, lo, hi in AGE_BANDS if lo <= age <= hi)

    age_labels = {k: label for k, label, _lo, _hi in AGE_BANDS}
    hires_age = Counter(_age_band(r, on_hire=True) for r, _c, _g in period_hires)
    seps_age = Counter(_age_band(r) for r, _c, _g in period_seps)
    age_rows = [
        {"key": k or "unknown", "label": age_labels.get(k, "نامشخص"), "hires": hires_age.get(k, 0), "separations": seps_age.get(k, 0)}
        for k in [b[0] for b in AGE_BANDS] + [None]
        if hires_age.get(k, 0) or seps_age.get(k, 0)
    ]
    gender_labels = {1: "مرد", 2: "زن", None: "نامشخص"}
    demographics = {
        "gender": _dimension(lambda r: r.gender, lambda k: gender_labels.get(k, "نامشخص"), [1, 2, None]),
        "age": age_rows,
        "education": _dimension(lambda r: r.education, lambda k: education_names.get(k, k) if k else "نامشخص"),
        "positions": _dimension(lambda r: r.position, lambda k: position_names.get(k, k) if k else "نامشخص")[:10],
    }

    for m in months:
        m.pop("idx", None)
        m["avg_headcount"] = _round(m["avg_headcount"])
    return {
        "range": {"from_month": month_label(from_idx), "to_month": month_label(to_idx), "start_month": month_label(start_idx)},
        "kpis": kpis,
        "monthly": months,
        "yearly": yearly,
        "reasons": reasons,
        "tenure_buckets": tenure_buckets,
        "cohorts": cohorts,
        "departments": dept_rows,
        "heatmap": heatmap,
        "demographics": demographics,
        "department_options": [{"code": c, "name": dept_names.get(c, c)} for c in department_options],
        "warnings": warnings,
        "category_titles": {str(k): v for k, v in category_title.items()},
    }
