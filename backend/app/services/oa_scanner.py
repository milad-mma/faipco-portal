"""
اسکن ویروس فایل‌های اتوماسیون با ClamAV محلی (clamd روی Unix socket) — docs/office-automation-spec.md بخش ۹.۲ و ۱۲.

- بدون اینترنت هم کار می‌کند (با آخرین بانک موجود)؛ قدیمی بودن بانک فقط هشدار است.
- اگر clamd در دسترس نباشد یا خطا بدهد → ScannerUnavailable (فایل scan_pending می‌ماند و Job دوباره امتحان می‌کند).
پروتکل: zINSTREAM با قطعه‌های <طول ۴ بایتی><داده> و قطعه‌ی صفر در پایان؛ پاسخ «stream: OK» یا «stream: <نام> FOUND».
"""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from datetime import datetime


TIMEOUT_SECONDS = 120

def _settings():
    from app.core.config import get_settings  # import محلی: ماژول بدون .env هم قابل تست است

    return get_settings()


CHUNK = 1 << 16


class ScannerUnavailable(RuntimeError):
    pass


@dataclass
class ScanResult:
    clean: bool
    signature: str | None
    db_version: str | None


def _connect(socket_path: str) -> socket.socket:
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT_SECONDS)
        s.connect(socket_path)
        return s
    except OSError as e:
        raise ScannerUnavailable(f"اتصال به ClamAV برقرار نشد: {e}") from None


def _read_reply(s: socket.socket) -> str:
    data = b""
    while not data.endswith(b"\0"):
        part = s.recv(4096)
        if not part:
            break
        data += part
    return data.rstrip(b"\0").decode("utf-8", "replace").strip()


def version(socket_path: str | None = None) -> str:
    """مثل «ClamAV 1.0.7/27434/Thu Oct 30 08:24:01 2026» (نسخه/بانک/تاریخ بانک)."""
    s = _connect(socket_path or _settings().OA_CLAMD_SOCKET)
    with s:
        try:
            s.sendall(b"zVERSION\0")
            return _read_reply(s)
        except OSError as e:
            raise ScannerUnavailable(f"ClamAV پاسخ نداد: {e}") from None


def parse_version(text: str) -> dict:
    """تجزیه‌ی پاسخ VERSION به نسخه‌ی برنامه، شماره‌ی بانک و تاریخ بانک (اگر قابل خواندن باشد)."""
    parts = text.split("/")
    out = {"raw": text, "engine": parts[0].replace("ClamAV", "").strip() or None, "db": None, "db_date": None}
    if len(parts) >= 2:
        out["db"] = parts[1].strip() or None
    if len(parts) >= 3:
        try:
            out["db_date"] = datetime.strptime(parts[2].strip(), "%a %b %d %H:%M:%S %Y")
        except ValueError:
            pass
    return out


def scan_file(path: str, socket_path: str | None = None) -> ScanResult:
    """اسکن جریانی یک فایل؛ خطای اتصال/اسکنر → ScannerUnavailable."""
    sock_path = socket_path or _settings().OA_CLAMD_SOCKET
    db_version = version(sock_path)  # بانک شناسایی‌ای که این اسکن با آن انجام شد (scan_db_version)
    s = _connect(sock_path)
    with s:
        try:
            s.sendall(b"zINSTREAM\0")
            with open(path, "rb") as f:
                while True:
                    block = f.read(CHUNK)
                    if not block:
                        break
                    s.sendall(struct.pack("!L", len(block)) + block)
            s.sendall(struct.pack("!L", 0))
            reply = _read_reply(s)
        except OSError as e:
            raise ScannerUnavailable(f"اسکن ناتمام ماند: {e}") from None
    return interpret_reply(reply, db_version)


def interpret_reply(reply: str, db_version: str | None = None) -> ScanResult:
    """«stream: OK» → سالم؛ «stream: X FOUND» → آلوده؛ هر چیز دیگر (ERROR، سقف حجم clamd) → ScannerUnavailable."""
    body = reply.split(":", 1)[1].strip() if ":" in reply else reply.strip()
    if body == "OK":
        return ScanResult(True, None, db_version)
    if body.endswith("FOUND"):
        return ScanResult(False, body[: -len("FOUND")].strip()[:255] or "unknown", db_version)
    raise ScannerUnavailable(f"پاسخ نامعتبر ClamAV: {reply[:200]}")
