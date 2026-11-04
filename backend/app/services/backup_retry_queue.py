"""
صف تلاش دوباره برای ارسال‌های ناموفق بکاپ (docs/backup.md بخش «صف تلاش دوباره»).

وقتی ارسال یک بکاپ به یک یا چند مقصد شکست می‌خورد، همان فایل ZIP در /var/lib/faipco/backups/pending می‌ماند و کنارش
یک فایل JSON با مقصدهای باقی‌مانده، تعداد تلاش، زمان تلاش بعدی و آخرین خطا نوشته می‌شود. Job زمان‌بندی (هر ۵ دقیقه،
زیر قفل بکاپ) مقصدهای سررسیده را دوباره امتحان می‌کند:
- موفق → آن مقصد از صف خارج می‌شود (و از ورودی‌های قدیمی‌تر هم، چون بکاپ جدیدتر رسیده است)؛
- ناموفق → تلاش بعدی با فاصله‌ی بیشتر (core/backup_dest_rules.RETRY_DELAYS_MIN)؛ بعد از سقف تلاش کنار گذاشته می‌شود؛
- ورودی بدون مقصد باقی‌مانده با فایلش پاک می‌شود. حداکثر MAX_QUEUED_ARCHIVES فایل روی دیسک می‌ماند.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core import backup_dest_rules as R

logger = logging.getLogger("faipco.backup_retry")


def pending_dir() -> Path:
    from app.services.backup_archive import backup_dir

    d = backup_dir() / "pending"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def _meta_path(filename: str) -> Path:
    return pending_dir() / f"{filename}.json"


def _read(meta: Path) -> dict | None:
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(entry: dict) -> None:
    meta = _meta_path(entry["filename"])
    tmp = meta.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, meta)


def _remove(filename: str) -> None:
    d = pending_dir()
    (d / filename).unlink(missing_ok=True)
    (d / f"{filename}.json").unlink(missing_ok=True)


def list_entries() -> list[dict]:
    """ورودی‌های صف، جدیدترین اول. هر ورودی: {filename, created_at, sha256, size, kinds: {kind: {attempts, next_at, last_error}}, given_up: {kind: error}}"""
    out = []
    from app.services.backup_archive import BACKUP_DIR

    # فقط خواندن: اگر پوشه هنوز ساخته نشده (هیچ بکاپی در صف نیست) چیزی نمی‌سازد و خطا نمی‌دهد
    if not (BACKUP_DIR / "pending").is_dir():
        return out
    for meta in pending_dir().glob("*.json"):
        entry = _read(meta)
        if entry and R.parse_filename_ok(entry.get("filename", "")):
            if not (pending_dir() / entry["filename"]).exists():
                meta.unlink(missing_ok=True)  # فایل ZIP نیست → ورودی بی‌فایده
                continue
            out.append(entry)
    out.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return out


def enqueue(local_path: Path, filename: str, sha256: str, created_at: datetime, failures: dict[str, str]) -> None:
    """
    فایل ZIP را به صف منتقل می‌کند (همان دیسک → os.replace) و مقصدهای ناموفق را با زمان تلاش بعدی ثبت می‌کند.
    failures: {kind: پیام خطا}. اگر صف از سقف بیشتر شود قدیمی‌ترین ورودی کنار می‌رود.
    """
    if not failures:
        return
    target = pending_dir() / filename
    os.replace(local_path, target)
    now = datetime.now(timezone.utc)
    entry = {
        "filename": filename,
        "created_at": created_at.isoformat(),
        "sha256": sha256,
        "size": target.stat().st_size,
        "kinds": {
            k: {"attempts": 1, "next_at": R.next_retry_at(1, now).isoformat(), "last_error": msg[:500]}
            for k, msg in failures.items()
        },
        "given_up": {},
    }
    _write(entry)
    for name in R.entries_to_drop(list_entries()):
        logger.warning("صف تلاش دوباره‌ی بکاپ پر است؛ فایل قدیمی %s کنار گذاشته شد", name)
        _remove(name)


def note_success(kind: str, created_at: datetime) -> None:
    """یک بکاپ جدیدتر به kind رسید → همان مقصد از ورودی‌های قدیمی‌تر صف حذف می‌شود (دیگر لازم نیست)."""
    ts = created_at.isoformat()
    for entry in list_entries():
        if kind in entry["kinds"] and R.superseded_kinds(entry["created_at"], {kind: ts}):
            entry["kinds"].pop(kind)
            _save_or_remove(entry)


def _save_or_remove(entry: dict) -> None:
    if entry["kinds"]:
        _write(entry)
    else:
        _remove(entry["filename"])


def discard(filename: str) -> bool:
    """حذف دستی یک ورودی از صف (دکمه‌ی «حذف از صف»). خروجی: آیا وجود داشت."""
    if not R.parse_filename_ok(filename) or not _meta_path(filename).exists():
        return False
    _remove(filename)
    return True


async def retry_due(db, *, force: bool = False) -> list[str]:
    """
    مقصدهای سررسیده‌ی صف را دوباره امتحان می‌کند (force=True: همه، بدون توجه به زمان). فراخواننده قفل بکاپ را دارد.
    خروجی: خلاصه‌ی نتیجه‌ها برای لاگ/نمایش.
    """
    from app.services.backup_settings_service import BackupSettingsService, deliver_to

    settings = await BackupSettingsService(db).get_settings()
    now = datetime.now(timezone.utc)
    report: list[str] = []
    had_failure = False
    for entry in sorted(list_entries(), key=lambda e: e["created_at"]):  # قدیمی‌ترین اول
        path = pending_dir() / entry["filename"]
        for kind in list(entry["kinds"]):
            state = entry["kinds"][kind]
            if not force and datetime.fromisoformat(state["next_at"]) > now:
                continue
            try:
                msg = await deliver_to(db, settings, kind, path, entry["filename"], entry["sha256"])
            except Exception as e:  # noqa: BLE001 — هر خطا در صف ثبت شود
                had_failure = True
                state["attempts"] += 1
                state["last_error"] = str(e)[:500]
                nxt = R.next_retry_at(state["attempts"], now)
                if nxt is None:
                    entry["given_up"][kind] = state["last_error"]
                    entry["kinds"].pop(kind)
                    report.append(f"{R.LABELS[kind]}: بعد از {state['attempts'] - 1} تلاش کنار گذاشته شد — {state['last_error']}")
                else:
                    state["next_at"] = nxt.isoformat()
                    report.append(f"{R.LABELS[kind]}: باز هم ناموفق — {state['last_error']}")
                continue
            entry["kinds"].pop(kind)
            report.append(f"{R.LABELS[kind]}: با تلاش دوباره رسید ({entry['filename']}) — {msg}")
            note_success(kind, datetime.fromisoformat(entry["created_at"]))
        _save_or_remove(entry)
    for line in report:
        logger.info("صف تلاش دوباره‌ی بکاپ: %s", line)
    if report:
        # فقط وضعیت و پیام؛ last_run_at دست نمی‌خورد چون زمان‌بندی بکاپ بعدی بر اساس آن است
        remaining = any(e["kinds"] for e in list_entries())
        settings.last_run_success = not had_failure and not remaining
        settings.last_run_message = ("تلاش دوباره — " + " | ".join(report))[:2000]
        await db.commit()
    return report
