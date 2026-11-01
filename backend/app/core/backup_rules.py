"""
قواعد خالص بکاپ نسخه‌ی ۴ (docs/office-automation-spec.md بخش ۱۰؛ docs/backup.md).

مجموعه‌ی بکاپ = یک فایل tar.gz (و اگر کلید فعال است رمزنگاری‌شده با age: «.tar.gz.age») شامل:
- database.dump  (pg_dump --format=custom با snapshot همان تراکنشی که فهرست فایل‌ها از آن خوانده شد)
- files/<storage_key>  همه‌ی فایل‌های اتوماسیون که در دیتابیس به آن‌ها ارجاع شده (به‌جز قرنطینه)
- RESTORE.txt  راهنمای بازیابی
- manifest.json  (آخرین عضو) شناسه، زمان، نسخه‌ها، key_id، هش dump و هر فایل، روش سازگاری، وضعیت تکمیل.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

FORMAT_V4 = "faipco-portal-backup-v4"
FORMAT_V3 = "faipco-portal-backup-v3-fullsnapshot"

# نام فایل: faipco-backup-YYYYMMDD-HHMMSS + پسوند (zip قدیمی، tar.gz بدون رمز، tar.gz.age رمزدار)
_EXTS = ("tar.gz.age", "tar.gz", "zip")
FILENAME_RE = re.compile(r"faipco-backup-(\d{8}-\d{6})\.(tar\.gz\.age|tar\.gz|zip)")

DUMP_MEMBER = "database.dump"
MANIFEST_MEMBER = "manifest.json"
GUIDE_MEMBER = "RESTORE.txt"
FILES_PREFIX = "files/"

MAX_RESTORE_MEMBERS = 2_000_000
MAX_RESTORE_BYTES = 200 * 1024**3  # سقف استخراج (۲۰۰ گیگابایت) — جلوگیری از archive bomb


class BackupRulesError(ValueError):
    """خطای قابل نمایش (پیام فارسی)."""


def backup_filename(now: datetime, encrypted: bool) -> str:
    return f"faipco-backup-{now.astimezone(timezone.utc):%Y%m%d-%H%M%S}.{'tar.gz.age' if encrypted else 'tar.gz'}"


def parse_filename(name: str) -> dict | None:
    """{"created_at": datetime UTC، "kind": "v4"|"v4-encrypted"|"v3"} یا None."""
    m = FILENAME_RE.fullmatch(name or "")
    if not m:
        return None
    try:
        created = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    kind = {"tar.gz.age": "v4-encrypted", "tar.gz": "v4", "zip": "v3"}[m.group(2)]
    return {"created_at": created, "kind": kind}


def local_copies_to_delete(names: list[str], keep: int) -> list[str]:
    """از نسخه‌های محلی، جدیدترین keep مورد می‌ماند؛ بقیه (فقط فایل‌های با الگوی بکاپ) حذف می‌شوند."""
    dated = [(n, p["created_at"]) for n in names if (p := parse_filename(n))]
    dated.sort(key=lambda x: x[1], reverse=True)
    return [n for n, _ in dated[max(keep, 0):]]


def file_member(storage_key: str) -> str:
    """نام عضو tar برای یک فایل اتوماسیون؛ کلید باید نسبی و داخل objects/ باشد."""
    key = (storage_key or "").replace("\\", "/")
    if not key.startswith("objects/") or ".." in key.split("/") or key.startswith("/"):
        raise BackupRulesError(f"کلید فایل نامعتبر برای بکاپ: {storage_key}")
    return FILES_PREFIX + key


def check_member_name(name: str) -> str:
    """
    نام عضو آرشیو هنگام بازیابی: فقط database.dump، manifest.json، RESTORE.txt یا files/objects/...؛ مسیر مطلق، «..»،
    بک‌اسلش یا نام دیگر → BackupRulesError. خروجی: همان نام نرمال.
    """
    n = name or ""
    if "\\" in n or n.startswith("/") or ".." in n.split("/") or "\x00" in n:
        raise BackupRulesError(f"مسیر غیرمجاز داخل فایل بکاپ: {name}")
    if n in (DUMP_MEMBER, MANIFEST_MEMBER, GUIDE_MEMBER):
        return n
    if n.startswith(FILES_PREFIX + "objects/") and not n.endswith("/"):
        return n
    raise BackupRulesError(f"عضو ناشناخته داخل فایل بکاپ: {name}")


def build_manifest(
    *,
    set_id: str,
    started_at: datetime,
    finished_at: datetime,
    app_version: str | None,
    alembic_head: str | None,
    pg_dump_version: str | None,
    key_id: str | None,
    key_mode: str | None,
    dump_sha256: str,
    dump_size: int,
    files: list[dict],
    excluded: dict,
    consistency_method: str,
) -> dict:
    """manifest.json — بدون هیچ کلید خام؛ files: [{"key", "size", "sha256"}]."""
    return {
        "format": FORMAT_V4,
        "set_id": set_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "app_version": app_version,
        "alembic_head": alembic_head,
        "pg_dump_version": pg_dump_version,
        "encryption": {"key_id": key_id, "mode": key_mode} if key_id else None,
        "database": {"member": DUMP_MEMBER, "size": dump_size, "sha256": dump_sha256},
        "files": {
            "count": len(files),
            "bytes": sum(f["size"] for f in files),
            "items": files,
        },
        "excluded": excluded,
        "consistency_method": consistency_method,
        "complete": True,
    }


def parse_manifest(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BackupRulesError("manifest.json فایل بکاپ خوانا نیست") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT_V4:
        raise BackupRulesError("قالب فایل بکاپ ناشناخته است")
    if not data.get("complete"):
        raise BackupRulesError("فایل بکاپ ناقص است (ساخت آن کامل نشده بود)")
    db = data.get("database") or {}
    if not isinstance(db.get("sha256"), str) or len(db["sha256"]) != 64:
        raise BackupRulesError("هش دیتابیس در manifest نیست")
    items = (data.get("files") or {}).get("items")
    if not isinstance(items, list):
        raise BackupRulesError("فهرست فایل‌ها در manifest نیست")
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get("sha256"), str) or not isinstance(it.get("size"), int):
            raise BackupRulesError("یک ردیف فایل در manifest نامعتبر است")
        file_member(it.get("key", ""))
    return data


def verify_extracted(manifest: dict, extracted: dict[str, tuple[int, str]]) -> list[str]:
    """
    مقایسه‌ی عضوهای استخراج‌شده {نام عضو: (حجم، sha256)} با manifest. خروجی: فهرست خطاها (خالی = سالم).
    هر فایل manifest باید با همان حجم و هش موجود باشد؛ عضو اضافه‌ای جز dump/manifest/راهنما مجاز نیست.
    """
    errors: list[str] = []
    db = manifest["database"]
    got = extracted.get(DUMP_MEMBER)
    if got is None:
        errors.append("database.dump در فایل بکاپ نیست")
    elif got[1] != db["sha256"] or got[0] != db.get("size", got[0]):
        errors.append("هش یا حجم database.dump با manifest نمی‌خواند")
    expected = {file_member(it["key"]): it for it in manifest["files"]["items"]}
    for member, it in expected.items():
        g = extracted.get(member)
        if g is None:
            errors.append(f"فایل {it['key']} در بکاپ نیست")
        elif g[0] != it["size"] or g[1] != it["sha256"]:
            errors.append(f"هش یا حجم فایل {it['key']} با manifest نمی‌خواند")
    extra = set(extracted) - set(expected) - {DUMP_MEMBER, MANIFEST_MEMBER, GUIDE_MEMBER}
    if extra:
        errors.append(f"{len(extra)} عضو اضافه در فایل بکاپ هست")
    return errors


# ---------- مجوزها (بخش ۱۰.۵) ----------

NEW_PERMISSIONS = {
    "backup.run_view": "پشتیبان‌گیری: اجرای بکاپ و مشاهده‌ی وضعیت و تاریخچه",
    "backup.destinations": "پشتیبان‌گیری: تنظیم زمان‌بندی، مقصدها و سیاست نگهداری",
    "backup.download": "پشتیبان‌گیری: دانلود دستی فایل بکاپ",
    "backup.key_manage": "پشتیبان‌گیری: ساخت/چرخش کلید رمزنگاری و انتخاب حالت کلید",
    "backup.restore": "پشتیبان‌گیری: بازیابی بکاپ روی همین سرور",
}
# هر نقش/مجوز مستقیمی که system.backup دارد این‌ها را خودکار می‌گیرد؛ key_manage در ابتدا فقط ادمین کل
MIGRATED_FROM_SYSTEM_BACKUP = ("backup.run_view", "backup.destinations", "backup.download", "backup.restore")


def has_backup_permission(codes: set[str], needed: str) -> bool:
    """system.backup (منسوخ) تا یک نسخه معادل همه‌ی مجوزهای جدید به‌جز key_manage است."""
    if needed in codes:
        return True
    return needed in MIGRATED_FROM_SYSTEM_BACKUP and "system.backup" in codes


RESTORE_GUIDE = """راهنمای بازیابی بکاپ پرتال (قالب v4)
====================================
۱. اگر نام فایل به .age ختم می‌شود رمزنگاری شده است: age -d -i key.txt -o backup.tar.gz faipco-backup-....tar.gz.age
۲. tar -xzf backup.tar.gz  ← database.dump، files/objects/...، manifest.json
۳. هش‌ها را با manifest.json مقایسه کنید (sha256sum).
۴. ساده‌ترین راه: فایل را در /var/lib/faipco/backups روی سرور بگذارید و از پنل «پشتیبان‌گیری ← بازیابی» استفاده کنید.
   بازیابی دستی: pg_restore --no-owner --no-privileges روی schema خالی public، کپی files/objects به OA_STORAGE_DIR/objects
   با مالک www-data، سپس alembic upgrade head.
"""
