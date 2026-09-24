"""تست‌های قاعده‌ی «نزدیک‌ترین ریشه» برای تقسیم درخت واحدهای کاراوب بین سایت‌ها (app/core/org_tree.py)."""
import pytest

from app.core.org_tree import (
    OrgTreeError,
    assign_units_to_sites,
    build_parent_map,
    descendants_count,
    validate_roots,
)

FACTORY, HO, THIRD = 1, 2, 3


def _rows(pairs):
    """ردیف‌های شبیه جدول Sections کاراوب از جفت‌های (Sec_No, TFather) می‌سازد."""
    return [{"Sec_No": code, "TFather": parent} for code, parent in pairs]


# ساختار فعلی کاراوب: «مدیریت» (1) بدون بالادست و بقیه زیرش؛ اداری (3) زیر منابع انسانی (2)
CURRENT = _rows([(1, None), (2, 1), (3, 2), (4, 1), (25, 1)])


# نقشه‌ی بالادست: کدها رشته‌اند و بالادست NULL → None
def test_build_parent_map_normalizes_codes():
    parents = build_parent_map(_rows([(1, None), (2, 1.0), (" 3 ", "2"), (None, 1), (5, 5)]), "Sec_No", "TFather")
    assert parents == {"1": None, "2": "1", "3": "2", "5": None}


# حالت امروز: یک سایت با ریشه‌ی «مدیریت» همه‌ی واحدها را می‌گیرد (رفتار بدون تغییر)
def test_single_root_owns_whole_tree():
    parents = build_parent_map(CURRENT, "Sec_No", "TFather")
    result = assign_units_to_sites(parents, {FACTORY: {"1"}})
    assert set(result.values()) == {FACTORY}


# حالت ۱: دو ریشه‌ی جدا («مدیریت» و «مدیریت (HO)»)
def test_two_separate_roots():
    rows = CURRENT + _rows([(100, None), (101, 100), (102, 101)])
    parents = build_parent_map(rows, "Sec_No", "TFather")
    result = assign_units_to_sites(parents, {FACTORY: {"1"}, HO: {"100"}})
    assert {c for c, s in result.items() if s == FACTORY} == {"1", "2", "3", "4", "25"}
    assert {c for c, s in result.items() if s == HO} == {"100", "101", "102"}


# حالت ۲: «مدیریت» زیر «مدیریت (HO)»؛ زیرشاخه‌ی مدیریت به ریشه‌ی نزدیک‌تر (کارخانه) می‌رسد
def test_nested_root_nearest_wins():
    rows = _rows([(100, None), (101, 100), (1, 100), (2, 1), (3, 2), (4, 1)])
    parents = build_parent_map(rows, "Sec_No", "TFather")
    result = assign_units_to_sites(parents, {FACTORY: {"1"}, HO: {"100"}})
    assert result["100"] == HO and result["101"] == HO
    assert result["1"] == FACTORY and result["3"] == FACTORY and result["4"] == FACTORY


# سایت سوم تودرتو داخل شاخه‌ی کارخانه هم با همان قاعده جدا می‌شود
def test_third_site_nested_inside_factory():
    rows = CURRENT + _rows([(30, 4), (31, 30)])
    parents = build_parent_map(rows, "Sec_No", "TFather")
    result = assign_units_to_sites(parents, {FACTORY: {"1"}, THIRD: {"30"}})
    assert result["30"] == THIRD and result["31"] == THIRD
    assert result["4"] == FACTORY


# واحدی که زیر هیچ ریشه‌ای نیست بی‌سایت (None) می‌ماند
def test_unassigned_unit():
    rows = CURRENT + _rows([(100, None), (101, 100)])
    parents = build_parent_map(rows, "Sec_No", "TFather")
    result = assign_units_to_sites(parents, {FACTORY: {"1"}})
    assert result["100"] is None and result["101"] is None


# یک سایت می‌تواند چند ریشه داشته باشد
def test_multiple_roots_per_site():
    rows = CURRENT + _rows([(100, None), (101, 100)])
    parents = build_parent_map(rows, "Sec_No", "TFather")
    result = assign_units_to_sites(parents, {FACTORY: {"1", "100"}})
    assert set(result.values()) == {FACTORY}


# حلقه در داده‌ی خراب منبع باعث قفل نمی‌شود و واحدهای حلقه بی‌سایت می‌شوند
def test_cycle_does_not_hang():
    parents = {"1": None, "7": "8", "8": "7", "9": "7"}
    result = assign_units_to_sites(parents, {FACTORY: {"1"}})
    assert result["1"] == FACTORY
    assert result["7"] is None and result["8"] is None and result["9"] is None


# یک واحد نمی‌تواند ریشه‌ی دو سایت باشد
def test_duplicate_root_rejected():
    with pytest.raises(OrgTreeError):
        validate_roots({FACTORY: {"1"}, HO: {"1"}})
    with pytest.raises(OrgTreeError):
        assign_units_to_sites({"1": None}, {FACTORY: {"1"}, HO: {"1", "2"}})


# شمارش زیرواحدها برای پیش‌نمایش
def test_descendants_count():
    parents = build_parent_map(CURRENT, "Sec_No", "TFather")
    assert descendants_count(parents, "1") == 4
    assert descendants_count(parents, "2") == 1
    assert descendants_count(parents, "25") == 0


# جداسازی ردیف‌های پرسنل در Sync: مال این سایت، مال سایت دیگر (محافظت از غیرفعال‌شدن) و بی‌سایت (هشدار)
def test_sync_split_rows_by_org():
    pytest.importorskip("sqlalchemy")
    from app.sync_engine.sync_service import SyncService

    columns = {"personnel_code": "Emp_No", "department_raw": "Sec_No"}
    rows = [
        {"Emp_No": 10, "Sec_No": 4},  # کارخانه
        {"Emp_No": 11, "Sec_No": 101},  # دفتر مرکزی
        {"Emp_No": 12, "Sec_No": 999},  # واحد بی‌سایت
        {"Emp_No": 13, "Sec_No": None},  # بدون واحد
    ]
    assignment = {"1": FACTORY, "4": FACTORY, "100": HO, "101": HO, "999": None}
    own, elsewhere, unassigned, skipped, warning = SyncService._split_rows_by_org(
        FACTORY, columns, rows, assignment, {"999": "واحد جدید"}
    )
    assert [r["Emp_No"] for r in own] == [10]
    assert elsewhere == {"11": HO}
    assert unassigned == {"12", "13"}
    assert skipped == 2
    assert "واحد جدید (999): 1" in warning


# داشتن نقش/مجوز برای همه‌ی سایت‌های موجود معادل سراسری است؛ بدون سایت تعریف‌شده هیچ‌وقت
def test_covers_all_sites():
    pytest.importorskip("sqlalchemy")
    from app.core.site_access import covers_all_sites

    assert covers_all_sites({1, 2}, {1, 2})
    assert covers_all_sites({1, 2, 3}, {1, 2})
    assert not covers_all_sites({1}, {1, 2})
    assert not covers_all_sites(set(), set())
    assert not covers_all_sites({1}, set())
