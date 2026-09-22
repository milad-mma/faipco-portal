#!/usr/bin/env bash
# اجرای همه بررسی‌های «قبل از انتشار» - مرحله ۰ بازسازی ساختار.
#   bash scripts/check.sh            # همه (نیاز به venv و PostgreSQL)
#   bash scripts/check.sh --quick    # فقط بررسی‌های بدون وابستگی (مسیرهای API، syntax)
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
QUICK="${1:-}"
STATUS=0

step() { echo -e "\n\033[1;36m== $* ==\033[0m"; }

step "1. مسیرهای API مطابق مرجع (تحلیل ایستا)"
(cd "$ROOT/backend" && python3 tests/api_snapshot.py) || STATUS=1

step "2. syntax همه فایل‌های پایتون"
(cd "$ROOT" && python3 -m compileall -q backend/app database/migrations >/dev/null && echo "OK") || STATUS=1

if [ "$QUICK" = "--quick" ]; then
  [ $STATUS -eq 0 ] && echo -e "\n\033[1;32mبررسی‌های سریع موفق\033[0m" || echo -e "\n\033[1;31mبررسی‌های سریع شکست خورد\033[0m"
  exit $STATUS
fi

step "3. تست‌های واحد + مسیرهای واقعی FastAPI (pytest)"
if [ -d "$ROOT/backend/.venv" ]; then
  (cd "$ROOT/backend" && source .venv/bin/activate && python -m pytest -q tests && deactivate) || STATUS=1
else
  echo "backend/.venv پیدا نشد - رد شد"; STATUS=1
fi

step "4. زنجیره Migration ها روی دیتابیس خالی"
bash "$SCRIPT_DIR/test_migrations.sh" || STATUS=1

[ $STATUS -eq 0 ] && echo -e "\n\033[1;32mهمه بررسی‌ها موفق\033[0m" || echo -e "\n\033[1;31mبعضی بررسی‌ها شکست خورد\033[0m"
exit $STATUS
