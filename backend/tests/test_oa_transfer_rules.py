"""انتقال کارهای باز: محرمانه بدون افشا و بدون انتقال به خود."""

from app.core import oa_transfer_rules as R

TASKS = [
    {"id": 1, "letter_id": 10, "confidential": False, "subject": "عادی", "number": "01/1405/000001", "kind": "action"},
    {"id": 2, "letter_id": 11, "confidential": True, "subject": "محرمانه", "number": None, "kind": "action"},
    {"id": 3, "letter_id": 12, "confidential": True, "subject": "محرمانه ۲", "number": None, "kind": "sign"},
]


def test_transfer_to_other_moves_all_without_revealing_confidential():
    out = R.plan(TASKS, performer_id=99, to_id=5, prior_access=set())
    assert out["move"] == [1, 2, 3]
    assert [v["letter_id"] for v in out["visible"]] == [10]
    assert all("محرمانه" not in v["subject"] for v in out["visible"])
    assert out["note"] == R.CONFIDENTIAL_MOVED_NOTE


def test_transfer_to_self_skips_confidential_without_prior_access():
    out = R.plan(TASKS, performer_id=5, to_id=5, prior_access={12})
    assert out["move"] == [1, 3]  # ۱۱ بدون دسترسی قبلی منتقل نمی‌شود
    assert out["note"] == R.CONFIDENTIAL_SELF_NOTE


def test_check_request():
    for args in ((0, 5, "x"), (5, 5, "x"), (4, 5, "  ")):
        try:
            R.check_request(*args)
        except R.TransferRulesError:
            continue
        raise AssertionError(args)
    assert R.check_request(4, 5, " ترک کار ") == "ترک کار"
