"""
ساخت و آماده‌سازی بازیابی مجموعه‌ی بکاپ نسخه‌ی ۴ (docs/backup.md؛ سند اتوماسیون بخش ۱۰).

ساخت (build_archive):
- سازگاری «آنلاین»: یک تراکنش REPEATABLE READ READ ONLY باز، pg_export_snapshot()؛ فهرست فایل‌های اتوماسیون از همان snapshot
  خوانده و pg_dump --snapshot اجرا می‌شود. پاک‌سازی فایل‌های موقت هم‌زمان با بکاپ اجرا نمی‌شود (همان Advisory Lock بکاپ).
- tar جریانی + gzip + (اگر کلید فعال است) رمزنگاری جریانی با age؛ هیچ مرحله‌ای کل آرشیو را در RAM نمی‌خواند.
- هش هر فایل هنگام افزودن محاسبه و با هش دیتابیس مقایسه می‌شود؛ فایل دائم ناموجود یا هش ناهم‌خوان = بکاپ ناموفق.
- manifest.json آخرین عضو است؛ نام فایل موقت تا پایان «.part» است (نیمه‌کاره هرگز با نام نهایی نمی‌ماند).

آماده‌سازی بازیابی (stage_archive): رمزگشایی جریانی، استخراج فقط عضوهای مجاز با سقف حجم/تعداد، تطبیق همه‌ی هش‌ها با
manifest و سازگاری Migration — قبل از هر تغییری در دیتابیس یا فایل‌ها.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core import backup_rules as rules

logger = logging.getLogger("faipco.backup")

BACKUP_DIR = Path("/var/lib/faipco/backups")
CHUNK = 1 << 20


class ArchiveError(RuntimeError):
    """خطای قابل نمایش (پیام فارسی)."""


def backup_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    return BACKUP_DIR


def list_local() -> list[dict]:
    """نسخه‌های محلی بکاپ در پوشه‌ی بکاپ‌ها (جدیدترین اول)."""
    out = []
    try:
        names = os.listdir(backup_dir())
    except OSError:
        return out
    for name in names:
        info = rules.parse_filename(name)
        if not info:
            continue
        try:
            st = os.stat(BACKUP_DIR / name)
        except OSError:
            continue
        out.append({"name": name, "size": st.st_size, "kind": info["kind"], "created_at": info["created_at"]})
    out.sort(key=lambda x: x["created_at"], reverse=True)
    return out


def prune_local(keep: int) -> list[str]:
    removed = []
    for name in rules.local_copies_to_delete([x["name"] for x in list_local()], keep):
        try:
            (BACKUP_DIR / name).unlink()
            removed.append(name)
        except OSError:
            logger.warning("حذف نسخه‌ی محلی بکاپ %s ناموفق بود", name)
    return removed


def local_path(name: str) -> Path:
    if not rules.parse_filename(name) or "/" in name:
        raise ArchiveError("نام فایل بکاپ نامعتبر است")
    path = backup_dir() / name
    if not path.is_file():
        raise ArchiveError("فایل بکاپ پیدا نشد")
    return path


class _HashingReader(io.RawIOBase):
    """خواندن فایل و محاسبه‌ی هم‌زمان SHA-256 (برای tarfile.addfile)."""

    def __init__(self, f):
        self._f = f
        self.digest = hashlib.sha256()
        self.size = 0

    def readable(self):
        return True

    def readinto(self, b):
        data = self._f.read(len(b))
        n = len(data)
        b[:n] = data
        self.digest.update(data)
        self.size += n
        return n


def _add_bytes(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = int(datetime.now(timezone.utc).timestamp())
    info.mode = 0o600
    tar.addfile(info, io.BytesIO(data))


def _add_file(tar: tarfile.TarFile, name: str, path: str, size: int) -> tuple[int, str]:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = int(os.path.getmtime(path))
    info.mode = 0o600
    with open(path, "rb") as f:
        reader = _HashingReader(f)
        tar.addfile(info, io.BufferedReader(reader, CHUNK))
    if reader.size != size:
        raise ArchiveError(f"حجم فایل هنگام بکاپ تغییر کرد: {name}")
    return reader.size, reader.digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _pg_dump_version(pg_dump: str) -> str | None:
    try:
        return subprocess.run([pg_dump, "--version"], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def write_archive(part: Path, public_key: str | None, dump_path: Path, rows, path_of, meta: dict) -> dict:
    """
    tar.gz جریانی (و اگر public_key داده شده، رمزنگاری جریانی با age -r) در part: database.dump، فایل‌های rows
    (هر ردیف: id، storage_key، sha256، size، status، state)، RESTORE.txt و در آخر manifest.json. path_of(key) مسیر فایل را
    می‌دهد. فایل دائم ناموجود یا هش ناهم‌خوان → ArchiveError؛ فایل موقت ناموجود و فایل آلوده کنار گذاشته و در manifest
    شمرده می‌شوند. خروجی: {"manifest", "manifest_sha256"}.
    """
    from app.services import backup_keys

    age_proc = None
    if public_key:
        age_proc = subprocess.Popen(
            [backup_keys.age_binary("age"), "-r", public_key, "-o", str(part)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        sink = age_proc.stdin
    else:
        sink = open(part, "wb")
    files, excluded = [], {"infected": 0, "missing_temp": 0}
    try:
        with tarfile.open(fileobj=sink, mode="w|gz", format=tarfile.PAX_FORMAT) as tar:
            dump_size, dump_sha = _add_file(tar, rules.DUMP_MEMBER, str(dump_path), dump_path.stat().st_size)
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
                size, sha = _add_file(tar, rules.file_member(r.storage_key), str(path), path.stat().st_size)
                if r.sha256 and sha != r.sha256:
                    raise ArchiveError(f"هش فایل شماره {r.id} با دیتابیس نمی‌خواند (فایل تغییر کرده یا خراب است)")
                files.append({"key": r.storage_key, "size": size, "sha256": sha})
            _add_bytes(tar, rules.GUIDE_MEMBER, rules.RESTORE_GUIDE.encode("utf-8"))
            manifest = rules.build_manifest(
                **meta, finished_at=datetime.now(timezone.utc), dump_sha256=dump_sha, dump_size=dump_size,
                files=files, excluded=excluded,
            )
            raw = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            _add_bytes(tar, rules.MANIFEST_MEMBER, raw)
    finally:
        sink.close()
        if age_proc is not None:
            err = age_proc.stderr.read().decode(errors="ignore") if age_proc.stderr else ""
            if age_proc.wait(timeout=600) != 0:
                raise ArchiveError(f"رمزنگاری با age ناموفق بود: {err[:300]}")
    return {"manifest": manifest, "manifest_sha256": hashlib.sha256(raw).hexdigest()}


async def build_archive(*, trigger: str, user_id: int | None = None) -> dict:
    """
    یک مجموعه‌ی بکاپ کامل در پوشه‌ی بکاپ‌ها می‌سازد. فراخواننده باید Advisory Lock بکاپ را گرفته باشد.
    خروجی: {"path", "filename", "set_id", "size", "manifest", "manifest_sha256", "key_id"}. خطا: ArchiveError.
    """
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal, engine
    from app.services import backup_keys
    from app.services.backup_service import _find_pg_binary, _split_db_url, _to_libpq_url
    from app.services.oa_storage import LocalStorage

    from sqlalchemy import text

    settings = get_settings()
    started = datetime.now(timezone.utc)
    set_id = uuid.uuid4().hex
    async with AsyncSessionLocal() as db:
        key = await backup_keys.active_key(db)
    if key is not None and not backup_keys.age_available():
        raise ArchiveError("کلید رمزنگاری فعال است ولی ابزار age روی سرور نصب نیست؛ پرتال را یک بار آپدیت کنید.")

    out_dir = backup_dir()
    work = out_dir / f".work-{set_id}"
    work.mkdir(mode=0o700)
    filename = rules.backup_filename(started, encrypted=key is not None)
    final = out_dir / filename
    part = out_dir / f".{filename}.part"
    storage = LocalStorage()
    try:
        libpq_url, _user, password = _split_db_url(_to_libpq_url(settings.DATABASE_URL))
        pg_dump = _find_pg_binary("pg_dump")
        env = {**os.environ, "PGPASSWORD": password} if password else dict(os.environ)
        dump_path = work / rules.DUMP_MEMBER

        # --- snapshot مشترک دیتابیس و فهرست فایل‌ها ---
        conn = await engine.connect()
        try:
            trans = await conn.begin()
            consistency = "snapshot"
            snapshot = None
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

            files_bytes_est = sum(int(r.size or 0) for r in rows)
            free = shutil.disk_usage(out_dir).free
            needed = int((db_size * 0.6 + files_bytes_est) * 1.3) + 100 * 1024 * 1024
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

        # --- tar جریانی (+ age) ---
        meta = {
            "set_id": set_id, "started_at": started, "app_version": getattr(settings, "APP_VERSION", None),
            "alembic_head": alembic_head, "pg_dump_version": _pg_dump_version(pg_dump),
            "key_id": key.key_id if key else None, "key_mode": key.mode if key else None,
            "consistency_method": consistency,
        }
        result = await asyncio.to_thread(
            write_archive, part, key.public_key if key else None, dump_path, rows, storage.path_of, meta
        )
        os.replace(part, final)
        os.chmod(final, 0o600)
        return {
            "path": final,
            "filename": filename,
            "set_id": set_id,
            "size": final.stat().st_size,
            "key_id": key.key_id if key else None,
            **result,
        }
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---------- آماده‌سازی بازیابی ----------


def _code_heads() -> set[str]:
    """شماره‌ی Migration های موجود در کد (برای رد بکاپی که از نسخه‌ی جدیدتر پرتال است)."""
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


def stage_archive(path: Path, staging: Path, identities: list[str]) -> dict:
    """
    فایل بکاپ v4 را (در صورت نیاز با کلیدهای خصوصی — ذخیره‌شده روی سرور و/یا ارائه‌شده) رمزگشایی و در staging استخراج می‌کند و همه‌چیز را با manifest تطبیق
    می‌دهد. خروجی: manifest. خطا: ArchiveError (هیچ تغییری در دیتابیس یا فایل‌های جاری داده نشده است).
    """
    from app.services import backup_keys

    info = rules.parse_filename(path.name)
    if not info or info["kind"] == "v3":
        raise ArchiveError("این تابع فقط قالب v4 را آماده می‌کند")
    encrypted = info["kind"] == "v4-encrypted"
    identities = [i.strip() for i in identities if i and i.strip()]
    if encrypted and not identities:
        raise ArchiveError("این بکاپ رمزنگاری شده است و کلید خصوصی آن لازم است (کلید بیرون از سرور را وارد کنید)")
    free = shutil.disk_usage(staging.parent).free
    if free < path.stat().st_size * 4:
        raise ArchiveError("فضای دیسک برای استخراج بکاپ کافی نیست (حدود ۴ برابر حجم فایل لازم است)")

    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, mode=0o700)

    def run(source) -> dict:
        extracted: dict[str, tuple[int, str]] = {}
        manifest_raw = None
        total = 0
        with tarfile.open(fileobj=source, mode="r|gz") as tar:
            for member in tar:
                name = rules.check_member_name(member.name)
                if not member.isfile():
                    raise ArchiveError(f"عضو غیرعادی در فایل بکاپ: {member.name}")
                if len(extracted) >= rules.MAX_RESTORE_MEMBERS:
                    raise ArchiveError("تعداد فایل‌های داخل بکاپ بیش از حد مجاز است")
                total += member.size
                if total > rules.MAX_RESTORE_BYTES:
                    raise ArchiveError("حجم استخراج‌شده‌ی بکاپ بیش از حد مجاز است")
                f = tar.extractfile(member)
                digest, size = hashlib.sha256(), 0
                if name == rules.MANIFEST_MEMBER:
                    manifest_raw = f.read(16 * 1024 * 1024)
                    digest.update(manifest_raw)
                    size = len(manifest_raw)
                else:
                    dst = staging / name
                    dst.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with open(dst, "xb") as out:
                        for block in iter(lambda: f.read(CHUNK), b""):
                            digest.update(block)
                            size += len(block)
                            out.write(block)
                if size != member.size:
                    raise ArchiveError(f"عضو ناقص در فایل بکاپ: {member.name}")
                extracted[name] = (size, digest.hexdigest())
        if manifest_raw is None:
            raise ArchiveError("manifest.json در فایل بکاپ نیست (فایل ناقص است)")
        manifest = rules.parse_manifest(manifest_raw)
        errors = rules.verify_extracted(manifest, extracted)
        if errors:
            raise ArchiveError("فایل بکاپ سالم نیست: " + "؛ ".join(errors[:5]))
        return manifest

    try:
        if encrypted:
            with backup_keys.identity_file("\n".join(identities)) as id_path:
                proc = subprocess.Popen(
                    [backup_keys.age_binary("age"), "-d", "-i", id_path, str(path)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                try:
                    manifest = run(proc.stdout)
                except (tarfile.TarError, EOFError, OSError) as e:
                    err = proc.stderr.read().decode(errors="ignore") if proc.stderr else ""
                    proc.kill()
                    if "no identity matched" in err or "incorrect" in err.lower():
                        raise ArchiveError("کلید خصوصی با این بکاپ نمی‌خواند") from None
                    raise ArchiveError(f"رمزگشایی یا خواندن بکاپ ناموفق بود: {err[:200] or e}") from None
                finally:
                    proc.stdout.close()
                if proc.wait(timeout=600) != 0:
                    err = proc.stderr.read().decode(errors="ignore") if proc.stderr else ""
                    raise ArchiveError(f"رمزگشایی بکاپ ناموفق بود: {err[:200]}")
        else:
            with open(path, "rb") as f:
                try:
                    manifest = run(f)
                except (tarfile.TarError, EOFError) as e:
                    raise ArchiveError(f"فایل بکاپ خراب است: {e}") from None
        head = str(manifest.get("alembic_head") or "")
        heads = _code_heads()
        if head and heads and head not in heads:
            raise ArchiveError(
                f"این بکاپ از نسخه‌ی جدیدتر پرتال است (Migration {head})؛ اول پرتال را به همان نسخه یا بالاتر آپدیت کنید"
            )
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
