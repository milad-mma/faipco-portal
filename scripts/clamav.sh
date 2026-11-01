#!/usr/bin/env bash
# مدیریت ClamAV از پنل (اتوماسیون اداری ← تنظیمات ← اسکنر) — docs/office-automation.md
#   bash scripts/clamav.sh install     نصب clamav و clamav-daemon، تنظیم clamd، دریافت بانک، روشن کردن سرویس‌ها
#   bash scripts/clamav.sh update-db   دریافت/به‌روزرسانی بانک شناسایی (قفل «cool-down» قبلی freshclam برداشته می‌شود)
#   bash scripts/clamav.sh start       روشن کردن clamd و به‌روزرسانی خودکار بانک (حدود ۱ تا ۱.۵ گیگابایت RAM)
#   bash scripts/clamav.sh stop        خاموش و غیرفعال کردن هر دو سرویس (بدون مصرف RAM)
# از پنل با systemd-run به‌عنوان root اجرا می‌شود (قانون sudoers در install.sh). خروجی: /var/log/faipco-clamav.log
# با نشانگرهای [CLAMAV] START و [CLAMAV] RESULT: OK|FAIL تا پنل پایان را تشخیص دهد.
set -uo pipefail

ACTION="${1:-}"
LOG="/var/log/faipco-clamav.log"
: > "$LOG"; chmod 644 "$LOG"
exec >>"$LOG" 2>&1
echo "[CLAMAV] START ${ACTION} $(date '+%Y-%m-%d %H:%M:%S')"

DB_DIR="/var/lib/clamav"
CONF="/etc/clamav/clamd.conf"

finish() {
  echo "[CLAMAV] RESULT: $1"
  exit 0
}

has_db() {
  ls "$DB_DIR"/main.cvd "$DB_DIR"/main.cld >/dev/null 2>&1 && ls "$DB_DIR"/daily.cvd "$DB_DIR"/daily.cld >/dev/null 2>&1
}

clamd_set() {
  local key="$1" value="$2"
  [[ -f "$CONF" ]] || return 0
  if grep -qE "^${key}[[:space:]]" "$CONF"; then
    sed -i -E "s|^${key}[[:space:]].*|${key} ${value}|" "$CONF"
  else
    echo "${key} ${value}" >> "$CONF"
  fi
}

fetch_db() {
  # freshclam بعد از خطای 403/429 تا ۲۴ ساعت خودش تلاش نمی‌کند (freshclam.dat)؛ از پنل یعنی «همین الان امتحان کن»
  systemctl stop clamav-freshclam >/dev/null 2>&1 || true
  rm -f "$DB_DIR/freshclam.dat"
  echo "دریافت بانک شناسایی (ممکن است چند دقیقه طول بکشد)…"
  if timeout 1200 freshclam --stdout; then
    echo "بانک شناسایی دریافت/به‌روز شد."
  else
    echo "دریافت بانک ناموفق بود. اگر خطای 403 دیده می‌شود، سرور ClamAV این IP را مسدود کرده است (اتصال VPN را بررسی کنید)."
  fi
  ls -la "$DB_DIR"
}

case "$ACTION" in
  install)
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq || true
    if ! apt-get install -y -qq clamav clamav-daemon; then
      echo "نصب بسته‌های ClamAV ناموفق بود."
      finish FAIL
    fi
    clamd_set StreamMaxLength 100M
    clamd_set AlertOLE2Macros yes
    clamd_set LocalSocketMode 666
    fetch_db
    if has_db; then
      systemctl enable --now clamav-freshclam clamav-daemon
      sleep 20
      systemctl is-active clamav-daemon && finish OK
      echo "clamd روشن نشد؛ journalctl -u clamav-daemon را ببینید."
      finish FAIL
    fi
    # بدون بانک، clamd روشن نمی‌شود؛ سرویس‌ها خاموش می‌مانند تا «دریافت بانک» از پنل
    systemctl disable --now clamav-freshclam clamav-daemon >/dev/null 2>&1 || true
    echo "ClamAV نصب شد ولی بانک شناسایی دریافت نشد؛ بعد از برقراری VPN «دریافت بانک» را بزنید."
    finish FAIL
    ;;
  update-db)
    command -v freshclam >/dev/null || { echo "ClamAV نصب نیست."; finish FAIL; }
    was_active=false
    systemctl is-active --quiet clamav-daemon && was_active=true
    fetch_db
    has_db || finish FAIL
    if $was_active; then
      systemctl restart clamav-daemon
      systemctl start clamav-freshclam >/dev/null 2>&1 || true
    fi
    finish OK
    ;;
  start)
    command -v clamd >/dev/null || [[ -x /usr/sbin/clamd ]] || { echo "ClamAV نصب نیست."; finish FAIL; }
    has_db || { echo "بانک شناسایی وجود ندارد؛ اول «دریافت بانک» را بزنید."; finish FAIL; }
    systemctl enable --now clamav-freshclam clamav-daemon
    sleep 20
    systemctl is-active clamav-daemon && finish OK
    journalctl -u clamav-daemon -n 20 --no-pager
    finish FAIL
    ;;
  stop)
    systemctl disable --now clamav-daemon clamav-freshclam >/dev/null 2>&1 || true
    echo "ClamAV خاموش شد (بدون مصرف RAM)."
    finish OK
    ;;
  *)
    echo "عملیات نامعتبر: ${ACTION}"
    finish FAIL
    ;;
esac
