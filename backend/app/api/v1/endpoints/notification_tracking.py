"""Read-only administrative view of dispatch and office automation deliveries."""
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, literal, or_, select, union_all
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.models.employee import Employee
from app.models.office_automation import OaNotificationOutbox as Office
from app.models.push_dispatch import PushDispatchDelivery as Delivery, PushDispatchJob as Job
from app.services.push_dispatch import dispatch_origin

router = APIRouter(dependencies=[Depends(require_permission("system.logs"))])
Source = Literal["dispatch", "office"]


def page(rows, size):
    return {"items": [dict(row) for row in rows[:size]], "has_more": len(rows) > size}


MODULES = {
    "family": "مشخصات خانوادگی", "leave": "مرخصی و تردد", "loan": "وام", "advance": "مساعده",
    "feedback": "بازخورد", "insurance": "بیمه", "careers": "استخدام", "birthday": "تولد",
    "photo": "عکس پرسنلی", "evaluation": "ارزیابی", "login_security": "امنیت ورود",
}
KINDS = {
    "new_letter": "نامه جدید", "cc": "رونوشت", "referral": "ارجاع", "cancelled": "لغو",
    "transfer": "انتقال", "approval": "درخواست تأیید", "returned": "بازگشت برای اصلاح",
    "reply": "پاسخ", "new_message": "پیام جدید", "follow_up": "پیگیری",
    "hr_submitted": "ارسال به منابع انسانی", "approver_pending": "در انتظار تأیید",
    "approved": "تأیید درخواست", "rejected": "رد درخواست", "paid": "پرداخت", "settled": "تسویه",
    "guarantor_requested": "درخواست ضمانت", "guarantor_left": "ترک کار ضامن",
    "guarantor_declined": "رد ضمانت", "to_finance_queue": "ارجاع به مالی", "to_finance": "ارجاع به مالی",
    "new": "ثبت درخواست", "reminder": "یادآوری", "result": "نتیجه ارزیابی", "left": "ترک کار",
    "summary": "خلاصه واکنش‌ها", "first_reaction": "اولین واکنش", "threshold": "هشدار ورود",
    "transition": "تغییر وضعیت", "approver_new": "درخواست جدید", "requester_approved": "تأیید درخواست",
    "requester_rejected": "رد درخواست", "forgotten_approved": "تأیید فراموشی ثبت تردد",
    "forgotten_rejected": "رد فراموشی ثبت تردد", "forgotten_supervisor": "بررسی فراموشی ثبت تردد",
    "hr_forgotten_pending": "بررسی منابع انسانی",
}


def message_reference(source, key):
    parts = key.split(":")
    module, kind, record, event = "اعلان عمومی", "اعلان", None, None
    if source == "office":
        module = "اتوماسیون اداری"
        if len(parts) >= 3 and parts[1].isdigit():
            kind, record = KINDS.get(parts[0], parts[0]), parts[1]
            event = parts[3] if len(parts) > 3 and parts[3] else None
    elif len(parts) == 4 and parts[:2] == ["dispatch", "notice"] and parts[2].isdigit():
        module, record = "اطلاعیه", parts[2]
        kind = "انتشار" if parts[3] == "publish" else "ارسال مجدد"
    elif len(parts) == 5 and parts[0] == "dispatch":
        module = MODULES.get(parts[1], parts[1])
        kind = KINDS.get(parts[4], parts[4])
        record = parts[2] if parts[2] != "unknown" else None
        event = parts[3]
    elif len(parts) >= 2:
        module = MODULES.get(parts[1], module)
    return {"module": module, "event_type": kind, "record_id": record, "event_id": event}


async def personnel_matches(db, code):
    western = code.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    variants = {code, western, western.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")),
                western.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))}
    rows = await db.execute(select(Employee.id, User.id).select_from(Employee)
                            .outerjoin(User, User.employee_id == Employee.id)
                            .where(Employee.personnel_code.in_(variants)))
    pairs = rows.all()
    return {eid for eid, _ in pairs}, {uid for _, uid in pairs if uid is not None}


@router.get("")
async def events(source: Source | None = None, state: str = Query("", max_length=24),
                 q: str = Query("", max_length=100), offset: int = Query(0, ge=0),
                 db: AsyncSession = Depends(get_db), personnel_code: Annotated[str, Query(max_length=64)] = ""):
    code = personnel_code.strip()
    employees, users = await personnel_matches(db, code) if code else (set(), set())
    if code and not employees:
        return page([], 30)
    queries = []
    for name, model in (("dispatch", Job), ("office", Office)):
        if source and source != name:
            continue
        ids = Job.user_ids if model is Job else Office.payload["_delivery"]["recipient_user_ids"]
        employee = literal(None) if model is Job else Office.payload["employee_id"].as_integer()
        query = select(ids[0].as_integer().label("first_user"), ids[1].as_integer().label("second_user"),
                       employee.label("employee_id"), literal(name).label("source"), model.id, model.key, model.status,
                       model.created_at, model.next_attempt_at)
        if model is Job:
            query = query.where(Job.origin == dispatch_origin())
        if code:
            if model is Job:
                matches = [cast(Job.user_ids, JSONB).contains([uid]) for uid in users]
                recorded = select(Delivery.id).where(Delivery.job_id == Job.id, Delivery.user_id.in_(users))
                query = query.where(or_(recorded.exists(), *matches))
            else:
                query = query.where(employee.in_(employees))
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
    result = page(rows.mappings().all(), 30)
    items = result["items"]
    user_ids = {item["first_user"] for item in items if item["first_user"] is not None}
    emp_ids = {item["employee_id"] for item in items if item["employee_id"] is not None}
    user_codes = dict((await db.execute(select(User.id, Employee.personnel_code)
                      .join(Employee, Employee.id == User.employee_id).where(User.id.in_(user_ids)))).all()) if user_ids else {}
    emp_codes = dict((await db.execute(select(Employee.id, Employee.personnel_code)
                     .where(Employee.id.in_(emp_ids)))).all()) if emp_ids else {}
    for item in items:
        uid, multiple = item.pop("first_user"), item.pop("second_user") is not None
        item["user_id"] = None if multiple else uid
        item["multiple_users"] = multiple
        if item["source"] == "office":
            item["personnel_code"] = emp_codes.get(item["employee_id"])
        elif code:
            item["personnel_code"] = code
            if len(users) == 1:
                item["user_id"] = next(iter(users))
        else:
            item["personnel_code"] = user_codes.get(item["user_id"])
        item["message"] = message_reference(item["source"], item["key"])
    return result


def safe_reason(value):
    # Older workers may persist arbitrary exception text containing provider URLs.
    if not value:
        return None
    if re.fullmatch(r"[a-z][a-z0-9_]{0,95}", value):
        return value
    return "see_server_logs"


@router.get("/{source}/{event_id}")
async def event_detail(source: Source, event_id: int, offset: int = Query(0, ge=0),
                       db: AsyncSession = Depends(get_db), personnel_code: Annotated[str, Query(max_length=64)] = ""):
    if source == "dispatch":
        job = await db.scalar(select(Job).where(Job.id == event_id, Job.origin == dispatch_origin()))
        if job is None:
            raise HTTPException(404)
        single_user = job.user_ids[0] if job.user_ids and len(job.user_ids) == 1 else None
        code = await db.scalar(select(Employee.personnel_code).join(User, User.employee_id == Employee.id)
                               .where(User.id == single_user)) if single_user is not None else None
        device_query = (select(Delivery.id, Delivery.subscription_id, Delivery.user_id, Employee.personnel_code, Delivery.status,
                                       Delivery.attempts, Delivery.next_attempt_at, Delivery.accepted_at,
                                       Delivery.last_error).select_from(Delivery)
                                .outerjoin(User, User.id == Delivery.user_id)
                                .outerjoin(Employee, Employee.id == User.employee_id).where(Delivery.job_id == event_id)
                                .order_by(Delivery.id))
        matched_users = []
        if personnel_code.strip():
            _, users = await personnel_matches(db, personnel_code.strip())
            matched_users = sorted(users.intersection(job.user_ids or []))
            device_query = device_query.where(Delivery.user_id.in_(users))
        rows = await db.execute(device_query.offset(offset).limit(31))
        result = page(rows.mappings().all(), 30)
        for item in result["items"]:
            item["last_error"] = safe_reason(item["last_error"])
        return {**result, "single_user_id": single_user, "personnel_code": code,
                "matched_user_ids": matched_users, "message": message_reference(source, job.key),
                "target_count": job.target_count if job.initialized else None,
                "no_device_count": job.no_device_count if job.initialized else None,
                "deadline_at": job.deadline_at, "last_error": safe_reason(job.last_error)}
    event = await db.get(Office, event_id)
    if event is None:
        raise HTTPException(404)
    payload = event.payload or {}
    tracking = payload.get("_delivery") or {}
    employee_id = payload.get("employee_id")
    code = await db.scalar(select(Employee.personnel_code).where(Employee.id == employee_id)) if employee_id else None
    recipients = tracking.get("recipient_user_ids") or []
    single_user = recipients[0] if len(recipients) == 1 else None
    devices = [{"user_id": single_user, "personnel_code": code, "subscription_id": device, "status": status}
               for group, status in (("remaining", "pending"), ("sent", "accepted"),
                                     ("stale", "stale"), ("failed", "failed"))
               for device in tracking.get(group, [])]
    return {**page(devices[offset:offset + 31], 30), "employee_id": employee_id, "personnel_code": code, "single_user_id": single_user,
            "message": message_reference(source, event.key), "attempts": event.attempts, "last_error": safe_reason(event.last_error)}
