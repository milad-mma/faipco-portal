"""
قواعد خالص فایل و پیوست اتوماسیون اداری (docs/office-automation-spec.md بخش ۱۱ و ۶.۵؛ docs/office-automation.md).

- فهرست بسته‌ی فرمت‌هایی که سامانه برایشان بررسی نوع واقعی و ساختار دارد (FORMATS). هر سایت از پرتال انتخاب می‌کند کدام
  روشن باشند؛ فرمتی که بررسی‌کننده ندارد در فهرست نمی‌آید.
- پسوندهای همیشه ممنوع (اجرایی/اسکریپت، HTML، SVG، Office ماکرودار) که هیچ تنظیمی بازشان نمی‌کند.
- تنظیمات پیش‌فرض و اعتبارسنجی تعداد/حجم (حجم هر فایل حداکثر تا سقف آپلود سرور).
- بررسی محتوای فایل روی مسیر فایل موقت (بدون خواندن کامل در RAM، به‌جز PDF که با document_sanitizer بررسی می‌شود).

خطای قابل نمایش با FileRejected (پیام فارسی).
"""
from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass

MIB = 1024 * 1024


class FileRejected(ValueError):
    """فایل پذیرفته نشد؛ متن استثنا پیام فارسی برای کاربر است."""


@dataclass(frozen=True)
class FileFormat:
    code: str
    label: str
    extensions: tuple[str, ...]
    content_type: str
    default_on: bool
    note: str = ""


# ترتیب همان ترتیب نمایش در صفحه‌ی تنظیمات است
FORMATS: tuple[FileFormat, ...] = (
    FileFormat("pdf", "PDF", ("pdf",), "application/pdf", True),
    FileFormat("docx", "Word (DOCX)", ("docx",),
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document", True),
    FileFormat("xlsx", "Excel (XLSX)", ("xlsx",),
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", True),
    FileFormat("pptx", "PowerPoint (PPTX)", ("pptx",),
               "application/vnd.openxmlformats-officedocument.presentationml.presentation", True),
    FileFormat("jpg", "JPG / JPEG", ("jpg", "jpeg"), "image/jpeg", True),
    FileFormat("png", "PNG", ("png",), "image/png", True),
    FileFormat("webp", "WEBP", ("webp",), "image/webp", True),
    FileFormat("tiff", "TIFF", ("tif", "tiff"), "image/tiff", True),
    FileFormat("txt", "متن ساده (TXT)", ("txt",), "text/plain; charset=utf-8", True),
    FileFormat("csv", "CSV", ("csv",), "text/csv; charset=utf-8", True),
    FileFormat("doc", "Word قدیمی (DOC)", ("doc",), "application/msword", False, "فقط بدون ماکرو"),
    FileFormat("xls", "Excel قدیمی (XLS)", ("xls",), "application/vnd.ms-excel", False, "فقط بدون ماکرو"),
    FileFormat("ppt", "PowerPoint قدیمی (PPT)", ("ppt",), "application/vnd.ms-powerpoint", False, "فقط بدون ماکرو"),
    FileFormat("odt", "OpenDocument متن (ODT)", ("odt",), "application/vnd.oasis.opendocument.text", False),
    FileFormat("ods", "OpenDocument جدول (ODS)", ("ods",), "application/vnd.oasis.opendocument.spreadsheet", False),
    FileFormat("zip", "ZIP", ("zip",), "application/zip", False,
               "محتوای داخل هم بررسی می‌شود و باید از فرمت‌های روشن باشد"),
    FileFormat("mp3", "صوت MP3", ("mp3",), "audio/mpeg", False),
    FileFormat("mp4", "ویدیو MP4", ("mp4",), "video/mp4", False),
)
FORMAT_BY_CODE = {f.code: f for f in FORMATS}
FORMAT_BY_EXT = {ext: f for f in FORMATS for ext in f.extensions}
DEFAULT_FORMATS = tuple(f.code for f in FORMATS if f.default_on)

# همیشه ممنوع؛ هیچ تنظیمی بازشان نمی‌کند (بخش ۱۱)
FORBIDDEN_EXTENSIONS = frozenset(
    {
        "exe", "dll", "com", "bat", "cmd", "ps1", "psm1", "vbs", "vbe", "js", "jse", "wsf", "wsh", "msi", "msp", "scr",
        "pif", "cpl", "hta", "lnk", "reg", "jar", "apk", "sh", "bash", "py", "php", "pl", "rb", "html", "htm",
        "xhtml", "shtml", "mht", "mhtml", "svg", "svgz", "xml", "docm", "dotm", "xlsm", "xltm", "xlam", "pptm", "potm",
        "ppam", "ppsm", "sldm", "iso", "img", "vhd", "vhdx",
    }
)
FORBIDDEN_LABEL = "اجرایی و اسکریپت (exe، bat، js، ps1، …)، HTML، SVG، Office ماکرودار، فایل رمزدار"

# ---------- تنظیمات ----------

# (کلید، برچسب) — مقدار اولیه‌ی بخش ۱۱
DEFAULT_LIMITS = {
    "letter_max_files": 10,
    "letter_max_file_mb": 20,
    "letter_max_total_mb": 100,
    "action_max_files": 5,
    "action_max_file_mb": 20,
    "action_max_total_mb": 50,
    "letter_all_max_total_mb": 500,
}
MAX_FILES_CAP = 100
MAX_TOTAL_MB_CAP = 10_000


def default_settings() -> dict:
    return {**DEFAULT_LIMITS, "allowed_formats": list(DEFAULT_FORMATS)}


def validate_settings(values: dict, server_max_file_mb: int) -> dict:
    """
    تنظیمات پیوست یک سایت را بررسی و نرمال می‌کند. حجم هر فایل حداکثر server_max_file_mb (سقف آپلود سرور)؛
    مجموع هر بخش ≥ حجم یک فایل همان بخش؛ کل نامه ≥ مجموع پیوست نسخه. خطا → FileRejected با پیام فارسی.
    """
    out: dict = {}
    for key in DEFAULT_LIMITS:
        raw = values.get(key)
        try:
            v = int(raw)
        except (TypeError, ValueError):
            raise FileRejected("همه‌ی مقدارهای تعداد و حجم باید عدد صحیح باشند") from None
        out[key] = v
    for prefix, label in (("letter", "پیوست نامه"), ("action", "پیوست ارجاع/اقدام")):
        files, size, total = out[f"{prefix}_max_files"], out[f"{prefix}_max_file_mb"], out[f"{prefix}_max_total_mb"]
        if not 1 <= files <= MAX_FILES_CAP:
            raise FileRejected(f"تعداد فایل {label} باید بین ۱ و {MAX_FILES_CAP} باشد")
        if size < 1:
            raise FileRejected(f"حجم هر فایل {label} باید حداقل ۱ مگابایت باشد")
        if size > server_max_file_mb:
            raise FileRejected(
                f"حجم هر فایل {label} نمی‌تواند از سقف آپلود سرور ({server_max_file_mb} مگابایت) بیشتر باشد. "
                "برای بالاتر بردن آن، ادمین کل «سقف آپلود سرور» را در «تنظیمات سامانه» تغییر دهد."
            )
        if not size <= total <= MAX_TOTAL_MB_CAP:
            raise FileRejected(f"حجم مجموع {label} باید بین حجم یک فایل و {MAX_TOTAL_MB_CAP} مگابایت باشد")
    if not out["letter_max_total_mb"] <= out["letter_all_max_total_mb"] <= MAX_TOTAL_MB_CAP:
        raise FileRejected("حجم کل پیوست‌های نامه باید حداقل برابر مجموع پیوست یک نسخه و حداکثر ۱۰٬۰۰۰ مگابایت باشد")

    formats = values.get("allowed_formats")
    if not isinstance(formats, (list, tuple)):
        raise FileRejected("فهرست فرمت‌های مجاز نامعتبر است")
    unknown = [c for c in formats if c not in FORMAT_BY_CODE]
    if unknown:
        raise FileRejected("فرمت ناشناخته: " + "، ".join(map(str, unknown)))
    if not formats:
        raise FileRejected("حداقل یک فرمت باید مجاز باشد")
    out["allowed_formats"] = [f.code for f in FORMATS if f.code in set(formats)]  # ترتیب ثابت، بدون تکرار
    return out


def limits_hint(settings: dict, context: str = "letter") -> str:
    """متن راهنمای رابط: «حداکثر ۱۰ فایل، هر فایل تا ۲۰ مگابایت؛ فرمت‌های مجاز: …»."""
    files, size = settings[f"{context}_max_files"], settings[f"{context}_max_file_mb"]
    labels = "، ".join(FORMAT_BY_CODE[c].label for c in settings["allowed_formats"])
    return f"حداکثر {files} فایل، هر فایل تا {size} مگابایت؛ فرمت‌های مجاز: {labels}"


def check_quota(existing: list[int], new_size: int, max_files: int, max_total_mb: int) -> None:
    """سهمیه‌ی تعداد و مجموع حجم یک مجموعه پیوست (نسخه‌ی نامه/اقدام) قبل از افزودن فایل جدید."""
    if len(existing) + 1 > max_files:
        raise FileRejected(f"حداکثر {max_files} فایل مجاز است")
    if sum(existing) + new_size > max_total_mb * MIB:
        raise FileRejected(f"حجم مجموع پیوست‌ها نمی‌تواند از {max_total_mb} مگابایت بیشتر شود")


# ---------- نام و نوع فایل ----------


def extension_of(name: str | None) -> str:
    base = os.path.basename((name or "").replace("\\", "/")).strip().rstrip(".")
    return base.rsplit(".", 1)[-1].lower() if "." in base else ""


def format_for_name(name: str | None, allowed: list[str] | tuple[str, ...]) -> FileFormat:
    """فرمت فایل از روی پسوند؛ پسوند ممنوع/ناشناخته/خاموش → FileRejected."""
    ext = extension_of(name)
    if not ext:
        raise FileRejected("فایل بدون پسوند مجاز نیست")
    if ext in FORBIDDEN_EXTENSIONS:
        raise FileRejected(f"فایل با پسوند «{ext}» به دلایل امنیتی هرگز مجاز نیست")
    fmt = FORMAT_BY_EXT.get(ext)
    if fmt is None:
        raise FileRejected(f"فرمت «{ext}» پشتیبانی نمی‌شود")
    if fmt.code not in allowed:
        raise FileRejected(f"فرمت «{fmt.label}» در تنظیمات این سایت مجاز نیست")
    return fmt


# ---------- بررسی محتوا ----------

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAX_ENTRIES = 1000
ZIP_MAX_UNCOMPRESSED = 1024 * MIB
ZIP_MAX_RATIO = 200  # نسبت فشرده‌سازی بیشتر = احتمال ZIP bomb


def _head(path: str, n: int = 8192) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def _contains(path: str, needles: tuple[bytes, ...], chunk: int = 1 << 20) -> bool:
    """جست‌وجوی جریانی چند الگو در فایل (برای فایل‌های OLE)."""
    keep = max(len(n) for n in needles) - 1
    tail = b""
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                return False
            data = tail + block
            if any(n in data for n in needles):
                return True
            tail = data[-keep:] if keep else b""


def _u16(s: str) -> bytes:
    return s.encode("utf-16-le")


def _reject_encrypted_ole(path: str) -> None:
    """OOXML رمزدار در قالب OLE ذخیره می‌شود (EncryptionInfo/EncryptedPackage)."""
    if _contains(path, (_u16("EncryptedPackage"), _u16("EncryptionInfo"))):
        raise FileRejected("فایل رمزدار مجاز نیست؛ رمز فایل را بردارید و دوباره بارگذاری کنید")


def _open_zip(path: str) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise FileRejected("ساختار فایل معتبر نیست یا فایل خراب است") from None


def _zip_safety(zf: zipfile.ZipFile, size: int) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    if len(infos) > ZIP_MAX_ENTRIES:
        raise FileRejected("تعداد فایل‌های داخل فایل فشرده بیش از حد مجاز است")
    total = 0
    for info in infos:
        if info.flag_bits & 0x1:
            raise FileRejected("فایل فشرده‌ی رمزدار مجاز نیست")
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/"):
            raise FileRejected("مسیر نامعتبر داخل فایل فشرده")
        total += info.file_size
    if total > ZIP_MAX_UNCOMPRESSED or (size > 0 and total / size > ZIP_MAX_RATIO and total > 50 * MIB):
        raise FileRejected("حجم باز‌شده‌ی فایل فشرده بیش از حد مجاز است")
    return infos


_OOXML_PART = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}


def _check_ooxml(path: str, code: str) -> None:
    if _head(path, 8).startswith(_OLE_MAGIC):
        _reject_encrypted_ole(path)
        raise FileRejected("ساختار فایل با پسوند آن هم‌خوانی ندارد")
    zf = _open_zip(path)
    with zf:
        infos = _zip_safety(zf, os.path.getsize(path))
        names = {i.filename for i in infos}
        if "[Content_Types].xml" not in names or not any(n.startswith(_OOXML_PART[code]) for n in names):
            raise FileRejected("ساختار فایل با پسوند آن هم‌خوانی ندارد")
        if any(n.lower().endswith("vbaproject.bin") or n.lower().endswith("vbadata.xml") for n in names):
            raise FileRejected("فایل Office دارای ماکرو مجاز نیست")
        ct = zf.read("[Content_Types].xml").lower()
        if b"macroenabled" in ct or b"vbaproject" in ct:
            raise FileRejected("فایل Office دارای ماکرو مجاز نیست")


def _check_ole_legacy(path: str) -> None:
    if not _head(path, 8).startswith(_OLE_MAGIC):
        raise FileRejected("ساختار فایل با پسوند آن هم‌خوانی ندارد")
    _reject_encrypted_ole(path)
    # جریان ماکروی VBA در فایل‌های قدیمی Office (Word: Macros/VBA/_VBA_PROJECT، Excel: _VBA_PROJECT_CUR). فقط نام
    # جریان جست‌وجو می‌شود تا متن عادی سند («Macros»، «VBA») رد نشود؛ لایه‌ی دوم: AlertOLE2Macros در ClamAV (install.sh).
    if _contains(path, (_u16("_VBA_PROJECT"),)):
        raise FileRejected("فایل Office دارای ماکرو مجاز نیست")


_ODF_MIME = {"odt": b"application/vnd.oasis.opendocument.text", "ods": b"application/vnd.oasis.opendocument.spreadsheet"}


def _check_odf(path: str, code: str) -> None:
    zf = _open_zip(path)
    with zf:
        infos = _zip_safety(zf, os.path.getsize(path))
        names = {i.filename for i in infos}
        if "mimetype" not in names or zf.read("mimetype").strip() != _ODF_MIME[code]:
            raise FileRejected("ساختار فایل با پسوند آن هم‌خوانی ندارد")
        if any(n.startswith(("Basic/", "Scripts/")) for n in names):
            raise FileRejected("فایل دارای ماکرو مجاز نیست")
        if b"encryption-data" in (zf.read("META-INF/manifest.xml") if "META-INF/manifest.xml" in names else b""):
            raise FileRejected("فایل رمزدار مجاز نیست؛ رمز فایل را بردارید و دوباره بارگذاری کنید")


def _check_zip(path: str, allowed: list[str] | tuple[str, ...]) -> None:
    zf = _open_zip(path)
    with zf:
        infos = _zip_safety(zf, os.path.getsize(path))
        for info in infos:
            if info.is_dir():
                continue
            ext = extension_of(info.filename)
            if ext in FORBIDDEN_EXTENSIONS:
                raise FileRejected(f"فایل فشرده شامل فایل ممنوع است: {os.path.basename(info.filename)}")
            fmt = FORMAT_BY_EXT.get(ext)
            if fmt is None or fmt.code == "zip" or fmt.code not in allowed:
                raise FileRejected(
                    f"فایل فشرده شامل فایلی با فرمت غیرمجاز است: {os.path.basename(info.filename)}"
                )


_IMAGE_MAGIC = {
    "jpg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "tiff": (b"II*\x00", b"MM\x00*"),
}
MAX_IMAGE_PIXELS = 200_000_000  # اسکن A4 با وضوح بالا مجاز؛ بیشتر = بمب تصویری


def _check_image(path: str, code: str) -> None:
    head = _head(path, 16)
    if code == "webp":
        ok = head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    else:
        ok = head.startswith(_IMAGE_MAGIC[code])
    if not ok:
        raise FileRejected("ساختار فایل با پسوند آن هم‌خوانی ندارد")
    import warnings

    from PIL import Image

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as im:
                w, h = im.size
                if w * h > MAX_IMAGE_PIXELS:
                    raise FileRejected("ابعاد تصویر بیش از حد مجاز است")
                im.verify()
    except FileRejected:
        raise
    except Exception:  # noqa: BLE001 - هر خطای Pillow یعنی تصویر خراب
        raise FileRejected("فایل تصویر خراب یا نامعتبر است") from None


def _check_text(path: str) -> None:
    with open(path, "rb") as f:
        sample = f.read(1 << 20)
    if b"\x00" in sample:
        raise FileRejected("فایل متنی معتبر نیست")
    for enc in ("utf-8-sig", "cp1256"):
        try:
            sample.decode(enc)
            return
        except UnicodeDecodeError as e:
            if enc == "utf-8-sig" and e.start >= len(sample) - 4:
                return  # کاراکتر چندبایتی بریده‌شده در انتهای نمونه
    raise FileRejected("فایل متنی معتبر نیست (کدگذاری ناشناخته)")


def _check_mp3(path: str) -> None:
    head = _head(path, 4)
    if not (head[:3] == b"ID3" or (len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)):
        raise FileRejected("ساختار فایل با پسوند آن هم‌خوانی ندارد")


def _check_mp4(path: str) -> None:
    if _head(path, 12)[4:8] != b"ftyp":
        raise FileRejected("ساختار فایل با پسوند آن هم‌خوانی ندارد")


def check_content(path: str, fmt: FileFormat, allowed: list[str] | tuple[str, ...]) -> None:
    """
    نوع واقعی و ساختار فایل موقت را با فرمت ادعاشده (پسوند) می‌سنجد؛ ناهم‌خوانی، ماکرو، رمز، ساختار خراب یا
    ZIP bomb → FileRejected. اسکن ویروس جداست (ClamAV).
    """
    if os.path.getsize(path) == 0:
        raise FileRejected("فایل خالی است")
    code = fmt.code
    if code == "pdf":
        from app.core.document_sanitizer import DocumentRejected, check_pdf

        with open(path, "rb") as f:
            content = f.read()
        try:
            check_pdf(content)
        except DocumentRejected as e:
            raise FileRejected(str(e)) from None
    elif code in _OOXML_PART:
        _check_ooxml(path, code)
    elif code in ("doc", "xls", "ppt"):
        _check_ole_legacy(path)
    elif code in _ODF_MIME:
        _check_odf(path, code)
    elif code == "zip":
        _check_zip(path, allowed)
    elif code in ("jpg", "png", "webp", "tiff"):
        _check_image(path, code)
    elif code in ("txt", "csv"):
        _check_text(path)
    elif code == "mp3":
        _check_mp3(path)
    elif code == "mp4":
        _check_mp4(path)
    else:  # pragma: no cover - همه‌ی FORMATS بالا پوشش دارند
        raise FileRejected("فرمت پشتیبانی نمی‌شود")


# ---------- چرخه‌ی وضعیت فایل (۶.۵) ----------

STATUS_UPLOADING = "uploading"
STATUS_REJECTED = "rejected"
STATUS_SCANNING = "scanning"
STATUS_CLEAN = "clean"
STATUS_INFECTED = "infected"
STATUS_SCAN_PENDING = "scan_pending"

STATUS_LABELS = {
    STATUS_UPLOADING: "در حال بارگذاری",
    STATUS_REJECTED: "رد شد",
    STATUS_SCANNING: "در حال اسکن",
    STATUS_CLEAN: "سالم",
    STATUS_INFECTED: "آلوده (قرنطینه)",
    STATUS_SCAN_PENDING: "در انتظار اسکن",
}

# اسکن ویروس اختیاری است (oa.scan_enabled): خاموش → uploading مستقیم به clean («بدون اسکن ویروس»، scanned_at خالی)؛
# با روشن شدن اسکن، همان فایل‌های بدون اسکن clean → scanning → clean | infected | scan_pending. scan_pending با خاموش
# شدن اسکن → clean (بدون اسکن).
_TRANSITIONS = {
    STATUS_UPLOADING: {STATUS_SCANNING, STATUS_REJECTED, STATUS_CLEAN},
    STATUS_SCANNING: {STATUS_CLEAN, STATUS_INFECTED, STATUS_SCAN_PENDING},
    STATUS_SCAN_PENDING: {STATUS_SCANNING, STATUS_CLEAN},
    STATUS_CLEAN: {STATUS_SCANNING},
    STATUS_INFECTED: set(),
    STATUS_REJECTED: set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in _TRANSITIONS.get(current, set())


def can_download(status: str) -> bool:
    """infected، scan_pending و rejected هیچ مسیری به دانلود عادی ندارند."""
    return status == STATUS_CLEAN


def can_make_permanent(status: str) -> bool:
    return status == STATUS_CLEAN


def safe_download_name(name: str | None, fmt: FileFormat | None) -> str:
    """نام دانلود بدون کاراکتر کنترلی/جداکننده‌ی مسیر/کاراکترهای خطرناک هدر؛ پسوند همان فرمت."""
    import unicodedata

    base = os.path.basename((name or "").replace("\\", "/"))
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C" and ch not in '"<>:|?*;')
    base = base.strip(" .") or "file"
    if fmt is not None and extension_of(base) not in fmt.extensions:
        base = f"{base}.{fmt.extensions[0]}"
    return base[:200]
