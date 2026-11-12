"""Stable, JSON-serializable evidence of recipients and approval steps per OA version.

These snapshots do not grant access and must never be used for authorization.
"""

def snapshot_recipients(recipients):
    return [
        {
            "role": r.role,
            "employee_id": r.employee_id,
            "name": r.name_snapshot,
            "title": r.title_snapshot,
            "department": r.department_snapshot,
            "selected_via": r.selected_via,
            "sort_order": r.sort_order,
        }
        for r in sorted(recipients, key=lambda x: (x.sort_order, x.employee_id or 0))
    ]


def snapshot_approval_plan(steps):
    return [
        {
            "step_no": s.step_no,
            "employee_id": s.approver_employee_id,
            "name": s.approver_name_snapshot,
            "title": s.approver_title_snapshot,
            "kind": s.kind,
            "required": bool(s.required),
        }
        for s in sorted(steps, key=lambda x: x.step_no)
    ]
