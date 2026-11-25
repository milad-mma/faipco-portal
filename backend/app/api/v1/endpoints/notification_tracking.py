"""Read-only administrative view of dispatch and office automation deliveries."""
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.office_automation import OaNotificationOutbox as Office
from app.models.push_dispatch import PushDispatchDelivery as Delivery, PushDispatchJob as Job
from app.services.push_dispatch import dispatch_origin

router = APIRouter(dependencies=[Depends(require_permission("system.logs"))])
Source = Literal["dispatch", "office"]


def page(rows, size):
    return {"items": [dict(row) for row in rows[:size]], "has_more": len(rows) > size}


@router.get("")
async def events(source: Source | None = None, state: str = Query("", max_length=24),
                 q: str = Query("", max_length=100), offset: int = Query(0, ge=0),
                 db: AsyncSession = Depends(get_db)):
    queries = []
    for name, model in (("dispatch", Job), ("office", Office)):
        if source and source != name:
            continue
        query = select(literal(name).label("source"), model.id, model.key, model.status,
                       model.created_at, model.next_attempt_at)
        if model is Job:
            query = query.where(Job.origin == dispatch_origin())
        if state:
            query = query.where(model.status == state)
        term = q.strip()
        if term:
            query = query.where(or_(model.key.contains(term, autoescape=True),
                                    cast(model.id, String) == term))
        queries.append(query)
    records = union_all(*queries).subquery()
    rows = await db.execute(select(records).order_by(records.c.created_at.desc(),
                            records.c.source, records.c.id.desc()).offset(offset).limit(31))
    return page(rows.mappings().all(), 30)


def safe_reason(value):
    # Older workers may persist arbitrary exception text containing provider URLs.
    if not value:
        return None
    if re.fullmatch(r"[a-z][a-z0-9_]{0,95}", value):
        return value
    return "see_server_logs"


@router.get("/{source}/{event_id}")
async def event_detail(source: Source, event_id: int, offset: int = Query(0, ge=0),
                       db: AsyncSession = Depends(get_db)):
    if source == "dispatch":
        job = await db.scalar(select(Job).where(Job.id == event_id, Job.origin == dispatch_origin()))
        if job is None:
            raise HTTPException(404)
        rows = await db.execute(select(Delivery.subscription_id, Delivery.user_id, Delivery.status,
                                       Delivery.attempts, Delivery.next_attempt_at, Delivery.accepted_at,
                                       Delivery.last_error).where(Delivery.job_id == event_id)
                                .order_by(Delivery.id).offset(offset).limit(31))
        result = page(rows.mappings().all(), 30)
        for item in result["items"]:
            item["last_error"] = safe_reason(item["last_error"])
        return {**result, "single_user_id": job.user_ids[0] if job.user_ids and len(job.user_ids) == 1 else None,
                "target_count": job.target_count if job.initialized else None,
                "no_device_count": job.no_device_count if job.initialized else None,
                "deadline_at": job.deadline_at, "last_error": safe_reason(job.last_error)}
    event = await db.get(Office, event_id)
    if event is None:
        raise HTTPException(404)
    payload = event.payload or {}
    tracking = payload.get("_delivery") or {}
    devices = [{"subscription_id": device, "status": status}
               for group, status in (("remaining", "pending"), ("sent", "accepted"),
                                     ("stale", "stale"), ("failed", "failed"))
               for device in tracking.get(group, [])]
    return {**page(devices[offset:offset + 31], 30), "employee_id": payload.get("employee_id"),
            "attempts": event.attempts, "last_error": safe_reason(event.last_error)}
