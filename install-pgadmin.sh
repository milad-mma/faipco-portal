#!/usr/bin/env bash
#
# نصب pgAdmin 4 برای مدیریت مستقیم دیتابیس PostgreSQL این پروژه — دقیقاً با
# همان معماری خودِ FAIPCO Portal (venv پایتون + Gunicorn + Nginx)، نه Apache
# (که یک Web Server کاملاً جدا و اضافه به سرور می‌آورد).
#
# ⚠️ فقط از IP های داخل شبکه محلی قابل‌دسترسی است — نه از طریق Reverse Proxy
# خارجی/اینترنت. یعنی این ابزار هرگز از بیرون شبکه شرکت در دسترس نیست، حتی
# اگر URL دقیقش را کسی حدس بزند.
#
# استفاده:
#   sudo bash install-pgadmin.sh --allowed-network 192.168.99.0/24 --admin-email you@company.com
#
set -euo pipefail

# ---------- تنظیمات پیش‌فرض (با فلگ یا Environment Variable قابل تغییر) ----------
PGADMIN_DIR="${FAIPCO_PGADMIN_DIR:-/opt/pgadmin4}"
PGADMIN_PORT="${FAIPCO_PGADMIN_PORT:-5050}"
# ⚠️ حتماً با --allowed-network رنج واقعی شبکه محلی خودتان را بدهید — این
# مقدار فقط یک نمونه رایج (192.168.x.x /24) است، نه لزوماً شبکه شما.
ALLOWED_NETWORK="${FAIPCO_PGADMIN_ALLOWED_NETWORK:-192.168.99.0/24}"
ADMIN_EMAIL="${FAIPCO_PGADMIN_ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${FAIPCO_PGADMIN_ADMIN_PASSWORD:-}"
SYSTEM_USER="pgadmin4"

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
[[ -n "$ADMIN_EMAIL" ]] || err "ایمیل حساب اولیه pgAdmin را با --admin-email بدهید."
if [[ -z "$ADMIN_PASSWORD" ]]; then
  ADMIN_PASSWORD="$(openssl rand -base64 18)"
  log "رمز عبور تصادفی تولید شد (پایین صفحه نشان داده می‌شود) — چون --admin-password داده نشد."
fi

log "شبکه مجاز برای دسترسی: ${ALLOWED_NETWORK} — از هر IP دیگری، حتی با URL درست، رد می‌شود."

# ---------- ۱. کاربر سیستمی جدا (ایزوله از www-data خودِ پرتال) ----------
mkdir -p "$PGADMIN_DIR"
if ! id "$SYSTEM_USER" &>/dev/null; then
  log "ساخت کاربر سیستمی $SYSTEM_USER"
  useradd --system --home-dir "$PGADMIN_DIR" --shell /usr/sbin/nologin "$SYSTEM_USER"
fi

# ---------- ۲. پیش‌نیازها ----------
log "نصب پیش‌نیازها"
apt-get update -qq
apt-get install -y -qq python3-venv python3-dev libpq-dev build-essential >/dev/null

# ---------- ۳. محیط مجازی + نصب pgAdmin4 ----------
log "ساخت Virtual Environment و نصب pgAdmin4 + Gunicorn"
python3 -m venv "$PGADMIN_DIR/venv"
"$PGADMIN_DIR/venv/bin/pip" install --upgrade pip --quiet
"$PGADMIN_DIR/venv/bin/pip" install pgadmin4 gunicorn --quiet

PGADMIN_PKG_DIR="$("$PGADMIN_DIR/venv/bin/python" -c "import pgadmin4, os; print(os.path.dirname(pgadmin4.__file__))")"
log "pgAdmin4 نصب شد در: $PGADMIN_PKG_DIR"

# ---------- ۴. دایرکتوری‌های داده ----------
mkdir -p /var/lib/pgadmin4/sessions /var/lib/pgadmin4/storage /var/log/pgadmin4
chown -R "$SYSTEM_USER:$SYSTEM_USER" /var/lib/pgadmin4 /var/log/pgadmin4 "$PGADMIN_DIR"

# ---------- ۵. فایل تنظیمات (config_local.py) ----------
log "نوشتن config_local.py"
cat > "$PGADMIN_PKG_DIR/config_local.py" <<EOF
SERVER_MODE = True
LOG_FILE = '/var/log/pgadmin4/pgadmin4.log'
SQLITE_PATH = '/var/lib/pgadmin4/pgadmin4.db'
SESSION_DB_PATH = '/var/lib/pgadmin4/sessions'
STORAGE_DIR = '/var/lib/pgadmin4/storage'
DEFAULT_SERVER = '127.0.0.1'
DEFAULT_SERVER_PORT = ${PGADMIN_PORT}
EOF
chown "$SYSTEM_USER:$SYSTEM_USER" "$PGADMIN_PKG_DIR/config_local.py"

# ---------- ۶. ساخت حساب اولیه (غیرتعاملی) ----------
log "ساخت حساب کاربری اولیه pgAdmin"
sudo -u "$SYSTEM_USER" "$PGADMIN_DIR/venv/bin/pgadmin4-cli" add-user "$ADMIN_EMAIL" "$ADMIN_PASSWORD" --admin \
  || log "⚠️  اگر این حساب از قبل وجود داشت، این پیام را نادیده بگیرید."

# ---------- ۷. سرویس systemd (Gunicorn) ----------
log "ساخت سرویس systemd"
cat > /etc/systemd/system/pgadmin4.service <<EOF
[Unit]
Description=pgAdmin 4 (مدیریت دیتابیس FAIPCO Portal — فقط شبکه محلی)
After=network.target postgresql.service

[Service]
Type=simple
User=${SYSTEM_USER}
Group=${SYSTEM_USER}
WorkingDirectory=${PGADMIN_DIR}
# فقط روی 127.0.0.1 — یعنی حتی اگر تنظیمات Nginx/Firewall یک‌جا اشتباه شود،
# خودِ Gunicorn هرگز مستقیم از بیرون این سرور در دسترس نیست.
ExecStart=${PGADMIN_DIR}/venv/bin/gunicorn --bind 127.0.0.1:${PGADMIN_PORT} --workers 2 --threads 4 --chdir ${PGADMIN_PKG_DIR} pgAdmin4:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pgadmin4 >/dev/null
systemctl restart pgadmin4

# ---------- ۸. Nginx — فقط شبکه محلی ----------
log "تنظیم Nginx (فقط شبکه محلی: ${ALLOWED_NETWORK})"
cat > /etc/nginx/sites-available/pgadmin4 <<EOF
# این سرور عمداً هیچ server_name عمومی/دامنه‌ای ندارد و هرگز از طریق
# Reverse Proxy خارجی پرتال routing نمی‌شود — فقط با آدرس IP داخلی همین
# سرور (مثلاً http://192.168.x.x:8080) از داخل شبکه محلی در دسترس است.
server {
    listen 8080;
    listen [::]:8080;

    # لایه اول دفاع: فقط شبکه محلی مجاز است — همه‌چیز دیگر رد می‌شود، حتی
    # اگر IP/Port درست را حدس بزند.
    allow ${ALLOWED_NETWORK};
    deny all;

    location / {
        proxy_pass http://127.0.0.1:${PGADMIN_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/pgadmin4 /etc/nginx/sites-enabled/pgadmin4
nginx -t
systemctl reload nginx

# ---------- ۹. فایروال — همان رنج شبکه محلی، نه بیشتر ----------
if command -v ufw &>/dev/null; then
  ufw allow from "$ALLOWED_NETWORK" to any port 8080 proto tcp comment "pgAdmin4 - local network only" >/dev/null
  log "قانون Firewall برای پورت 8080 (فقط از ${ALLOWED_NETWORK}) اضافه شد."
fi

SERVER_IP="$(hostname -I | awk '{print $1}')"
log "✅ نصب کامل شد"
echo ""
echo "آدرس دسترسی (فقط از داخل شبکه محلی): http://${SERVER_IP}:8080"
echo "ایمیل ورود: ${ADMIN_EMAIL}"
echo "رمز عبور: ${ADMIN_PASSWORD}"
echo ""
echo "⚠️ این رمز را همین الان در یک مکان امن (Password Manager) ذخیره کنید — دیگر نمایش داده نمی‌شود."
echo ""
echo "بعد از ورود، برای اتصال به دیتابیس خودِ پرتال، یک Server جدید در pgAdmin اضافه کنید:"
echo "  Host: localhost یا 127.0.0.1 (چون pgAdmin روی همین سرور نصب شده)"
echo "  Port: 5432"
echo "  Database/Username/Password: همان مقادیر backend/.env (DATABASE_URL) خودِ پرتال"
