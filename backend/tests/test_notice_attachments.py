"""تست منطق خالص پیوست اطلاعیه: ثابت‌ها و نوع‌های مجاز."""
import pytest


def test_attachment_limits():
    pytest.importorskip("sqlalchemy")
    from app.services import notice_service as svc

    assert svc.ATTACHMENT_MAX_COUNT == 5
    assert svc.ATTACHMENT_MAX_BYTES == 10 * 1024 * 1024
    assert {"image/jpeg", "image/png", "application/pdf"} <= svc.ATTACHMENT_ALLOWED_TYPES
    assert svc.ATTACHMENT_PERMISSION == "notices.attachments"


def test_sniff_types_for_attachments():
    from app.core.document_sanitizer import sniff_content_type

    assert sniff_content_type(b"%PDF-1.7\n...") == "application/pdf"
    assert sniff_content_type(b"\x89PNG\r\n\x1a\n" + b"0" * 8) == "image/png"
    assert sniff_content_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert sniff_content_type(b"MZ\x90\x00") not in {"image/jpeg", "image/png", "application/pdf"}
