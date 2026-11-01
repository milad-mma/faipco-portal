"""
قواعد خالص فایل ZIP بکاپ (docs/backup.md): نام فایل، نام عضوها، manifest و تطبیق هش.

ZIP بکاپ = database.dump + files/objects/... (فایل‌های آپلودی اتوماسیون) + manifest.json (حجم و SHA-256 هر عضو).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

FORMAT_V4 = "faipco-portal-backup-v4"

FILENAME_RE = re.compile(r"faipco-backup-(\d{8}-\d{6})\.zip")

DUMP_MEMBER = "database.dump"
MANIFEST_MEMBER = "manifest.json"
FILES_PREFIX = "files/"

MAX_RESTORE_MEMBERS = 2_000_000
MAX_RESTORE_BYTES = 200 * 1024**3  # سقف استخراج (۲۰۰ گیگابایت) — جلوگیری از archive bomb


class BackupRulesError(ValueError):
    """خطای قابل نمایش (پیام فارسی)."""


def parse_filename(name: str) -> dict | None:
    """{"created_at": datetime UTC} برای نام faipco-backup-YYYYMMDD-HHMMSS.zip، وگرنه None."""
    m = FILENAME_RE.fullmatch(name or "")
    if not m:
        return None
    try:
        return {"created_at": datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)}
    except ValueError:
        return None


def file_member(storage_key: str) -> str:
    """نام عضو ZIP برای یک فایل اتوماسیون؛ کلید باید نسبی و داخل objects/ باشد."""
    key = (storage_key or "").replace("\\", "/")
    if not key.startswith("objects/") or ".." in key.split("/") or key.startswith("/"):
        raise BackupRulesError(f"کلید فایل نامعتبر برای بکاپ: {storage_key}")
    return FILES_PREFIX + key


def check_member_name(name: str) -> str:
    """
    نام عضو آرشیو هنگام بازیابی: فقط database.dump، manifest.json یا files/objects/...؛ مسیر مطلق، «..»،
    بک‌اسلش یا نام دیگر → BackupRulesError. خروجی: همان نام نرمال.
    """
    n = name or ""
    if "\\" in n or n.startswith("/") or ".." in n.split("/") or "\x00" in n:
        raise BackupRulesError(f"مسیر غیرمجاز داخل فایل بکاپ: {name}")
    if n in (DUMP_MEMBER, MANIFEST_MEMBER):
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
    encrypted: bool,
    dump_sha256: str,
    dump_size: int,
    files: list[dict],
    excluded: dict,
    consistency_method: str,
) -> dict:
    """manifest.json — files: [{"key", "size", "sha256"}]؛ encrypted: آیا ZIP رمز دارد (خود رمز هرگز این‌جا نیست)."""
    return {
        "format": FORMAT_V4,
        "set_id": set_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "app_version": app_version,
        "alembic_head": alembic_head,
        "pg_dump_version": pg_dump_version,
        "encrypted": bool(encrypted),
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
    extra = set(extracted) - set(expected) - {DUMP_MEMBER, MANIFEST_MEMBER}
    if extra:
        errors.append(f"{len(extra)} عضو اضافه در فایل بکاپ هست")
    return errors
