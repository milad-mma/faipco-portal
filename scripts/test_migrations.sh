#!/usr/bin/env bash
# مرحله ۰ بازسازی ساختار: تست کامل بودن زنجیره Migration ها روی یک دیتابیس خالی.
#
# چه می‌کند:
#   1. یک دیتابیس موقت می‌سازد (faipco_migtest_<pid>)
#   2. alembic upgrade head  → همه Migration ها از صفر (مثل نصب جدید)
#   3. بررسی می‌کند alembic current == head
#   4. downgrade -1 و دوباره upgrade head → آخرین Migration برگشت‌پذیر است
#   5. دیتابیس موقت را حذف می‌کند (حتی در صورت خطا)
#
# دیتابیس واقعی پرتال دست نمی‌خورد. اجرا روی سرور (به‌عنوان root) یا محیط توسعه:
#   bash scripts/test_migrations.sh
# متغیرهای اختیاری: INSTALL_DIR (پیش‌فرض: پوشه والد این اسکریپت)، PG_SUPERUSER (postgres)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-$(dirname "$SCRIPT_DIR")}"
BACKEND_DIR="$INSTALL_DIR/backend"
PG_SUPERUSER="${PG_SUPERUSER:-postgres}"
TEST_DB="faipco_migtest_$$"

log() { echo -e "\033[1;34m[migtest]\033[0m $*"; }
fail() { echo -e "\033[1;31m[migtest] ✗ $*\033[0m" >&2; exit 1; }

[ -f "$BACKEND_DIR/.env" ] || fail "backend/.env پیدا نشد ($BACKEND_DIR)"
[ -d "$BACKEND_DIR/.venv" ] || fail "backend/.venv پیدا نشد - اول install.sh را اجرا کنید"

# DATABASE_URL واقعی: postgresql+asyncpg://user:pass@host:port/dbname
REAL_URL="$(grep -E '^DATABASE_URL=' "$BACKEND_DIR/.env" | head -1 | cut -d= -f2- | tr -d '"'"'"'')"
[ -n "$REAL_URL" ] || fail "DATABASE_URL در .env نیست"
DB_USER="$(echo "$REAL_URL" | sed -E 's#^[a-z+]+://([^:/@]+).*#\1#')"
TEST_URL="$(echo "$REAL_URL" | sed -E "s#/[^/?]+(\?.*)?\$#/$TEST_DB\1#")"

run_psql() {
  if [ "$(id -u)" = "0" ] && id "$PG_SUPERUSER" >/dev/null 2>&1; then
    su - "$PG_SUPERUSER" -c "psql -v ON_ERROR_STOP=1 -q $*"
  else
    psql -v ON_ERROR_STOP=1 -q "$@"
  fi
}

cleanup() {
  log "حذف دیتابیس موقت $TEST_DB"
  run_psql -c "\"DROP DATABASE IF EXISTS $TEST_DB\"" >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "ساخت دیتابیس موقت $TEST_DB (مالک: $DB_USER)"
run_psql -c "\"CREATE DATABASE $TEST_DB OWNER $DB_USER\""

cd "$BACKEND_DIR"
# shellcheck disable=SC1091
source .venv/bin/activate
export DATABASE_URL="$TEST_URL"

log "alembic upgrade head (از صفر)"
alembic upgrade head >/tmp/migtest_up.log 2>&1 || { cat /tmp/migtest_up.log; fail "upgrade head شکست خورد"; }

# alembic current وقتی روی آخرین Migration باشد، خودش «(head)» را کنار شماره چاپ می‌کند
CURRENT_LINE="$(alembic current 2>&1 | grep -E '\(head\)' | head -1 || true)"
[ -n "$CURRENT_LINE" ] || { alembic current 2>&1 | tail -3; fail "دیتابیس موقت روی head نیست"; }
HEAD="$(echo "$CURRENT_LINE" | grep -oE '[0-9a-f]+' | head -1)"
log "✓ همه Migration ها اجرا شدند (head = $HEAD)"

log "downgrade -1 و upgrade head (برگشت‌پذیری آخرین Migration)"
alembic downgrade -1 >/tmp/migtest_down.log 2>&1 || { cat /tmp/migtest_down.log; fail "downgrade -1 شکست خورد"; }
alembic upgrade head >/tmp/migtest_up2.log 2>&1 || { cat /tmp/migtest_up2.log; fail "upgrade مجدد شکست خورد"; }
log "✓ آخرین Migration برگشت‌پذیر است"

TABLES="$(run_psql -d "$TEST_DB" -tAc "\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'\"")"
log "✓ $TABLES جدول ساخته شد"
deactivate
echo -e "\033[1;32m[migtest] همه تست‌های Migration موفق بودند\033[0m"
