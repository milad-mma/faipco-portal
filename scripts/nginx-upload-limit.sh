#!/usr/bin/env bash
# اعمال «سقف آپلود سرور» که از پنل (تنظیمات سامانه) تعیین شده روی nginx همین سرور — docs/upload-limit.md
#   bash scripts/nginx-upload-limit.sh apply
# مقدار (مگابایت) را از /var/lib/faipco/upload-limit-mb می‌خواند (پرتال آن را می‌نویسد؛ بدون آرگومان، تا قانون sudoers
# ثابت بماند)، در /etc/nginx/faipco-upload-limit.conf می‌نویسد، nginx -t و reload؛ اگر تست رد شد مقدار قبلی برمی‌گردد.
# از پنل با systemd-run به‌عنوان root اجرا می‌شود. لاگ: /var/log/faipco-upload-limit.log ([UPLOAD-LIMIT] START/RESULT).
set -uo pipefail

LOG="/var/log/faipco-upload-limit.log"
: > "$LOG"; chmod 644 "$LOG"
exec >>"$LOG" 2>&1
echo "[UPLOAD-LIMIT] START $(date '+%Y-%m-%d %H:%M:%S')"

VALUE_FILE="/var/lib/faipco/upload-limit-mb"
CONF="/etc/nginx/faipco-upload-limit.conf"
MIN=2
MAX=2048

finish() { echo "[UPLOAD-LIMIT] RESULT: $1"; exit 0; }

[[ "${1:-}" == "apply" ]] || { echo "عملیات نامعتبر"; finish FAIL; }
[[ -f "$VALUE_FILE" ]] || { echo "مقداری از پنل ثبت نشده است."; finish FAIL; }
value="$(tr -d '[:space:]' < "$VALUE_FILE")"
if ! [[ "$value" =~ ^[0-9]+$ ]] || (( value < MIN || value > MAX )); then
  echo "مقدار نامعتبر: «${value}» (باید عدد صحیح بین ${MIN} و ${MAX} مگابایت باشد)"
  finish FAIL
fi

backup=""
[[ -f "$CONF" ]] && backup="$(cat "$CONF")"
printf '# مدیریت‌شده از پنل پرتال (تنظیمات سامانه ← سقف آپلود سرور) — دستی تغییر ندهید\nclient_max_body_size %sm;\n' "$value" > "$CONF"
chmod 644 "$CONF"

if ! grep -q "faipco-upload-limit.conf" /etc/nginx/sites-available/faipco-portal 2>/dev/null; then
  echo "تنظیم nginx پرتال هنوز فایل سقف را include نمی‌کند (یک بار آپدیت پرتال لازم است)."
  [[ -n "$backup" ]] && printf '%s\n' "$backup" > "$CONF"
  finish FAIL
fi

if nginx -t; then
  systemctl reload nginx && { echo "سقف آپلود nginx: ${value} مگابایت"; finish OK; }
fi
echo "تست nginx رد شد؛ مقدار قبلی برگردانده شد."
if [[ -n "$backup" ]]; then printf '%s\n' "$backup" > "$CONF"; else rm -f "$CONF"; fi
nginx -t && systemctl reload nginx
finish FAIL
