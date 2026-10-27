"""
انتقال تأییدکننده‌های درخواست‌های باز وام و مساعده (docs/loans.md «انتقال تأییدکننده‌ها»).

هر درخواست هنگام ثبت، تأییدکننده‌ی هر مرحله (مدیر واحد، منابع انسانی، مدیر سایت) را روی خودش ذخیره می‌کند. اگر آن شخص
ترک کار کند یا مدیر سایت/منابع انسانی در تنظیمات عوض شود، درخواست نباید گم شود یا دوباره ثبت شود؛ این ماژول مراحل
شخصیِ باقی‌مانده (جاری و بعدی) را به تأییدکننده‌ی امروز منتقل می‌کند:
- مدیر سایت / منابع انسانی ← شخص فعلی تنظیمات سایت (اگر فعال باشد)؛
- مدیر واحد ← اگر شخص ذخیره‌شده دیگر فعال نیست یا refresh_unit_manager، دوباره از زنجیره‌ی تأیید مرخصی پیدا می‌شود.
مراحل گذشته و تصمیم‌های ثبت‌شده دست نمی‌خورند؛ نوبت وام عوض نمی‌شود. برای تأییدکننده‌ی جدیدِ مرحله‌ی جاری اعلان فرستاده
و در سابقه‌ی درخواست «تغییر تأییدکننده» ثبت می‌شود. تأییدکننده‌ای که پیدا نشود جایگزین نمی‌شود (unresolved).
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.loan_rules import plan_reassignment
from app.models.employee import Employee
from app.models.user import User

logger = logging.getLogger(__name__)

STEP_FIELDS = {
    "unit_manager": "unit_manager_employee_id",
    "hr": "hr_employee_id",
    "site_manager": "site_manager_employee_id",
}
STEP_TITLES = {"unit_manager": "مدیر واحد", "hr": "منابع انسانی", "site_manager": "مدیر سایت"}


class ApproverChecker:
    """«آیا این پرسنل می‌تواند تأیید کند؟» (فعال، فعال‌شده توسط ادمین، حساب پرتال) با Cache در طول یک اجرا."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache: dict[int, bool] = {}
        self._names: dict[int, str] = {}

    async def ok(self, employee_id: int | None) -> bool:
        if employee_id is None:
            return False
        if employee_id not in self._cache:
            emp = await self.db.get(Employee, employee_id)
            usable = bool(emp and emp.is_active and emp.is_enabled)
            if usable:
                usable = (
                    await self.db.execute(select(User.id).where(User.employee_id == employee_id).limit(1))
                ).first() is not None
            self._cache[employee_id] = usable
            self._names[employee_id] = f"{emp.first_name} {emp.last_name}" if emp else "—"
        return self._cache[employee_id]

    async def name(self, employee_id: int | None) -> str:
        if employee_id is None:
            return "—"
        if employee_id not in self._names:
            await self.ok(employee_id)
        return self._names.get(employee_id, "—")


async def reassign_requests(
    db: AsyncSession,
    requests: list,
    *,
    site_approvers: Callable[[int], Awaitable[dict[str, int | None]]],
    resolve_unit_manager: Callable[[Employee], Awaitable[int | None]],
    refresh_unit_manager: bool,
    current_step: Callable[[object], str | None],
    event: Callable[..., None],
    push: Callable[..., None],
    push_url: str,
    push_key: str,
    reason: str,
) -> dict:
    """
    requests: درخواست‌های «در حال تأیید» (با events بارگذاری‌شده). site_approvers(site_id) → {hr, site_manager} از تنظیمات.
    خروجی: {"changed": تعداد درخواست‌های تغییرکرده, "unresolved": درخواست‌هایی که تأییدکننده‌ی جاری‌شان قابل تأیید نیست
    و جایگزینی پیدا نشد}.
    """
    checker = ApproverChecker(db)
    settings_cache: dict[int, dict] = {}
    changed = unresolved = 0
    for req in requests:
        steps = list(req.steps or [])
        remaining = {k for i, k in enumerate(steps) if i >= req.step_index and k in STEP_FIELDS}
        if not remaining:
            continue
        stored = {k: getattr(req, STEP_FIELDS[k], None) for k in remaining}
        fresh: dict[str, int | None] = {}
        if remaining & {"hr", "site_manager"}:
            if req.site_id not in settings_cache:
                settings_cache[req.site_id] = await site_approvers(req.site_id)
            for key in ("hr", "site_manager"):
                if key in remaining:
                    candidate = settings_cache[req.site_id].get(key)
                    fresh[key] = candidate if await checker.ok(candidate) else None
        if "unit_manager" in remaining and (refresh_unit_manager or not await checker.ok(stored.get("unit_manager"))):
            requester = await db.get(Employee, req.employee_id)
            try:
                fresh["unit_manager"] = await resolve_unit_manager(requester) if requester else None
            except Exception:
                logger.warning("پیدا کردن دوباره‌ی مدیر واحد درخواست %s ناموفق بود", req.id, exc_info=True)
                fresh["unit_manager"] = None
        changes = plan_reassignment(steps, req.step_index, stored, fresh, req.employee_id)
        step_now = current_step(req)
        if changes:
            notes = []
            for key, new_id in changes.items():
                notes.append(f"{STEP_TITLES[key]}: {await checker.name(stored.get(key))} ← {await checker.name(new_id)}")
                setattr(req, STEP_FIELDS[key], new_id)
            if step_now in changes:
                req.current_approver_employee_id = changes[step_now]
                push([changes[step_now]], push_url, req.site_id, push_key)
            event(req, "approver_changed", "سامانه", None, f"{reason} — " + "؛ ".join(notes))
            changed += 1
        if step_now in STEP_FIELDS and not await checker.ok(req.current_approver_employee_id):
            unresolved += 1
    await db.flush()
    return {"changed": changed, "unresolved": unresolved}


async def stuck_count(db: AsyncSession, requests: list, current_step: Callable[[object], str | None]) -> int:
    """درخواست‌های «در حال تأیید» که تأییدکننده‌ی مرحله‌ی جاری‌شان دیگر نمی‌تواند تأیید کند (ترک کار/غیرفعال)."""
    checker = ApproverChecker(db)
    n = 0
    for req in requests:
        if current_step(req) in STEP_FIELDS and not await checker.ok(req.current_approver_employee_id):
            n += 1
    return n
