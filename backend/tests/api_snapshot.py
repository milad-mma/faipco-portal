"""
ابزار «عکس فوری از مسیرهای API» - مرحله ۰ بازسازی ساختار.

هدف: هر جابه‌جایی فایل/ماژول در بازسازی، نباید حتی یک مسیر HTTP را تغییر
دهد، چون فرانت‌اند نصب‌شده و PWA کاربران به همین مسیرها وابسته‌اند.

این ابزار بدون هیچ وابستگی (بدون FastAPI) و فقط با تحلیل ایستای کد،
فهرست «METHOD /api/v1/path» را از دو منبع می‌سازد:
  1. app/api/v1/router.py  ← پیشوند هر روتر (include_router(..., prefix="..."))
  2. app/api/v1/endpoints/*.py ← دکوراتورهای @router.get/post/put/patch/delete/websocket
و با فایل مرجع api_routes.snapshot.json مقایسه می‌کند.

استفاده (از پوشه backend):
    python3 tests/api_snapshot.py            # مقایسه با مرجع؛ خروجی ≠ ۰ یعنی تفاوت
    python3 tests/api_snapshot.py --write    # به‌روزرسانی مرجع (فقط وقتی تغییر مسیر عمدی است)
    python3 tests/api_snapshot.py --print    # فقط چاپ فهرست فعلی

test_api_routes_runtime.py همین مرجع را با مسیرهای واقعی FastAPI (در محیطی که
وابستگی‌ها نصب‌اند) هم مقایسه می‌کند تا چیزی که تحلیل ایستا نمی‌بیند از قلم نیفتد.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_DIR / "app"
ENDPOINTS_DIR = APP_DIR / "api" / "v1" / "endpoints"
ROUTER_FILE = APP_DIR / "api" / "v1" / "router.py"
MAIN_FILE = APP_DIR / "main.py"
SNAPSHOT_FILE = Path(__file__).resolve().parent / "api_routes.snapshot.json"

API_PREFIX = "/api/v1"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "websocket"}


def _router_prefixes() -> list[tuple[str, str]]:
    """[(module_name, prefix)] به ترتیب include در router.py - ترتیب مهم است (اولویت مسیرهای هم‌نام)."""
    src = ROUTER_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r"include_router\(\s*(\w+)\.router\s*,\s*prefix\s*=\s*\"([^\"]*)\"")
    return [(m.group(1), m.group(2)) for m in pattern.finditer(src)]


def _decorator_routes(module_path: Path) -> list[tuple[str, str]]:
    """[(METHOD, path)] از دکوراتورهای @router.<method>("...") - به ترتیب تعریف در فایل."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    routes: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            if not (isinstance(dec.func.value, ast.Name) and dec.func.value.id == "router"):
                continue
            method = dec.func.attr
            if method not in HTTP_METHODS:
                continue
            if not dec.args or not isinstance(dec.args[0], ast.Constant):
                continue
            path = dec.args[0].value
            routes.append((method.upper(), path))
    return routes


def _app_level_routes() -> list[str]:
    """مسیرهایی که مستقیم روی app تعریف شده‌اند (مثل /api/health)."""
    tree = ast.parse(MAIN_FILE.read_text(encoding="utf-8"), filename=str(MAIN_FILE))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and isinstance(dec.func.value, ast.Name)
                and dec.func.value.id == "app"
                and dec.func.attr in HTTP_METHODS
                and dec.args
                and isinstance(dec.args[0], ast.Constant)
            ):
                found.append(f"{dec.func.attr.upper()} {dec.args[0].value}")
    return found


def collect_routes() -> list[str]:
    routes: list[str] = _app_level_routes()
    for module_name, prefix in _router_prefixes():
        module_path = ENDPOINTS_DIR / f"{module_name}.py"
        if not module_path.exists():
            raise SystemExit(f"router.py به ماژولی اشاره می‌کند که وجود ندارد: {module_path}")
        for method, path in _decorator_routes(module_path):
            routes.append(f"{method} {API_PREFIX}{prefix}{path}")
    return sorted(set(routes))


def load_snapshot() -> list[str]:
    if not SNAPSHOT_FILE.exists():
        return []
    return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))["routes"]


def main(argv: list[str]) -> int:
    current = collect_routes()
    if "--print" in argv:
        print("\n".join(current))
        return 0
    if "--write" in argv:
        SNAPSHOT_FILE.write_text(
            json.dumps({"count": len(current), "routes": current}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"مرجع به‌روز شد: {len(current)} مسیر → {SNAPSHOT_FILE.name}")
        return 0

    expected = load_snapshot()
    if not expected:
        print("فایل مرجع وجود ندارد - با --write بسازید.")
        return 2
    removed = sorted(set(expected) - set(current))
    added = sorted(set(current) - set(expected))
    if not removed and not added:
        print(f"OK: {len(current)} مسیر API دقیقاً مطابق مرجع است.")
        return 0
    if removed:
        print(f"⚠️ {len(removed)} مسیر حذف/تغییر کرده (فرانت‌اند نصب‌شده به این‌ها وابسته است):")
        for r in removed:
            print(f"   - {r}")
    if added:
        print(f"ℹ️ {len(added)} مسیر جدید (اگر عمدی است، مرجع را با --write به‌روز کنید):")
        for a in added:
            print(f"   + {a}")
    return 1 if removed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
