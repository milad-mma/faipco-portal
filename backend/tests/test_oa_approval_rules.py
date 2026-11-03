"""گردش تأیید ترتیبی: پاک‌سازی مسیر، مرحله‌ی خودکار امضای مدیر، مرحله‌ی بعد، توضیح اجباری برگشت."""

from app.core import oa_approval_rules as R


def _raises(fn, *a, **k):
    try:
        fn(*a, **k)
    except R.ApprovalRulesError as e:
        return str(e)
    raise AssertionError("expected ApprovalRulesError")


def test_clean_plan_rules():
    plan = R.clean_plan([{"employee_id": 5, "kind": "paraph"}, {"employee_id": "7", "kind": "sign"}], author_id=1, principal_id=None)
    assert plan == [{"employee_id": 5, "kind": "paraph"}, {"employee_id": 7, "kind": "sign"}]
    assert "نویسنده" in _raises(R.clean_plan, [{"employee_id": 1, "kind": "approve"}], author_id=1, principal_id=None)
    assert "یک بار" in _raises(R.clean_plan, [{"employee_id": 5, "kind": "paraph"}, {"employee_id": 5, "kind": "sign"}],
                               author_id=1, principal_id=None)
    assert "نوع" in _raises(R.clean_plan, [{"employee_id": 5, "kind": "x"}], author_id=1, principal_id=None)
    assert "حداکثر" in _raises(R.clean_plan, [{"employee_id": i, "kind": "approve"} for i in range(10, 20)],
                               author_id=1, principal_id=99)


def test_principal_step_is_automatic_and_last():
    explicit = R.clean_plan([{"employee_id": 9, "kind": "sign"}, {"employee_id": 5, "kind": "paraph"}], author_id=1, principal_id=9)
    assert explicit == [{"employee_id": 5, "kind": "paraph"}]  # مدیر از مسیر صریح حذف می‌شود
    eff = R.effective_plan(explicit, 9)
    assert eff[-1] == {"employee_id": 9, "kind": "sign", "required": True}
    assert R.effective_plan([], None) == []


def test_next_index_and_note():
    assert R.next_index(["approved", "pending", "pending"]) == 1
    assert R.next_index(["approved", "approved"]) is None
    assert R.next_index(["approved", "returned"]) is None
    assert "توضیح" in _raises(R.check_return_note, "  ")
    assert R.check_return_note(" متن ") == "متن"
