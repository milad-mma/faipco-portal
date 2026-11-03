"""
امضای شخصی (فاز ۳ب، سند مرجع بخش ۸.۱؛ تصمیم‌های ۱۴۰۵/۰۸/۱۲):
- «امضای من» در پنل کاربری برای دارندگان automation.access: رسم یا بارگذاری؛ بدون تأیید هویت دوباره (تصمیم کاربر).
- هر ثبت = نسخه‌ی تازه‌ی active؛ نسخه‌ی قبلی inactive می‌شود ولی فایلش حذف نمی‌شود (روی نامه‌های قبلی می‌ماند).
- فایل در Storage خصوصی اتوماسیون (write-once)؛ نمایش فقط از API: صاحب امضا یا هر کسی که به نامه‌ی امضاشده دسترسی دارد.
- هیچ‌کس به نام دیگری امضا نمی‌کند: امضا فقط امضای خود فرستنده است (نه نامه‌ای که منشی به نام مدیر می‌فرستد).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import oa_signature_rules as srules
from app.models.employee import Employee
from app.models.office_automation import OaFile, OaSignatureVersion
from app.models.user import User
from app.services.oa_file_service import OaFileService


class OaSignatureError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class OaSignatureService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.files = OaFileService(db)

    async def _me(self, user: User) -> Employee:
        e = await self.db.get(Employee, user.employee_id) if user.employee_id else None
        if e is None:
            raise OaSignatureError("حساب شما به پرسنل وصل نیست", 403)
        return e

    async def active_for(self, employee_id: int) -> OaSignatureVersion | None:
        return (await self.db.execute(
            select(OaSignatureVersion).where(OaSignatureVersion.owner_employee_id == employee_id,
                                             OaSignatureVersion.status == "active")
        )).scalar_one_or_none()

    @staticmethod
    def _out(v: OaSignatureVersion) -> dict:
        return {"id": v.id, "version_no": v.version_no, "method": v.method, "status": v.status,
                "created_at": v.created_at, "deactivated_at": v.deactivated_at}

    async def mine(self, user: User) -> dict:
        me = await self._me(user)
        rows = (await self.db.execute(
            select(OaSignatureVersion).where(OaSignatureVersion.owner_employee_id == me.id)
            .order_by(OaSignatureVersion.version_no.desc())
        )).scalars().all()
        active = next((r for r in rows if r.status == "active"), None)
        return {"active": self._out(active) if active else None, "history": [self._out(r) for r in rows]}

    async def create(self, user: User, raw: bytes, *, method: str, remove_background: bool) -> dict:
        if method not in srules.METHODS:
            raise OaSignatureError("روش ثبت امضا نامعتبر است")
        me = await self._me(user)
        try:
            png = await asyncio.to_thread(srules.process_signature, raw, remove_background=remove_background)
        except srules.SignatureRulesError as e:
            raise OaSignatureError(str(e)) from None

        async def chunks():
            yield png

        key, size, sha = await self.files.storage.receive(chunks(), srules.MAX_UPLOAD_BYTES * 2)
        storage_key = self.files.storage.commit(key)
        now = datetime.now(timezone.utc)
        f = OaFile(site_id=me.site_id, storage_key=storage_key, original_name=f"signature-{me.id}.png", size=size,
                   detected_format="png", content_type="image/png", sha256=sha, uploaded_by=user.id,
                   purpose="signature", status="clean", state="permanent")
        self.db.add(f)
        await self.db.flush()
        await self.db.execute(
            update(OaSignatureVersion)
            .where(OaSignatureVersion.owner_employee_id == me.id, OaSignatureVersion.status == "active")
            .values(status="inactive", deactivated_at=now, deactivate_reason="جایگزین با امضای جدید")
        )
        last = (await self.db.execute(
            select(func.max(OaSignatureVersion.version_no)).where(OaSignatureVersion.owner_employee_id == me.id)
        )).scalar() or 0
        v = OaSignatureVersion(owner_employee_id=me.id, version_no=last + 1, file_id=f.id, sha256=sha, method=method,
                               status="active", created_by_user_id=user.id, created_at=now)
        self.db.add(v)
        self.files.audit("signature.create", user, entity="signature", entity_id=me.id, site_id=me.site_id,
                         details={"version": last + 1, "method": method, "sha256": sha})
        await self.db.commit()
        return await self.mine(user)

    async def deactivate_mine(self, user: User) -> dict:
        me = await self._me(user)
        active = await self.active_for(me.id)
        if active is None:
            raise OaSignatureError("امضای فعالی ندارید")
        active.status, active.deactivated_at = "inactive", datetime.now(timezone.utc)
        active.deactivate_reason = "غیرفعال‌سازی توسط صاحب امضا"
        self.files.audit("signature.deactivate", user, entity="signature", entity_id=me.id, site_id=me.site_id,
                         details={"version": active.version_no})
        await self.db.commit()
        return await self.mine(user)

    async def file_of(self, version_id: int) -> OaFile:
        v = await self.db.get(OaSignatureVersion, version_id)
        f = await self.db.get(OaFile, v.file_id) if v else None
        if f is None or not f.storage_key or not self.files.storage.exists(f.storage_key):
            raise OaSignatureError("تصویر امضا یافت نشد", 404)
        return f

    async def my_file(self, user: User, version_id: int | None = None) -> OaFile:
        """تصویر امضای خود کاربر (نسخه‌ی active یا نسخه‌ی مشخص از تاریخچه‌ی خودش)."""
        me = await self._me(user)
        v = await self.db.get(OaSignatureVersion, version_id) if version_id else await self.active_for(me.id)
        if v is None or v.owner_employee_id != me.id:
            raise OaSignatureError("تصویر امضا یافت نشد", 404)
        return await self.file_of(v.id)
