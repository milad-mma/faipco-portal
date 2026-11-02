"""
منشی در اتوماسیون اداری (فاز ۳الف): منشی برای مدیر پیش‌نویس تهیه می‌کند و به نام مدیر ارسال می‌کند.
- تعیین منشی: خود مدیر (از کارتابل) یا دارنده‌ی automation.settings سایت مدیر.
- منشی کارتابل مدیر را نمی‌بیند (تصمیم ۱۴۰۵/۰۸/۱۱)؛ فقط نامه‌هایی که خودش تهیه کرده.
- هر دو طرف باید فعال و دارای دسترسی اتوماسیون باشند؛ در لحظه‌ی ارسال دوباره بررسی می‌شود.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.models.employee import Department, Employee
from app.models.office_automation import OaSecretary
from app.models.site import Site
from app.models.user import User
from app.services.oa_cartable_service import OaCartableError, OaCartableService, _full_name, eligible_users_subquery

MAX_SECRETARIES = 5


class OaSecretaryService(OaCartableService):
    async def _person(self, employee_id: int) -> dict:
        row = (await self.db.execute(
            select(Employee, Department.name).outerjoin(Department, Department.id == Employee.department_id)
            .where(Employee.id == employee_id)
        )).first()
        if row is None:
            return {"employee_id": employee_id, "name": "—", "title": None, "department": None}
        e, d = row
        return {"employee_id": e.id, "name": _full_name(e), "title": e.position_title, "department": d}

    async def _active_ok(self, employee_id: int) -> bool:
        """فعال + دسترسی اتوماسیون (بدون محدودیت سایت)."""
        return bool((await self.db.execute(
            select(Employee.id).where(Employee.id == employee_id, Employee.is_active.is_(True),
                                      Employee.is_enabled.is_(True), Employee.id.in_(eligible_users_subquery()))
        )).scalar_one_or_none())

    async def is_secretary(self, principal_id: int, secretary_id: int) -> bool:
        if not principal_id or not secretary_id or principal_id == secretary_id:
            return False
        pair = (await self.db.execute(
            select(OaSecretary.id).where(OaSecretary.principal_employee_id == principal_id,
                                         OaSecretary.secretary_employee_id == secretary_id)
        )).scalar_one_or_none()
        return bool(pair) and await self._active_ok(principal_id)

    async def principals_of(self, secretary_id: int) -> list[dict]:
        ids = (await self.db.execute(
            select(OaSecretary.principal_employee_id).where(OaSecretary.secretary_employee_id == secretary_id)
            .order_by(OaSecretary.id)
        )).scalars().all()
        return [await self._person(i) for i in ids if await self._active_ok(i)]

    # ---------- خود مدیر ----------

    async def mine(self, user: User) -> dict:
        me = await self._me(user)
        rows = (await self.db.execute(
            select(OaSecretary).where(OaSecretary.principal_employee_id == me.id).order_by(OaSecretary.id)
        )).scalars().all()
        return {
            "secretaries": [{**await self._person(r.secretary_employee_id), "id": r.id} for r in rows],
            "principals": await self.principals_of(me.id),
            "max": MAX_SECRETARIES,
        }

    async def _add(self, principal: Employee, secretary_id: int, user: User) -> None:
        if secretary_id == principal.id:
            raise OaCartableError("هر کس نمی‌تواند منشی خودش باشد")
        exists = (await self.db.execute(
            select(OaSecretary.id).where(OaSecretary.principal_employee_id == principal.id,
                                         OaSecretary.secretary_employee_id == secretary_id)
        )).scalar_one_or_none()
        if exists:
            return
        count = len((await self.db.execute(
            select(OaSecretary.id).where(OaSecretary.principal_employee_id == principal.id)
        )).scalars().all())
        if count >= MAX_SECRETARIES:
            raise OaCartableError(f"حداکثر {MAX_SECRETARIES} منشی برای هر نفر")
        self.db.add(OaSecretary(principal_employee_id=principal.id, secretary_employee_id=secretary_id,
                                created_by_user_id=user.id))
        self.files.audit("secretary.add", user, entity="employee", entity_id=principal.id, site_id=principal.site_id,
                         details={"secretary": secretary_id})
        await self.db.commit()

    async def add_mine(self, user: User, secretary_id: int) -> dict:
        me = await self._me(user)
        if secretary_id not in await self._eligible({secretary_id}, user):
            raise OaCartableError("این شخص مجاز نیست (غیرفعال، بدون دسترسی اتوماسیون یا در سایتی خارج از دسترسی شما)")
        await self._add(me, secretary_id, user)
        return await self.mine(user)

    async def remove_mine(self, user: User, pair_id: int) -> dict:
        me = await self._me(user)
        pair = await self.db.get(OaSecretary, pair_id)
        if pair is None or pair.principal_employee_id != me.id:
            raise OaCartableError("یافت نشد", 404)
        await self.db.delete(pair)
        self.files.audit("secretary.remove", user, entity="employee", entity_id=me.id, site_id=me.site_id,
                         details={"secretary": pair.secretary_employee_id})
        await self.db.commit()
        return await self.mine(user)

    # ---------- مدیر سامانه (automation.settings، سایت‌محور بر اساس سایت مدیر) ----------

    async def admin_list(self, sites: set[int] | None) -> list[dict]:
        principal = aliased(Employee)
        stmt = (
            select(OaSecretary, Site.name)
            .join(principal, principal.id == OaSecretary.principal_employee_id)
            .join(Site, Site.id == principal.site_id)
            .order_by(Site.name, principal.last_name, principal.first_name, OaSecretary.id)
        )
        if sites is not None:
            stmt = stmt.where(principal.site_id.in_(sites or {-1}))
        out = []
        for pair, site_name in (await self.db.execute(stmt)).all():
            out.append({
                "id": pair.id, "site": site_name,
                "principal": await self._person(pair.principal_employee_id),
                "secretary": await self._person(pair.secretary_employee_id),
                "principal_active": await self._active_ok(pair.principal_employee_id),
                "secretary_active": await self._active_ok(pair.secretary_employee_id),
            })
        return out

    async def admin_add(self, user: User, sites: set[int] | None, principal_id: int, secretary_id: int) -> list[dict]:
        principal = await self.db.get(Employee, principal_id)
        secretary = await self.db.get(Employee, secretary_id)
        if principal is None or secretary is None:
            raise OaCartableError("پرسنل انتخاب‌شده پیدا نشد", 404)
        if sites is not None and (principal.site_id not in sites or secretary.site_id not in sites):
            raise OaCartableError("مدیر و منشی باید در سایت‌هایی باشند که تنظیمات اتوماسیونشان با شماست", 403)
        if not (await self._active_ok(principal_id) and await self._active_ok(secretary_id)):
            raise OaCartableError("مدیر و منشی هر دو باید فعال و دارای دسترسی اتوماسیون باشند")
        await self._add(principal, secretary_id, user)
        return await self.admin_list(sites)

    async def admin_remove(self, user: User, sites: set[int] | None, pair_id: int) -> list[dict]:
        pair = await self.db.get(OaSecretary, pair_id)
        principal = await self.db.get(Employee, pair.principal_employee_id) if pair else None
        if pair is None or principal is None or (sites is not None and principal.site_id not in sites):
            raise OaCartableError("یافت نشد", 404)
        await self.db.delete(pair)
        self.files.audit("secretary.remove", user, entity="employee", entity_id=principal.id, site_id=principal.site_id,
                         details={"secretary": pair.secretary_employee_id, "by_admin": True})
        await self.db.commit()
        return await self.admin_list(sites)

