"""تست مقصدهای بکاپ و صف تلاش دوباره: امضای S3 با نمونه‌های رسمی AWS، پوشه‌ی محلی، و منطق صف (بدون شبکه/دیتابیس)."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core import backup_dest_rules as R

AK, SK = "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
T0 = datetime(2013, 5, 24, tzinfo=timezone.utc)


def _raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc as e:
        return str(e)
    raise AssertionError(f"expected {exc.__name__}")


def test_sigv4_aws_examples():
    # نمونه‌های مستند AWS (Signature V4 برای S3: GET Object و List Objects)
    h = R.sigv4_headers(method="GET", host="examplebucket.s3.amazonaws.com", canonical_uri="/test.txt", query=None,
                        headers={"Range": "bytes=0-9"}, payload_sha256=R.EMPTY_SHA256, access_key=AK, secret_key=SK,
                        region="us-east-1", now=T0)
    assert h["Authorization"].endswith("f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")
    h = R.sigv4_headers(method="GET", host="examplebucket.s3.amazonaws.com", canonical_uri="/",
                        query={"max-keys": "2", "prefix": "J"}, headers=None, payload_sha256=R.EMPTY_SHA256,
                        access_key=AK, secret_key=SK, region="us-east-1", now=T0)
    assert h["Authorization"].endswith("34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7")
    assert h["x-amz-date"] == "20130524T000000Z" and "host" not in h


def test_s3_urls():
    url, host, canon = R.s3_object_url("s3.example.com", "bk", "a b/f.zip", path_style=True)
    assert url == "https://s3.example.com/bk/a%20b/f.zip" and host == "s3.example.com" and canon == "/bk/a%20b/f.zip"
    url, host, canon = R.s3_object_url("https://s3.example.com/", "bk", "f.zip", path_style=False)
    assert host == "bk.s3.example.com" and canon == "/f.zip"
    assert R.s3_object_url("http://minio:9000", "bk", "", path_style=True)[2] == "/bk"
    assert R.s3_key("/backups/faipco/", "x.zip") == "backups/faipco/x.zip" and R.s3_key(None, "x.zip") == "x.zip"


def test_local_path_rules():
    assert R.check_local_path(" /mnt/backup/faipco/ ") == "/mnt/backup/faipco"
    for bad in ("", "mnt/x", "/", "/etc/x", "/var/www/html/b", "/var/lib/faipco/backups", "/mnt/../etc", "/proc"):
        _raises(ValueError, R.check_local_path, bad)
    assert R.check_local_path("/var/backups/faipco") == "/var/backups/faipco"


def test_retry_schedule():
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert R.next_retry_at(1, now) == now + timedelta(minutes=15)
    assert R.next_retry_at(R.MAX_ATTEMPTS, now) == now + timedelta(minutes=R.RETRY_DELAYS_MIN[-1])
    assert R.next_retry_at(R.MAX_ATTEMPTS + 1, now) is None and R.next_retry_at(0, now) is None
    entries = [{"filename": f"f{i}", "created_at": f"2026-11-0{i}T00:00:00+00:00"} for i in range(1, 6)]
    assert sorted(R.entries_to_drop(entries, keep=3)) == ["f1", "f2"]
    assert R.superseded_kinds("2026-11-01T00:00:00+00:00", {"sftp": "2026-11-02T00:00:00+00:00", "s3": "2026-10-01"}) == {"sftp"}
    assert R.parse_filename_ok("faipco-backup-20261101-101010.zip") and not R.parse_filename_ok("../x.zip")


def _archive(folder: Path, name="faipco-backup-20261101-101010.zip", data=b"zipdata" * 100) -> tuple[Path, str]:
    p = folder / name
    p.write_bytes(data)
    return p, R.sha256_file(p)


def test_local_destination():
    from app.services import backup_destinations as D
    from app.services.remote_backup_service import RemoteBackupError

    with tempfile.TemporaryDirectory() as tmp:
        src_dir, dest = Path(tmp) / "src", Path(tmp) / "mnt" / "faipco"
        src_dir.mkdir()
        D.R.check_local_path = lambda raw: str(raw).rstrip("/")  # پوشه‌ی موقت تست زیر /tmp است
        try:
            assert "موفق" in D.test_local(str(dest))
            src, sha = _archive(src_dir)
            D.upload_local(src, src.name, sha, path=str(dest))
            assert (dest / src.name).read_bytes() == src.read_bytes() and not list(dest.glob(".*part"))
            msg = _raises(RemoteBackupError, D.upload_local, src, "faipco-backup-20261101-111111.zip", "0" * 64, path=str(dest))
            assert "هش" in msg and not (dest / "faipco-backup-20261101-111111.zip").exists()
            for d in ("20261001-000000", "20261002-000000", "20261003-000000"):
                (dest / f"faipco-backup-{d}.zip").write_bytes(b"x")
            (dest / "other.txt").write_bytes(b"keep")
            assert D.retention_local(path=str(dest), mode="count", retention_count=2, retention_days=0) == 2
            assert sorted(os.listdir(dest)) == ["faipco-backup-20261003-000000.zip", src.name, "other.txt"]
        finally:
            import importlib

            importlib.reload(R)


def test_retry_queue_files():
    from app.services import backup_archive, backup_retry_queue as Q

    with tempfile.TemporaryDirectory() as tmp:
        backup_archive.BACKUP_DIR = Path(tmp) / "backups"
        work = backup_archive.backup_dir()
        t = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
        for i in range(4):
            name = f"faipco-backup-2026110{i + 1}-100000.zip"
            src, sha = _archive(work, name)
            Q.enqueue(src, name, sha, t + timedelta(days=i), {"sftp": "timeout", "s3": "denied"})
            assert not src.exists()
        items = Q.list_entries()
        assert len(items) == R.MAX_QUEUED_ARCHIVES and items[0]["filename"].startswith("faipco-backup-20261104")
        assert not (Q.pending_dir() / "faipco-backup-20261101-100000.zip").exists()  # قدیمی‌ترین کنار رفت
        assert items[0]["kinds"]["sftp"]["attempts"] == 1
        # بکاپ جدیدتری به SFTP رسید → SFTP از همه‌ی ورودی‌های قدیمی‌تر حذف می‌شود
        Q.note_success("sftp", t + timedelta(days=10))
        assert all(list(e["kinds"]) == ["s3"] for e in Q.list_entries())
        Q.note_success("s3", t + timedelta(days=2, hours=1))  # فقط ورودی‌های قدیمی‌تر از این زمان
        names = [e["filename"] for e in Q.list_entries()]
        assert names == ["faipco-backup-20261104-100000.zip"]
        assert not Q.discard("../../etc/passwd") and Q.discard(names[0]) and Q.list_entries() == []
