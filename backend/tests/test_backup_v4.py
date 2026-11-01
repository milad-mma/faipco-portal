"""تست بکاپ نسخه‌ی ۴: قواعد، و ساخت/رمزنگاری/استخراج/تطبیق هش واقعی با age (بدون دیتابیس)."""

import hashlib
import json
import os
import zipfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.core import backup_rules as r


def _raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc as e:
        return str(e)
    raise AssertionError(f"expected {exc.__name__}")


def test_filenames_and_local_prune():
    t = datetime(2026, 11, 1, 10, 20, 30, tzinfo=timezone.utc)
    assert r.backup_filename(t, True) == "faipco-backup-20261101-102030.tar.gz.age"
    assert r.parse_filename("faipco-backup-20261101-102030.tar.gz")["kind"] == "v4"
    assert r.parse_filename("faipco-backup-20261101-102030.zip")["kind"] == "v3"
    assert r.parse_filename("faipco-backup-20261101-102030.tar.gz.age")["kind"] == "v4-encrypted"
    assert r.parse_filename("evil.tar.gz") is None and r.parse_filename("faipco-backup-20261399-000000.zip") is None
    names = ["faipco-backup-20261101-000000.tar.gz", "faipco-backup-20261102-000000.tar.gz.age",
             "faipco-backup-20261031-000000.zip", "other.txt"]
    assert r.local_copies_to_delete(names, 2) == ["faipco-backup-20261031-000000.zip"]


def test_member_names():
    assert r.file_member("objects/2026/11/abc") == "files/objects/2026/11/abc"
    _raises(r.BackupRulesError, r.file_member, "../etc/passwd")
    _raises(r.BackupRulesError, r.file_member, "quarantine/x")
    for bad in ("/etc/passwd", "files/../x", "files/objects/../../x", "other.txt", "files\\objects\\a", "files/tmp/a"):
        _raises(r.BackupRulesError, r.check_member_name, bad)
    assert r.check_member_name("database.dump") == "database.dump"


def test_manifest_and_verify():
    files = [{"key": "objects/2026/11/a", "size": 3, "sha256": "a" * 64}]
    m = r.build_manifest(
        set_id="s", started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc), app_version="v",
        alembic_head="132", pg_dump_version="pg", key_id=None, key_mode=None, dump_sha256="d" * 64, dump_size=10,
        files=files, excluded={}, consistency_method="snapshot",
    )
    parsed = r.parse_manifest(json.dumps(m).encode())
    ok = {"database.dump": (10, "d" * 64), "files/objects/2026/11/a": (3, "a" * 64)}
    assert r.verify_extracted(parsed, ok) == []
    assert r.verify_extracted(parsed, {**ok, "files/objects/2026/11/a": (3, "b" * 64)})
    assert r.verify_extracted(parsed, {"database.dump": (10, "d" * 64)})
    assert r.verify_extracted(parsed, {**ok, "files/objects/x": (1, "c" * 64)})
    _raises(r.BackupRulesError, r.parse_manifest, json.dumps({**m, "complete": False}).encode())
    _raises(r.BackupRulesError, r.parse_manifest, b"not json")
    _raises(r.BackupRulesError, r.parse_manifest, json.dumps({**m, "format": "x"}).encode())


def test_permissions_migration_rule():
    assert r.has_backup_permission({"system.backup"}, "backup.restore")
    assert not r.has_backup_permission({"system.backup"}, "backup.key_manage")
    assert r.has_backup_permission({"backup.key_manage"}, "backup.key_manage")
    assert not r.has_backup_permission(set(), "backup.run_view")


# ---------- ZIP بکاپ: ساخت، استخراج و تطبیق هش (بدون دیتابیس) ----------


def _setup(tmp: Path):
    root = tmp / "oa"
    rows = []
    for i, data in enumerate([b"hello", os.urandom(300_000), b""]):
        key = f"objects/2026/11/f{i}"
        p = root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        rows.append(SimpleNamespace(id=i + 1, storage_key=key, sha256=hashlib.sha256(data).hexdigest(), size=len(data),
                                    status="clean", state="permanent"))
    rows.append(SimpleNamespace(id=9, storage_key="quarantine/x", sha256=None, size=1, status="infected", state="temp"))
    rows.append(SimpleNamespace(id=10, storage_key="objects/2026/11/gone", sha256=None, size=1, status="clean",
                                state="temp"))
    dump = tmp / "database.dump"
    dump.write_bytes(os.urandom(200_000))
    meta = {"set_id": "s1", "started_at": datetime.now(timezone.utc), "app_version": "t", "alembic_head": "133",
            "pg_dump_version": "pg", "key_id": None, "key_mode": None, "consistency_method": "snapshot"}
    return root, rows, dump, meta


def test_zip_roundtrip_and_integrity():
    from app.services import backup_archive as A

    tmp = Path(tempfile.mkdtemp())
    root, rows, dump, meta = _setup(tmp)
    out = tmp / "faipco-backup-20261101-101010.zip"
    m = A.write_zip(out, None, dump, rows, lambda k: root / k, meta)
    assert m["files"]["count"] == 3 and m["excluded"] == {"infected": 1, "missing_temp": 1}
    assert not A.is_encrypted(out)
    with zipfile.ZipFile(out) as zf:  # ZIP معمولی، قابل باز شدن با هر ابزاری
        assert zf.namelist()[0] == "database.dump" and zf.namelist()[-1] == "manifest.json"
    res = A.stage_zip(out, tmp / "st", None)
    assert not res["legacy"] and res["file_count"] == 3
    assert res["dump"].read_bytes() == dump.read_bytes()
    for row in rows[:3]:
        assert (res["files_dir"] / row.storage_key.split("/", 1)[1]).read_bytes() == (root / row.storage_key).read_bytes()

    # فایل دائم ناموجود یا هش ناهم‌خوان → ساخت ناموفق
    (root / rows[0].storage_key).unlink()
    _raises(A.ArchiveError, A.write_zip, tmp / "x.zip", None, dump, rows, lambda k: root / k, meta)
    (root / rows[0].storage_key).write_bytes(b"changed")
    _raises(A.ArchiveError, A.write_zip, tmp / "y.zip", None, dump, rows, lambda k: root / k, meta)

    # عضو دست‌کاری‌شده → «سالم نیست» و هیچ‌چیز در staging نمی‌ماند
    forged = tmp / "forged.zip"
    with zipfile.ZipFile(out) as src, zipfile.ZipFile(forged, "w") as dst:
        for info in src.infolist():
            dst.writestr(info.filename, b"forged" if info.filename == "database.dump" else src.read(info.filename))
    assert "سالم نیست" in _raises(A.ArchiveError, A.stage_zip, forged, tmp / "f", None)
    assert not (tmp / "f").exists()

    # مسیر خطرناک → رد
    evil = tmp / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("database.dump", b"x")
        zf.writestr("../../etc/x", b"x")
    _raises(A.ArchiveError, A.stage_zip, evil, tmp / "e", None)
    assert not (tmp / "e").exists()

    # بکاپ قدیمی (فقط database.dump + manifest قدیمی) → فقط دیتابیس
    legacy = tmp / "legacy.zip"
    with zipfile.ZipFile(legacy, "w") as zf:
        zf.writestr("database.dump", b"old-dump")
        zf.writestr("manifest.json", json.dumps({"format": "faipco-portal-backup-v3-fullsnapshot"}))
    res = A.stage_zip(legacy, tmp / "lg", None)
    assert res["legacy"] and res["files_dir"] is None and res["dump"].read_bytes() == b"old-dump"
    _raises(A.ArchiveError, A.stage_zip, tmp / "database.dump", tmp / "bad", None)  # فایل غیر ZIP


def test_zip_password_roundtrip():
    try:
        import pyzipper  # noqa: F401
    except ImportError:
        return  # روی سرور با requirements نصب است
    from app.services import backup_archive as A

    tmp = Path(tempfile.mkdtemp())
    root, rows, dump, meta = _setup(tmp)
    out = tmp / "faipco-backup-20261101-101010.zip"
    A.write_zip(out, "a-strong-pass", dump, rows, lambda k: root / k, meta)
    assert A.is_encrypted(out)
    assert "رمز" in _raises(A.PasswordRequired, A.stage_zip, out, tmp / "s1", None)
    assert "اشتباه" in _raises(A.ArchiveError, A.stage_zip, out, tmp / "s2", "wrong-pass")
    res = A.stage_zip(out, tmp / "s3", "a-strong-pass")
    assert res["file_count"] == 3 and res["dump"].read_bytes() == dump.read_bytes()
