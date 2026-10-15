from app.services.session_service import device_label


def test_device_label_detects_browser_and_os():
    chrome_win = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0 Safari/537.36"
    assert device_label(chrome_win) == "Chrome روی Windows"
    edge = chrome_win + " Edg/155.0"
    assert device_label(edge) == "Edge روی Windows"
    iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
    assert device_label(iphone) == "Safari روی iPhone"
    android_chrome = "Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 Chrome/155.0 Mobile Safari/537.36"
    assert device_label(android_chrome) == "Chrome روی Android"
    # پرتال داخل اپ اندروید (هدر X-Client-App) برچسب جدا دارد
    assert device_label(android_chrome, "android") == "اپ اندروید"
    assert device_label(None) == "مرورگر"
