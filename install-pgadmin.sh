#!/usr/bin/env bash
#
# نصب pgAdmin 4 با ایمیج رسمی Docker خودِ تیم pgAdmin (dpage/pgadmin4) —
# بعد از چند مشکل پیاپی در نصب دستی با pip+Gunicorn (کندی نصب، عدم ساخت
# خودکار دیتابیس تنظیمات، تداخل CSRF/Cookie پشت Reverse Proxy)، به روش
# رسمی و پرکاربردترین روش نصب خودِ این پروژه سوییچ شد — چون این ایمیج
# مستقیماً توسط تیم pgAdmin نگه‌داری می‌شود و تمام این مسیرها/تنظیمات را
# از قبل درست پیکربندی کرده.
#
# ⚠️ فقط از IP های داخل شبکه محلی قابل‌دسترسی است — نه از طریق Reverse Proxy
# خارجی/اینترنت.
#
# استفاده:
#   sudo bash install-pgadmin.sh --allowed-network 192.168.99.0/24 --admin-email you@company.com
#
set -euo pipefail

PGADMIN_PORT="${FAIPCO_PGADMIN_PORT:-5050}"
# ⚠️ حتماً با --allowed-network رنج واقعی شبکه محلی خودتان را بدهید.
ALLOWED_NETWORK="${FAIPCO_PGADMIN_ALLOWED_NETWORK:-192.168.99.0/24}"
ADMIN_EMAIL="${FAIPCO_PGADMIN_ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${FAIPCO_PGADMIN_ADMIN_PASSWORD:-}"
DATA_DIR="${FAIPCO_PGADMIN_DATA_DIR:-/opt/pgadmin4-data}"

log() { echo -e "\n\033[1;34m[pgAdmin]\033[0m $1"; }
err() { echo -e "\033[1;31m[خطا]\033[0m $1" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allowed-network) ALLOWED_NETWORK="$2"; shift 2 ;;
    --port) PGADMIN_PORT="$2"; shift 2 ;;
    --admin-email) ADMIN_EMAIL="$2"; shift 2 ;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
    *) err "پارامتر ناشناخته: $1" ;;
  esac
done

[[ $EUID -eq 0 ]] || err "این اسکریپت باید با sudo/root اجرا شود."

if [[ -z "$ADMIN_EMAIL" ]]; then
  read -rp "ایمیل حساب ورود به pgAdmin: " ADMIN_EMAIL
fi
[[ -n "$ADMIN_EMAIL" ]] || err "ایمیل نمی‌تواند خالی باشد."

if [[ -z "$ADMIN_PASSWORD" ]]; then
  read -rsp "رمز عبور (اگر خالی بگذارید و Enter بزنید، یک رمز تصادفی ساخته می‌شود): " ADMIN_PASSWORD
  echo ""
fi
if [[ -z "$ADMIN_PASSWORD" ]]; then
  ADMIN_PASSWORD="$(openssl rand -base64 18)"
  log "رمز عبور تصادفی تولید شد (پایین صفحه نشان داده می‌شود)."
fi

log "شبکه مجاز برای دسترسی: ${ALLOWED_NETWORK} — از هر IP دیگری، حتی با URL درست، رد می‌شود."

# ---------- ۱. نصب Docker (اگر از قبل نصب نیست) ----------
if ! command -v docker &>/dev/null; then
  log "نصب Docker (بسته docker.io از مخزن رسمی Ubuntu — ساده و کافی برای یک کانتینر)"
  apt-get update -qq
  apt-get install -y -qq docker.io >/dev/null
  systemctl enable --now docker >/dev/null
else
  log "Docker از قبل نصب است"
fi

# ---------- ۲. حذف نصب/کانتینر قبلی (اگر این اسکریپت قبلاً اجرا شده) ----------
if docker ps -a --format '{{.Names}}' | grep -qx pgadmin4; then
  log "حذف کانتینر قبلی pgadmin4 (داده‌های قبلی در ${DATA_DIR} دست‌نخورده می‌ماند)"
  docker rm -f pgadmin4 >/dev/null
fi

# ---------- ۳. دایرکتوری داده روی Host (برای ماندگاری بعد از هر Restart) ----------
mkdir -p "$DATA_DIR"
# UID/GID داخل ایمیج رسمی pgAdmin برابر 5050 است — طبق مستندات رسمی خودشان
chown -R 5050:5050 "$DATA_DIR"

# ---------- ۴. اجرای کانتینر ----------
# ⚠️ عمداً --network=host (نه Bridge پیش‌فرض داکر) — چون PostgreSQL خودِ
# پرتال روی خودِ این سرور نصب است (نه در یک کانتینر دیگر)؛ با شبکه Bridge
# پیش‌فرض، «localhost» داخل کانتینر به خودِ کانتینر اشاره می‌کرد نه به این
# سرور، و اتصال کانتینر به PostgreSQL میزبان می‌توانست کاملاً غیرقابل‌اعتماد
# باشد (یک مشکل واقعی و مستندشده، حتی در بحث‌های رسمی جامعه). با
# --network=host، این کانتینر دقیقاً همان Namespace شبکه‌ای خودِ سرور را
# به اشتراک می‌گذارد — یعنی localhost:5432 دقیقاً همانی است که در نصب
# مستقیم (غیر Docker) هم بود.
#
# چون با --network=host نگاشت پورت (-p) اصلاً معنا ندارد (پورت‌ها مستقیم
# روی شبکه میزبان باز می‌شوند)، پورت داخلی pgAdmin با PGADMIN_LISTEN_PORT
# مستقیم به همان پورتی تنظیم می‌شود که می‌خواهیم (تا با چیز دیگری، مثلاً
# پورت ۸۰ خودِ Nginx پرتال، تداخل نکند) — طبق مستندات رسمی pgAdmin4:
# https://www.pgadmin.org/docs/pgadmin4/latest/container_deployment.html
log "اجرای کانتینر pgAdmin4"
docker run \
  --name pgadmin4 \
  --restart=always \
  --network=host \
  -e "PGADMIN_LISTEN_PORT=${PGADMIN_PORT}" \
  -e "PGADMIN_DEFAULT_EMAIL=${ADMIN_EMAIL}" \
  -e "PGADMIN_DEFAULT_PASSWORD=${ADMIN_PASSWORD}" \
  -v "${DATA_DIR}:/var/lib/pgadmin" \
  -d dpage/pgadmin4:latest >/dev/null

# ---------- ۵. فایروال — تنها لایه محدودیت IP (چون --network=host نگاشت IP-محور ندارد) ----------
if command -v ufw &>/dev/null; then
  ufw allow from "$ALLOWED_NETWORK" to any port "$PGADMIN_PORT" proto tcp comment "pgAdmin4 - local network only" >/dev/null
  log "قانون Firewall برای پورت ${PGADMIN_PORT} (فقط از ${ALLOWED_NETWORK}) اضافه شد."
else
  log "⚠️ ufw پیدا نشد — حتماً با iptables یا فایروال دیگری همین محدودیت را دستی اعمال کنید."
fi

SERVER_IP="$(hostname -I | awk '{print $1}')"
log "✅ نصب کامل شد — منتظر بمانید ۱۰-۲۰ ثانیه تا کانتینر کاملاً بالا بیاید"
echo ""
echo "آدرس دسترسی (فقط از داخل شبکه محلی): http://${SERVER_IP}:${PGADMIN_PORT}"
echo "ایمیل ورود: ${ADMIN_EMAIL}"
echo "رمز عبور: ${ADMIN_PASSWORD}"
echo ""
echo "⚠️ این رمز را همین الان در یک مکان امن (Password Manager) ذخیره کنید — دیگر نمایش داده نمی‌شود."
echo ""
echo "بعد از ورود، برای اتصال به دیتابیس خودِ پرتال، یک Server جدید در pgAdmin اضافه کنید:"
echo "  Host: localhost یا 127.0.0.1 (چون با --network=host، دقیقاً مثل نصب مستقیم کار می‌کند)"
echo "  Port: 5432"
echo "  Database/Username/Password: همان مقادیر backend/.env (DATABASE_URL) خودِ پرتال"
echo ""
echo "برای دیدن وضعیت یا لاگ کانتینر:"
echo "  docker ps | grep pgadmin4"
echo "  docker logs pgadmin4"
