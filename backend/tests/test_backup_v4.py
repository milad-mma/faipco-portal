"""تست بکاپ نسخه‌ی ۴: قواعد، و ساخت/رمزنگاری/استخراج/تطبیق هش واقعی با age (بدون دیتابیس)."""

import hashlib
import io
import json
import os
import shutil
import tarfile
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


# ---------- end-to-end با age واقعی ----------


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
    meta = {"set_id": "s1", "started_at": datetime.now(timezone.utc), "app_version": "t", "alembic_head": "132",
            "pg_dump_version": "pg", "key_id": None, "key_mode": None, "consistency_method": "snapshot"}
    return root, rows, dump, meta


def test_archive_roundtrip_encrypted_and_tamper():
    if not shutil.which("age"):
        return  # روی سرور CI بدون age رد می‌شود
    from app.services import backup_archive as A
    from app.services import backup_keys as K

    tmp = Path(tempfile.mkdtemp())
    root, rows, dump, meta = _setup(tmp)
    identity, public = K.generate_identity()
    assert public.startswith("age1") and K.public_key_of(identity) == public
    meta.update(key_id=K.key_id_of(public), key_mode="external")
    out = tmp / "faipco-backup-20261101-101010.tar.gz.age"
    res = A.write_archive(out, public, dump, rows, lambda k: root / k, meta)
    m = res["manifest"]
    assert m["files"]["count"] == 3 and m["excluded"] == {"infected": 1, "missing_temp": 1}
    assert out.read_bytes()[:21] == b"age-encryption.org/v1"  # واقعاً رمزنگاری شده

    staging = tmp / "stage"
    got = A.stage_archive(out, staging, [identity])
    assert got["set_id"] == "s1"
    assert (staging / "database.dump").read_bytes() == dump.read_bytes()
    for row in rows[:3]:
        assert (staging / "files" / row.storage_key).read_bytes() == (root / row.storage_key).read_bytes()

    other, _ = K.generate_identity()
    assert "کلید" in _raises(A.ArchiveError, A.stage_archive, out, tmp / "s2", [other])
    assert not (tmp / "s2").exists()  # استخراج نیمه‌کاره پاک شد
    assert "کلید خصوصی" in _raises(A.ArchiveError, A.stage_archive, out, tmp / "s3", [])
    # چند کلید (قدیمی + جدید) با هم
    A.stage_archive(out, tmp / "s4", [other, identity])
    # دست‌کاری فایل رمزنگاری‌شده
    data = bytearray(out.read_bytes())
    data[len(data) // 2] ^= 0xFF
    bad = tmp / "faipco-backup-20261101-101011.tar.gz.age"
    bad.write_bytes(bytes(data))
    _raises(A.ArchiveError, A.stage_archive, bad, tmp / "s5", [identity])


def test_archive_unencrypted_and_integrity():
    from app.services import backup_archive as A

    tmp = Path(tempfile.mkdtemp())
    root, rows, dump, meta = _setup(tmp)
    out = tmp / "faipco-backup-20261101-101010.tar.gz"
    A.write_archive(out, None, dump, rows, lambda k: root / k, meta)
    A.stage_archive(out, tmp / "ok", [])
    # فایل دائم ناموجود → بکاپ ناموفق
    (root / rows[0].storage_key).unlink()
    _raises(A.ArchiveError, A.write_archive, tmp / "x.part", None, dump, rows, lambda k: root / k, meta)
    # هش ناهم‌خوان با دیتابیس → ناموفق
    (root / rows[0].storage_key).write_bytes(b"changed")
    _raises(A.ArchiveError, A.write_archive, tmp / "y.part", None, dump, rows, lambda k: root / k, meta)
    # آرشیوی که عضوش با manifest نمی‌خواند (دست‌کاری) → رد
    raw_manifest = None
    with tarfile.open(out, "r:gz") as t:
        raw_manifest = t.extractfile("manifest.json").read()
    forged = tmp / "faipco-backup-20261101-101012.tar.gz"
    with tarfile.open(forged, "w:gz") as t:
        for name, data in (("database.dump", b"forged"), ("manifest.json", raw_manifest)):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    assert "سالم نیست" in _raises(A.ArchiveError, A.stage_archive, forged, tmp / "f", [])
    # مسیر خطرناک داخل آرشیو → رد
    evil = tmp / "faipco-backup-20261101-101013.tar.gz"
    with tarfile.open(evil, "w:gz") as t:
        info = tarfile.TarInfo("../../etc/x")
        info.size = 1
        t.addfile(info, io.BytesIO(b"x"))
    _raises(Exception, A.stage_archive, evil, tmp / "e", [])
    assert not (tmp / "e").exists()


def test_key_package_roundtrip():
    if not shutil.which("age"):
        return
    from app.services import backup_keys as K

    identity, public = K.generate_identity()
    pkg = K.export_package(identity, "a long passphrase!")
    assert identity not in pkg.decode()
    assert K.import_package(pkg, "a long passphrase!") == identity
    assert "اشتباه" in _raises(K.BackupKeyError, K.import_package, pkg, "wrong passphrase!!")
    assert "۱۲" in _raises(K.BackupKeyError, K.export_package, identity, "short")
    _raises(K.BackupKeyError, K.public_key_of, "not a key")
