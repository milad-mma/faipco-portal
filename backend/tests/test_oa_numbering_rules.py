"""قواعد شماره‌ی دبیرخانه: پیشوند، قالب prefix/yyyy/seq و خواندن دوباره."""

from app.core import oa_numbering_rules as R


def _raises(fn, *a):
    try:
        fn(*a)
    except R.NumberingError as e:
        return str(e)
    raise AssertionError("expected NumberingError")


def test_prefix_rules():
    assert R.clean_prefix(" 01 ") == "01"
    assert R.clean_prefix("SAF1") == "SAF1"
    for bad in ("", "a/b", "a b", "۱۲", "ABCDEFGHIJK", None):
        assert "پیشوند" in _raises(R.clean_prefix, bad)


def test_format_and_parse():
    assert R.format_number("01", 1405, 125) == "01/1405/000125"
    assert R.format_number("HQ", 1406, 1) == "HQ/1406/000001"
    assert R.format_number("A", 1405, 1234567) == "A/1405/1234567"
    assert R.parse_number("01/1405/000125") == ("01", 1405, 125)
    assert R.parse_number("bad") is None
    _raises(R.format_number, "01", 1405, 0)
    _raises(R.format_number, "01", 2026, 1)
