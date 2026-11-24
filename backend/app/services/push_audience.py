"""Narrow queued recipients using current domain permissions, never expand them.

Legacy generic jobs have no structured event identity. Do not infer ownership
from their text or replay them. New workflow/HR events have explicit keys.
"""
from sqlalchemy import or_, select
from app.core.permission_grants import grants_subquery
from app.models.user import User
from app.models.employee import Employee


async def _granted(db, ids, codes, site_id=None, *, any_site=False, superuser=False, global_only=False):
    g = grants_subquery()
    condition = g.c.code.in_(codes)
    if not any_site:
        scope = g.c.site_id.is_(None)
        if site_id is not None and not global_only:
            scope = scope | (g.c.site_id == site_id)
        condition = condition & scope
    permission = User.id.in_(select(g.c.user_id).where(condition))
    if superuser:
        permission = or_(permission, User.is_superuser.is_(True))
    return set((await db.execute(select(User.id).where(User.id.in_(ids), permission))).scalars().all())


async def _employee_users(db, ids, employee_ids):
    return set((await db.execute(select(User.id).where(User.id.in_(ids),
        User.employee_id.in_(set(employee_ids) - {None})))).scalars().all())


async def restrict_business_audience(db, job):
    ids = set(job.user_ids or [])
    if not ids:
        return ids
    parts = job.key.split(":", 4)
    if len(parts) != 5 or parts[0] != "dispatch":
        return ids
    _, module, object_id, event_id, kind = parts
    if module == "login_security":
        return await _granted(db, ids, ("system.login_security",), any_site=True, superuser=True)
    if module == "careers":
        return await _granted(db, ids, ("careers.manage",), global_only=True, superuser=True)
    if module == "insurance" and kind == "left":
        return await _granted(db, ids, ("insurance.view", "insurance.manage"),
                              int(object_id) if object_id != "None" else None)
    if module == "photo":
        from app.models.profile_photo import ProfilePhotoRequest
        req = await db.get(ProfilePhotoRequest, int(object_id))
        if req is None or req.status != event_id:
            return set()
        if event_id == "pending":
            return await _granted(db, ids, ("photo.approve",), req.site_id)
        return await _employee_users(db, ids, [req.employee_id])
    if module == "family" and kind == "hr_submitted":
        from app.models.family import FamilyProfile, FamilySiteSetting
        profile = await db.get(FamilyProfile, int(object_id))
        if profile is None or profile.status != "pending":
            return set()
        employee = await db.get(Employee, profile.employee_id)
        if employee is None:
            return set()
        hr = (await db.execute(select(FamilySiteSetting.hr_employee_id).where(
            FamilySiteSetting.site_id == employee.site_id))).scalar_one_or_none()
        return await _employee_users(db, ids, [hr])
    if module == "feedback":
        from app.models.feedback import FeedbackMessage
        feedback = await db.get(FeedbackMessage, int(object_id))
        if feedback is None or feedback.is_deleted:
            return set()
        if kind == "reply":
            return ids & {feedback.sender_id}
        site = (await db.execute(select(Employee.site_id).join(User, User.employee_id == Employee.id)
                .where(User.id == feedback.sender_id))).scalar_one_or_none()
        ordinary = await _granted(db, ids, ("feedback.view", "feedback.reply"), site)
        full = await _granted(db, ids, ("feedback.view_all",), any_site=True)
        return (ordinary | full) - {feedback.sender_id}
    if module in ("advance", "loan"):
        from app.models.advance import AdvanceRequest, AdvanceSettings
        from app.models.loan import LoanRequest, LoanRequestGuarantor, LoanSiteSettings
        model, settings_model = ((AdvanceRequest, AdvanceSettings) if module == "advance"
                                 else (LoanRequest, LoanSiteSettings))
        req = await db.get(model, int(object_id))
        if req is None:
            return set()
        if kind == "approver_pending":
            if req.status != "in_review" or req.current_approver_employee_id is None:
                return set()
            direct = await _employee_users(db, ids, [req.current_approver_employee_id])
            if direct == ids:
                return direct
            # Only query KaraWeb for delegated accounts that were original recipients.
            from app.services.kara_substitute import substitute_of
            substitute = await substitute_of(db, settings_model, req.site_id, req.current_approver_employee_id)
            if substitute == req.employee_id:
                substitute = None
            return direct | await _employee_users(db, ids - direct, [substitute])
        if module == "loan" and kind == "guarantor_requested":
            if req.status != "in_review":
                return set()
            employees = (await db.execute(select(LoanRequestGuarantor.employee_id).where(
                LoanRequestGuarantor.request_id == req.id,
                LoanRequestGuarantor.status == "pending"))).scalars().all()
            return await _employee_users(db, ids, employees)
        return await _employee_users(db, ids, [req.employee_id])
    return ids


async def restrict_delivery_audience(db, job, ids, now):
    """Check time-sensitive domain state just before contacting the provider.

    The original account snapshot is never expanded. For KaraWeb, reuse the
    read-only, site-scoped cartable/own-request queries and their delegate rules;
    do not guess a current approver from old notification text. No KaraWeb write.
    A connection failure propagates to the dispatcher's bounded retry; it is not
    treated as authorization or as a terminal absence of the request.
    """
    if not ids:
        return set()
    _, module, object_id, event_id, kind = job.key.split(":", 4)
    if module == "leave":
        if not object_id.isdigit():
            # Historical events without a request ID cannot be safely replayed.
            return set()
        site_id, separator, _ = event_id.partition(".")
        if not separator or not site_id.isdigit():
            return set()
        from app.services.leave_request_service import LeaveRequestService
        service = LeaveRequestService(db)
        users = (await db.execute(select(User.id, Employee).join(Employee, Employee.id == User.employee_id)
            .where(User.id.in_(ids), Employee.site_id == int(site_id)))).all()
        allowed = set()
        for user_id, employee in users:
            if kind in ("approver_pending", "hr_pending"):
                rows = await service.list_pending_for_approver(employee, request_id=int(object_id))
                valid = any(str(r["request_id"]) == object_id and r["status"] == "pending"
                            and (kind != "hr_pending" or r.get("awaiting_hr")) for r in rows)
            else:
                rows = await service.list_my_requests(employee, request_id=int(object_id))
                expected = {"approved": "approved", "rejected": "rejected",
                            "forgotten_approved": "approved", "forgotten_rejected": "rejected",
                            "forgotten_supervisor": "pending"}.get(kind)
                valid = any(str(r["request_id"]) == object_id and r["status"] == expected
                            and (kind != "forgotten_supervisor" or r.get("awaiting_hr")) for r in rows)
            if valid:
                allowed.add(user_id)
        return allowed
    if module == "evaluation":
        from datetime import timedelta
        from app.models.evaluation_content import EvaluationPeriod, EvaluationPeriodStatus
        from app.models.evaluation_process import (Evaluation, EvaluationAssignment,
            EvaluationAssignmentStatus, EvaluationStatus)
        if kind == "reminder":
            employees = select(EvaluationAssignment.evaluator_employee_id).join(
                EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id).where(
                    EvaluationAssignment.status == EvaluationAssignmentStatus.pending,
                    EvaluationPeriod.status == EvaluationPeriodStatus.active,
                    EvaluationPeriod.is_disabled.is_(False), EvaluationPeriod.incomplete_closed.is_(False),
                    EvaluationPeriod.end_date > now, EvaluationPeriod.end_date <= now + timedelta(days=3))
            stmt = select(User.id).where(User.id.in_(ids), User.employee_id.in_(employees))
        elif kind == "result" and object_id.isdigit():
            employees = select(EvaluationAssignment.target_employee_id).join(
                Evaluation, Evaluation.assignment_id == EvaluationAssignment.id).join(
                EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id).where(
                    Evaluation.id == int(object_id), Evaluation.status == EvaluationStatus.submitted,
                    EvaluationPeriod.is_disabled.is_(False))
            stmt = select(User.id).where(User.id.in_(ids), User.employee_id.in_(employees))
        else:
            return set()
        return set((await db.execute(stmt)).scalars().all())
    if module == "birthday" and object_id.isdigit():
        return await _employee_users(db, ids, [int(object_id)])
    return ids
