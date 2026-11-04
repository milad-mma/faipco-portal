"""
فایل بکاپ پرتال: یک ZIP (مثل قبل) که حالا فایل‌های آپلودی اتوماسیون را هم دارد و در صورت تعیین «رمز فایل بکاپ» با
AES-256 (استاندارد WinZip-AES، قابل باز شدن با 7-Zip/WinRAR) رمزگذاری می‌شود — docs/backup.md.

محتوای ZIP:
- database.dump  (pg_dump --format=custom با snapshot همان تراکنشی که فهرست فایل‌ها از آن خوانده شد)
- files/objects/...  فایل‌های اتوماسیون که در دیتابیس به آن‌ها ارجاع شده (به‌جز قرنطینه)
- manifest.json  (آخرین عضو) حجم و SHA-256 dump و هر فایل
بکاپ‌های قدیمی (فقط database.dump و manifest قدیمی) هم بازیابی می‌شوند.

ساخت روی دیسک انجام می‌شود (نه در RAM) و فایل‌ها تکه‌تکه کپی و هش می‌شوند.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.core import backup_rules as rules

logger = logging.getLogger("faipco.backup")

BACKUP_DIR = Path("/var/lib/faipco/backups")
CHUNK = 1 << 20


class ArchiveError(RuntimeError):
    """خطای قابل نمایش (پیام فارسی)."""


class PasswordRequired(ArchiveError):
    pass


def backup_dir() -> Path:
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    except PermissionError:
        # سرویس (www-data) اجازه‌ی ساخت /var/lib/faipco را ندارد: install.sh (یا StateDirectory سرویس) آن را می‌سازد
        raise ArchiveError(
            f"پوشه‌ی {BACKUP_DIR} وجود ندارد و سرویس اجازه‌ی ساخت آن را ندارد؛ یک بار install.sh را اجرا کنید "
            "(یا آپدیت از پنل) تا ساخته شود."
        ) from None
    return BACKUP_DIR


def _zip_module(password: str | None):
    """zipfile استاندارد، یا pyzipper برای ZIP رمزدار (AES)."""
    if not password:
        return zipfile
    try:
        import pyzipper
    except ImportError:
        raise ArchiveError("کتابخانه‌ی pyzipper نصب نیست؛ پرتال را یک بار آپدیت کنید تا فایل بکاپ رمزدار ساخته/باز شود.") from None
    return pyzipper


def _open_for_write(path: Path, password: str | None):
    mod = _zip_module(password)
    if password:
        zf = mod.AESZipFile(path, "w", compression=mod.ZIP_STORED, encryption=mod.WZ_AES)
        zf.setpassword(password.encode("utf-8"))
        zf.setencryption(mod.WZ_AES, nbits=256)
        return zf
    return zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED, allowZip64=True)


def _copy_into(zf, arcname: str, src: Path) -> tuple[int, str]:
    """کپی تکه‌تکه‌ی فایل داخل ZIP همراه با محاسبه‌ی SHA-256 (بدون خواندن کامل در RAM)."""
    digest, size = hashlib.sha256(), 0
    with open(src, "rb") as f, zf.open(arcname, "w", force_zip64=True) as out:
        for block in iter(lambda: f.read(CHUNK), b""):
            digest.update(block)
            size += len(block)
            out.write(block)
    return size, digest.hexdigest()


def _pg_dump_version(pg_dump: str) -> str | None:
    try:
        return subprocess.run([pg_dump, "--version"], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def write_zip(out: Path, password: str | None, dump_path: Path, rows, path_of, meta: dict) -> dict:
    """
    ZIP بکاپ را در out می‌نویسد: database.dump، فایل‌های rows (هر ردیف: id، storage_key، sha256، status، state) و در آخر
    manifest.json. path_of(key) مسیر فایل را می‌دهد. فایل دائم ناموجود یا هش ناهم‌خوان → ArchiveError؛ فایل آلوده و فایل
    موقتِ ناموجود کنار گذاشته و در manifest شمرده می‌شوند. خروجی: manifest.
    """
    files, excluded = [], {"infected": 0, "missing_temp": 0}
    with _open_for_write(out, password) as zf:
        dump_size, dump_sha = _copy_into(zf, rules.DUMP_MEMBER, dump_path)
        for r in rows:
            if r.status == "infected" or str(r.storage_key).startswith("quarantine/"):
                excluded["infected"] += 1
                continue
            path = path_of(r.storage_key)
            if not path.is_file():
                if r.state == "temp":
                    excluded["missing_temp"] += 1
                    continue
                raise ArchiveError(f"فایل ثبت‌شده‌ی شماره {r.id} در محل نگهداری نیست؛ بکاپ ناقص ساخته نمی‌شود")
            size, sha = _copy_into(zf, rules.file_member(r.storage_key), path)
            if r.sha256 and sha != r.sha256:
                raise ArchiveError(f"هش فایل شماره {r.id} با دیتابیس نمی‌خواند (فایل تغییر کرده یا خراب است)")
            files.append({"key": r.storage_key, "size": size, "sha256": sha})
        manifest = rules.build_manifest(
            **meta, finished_at=datetime.now(timezone.utc), dump_sha256=dump_sha, dump_size=dump_size,
            files=files, excluded=excluded,
        )
        zf.writestr(rules.MANIFEST_MEMBER, json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


async def build_archive(*, password: str | None = None) -> dict:
    """
    یک ZIP بکاپ کامل در پوشه‌ی بکاپ‌ها می‌سازد (فراخواننده Advisory Lock بکاپ را گرفته است).
    خروجی: {"path", "filename", "size", "manifest"}. خطا: ArchiveError.
    """
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.db.session import engine
    from app.services.backup_service import _find_pg_binary, _split_db_url, _to_libpq_url
    from app.services.oa_storage import LocalStorage

    _zip_module(password)  # اگر رمز هست و pyzipper نیست، همین اول خطا
    settings = get_settings()
    started = datetime.now(timezone.utc)
    set_id = uuid.uuid4().hex
    out_dir = backup_dir()
    work = out_dir / f".work-{set_id}"
    work.mkdir(mode=0o700)
    filename = f"faipco-backup-{started:%Y%m%d-%H%M%S}.zip"
    final = out_dir / filename
    part = out_dir / f".{filename}.part"
    storage = LocalStorage()
    try:
        libpq_url, _user, db_password = _split_db_url(_to_libpq_url(settings.DATABASE_URL))
        pg_dump = _find_pg_binary("pg_dump")
        env = {**os.environ, "PGPASSWORD": db_password} if db_password else dict(os.environ)
        dump_path = work / rules.DUMP_MEMBER

        # snapshot مشترک: فهرست فایل‌ها و pg_dump از یک لحظه‌ی دیتابیس
        conn = await engine.connect()
        trans = await conn.begin()
        try:
            consistency, snapshot = "snapshot", None
            try:
                await conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                snapshot = (await conn.execute(text("SELECT pg_export_snapshot()"))).scalar_one()
            except Exception as e:  # noqa: BLE001
                logger.warning("pg_export_snapshot ناموفق بود؛ بکاپ بدون snapshot مشترک: %s", e)
                consistency = "none"
                await trans.rollback()
                trans = await conn.begin()
            try:
                rows = (await conn.execute(text(
                    "SELECT id, storage_key, sha256, size, status, state FROM oa_files WHERE storage_key IS NOT NULL"
                ))).all()
            except Exception:  # noqa: BLE001 - پیش از Migration 131 جدول نیست
                rows = []
            try:
                alembic_head = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            except Exception:  # noqa: BLE001
                alembic_head = None
            try:
                db_size = (await conn.execute(text("SELECT pg_database_size(current_database())"))).scalar() or 0
            except Exception:  # noqa: BLE001
                db_size = 0
            free = shutil.disk_usage(out_dir).free
            needed = int((db_size * 0.6 + sum(int(r.size or 0) for r in rows)) * 1.3) + 100 * 1024 * 1024
            if free < needed:
                raise ArchiveError(
                    f"فضای دیسک برای بکاپ کافی نیست (لازم حدود {needed // 2**20} مگابایت، آزاد {free // 2**20} مگابایت)"
                )
            args = [pg_dump, "--format=custom", "--no-owner", "--no-privileges", f"--file={dump_path}"]
            if snapshot:
                args.append(f"--snapshot={snapshot}")
            proc = await asyncio.create_subprocess_exec(
                *args, libpq_url, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise ArchiveError(f"pg_dump ناموفق بود: {stderr.decode(errors='ignore')[:600]}")
        finally:
            try:
                await trans.rollback()
            except Exception:  # noqa: BLE001
                pass
            await conn.close()

        meta = {
            "set_id": set_id, "started_at": started, "app_version": getattr(settings, "APP_VERSION", None),
            "alembic_head": alembic_head, "pg_dump_version": _pg_dump_version(pg_dump),
            "encrypted": bool(password), "consistency_method": consistency,
        }
        manifest = await asyncio.to_thread(write_zip, part, password, dump_path, rows, storage.path_of, meta)
        os.replace(part, final)
        os.chmod(final, 0o600)
        return {"path": final, "filename": filename, "size": final.stat().st_size, "manifest": manifest}
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)


def remove_old_local(keep_names: set[str]) -> None:
    """فایل‌های بکاپ قدیمی در پوشه‌ی بکاپ‌ها (به‌جز keep_names) پاک می‌شوند؛ نسخه‌ی محلی فقط موقت است."""
    try:
        for name in os.listdir(backup_dir()):
            if name not in keep_names and rules.parse_filename(name):
                (BACKUP_DIR / name).unlink(missing_ok=True)
    except OSError:
        logger.warning("پاک‌سازی فایل‌های موقت بکاپ ناموفق بود", exc_info=True)


# ---------- آماده‌سازی بازیابی ----------


def _code_heads() -> set[str]:
    versions = Path(__file__).resolve().parents[3] / "database" / "migrations" / "versions"
    heads = set()
    try:
        for p in versions.glob("*.py"):
            m = re.match(r"(\d+)_", p.name)
            if m:
                heads.add(m.group(1))
    except OSError:
        pass
    return heads


def is_encrypted(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as zf:
            return any(info.flag_bits & 0x1 for info in zf.infolist())
    except zipfile.BadZipFile:
        raise ArchiveError("فایل بکاپ معتبر نیست (فرمت Zip قابل خواندن نیست).") from None


def stage_zip(path: Path, staging: Path, password: str | None) -> dict:
    """
    ZIP بکاپ را (در صورت رمزدار بودن با رمز) در staging استخراج و بررسی می‌کند — قبل از هر تغییری در دیتابیس یا فایل‌ها.
    خروجی: {"dump": مسیر database.dump، "files_dir": مسیر files/objects یا None، "file_count": int، "legacy": bool}.
    خطا: PasswordRequired، ArchiveError.
    """
    encrypted = is_encrypted(path)
    if encrypted and not password:
        raise PasswordRequired("این فایل بکاپ رمز دارد؛ رمز فایل بکاپ را وارد کنید.")
    free = shutil.disk_usage(staging.parent).free
    if free < path.stat().st_size * 2 + 200 * 1024 * 1024:
        raise ArchiveError("فضای دیسک برای استخراج بکاپ کافی نیست (حدود ۲ برابر حجم فایل لازم است).")
    if staging.is_symlink():
        staging.unlink()
    elif staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, mode=0o700)
    mod = _zip_module(password if encrypted else None)
    try:
        zf = mod.AESZipFile(path) if encrypted else zipfile.ZipFile(path)
        with zf:
            if encrypted:
                zf.setpassword(password.encode("utf-8"))
            infos = zf.infolist()
            if len(infos) > rules.MAX_RESTORE_MEMBERS:
                raise ArchiveError("تعداد فایل‌های داخل بکاپ بیش از حد مجاز است")
            if sum(i.file_size for i in infos) > rules.MAX_RESTORE_BYTES:
                raise ArchiveError("حجم استخراج‌شده‌ی بکاپ بیش از حد مجاز است")
            names = {i.filename for i in infos}
            for name in names:
                if not name.endswith("/"):
                    rules.check_member_name(name)
            if rules.DUMP_MEMBER not in names:
                raise ArchiveError("فایل بکاپ نامعتبر است — database.dump داخلش نیست.")
            manifest = None
            if rules.MANIFEST_MEMBER in names:
                raw = zf.read(rules.MANIFEST_MEMBER)
                try:
                    data = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise ArchiveError("manifest.json فایل بکاپ خوانا نیست") from None
                if isinstance(data, dict) and data.get("format") == rules.FORMAT_V4:
                    manifest = rules.parse_manifest(raw)
            extracted: dict[str, tuple[int, str]] = {}
            for info in infos:
                name = info.filename
                if name.endswith("/") or name == rules.MANIFEST_MEMBER:
                    continue
                if name.startswith(rules.FILES_PREFIX) and manifest is None:
                    continue  # بکاپ قدیمی: فقط دیتابیس
                dst = staging / name
                dst.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                digest, size = hashlib.sha256(), 0
                with zf.open(info) as src, open(dst, "xb") as out:
                    for block in iter(lambda: src.read(CHUNK), b""):
                        digest.update(block)
                        size += len(block)
                        out.write(block)
                extracted[name] = (size, digest.hexdigest())
        if manifest is not None:
            errors = rules.verify_extracted(manifest, {**extracted, rules.MANIFEST_MEMBER: (0, "")})
            if errors:
                raise ArchiveError("فایل بکاپ سالم نیست: " + "؛ ".join(errors[:5]))
            head = str(manifest.get("alembic_head") or "")
            heads = _code_heads()
            if head and heads and head not in heads:
                raise ArchiveError(
                    f"این بکاپ از نسخه‌ی جدیدتر پرتال است (Migration {head})؛ اول پرتال را به همان نسخه یا بالاتر آپدیت کنید"
                )
        files_dir = staging / "files" / "objects"
        return {
            "dump": staging / rules.DUMP_MEMBER,
            "files_dir": files_dir if manifest is not None and files_dir.is_dir() else None,
            "file_count": manifest["files"]["count"] if manifest else 0,
            "legacy": manifest is None,
        }
    except RuntimeError as e:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(e, ArchiveError):
            raise
        if "password" in str(e).lower() or "Bad password" in str(e):
            raise ArchiveError("رمز فایل بکاپ اشتباه است.") from None
        raise ArchiveError(f"خواندن فایل بکاپ ناموفق بود: {e}") from None
    except (zipfile.BadZipFile, OSError, ValueError) as e:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(e, ArchiveError):
            raise
        raise ArchiveError(f"فایل بکاپ خراب است: {e}") from None
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
