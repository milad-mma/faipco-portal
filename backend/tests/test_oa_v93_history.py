"""Contract tests for stable per-round approval and recipient evidence."""
from types import SimpleNamespace

from app.core.oa_version_snapshots import snapshot_approval_plan, snapshot_recipients


def test_recipient_snapshot_uses_order_and_person_at_selection_time():
    recipients = [
        SimpleNamespace(role="cc", employee_id=22, name_snapshot="ب", title_snapshot="کارشناس",
                        department_snapshot="انبار", selected_via="direct", sort_order=2),
        SimpleNamespace(role="to", employee_id=11, name_snapshot="الف", title_snapshot="مدیر",
                        department_snapshot="تولید", selected_via="position", sort_order=1),
    ]
    snapshot = snapshot_recipients(recipients)
    assert [r["employee_id"] for r in snapshot] == [11, 22]
    assert snapshot[0]["selected_via"] == "position"
    recipients[1].name_snapshot = "شخص جدید"
    assert snapshot[0]["name"] == "الف"


def test_approval_plan_snapshot_freezes_each_stage():
    steps = [
        SimpleNamespace(step_no=2, approver_employee_id=18, approver_name_snapshot="مریم",
                        approver_title_snapshot="سرپرست", kind="sign", required=True),
        SimpleNamespace(step_no=1, approver_employee_id=9, approver_name_snapshot="علی",
                        approver_title_snapshot=None, kind="paraph", required=False),
    ]
    snap = snapshot_approval_plan(steps)
    assert [s["step_no"] for s in snap] == [1, 2]
    assert snap[1] == {"step_no": 2, "employee_id": 18, "name": "مریم", "title": "سرپرست", "kind": "sign", "required": True}
