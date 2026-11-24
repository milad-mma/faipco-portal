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
