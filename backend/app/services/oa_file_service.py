"""
سرویس فایل و تنظیمات پیوست اتوماسیون اداری — فاز ۱ (docs/office-automation.md).

چرخه‌ی آپلود (بخش ۱۱ سند): مجوز و تنظیم سایت → پسوند (ممنوع/خاموش) → دریافت جریانی با سقف حجم → بررسی نوع واقعی و
ساختار → انتقال write-once به objects/ → اسکن ClamAV → clean | infected (قرنطینه) | scan_pending (Job دوباره امتحان می‌کند).
دانلود فقط برای فایل clean. فاز ۱: فقط بارگذارنده فایل خودش را می‌بیند (پیوست به نامه از فاز ۳الف).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import oa_file_rules as rules
from app.core.config import get_settings
from app.models.office_automation import OaAttachmentSettings, OaAuditEvent, OaFile
from app.models.site import Site
from app.models.user import User
from app.services import oa_clamav, oa_scanner, server_upload_limit
from app.services.oa_storage import LocalStorage, SizeLimitExceeded

logger = logging.getLogger(__name__)

SCAN_RETRY_MAX = 200  # پس از این تعداد تلاش ناموفق (حدود ۱۷ ساعت با فاصله‌ی ۵ دقیقه) فقط در پنل هشدار می‌ماند
DB_STALE_DAYS = 7  # بانک شناسایی قدیمی‌تر = هشدار (اسکن متوقف نمی‌شود)


class OaFileError(ValueError):
    """خطای قابل نمایش (پیام فارسی)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _actor_name(user: User | None) -> str | None:
    return getattr(user, "username", None) if user else None


class OaFileService:
    def __init__(self, db: AsyncSession, storage: LocalStorage | None = None):
        self.db = db
        self.storage = storage or LocalStorage()

    # ---------- ثبت وقایع ----------

    def audit(self, action: str, user: User | None, *, entity: str, entity_id=None, site_id=None, details=None,
              ip: str | None = None) -> None:
        self.db.add(
            OaAuditEvent(
                entity=entity, entity_id=entity_id, site_id=site_id, action=action,
                actor_user_id=user.id if user else None, actor_name=_actor_name(user), ip=ip, details=details,
            )
        )

    # ---------- تنظیمات پیوست ----------

    async def _row(self, site_id: int) -> OaAttachmentSettings | None:
        return (
            await self.db.execute(select(OaAttachmentSettings).where(OaAttachmentSettings.site_id == site_id))
        ).scalar_one_or_none()

    @staticmethod
    def _row_values(row: OaAttachmentSettings | None) -> dict:
        if row is None:
            return rules.default_settings()
        values = {k: getattr(row, k) for k in rules.DEFAULT_LIMITS}
        values["allowed_formats"] = [c for c in (row.allowed_formats or []) if c in rules.FORMAT_BY_CODE]
        return values

    async def site_settings(self, site_id: int) -> dict:
        return self._row_values(await self._row(site_id))

    async def settings_for_sites(self, site_ids: set[int] | None) -> list[dict]:
        stmt = select(Site).where(Site.is_active.is_(True)).order_by(Site.id)
        if site_ids is not None:
            stmt = stmt.where(Site.id.in_(site_ids or {-1}))
        sites = (await self.db.execute(stmt)).scalars().all()
        rows = {
            r.site_id: r
            for r in (await self.db.execute(select(OaAttachmentSettings))).scalars().all()
        }
        out = []
        for site in sites:
            row = rows.get(site.id)
            out.append(
                {
                    "site_id": site.id,
                    "site_name": site.name,
                    "is_default": row is None,
                    "updated_at": row.updated_at if row else None,
                    "values": self._row_values(row),
                }
            )
        return out

    async def catalog(self) -> dict:
        """فهرست ثابت فرمت‌ها، ممنوع‌ها و سقف سرور برای صفحه‌ی تنظیمات."""
        return {
            "formats": [
                {"code": f.code, "label": f.label, "extensions": list(f.extensions), "default_on": f.default_on,
                 "note": f.note}
                for f in rules.FORMATS
            ],
            "forbidden_label": rules.FORBIDDEN_LABEL,
            "server_max_file_mb": await server_upload_limit.portal_max_file_mb(self.db),
            "server_upload_limit_mb": await server_upload_limit.get_limit_mb(self.db),
            "defaults": rules.default_settings(),
            "max_files_cap": rules.MAX_FILES_CAP,
            "max_total_mb_cap": rules.MAX_TOTAL_MB_CAP,
        }

    async def save_site_settings(self, site_id: int, values: dict, user: User, ip: str | None = None) -> dict:
        try:
            clean = rules.validate_settings(values, await server_upload_limit.portal_max_file_mb(self.db))
        except rules.FileRejected as e:
            raise OaFileError(str(e)) from None
        if await self.db.get(Site, site_id) is None:
            raise OaFileError("سایت یافت نشد", 404)
        row = await self._row(site_id)
        created = row is None
        before = self._row_values(row)
        if row is None:
            row = OaAttachmentSettings(site_id=site_id, **clean)
            self.db.add(row)
        else:
            for k, v in clean.items():
                setattr(row, k, v)
        row.updated_by = user.id
        changes = {k: {"from": before.get(k), "to": v} for k, v in clean.items() if before.get(k) != v}
        if changes or created:
            self.audit("settings.attachments", user, entity="site", entity_id=site_id, site_id=site_id,
                       details=changes, ip=ip)
        await self.db.commit()
        return clean

    # ---------- آپلود ----------

    async def upload(
        self,
        *,
        site_id: int,
        filename: str,
        chunks: AsyncIterator[bytes],
        user: User,
        context: str = "letter",
        purpose: str = "attachment",
        ip: str | None = None,
        formats: list[str] | None = None,
    ) -> OaFile:
        """
        یک فایل را طبق تنظیمات سایت می‌پذیرد. رد (پسوند/حجم/ساختار) → OaFileError با پیام فارسی (ردیف rejected
        برای سابقه می‌ماند، محتوا ذخیره نمی‌شود). خروجی: ردیف OaFile با وضعیت clean، infected یا scan_pending.
        """
        if context not in ("letter", "action"):
            raise OaFileError("نوع پیوست نامعتبر است")
        settings = await self.site_settings(site_id)
        if formats is not None:  # مثلاً لوگوی قالب: فقط تصویر، مستقل از فرمت‌های پیوست سایت
            settings = {**settings, "allowed_formats": list(formats)}
        name = (filename or "").strip()[:255] or "file"
        try:
            fmt = rules.format_for_name(name, settings["allowed_formats"])
        except rules.FileRejected as e:
            self._record_rejected(site_id, name, user, str(e), purpose, ip)
            await self.db.commit()
            raise OaFileError(str(e)) from None

        max_mb = min(settings[f"{context}_max_file_mb"], await server_upload_limit.portal_max_file_mb(self.db))
        try:
            temp_key, size, sha = await self.storage.receive(chunks, max_mb * rules.MIB)
        except SizeLimitExceeded:
            msg = f"حجم فایل نمی‌تواند از {max_mb} مگابایت بیشتر باشد"
            self._record_rejected(site_id, name, user, msg, purpose, ip, fmt.code)
            await self.db.commit()
            raise OaFileError(msg, 413) from None

        row = OaFile(
            site_id=site_id, original_name=name, size=size, detected_format=fmt.code, content_type=fmt.content_type,
            sha256=sha, uploaded_by=user.id, purpose=purpose, status=rules.STATUS_UPLOADING, state="temp",
        )
        self.db.add(row)
        await self.db.flush()

        temp_path = str(self.storage.path_of(temp_key))
        try:
            await asyncio.to_thread(rules.check_content, temp_path, fmt, settings["allowed_formats"])
        except rules.FileRejected as e:
            self.storage.delete(temp_key)
            row.status, row.reject_reason = rules.STATUS_REJECTED, str(e)[:500]
            self.audit("file.rejected", user, entity="file", entity_id=row.id, site_id=site_id,
                       details={"name": name, "reason": str(e)}, ip=ip)
            await self.db.commit()
            raise OaFileError(str(e)) from None
        except Exception:
            self.storage.delete(temp_key)
            raise

        row.storage_key = self.storage.commit(temp_key)
        if await oa_clamav.scan_enabled(self.db):
            row.status = rules.STATUS_SCANNING
            await self.db.flush()
            await self._scan(row)
        else:
            # اسکن ویروس خاموش (تنظیم سراسری): بعد از بررسی نوع/ساختار «سالم (بدون اسکن ویروس)»؛ scanned_at خالی می‌ماند
            # تا با روشن شدن اسکن، Job آن را هم اسکن کند.
            row.status = rules.STATUS_CLEAN
        self.audit("file.upload", user, entity="file", entity_id=row.id, site_id=site_id,
                   details={"name": name, "size": size, "format": fmt.code, "status": row.status}, ip=ip)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    def _record_rejected(self, site_id, name, user, reason, purpose, ip, fmt_code=None) -> None:
        row = OaFile(
            site_id=site_id, original_name=name, size=0, detected_format=fmt_code, uploaded_by=user.id,
            purpose=purpose, status=rules.STATUS_REJECTED, state="temp", reject_reason=reason[:500],
        )
        self.db.add(row)
        self.audit("file.rejected", user, entity="file", site_id=site_id, details={"name": name, "reason": reason}, ip=ip)

    async def _scan(self, row: OaFile) -> None:
        """اسکن فایل ذخیره‌شده؛ وضعیت را clean / infected (+قرنطینه) / scan_pending می‌کند (بدون commit)."""
        row.scan_attempts = (row.scan_attempts or 0) + 1
        try:
            result = await asyncio.to_thread(oa_scanner.scan_file, str(self.storage.path_of(row.storage_key)))
        except oa_scanner.ScannerUnavailable as e:
            row.status, row.scan_result = rules.STATUS_SCAN_PENDING, str(e)[:255]
            logger.warning("اسکن فایل %s انجام نشد: %s", row.id, e)
            return
        row.scan_db_version = (result.db_version or "")[:128] or None
        row.scanned_at = datetime.now(timezone.utc)
        if result.clean:
            row.status, row.scan_result = rules.STATUS_CLEAN, None
        else:
            row.status, row.scan_result = rules.STATUS_INFECTED, result.signature
            row.storage_key = self.storage.quarantine(row.storage_key)
            logger.warning("فایل %s آلوده بود (%s) و قرنطینه شد", row.id, result.signature)

    async def retry_pending_scans(self, limit: int = 50) -> int:
        """
        Job: فایل‌های scan_pending دوباره اسکن می‌شوند؛ سپس فایل‌های «سالم بدون اسکن» (بارگذاری‌شده وقتی اسکن خاموش بود).
        اگر اسکن خاموش شده باشد، scan_pending ها «سالم (بدون اسکن ویروس)» می‌شوند. خروجی: تعداد فایل‌هایی که وضعیتشان مشخص شد.
        """
        if not await oa_clamav.scan_enabled(self.db):
            pending = (
                await self.db.execute(select(OaFile).where(OaFile.status == rules.STATUS_SCAN_PENDING).limit(500))
            ).scalars().all()
            for row in pending:
                row.status, row.scan_result = rules.STATUS_CLEAN, None
            await self.db.commit()
            return len(pending)
        done = await self._scan_batch(OaFile.status == rules.STATUS_SCAN_PENDING, limit)
        if done >= 0:
            unscanned = (OaFile.status == rules.STATUS_CLEAN) & OaFile.scanned_at.is_(None) & OaFile.storage_key.isnot(None)
            done += max(await self._scan_batch(unscanned, limit), 0)
        return max(done, 0)

    async def _scan_batch(self, condition, limit: int) -> int:
        """یک دسته فایل را اسکن می‌کند؛ اگر اسکنر در دسترس نباشد متوقف می‌شود و -1 برمی‌گرداند."""
        rows = (
            await self.db.execute(
                select(OaFile)
                .where(condition, OaFile.scan_attempts < SCAN_RETRY_MAX)
                .order_by(OaFile.id)
                .limit(limit)
            )
        ).scalars().all()
        done = 0
        for row in rows:
            was_clean = row.status == rules.STATUS_CLEAN  # «سالم بدون اسکن» که حالا اسکن می‌شود
            row.status = rules.STATUS_SCANNING
            await self._scan(row)
            unavailable = row.status == rules.STATUS_SCAN_PENDING
            if unavailable and was_clean:
                # اسکنر در دسترس نیست: فایلی که قبلاً قابل دانلود بود قفل نمی‌شود؛ دفعه‌ی بعد دوباره امتحان می‌شود
                row.status, row.scan_result = rules.STATUS_CLEAN, None
            elif not unavailable:
                done += 1
                self.audit("file.scanned", None, entity="file", entity_id=row.id, site_id=row.site_id,
                           details={"status": row.status})
            await self.db.commit()
            if unavailable:
                return done or -1  # اسکنر هنوز در دسترس نیست؛ بقیه دفعه‌ی بعد
        return done

    async def cleanup_temp(self) -> int:
        """
        Job: فایل‌های موقتِ بی‌پیوند قدیمی‌تر از OA_TEMP_RETENTION_HOURS (و ردیف‌هایشان) پاک می‌شوند. فقط state=temp؛
        فایل دائم هرگز حذف خودکار ندارد. (پیوند به نامه از فاز ۳الف؛ آن‌جا فایل permanent می‌شود.)
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=get_settings().OA_TEMP_RETENTION_HOURS)
        rows = (
            await self.db.execute(select(OaFile).where(OaFile.state == "temp", OaFile.created_at < cutoff).limit(500))
        ).scalars().all()
        for row in rows:
            try:
                self.storage.delete(row.storage_key)
            except OSError:
                logger.exception("حذف فایل موقت %s ناموفق بود", row.id)
                continue
            await self.db.delete(row)
        if rows:
            self.audit("file.cleanup", None, entity="file", details={"count": len(rows)})
        await self.db.commit()
        return len(rows)

    # ---------- خواندن و دانلود ----------

    async def get_own(self, file_id: int, user: User) -> OaFile:
        """فاز ۱: فقط بارگذارنده. (از فاز ۳الف دسترسی از can() نامه می‌آید.)"""
        row = await self.db.get(OaFile, file_id)
        if row is None or row.uploaded_by != user.id:
            raise OaFileError("فایل یافت نشد", 404)
        return row

    async def open_download(self, file_id: int, user: User, ip: str | None = None) -> tuple[OaFile, str]:
        row = await self.get_own(file_id, user)
        if not rules.can_download(row.status) or not row.storage_key:
            raise OaFileError(f"این فایل قابل دانلود نیست (وضعیت: {rules.STATUS_LABELS.get(row.status, row.status)})", 409)
        if not self.storage.exists(row.storage_key):
            raise OaFileError("فایل در محل نگهداری پیدا نشد", 410)
        fmt = rules.FORMAT_BY_CODE.get(row.detected_format or "")
        self.audit("file.download", user, entity="file", entity_id=row.id, site_id=row.site_id, ip=ip)
        await self.db.commit()
        return row, rules.safe_download_name(row.original_name, fmt)

    async def delete_own_temp(self, file_id: int, user: User, ip: str | None = None) -> None:
        row = await self.get_own(file_id, user)
        if row.state != "temp":
            raise OaFileError("فایل ثبت‌شده حذف نمی‌شود", 409)
        self.storage.delete(row.storage_key)
        self.audit("file.delete", user, entity="file", entity_id=row.id, site_id=row.site_id, ip=ip)
        await self.db.delete(row)
        await self.db.commit()

    async def my_recent(self, user: User, site_id: int | None, limit: int = 20) -> list[OaFile]:
        stmt = select(OaFile).where(OaFile.uploaded_by == user.id).order_by(OaFile.id.desc()).limit(limit)
        if site_id is not None:
            stmt = stmt.where(OaFile.site_id == site_id)
        return list((await self.db.execute(stmt)).scalars().all())

    # ---------- وضعیت ----------

    async def status(self) -> dict:
        """وضعیت اسکنر، بانک شناسایی، فضای دیسک و صف scan_pending برای پنل."""
        scanner: dict = {"available": False, "error": None, "engine": None, "db": None, "db_date": None,
                         "db_stale": None}
        try:
            info = oa_scanner.parse_version(await asyncio.to_thread(oa_scanner.version))
            scanner.update(available=True, engine=info["engine"], db=info["db"], db_date=info["db_date"])
            if info["db_date"]:
                scanner["db_stale"] = (datetime.now() - info["db_date"]).days > DB_STALE_DAYS
        except oa_scanner.ScannerUnavailable as e:
            scanner["error"] = str(e)
        clam_state = await asyncio.to_thread(oa_clamav.system_state)
        if scanner["available"] and not scanner["db_date"]:
            # VERSION غیرفعال یا ناخوانا: تاریخ بانک از زمان فایل daily.* (آخرین به‌روزرسانی)
            daily = [f for f in clam_state["db_files"] if f["name"].startswith("daily.")]
            if daily:
                scanner["db_date"] = datetime.fromtimestamp(daily[0]["mtime"])
                scanner["db_stale"] = (datetime.now() - scanner["db_date"]).days > DB_STALE_DAYS
        try:
            disk = self.storage.usage()
        except OSError as e:
            disk = {"error": str(e)}
        scan_on = await oa_clamav.scan_enabled(self.db)
        counts = dict(
            (await self.db.execute(select(OaFile.status, func.count()).group_by(OaFile.status))).all()
        )
        unscanned = (
            await self.db.execute(
                select(func.count()).where(OaFile.status == rules.STATUS_CLEAN, OaFile.scanned_at.is_(None))
            )
        ).scalar_one()
        return {
            "scan_enabled": scan_on,
            "unscanned_clean": unscanned,
            "clamav": clam_state,
            "clamav_job": await asyncio.to_thread(oa_clamav.read_log),
            "scanner": scanner,
            "disk": disk,
            "storage_dir": str(self.storage.root),
            "counts": counts,
            "db_stale_days": DB_STALE_DAYS,
        }


def file_out(row: OaFile) -> dict:
    return {
        "id": row.id,
        "site_id": row.site_id,
        "name": row.original_name,
        "size": row.size,
        "format": row.detected_format,
        "status": row.status,
        "status_label": (
            "سالم (بدون اسکن ویروس)" if row.status == rules.STATUS_CLEAN and row.scanned_at is None
            else rules.STATUS_LABELS.get(row.status, row.status)
        ),
        "virus_scanned": row.scanned_at is not None,
        "state": row.state,
        "reject_reason": row.reject_reason,
        "scan_result": row.scan_result if row.status == rules.STATUS_INFECTED else None,
        "scan_db_version": row.scan_db_version,
        "sha256": row.sha256,
        "created_at": row.created_at,
        "can_download": rules.can_download(row.status),
    }
