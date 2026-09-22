"""
مرحله ۰ بازسازی ساختار: مسیرهای واقعی FastAPI باید دقیقاً با مرجع
api_routes.snapshot.json یکی باشند. این تست در محیطی اجرا می‌شود که
وابستگی‌ها نصب‌اند (venv سرور / محیط توسعه)؛ بدون FastAPI رد نمی‌شود، Skip می‌شود.
"""
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

SNAPSHOT_FILE = Path(__file__).resolve().parent / "api_routes.snapshot.json"


def _runtime_routes() -> set[str]:
    from fastapi.routing import APIRoute, APIWebSocketRoute

    from app.main import app

    found: set[str] = set()
    for route in app.routes:
        if isinstance(route, APIWebSocketRoute):
            found.add(f"WEBSOCKET {route.path}")
        elif isinstance(route, APIRoute):
            for method in route.methods or []:
                if method in {"HEAD", "OPTIONS"}:
                    continue
                found.add(f"{method} {route.path}")
    return found


def test_runtime_routes_match_snapshot():
    expected = set(json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))["routes"])
    actual = _runtime_routes()
    # مسیرهای غیر-API (استاتیک، docs) بیرون از مقایسه
    actual = {r for r in actual if r.split(" ", 1)[1].startswith("/api/")}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    assert not missing, f"مسیرهایی که از API حذف/تغییر شده‌اند: {missing}"
    assert not extra, f"مسیرهای جدید بدون به‌روزرسانی مرجع (python3 tests/api_snapshot.py --write): {extra}"
