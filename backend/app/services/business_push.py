"""Transactional notification helpers for PostgreSQL workflow events."""
from datetime import timedelta
from sqlalchemy import select
from app.models.user import User
from app.services import notification_templates


async def queue_workflow_pushes(db, pushes):
    """Snapshot event/recipient/text in the same transaction as the workflow.

    Events may have no ID until flush. Keep event object references, not the
    last event of a request at commit time (bulk actions can create several).
    """
    if not pushes:
        return
    from app.services.push_dispatch import business_event_key, enqueue_event_push
    await db.flush()
    employee_ids = {eid for _, _, ids, _, _, _, _ in pushes for eid in ids if eid is not None}
    recipients = {}
    if employee_ids:
        rows = (await db.execute(select(User.employee_id, User.id).where(User.employee_id.in_(employee_ids)))).all()
        for employee_id, user_id in rows:
            recipients.setdefault(employee_id, set()).add(user_id)
    templates = {}
    for request, event, ids, url, site_id, key, values in pushes:
        if event is None or event.id is None or request.id is None:
            raise RuntimeError("Workflow push has no persisted domain event")
        users = {uid for eid in ids for uid in recipients.get(eid, ())}
        cache_key = (site_id, key)
        if cache_key not in templates:
            templates[cache_key] = await notification_templates.get_text(site_id, key)
        body = notification_templates.fill(templates[cache_key], **values)
        module, kind = key.split(".", 1)
        await enqueue_event_push(db, users, url, body,
            event_key=business_event_key(module, request.id, event.id, kind),
            lifetime=timedelta(days=1) if "pending" in kind or kind == "guarantor_requested" else timedelta(days=7))
