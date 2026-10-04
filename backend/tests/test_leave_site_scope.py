"""تست منطق خالص محدود کردن درخواست‌های مرخصی/ماموریت به پرسنل همان سایت (دیتابیس کاراوب مشترک)."""
import pytest


def _svc():
    pytest.importorskip("sqlalchemy")
    from app.services.leave_request_service import LeaveRequestService

    return LeaveRequestService


def test_request_scope():
    svc = _svc()
    own, others = {225735}, {235508}
    assert svc._request_in_site_scope(225735, own, others, False)  # پرسنل همین سایت
    assert not svc._request_in_site_scope(235508, own, others, False)  # پرسنل سایت دیگر
    assert not svc._request_in_site_scope(235508, own, others, True)  # حتی با مجوز سراسری از این سایت دیده نمی‌شود
    assert not svc._request_in_site_scope(999999, own, others, False)  # کد ناشناخته، مجوز سایتی
    assert svc._request_in_site_scope(999999, own, others, True)  # کد ناشناخته، مجوز سراسری
    assert not svc._request_in_site_scope(None, own, others, False)
