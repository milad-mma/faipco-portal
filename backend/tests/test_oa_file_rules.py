"""تست قواعد فایل و پیوست اتوماسیون اداری (app/core/oa_file_rules.py، oa_scanner، oa_storage)."""

import asyncio
import io
import os
import tempfile
import zipfile

from app.core import oa_file_rules as r
from app.core.oa_file_rules import FileRejected


def _raises(fn, *args):
    try:
        fn(*args)
    except FileRejected as e:
        return str(e)
    raise AssertionError("expected FileRejected")


def _tmp(data: bytes, suffix: str = "") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def _zip(entries: dict[str, bytes], compress=zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compress) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


ALL = [f.code for f in r.FORMATS]


def test_settings_defaults_and_validation():
    d = r.default_settings()
    assert d["letter_max_files"] == 10 and d["letter_max_file_mb"] == 20 and d["letter_all_max_total_mb"] == 500
    assert "pdf" in d["allowed_formats"] and "zip" not in d["allowed_formats"]
    ok = r.validate_settings({**d, "allowed_formats": ["zip", "pdf", "pdf"]}, 24)
    assert ok["allowed_formats"] == ["pdf", "zip"]  # ترتیب ثابت، بدون تکرار
    assert "سقف آپلود سرور" in _raises(r.validate_settings, {**d, "letter_max_file_mb": 30}, 24)
    assert "حجم مجموع" in _raises(r.validate_settings, {**d, "letter_max_total_mb": 5}, 24)
    assert "کل پیوست" in _raises(r.validate_settings, {**d, "letter_all_max_total_mb": 50}, 24)
    assert "حداقل یک فرمت" in _raises(r.validate_settings, {**d, "allowed_formats": []}, 24)
    assert "ناشناخته" in _raises(r.validate_settings, {**d, "allowed_formats": ["exe"]}, 24)
    assert "عدد صحیح" in _raises(r.validate_settings, {**d, "action_max_files": "x"}, 24)
    assert "حداکثر 10 فایل، هر فایل تا 20 مگابایت" in r.limits_hint(d)


def test_quota():
    r.check_quota([r.MIB] * 9, r.MIB, 10, 100)
    assert "حداکثر 10" in _raises(r.check_quota, [1] * 10, 1, 10, 100)
    assert "حجم مجموع" in _raises(r.check_quota, [60 * r.MIB], 50 * r.MIB, 10, 100)


def test_extension_rules():
    assert r.format_for_name("نامه.PDF", ["pdf"]).code == "pdf"
    assert r.format_for_name("scan.jpeg", ["jpg"]).code == "jpg"
    assert "هرگز" in _raises(r.format_for_name, "x.exe", ALL)
    assert "هرگز" in _raises(r.format_for_name, "report.docm", ALL)
    assert "هرگز" in _raises(r.format_for_name, "a.pdf.html", ALL)
    assert "هرگز" in _raises(r.format_for_name, "logo.svg", ALL)
    assert "بدون پسوند" in _raises(r.format_for_name, "README", ALL)
    assert "مجاز نیست" in _raises(r.format_for_name, "a.zip", ["pdf"])
    assert "پشتیبانی" in _raises(r.format_for_name, "a.rar", ALL)
    # هیچ پسوند ممنوعی در فهرست فرمت‌ها نیست
    assert not (r.FORBIDDEN_EXTENSIONS & set(r.FORMAT_BY_EXT))


def test_ooxml_checks():
    docx = _zip({"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<w/>"})
    r.check_content(_tmp(docx), r.FORMAT_BY_CODE["docx"], ALL)
    # پسوند جعلی: xlsx با محتوای docx
    assert "هم‌خوانی" in _raises(r.check_content, _tmp(docx), r.FORMAT_BY_CODE["xlsx"], ALL)
    macro = _zip({"[Content_Types].xml": b"<Types/>", "word/document.xml": b"", "word/vbaProject.bin": b"x"})
    assert "ماکرو" in _raises(r.check_content, _tmp(macro), r.FORMAT_BY_CODE["docx"], ALL)
    macro_ct = _zip({"[Content_Types].xml": b"application/vnd.ms-word.document.macroEnabled.main+xml",
                     "word/document.xml": b""})
    assert "ماکرو" in _raises(r.check_content, _tmp(macro_ct), r.FORMAT_BY_CODE["docx"], ALL)
    # OOXML رمزدار = فایل OLE با EncryptionInfo
    enc = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 100 + "EncryptionInfo".encode("utf-16-le")
    assert "رمزدار" in _raises(r.check_content, _tmp(enc), r.FORMAT_BY_CODE["docx"], ALL)
    assert "خراب" in _raises(r.check_content, _tmp(b"not a zip at all"), r.FORMAT_BY_CODE["docx"], ALL)


def test_legacy_office_and_odf():
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 200 + "WordDocument Macros VBA".encode("utf-16-le")
    r.check_content(_tmp(ole), r.FORMAT_BY_CODE["doc"], ALL)  # متن «Macros/VBA» به‌تنهایی رد نمی‌شود
    vba = ole + "_VBA_PROJECT".encode("utf-16-le")
    assert "ماکرو" in _raises(r.check_content, _tmp(vba), r.FORMAT_BY_CODE["doc"], ALL)
    assert "هم‌خوانی" in _raises(r.check_content, _tmp(b"%PDF-1.4"), r.FORMAT_BY_CODE["xls"], ALL)
    odt = _zip({"mimetype": b"application/vnd.oasis.opendocument.text", "content.xml": b"<x/>"})
    r.check_content(_tmp(odt), r.FORMAT_BY_CODE["odt"], ALL)
    assert "هم‌خوانی" in _raises(r.check_content, _tmp(odt), r.FORMAT_BY_CODE["ods"], ALL)
    odt_macro = _zip({"mimetype": b"application/vnd.oasis.opendocument.text", "Basic/Standard/Module1.xml": b""})
    assert "ماکرو" in _raises(r.check_content, _tmp(odt_macro), r.FORMAT_BY_CODE["odt"], ALL)


def test_zip_checks():
    ok = _zip({"a.pdf": b"%PDF-1.4", "dir/b.png": b"x"})
    r.check_content(_tmp(ok), r.FORMAT_BY_CODE["zip"], ["zip", "pdf", "png"])
    assert "غیرمجاز" in _raises(r.check_content, _tmp(ok), r.FORMAT_BY_CODE["zip"], ["zip", "pdf"])
    bad = _zip({"run.exe": b"MZ"})
    assert "ممنوع" in _raises(r.check_content, _tmp(bad), r.FORMAT_BY_CODE["zip"], ALL)
    nested = _zip({"inner.zip": ok})
    assert "غیرمجاز" in _raises(r.check_content, _tmp(nested), r.FORMAT_BY_CODE["zip"], ALL)
    traversal = _zip({"../evil.pdf": b"%PDF"})
    assert "مسیر" in _raises(r.check_content, _tmp(traversal), r.FORMAT_BY_CODE["zip"], ALL)
    bomb = _zip({"big.txt": b"\0" * (60 * r.MIB)})
    assert "حجم" in _raises(r.check_content, _tmp(bomb), r.FORMAT_BY_CODE["zip"], ALL)


def test_images_text_media():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (20, 10), "white").save(buf, "PNG")
    r.check_content(_tmp(buf.getvalue()), r.FORMAT_BY_CODE["png"], ALL)
    assert "هم‌خوانی" in _raises(r.check_content, _tmp(buf.getvalue()), r.FORMAT_BY_CODE["jpg"], ALL)
    assert "خراب" in _raises(r.check_content, _tmp(b"\x89PNG\r\n\x1a\n" + b"junk"), r.FORMAT_BY_CODE["png"], ALL)
    r.check_content(_tmp("سلام، نامه".encode()), r.FORMAT_BY_CODE["txt"], ALL)
    r.check_content(_tmp("ستون,مقدار".encode("cp1256")), r.FORMAT_BY_CODE["csv"], ALL)
    assert "متنی" in _raises(r.check_content, _tmp(b"MZ\x00\x00binary"), r.FORMAT_BY_CODE["txt"], ALL)
    assert "خالی" in _raises(r.check_content, _tmp(b""), r.FORMAT_BY_CODE["txt"], ALL)
    r.check_content(_tmp(b"ID3\x03rest"), r.FORMAT_BY_CODE["mp3"], ALL)
    r.check_content(_tmp(b"\0\0\0\x18ftypmp42"), r.FORMAT_BY_CODE["mp4"], ALL)
    assert "هم‌خوانی" in _raises(r.check_content, _tmp(b"RIFFxxxxAVI "), r.FORMAT_BY_CODE["mp4"], ALL)


def test_pdf_reuses_sanitizer():
    good = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    r.check_content(_tmp(good), r.FORMAT_BY_CODE["pdf"], ALL)
    js = b"%PDF-1.4\n1 0 obj<</S/JavaScript/JS(app.alert(1))>>endobj\n%%EOF"
    _raises(r.check_content, _tmp(js), r.FORMAT_BY_CODE["pdf"], ALL)


def test_status_machine_and_download():
    assert r.can_transition("uploading", "scanning") and r.can_transition("scan_pending", "scanning")
    assert not r.can_transition("infected", "clean") and not r.can_transition("rejected", "scanning")
    # اسکن اختیاری: خاموش → مستقیم clean؛ روشن شدن بعدی → اسکن فایل‌های بدون اسکن؛ خاموش شدن → scan_pending به clean
    assert r.can_transition("uploading", "clean") and r.can_transition("clean", "scanning")
    assert r.can_transition("scan_pending", "clean") and not r.can_transition("rejected", "clean")
    for s in ("infected", "scan_pending", "rejected", "scanning", "uploading"):
        assert not r.can_download(s) and not r.can_make_permanent(s)
    assert r.can_download("clean")
    assert r.safe_download_name('a"b\n/../x.pdf', r.FORMAT_BY_CODE["pdf"]) == "x.pdf"
    assert r.safe_download_name("نامه", r.FORMAT_BY_CODE["docx"]) == "نامه.docx"


def test_scanner_reply_parsing():
    from app.services import oa_scanner

    assert oa_scanner.interpret_reply("stream: OK").clean
    res = oa_scanner.interpret_reply("stream: Eicar-Test-Signature FOUND", "ClamAV 1.0/27000/x")
    assert not res.clean and res.signature == "Eicar-Test-Signature" and res.db_version
    try:
        oa_scanner.interpret_reply("INSTREAM size limit exceeded. ERROR")
        raise AssertionError("expected ScannerUnavailable")
    except oa_scanner.ScannerUnavailable:
        pass
    info = oa_scanner.parse_version("ClamAV 1.0.7/27434/Thu Oct 30 08:24:01 2026")
    assert info["engine"] == "1.0.7" and info["db"] == "27434" and info["db_date"].year == 2026
    # بدون clamd → ScannerUnavailable (نه خطای کلی)
    try:
        oa_scanner.version("/nonexistent/clamd.sock")
        raise AssertionError("expected ScannerUnavailable")
    except oa_scanner.ScannerUnavailable:
        pass


def test_local_storage_write_once():
    from app.services.oa_storage import LocalStorage, SizeLimitExceeded, StorageError

    root = tempfile.mkdtemp()
    st = LocalStorage(root)

    async def gen(parts):
        for p in parts:
            yield p

    key, size, sha = asyncio.run(st.receive(gen([b"abc", b"def"]), 10))
    assert size == 6 and len(sha) == 64 and key.startswith("tmp/")
    final = st.commit(key)
    assert final.startswith("objects/") and st.exists(final) and not st.exists(key)
    assert b"".join(st.iter_file(final)) == b"abcdef" and st.sha256_of(final) == sha
    assert not os.access(st.path_of(final), os.W_OK) or os.geteuid() == 0  # فقط‌خواندنی
    try:
        asyncio.run(st.receive(gen([b"x" * 11]), 10))
        raise AssertionError("expected SizeLimitExceeded")
    except SizeLimitExceeded:
        pass
    assert os.listdir(os.path.join(root, "tmp")) == []  # فایل نیمه‌کاره حذف شد
    try:
        st.path_of("../etc/passwd")
        raise AssertionError("expected StorageError")
    except StorageError:
        pass
    q = st.quarantine(final)
    assert q.startswith("quarantine/") and st.exists(q)
    st.delete(q)
    assert not st.exists(q)
