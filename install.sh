#!/usr/bin/env bash
# ============================================================
# FAIPCO Portal — نصب خودکار روی Ubuntu Server (22.04 / 24.04)
#
# اجرای یک‌دستوری:
#   curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh | sudo bash
#
# آرگومان‌های اختیاری:
#   --domain example.com        دامنه (برای Nginx + SSL خودکار)
#   --no-ssl                    رد کردن مرحله SSL
#   --admin-username admin       نام کاربری Admin (پیش‌فرض: admin)
#   --admin-password '...'      رمز عبور Admin (اگر ندهید، تصادفی)
# ============================================================
set -euo pipefail

# ─── رنگ و لاگ ────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[FAIPCO]${NC} $1"; }
warn() { echo -e "${YELLOW}[هشدار]${NC} $1"; }
err()  { echo -e "${RED}[خطا]${NC} $1" >&2; exit 1; }
step() { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

# ─── مقادیر پیش‌فرض ────────────────────────────────────────
REPO_URL="https://github.com/milad-mma/faipco-portal.git"
REPO_BRANCH="main"
INSTALL_DIR="/var/www/html"          # ← کل ریپو مستقیم اینجا clone می‌شود
DOMAIN=""
ADMIN_USERNAME="admin"
ADMIN_PASSWORD=""
SKIP_SSL="false"
DB_NAME="faipco_portal"
DB_USER="faipco_user"
DB_PASSWORD=""
BACKEND_PORT=8000

# ─── پارس آرگومان ─────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)         DOMAIN="$2";         shift 2 ;;
        --no-ssl)         SKIP_SSL="true";     shift   ;;
        --admin-username) ADMIN_USERNAME="$2"; shift 2 ;;
        --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
        *) err "آرگومان ناشناخته: $1" ;;
    esac
done

LOG_FILE="/var/log/faipco-install.log"
exec > >(tee -a "$LOG_FILE") 2>&1
log "شروع نصب FAIPCO Portal... (لاگ کامل در $LOG_FILE ذخیره می‌شود)"

# ─── بررسی root ───────────────────────────────────────────
[[ $EUID -ne 0 ]] && err "با sudo اجرا کنید: sudo bash install.sh"

# ─── تولید رمز DB ─────────────────────────────────────────
DB_PASSWORD="$(openssl rand -hex 16)"

# ═══════════════════════════════════════════════════════════
step "مرحله ۱ — نصب پیش‌نیازها"
# ═══════════════════════════════════════════════════════════
log "به‌روزرسانی لیست پکیج‌ها و نصب پیش‌نیازها..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    curl git build-essential software-properties-common \
    python3 python3-venv python3-pip python3-dev \
    libpq-dev \
    nginx ufw openssl ca-certificates

# ─── Node.js ──────────────────────────────────────────────
if command -v node &>/dev/null && [[ "$(node -v | grep -oE '[0-9]+' | head -1)" -ge 18 ]]; then
    log "Node.js از قبل نصب است: $(node -v)"
else
    log "نصب Node.js 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
fi

# ─── PostgreSQL ────────────────────────────────────────────
if ! command -v psql &>/dev/null; then
    log "نصب PostgreSQL..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql postgresql-contrib
else
    log "PostgreSQL از قبل نصب است."
fi
systemctl enable --now postgresql
sleep 2

log "تنظیم کاربر و دیتابیس Portal در PostgreSQL..."
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
    sudo -u postgres psql -c "ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" >/dev/null
else
    sudo -u postgres psql -c "CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';" >/dev/null
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" >/dev/null
fi

# ═══════════════════════════════════════════════════════════
step "مرحله ۲ — دریافت سورس‌کد"
# ═══════════════════════════════════════════════════════════

# اگر از داخل ریپو اجرا می‌شود (clone قبلاً انجام شده)
if [[ -f "${INSTALL_DIR}/backend/app/main.py" ]]; then
    log "سورس از قبل در ${INSTALL_DIR} وجود دارد. به‌روزرسانی..."
    git -C "$INSTALL_DIR" fetch origin "$REPO_BRANCH" --quiet
    git -C "$INSTALL_DIR" reset --hard "origin/${REPO_BRANCH}" --quiet
else
    log "دریافت سورس از ${REPO_URL} در ${INSTALL_DIR}..."
    # اگر .git وجود ندارد از ابتدا clone کن
    if [[ -d "${INSTALL_DIR}/.git" ]]; then
        git -C "$INSTALL_DIR" fetch origin "$REPO_BRANCH" --quiet
        git -C "$INSTALL_DIR" reset --hard "origin/${REPO_BRANCH}" --quiet
    else
        # حذف محتوای قدیمی (نه خود /var/www/html) و clone مستقیم
        rm -rf "${INSTALL_DIR}/backend" "${INSTALL_DIR}/frontend" \
               "${INSTALL_DIR}/scripts" "${INSTALL_DIR}/database" \
               "${INSTALL_DIR}/docs" "${INSTALL_DIR}/install.sh" \
               "${INSTALL_DIR}/README.md" 2>/dev/null || true

        # clone به یک temp و انتقال فایل‌ها
        TMP_DIR="$(mktemp -d)"
        git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$TMP_DIR" --quiet
        cp -a "$TMP_DIR/." "$INSTALL_DIR/"
        rm -rf "$TMP_DIR"
    fi
fi

log "سورس‌کد آماده است در: ${INSTALL_DIR}"

# ═══════════════════════════════════════════════════════════
step "مرحله ۳ — راه‌اندازی Backend"
# ═══════════════════════════════════════════════════════════
cd "${INSTALL_DIR}/backend"
log "ساخت Virtual Environment و نصب وابستگی‌های Backend..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
log "وابستگی‌های Backend نصب شدند"

# ═══════════════════════════════════════════════════════════
step "مرحله ۴ — تولید فایل .env"
# ═══════════════════════════════════════════════════════════
log "تولید فایل .env با کلیدهای امنیتی یکتا..."
SECRET_KEY="$(openssl rand -hex 32)"
FERNET_KEY="$("${INSTALL_DIR}/backend/.venv/bin/python" -c \
    "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")"
CORS_ORIGIN="http://localhost"
[[ -n "$DOMAIN" ]] && CORS_ORIGIN="https://${DOMAIN}"

cat > "${INSTALL_DIR}/backend/.env" << EOF
APP_NAME=FAIPCO Portal
APP_ENV=production
DEBUG=false

DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}

SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

DB_CREDENTIALS_ENCRYPTION_KEY=${FERNET_KEY}

CORS_ORIGINS=["${CORS_ORIGIN}","http://localhost:3000"]

SYNC_ENABLED=true
SYNC_INTERVAL_MINUTES=30
EOF
chmod 600 "${INSTALL_DIR}/backend/.env"
log "فایل .env ساخته شد"

# ═══════════════════════════════════════════════════════════
step "مرحله ۵ — Migration های دیتابیس"
# ═══════════════════════════════════════════════════════════
cd "${INSTALL_DIR}/backend"
log "اجرای Alembic migrations..."
.venv/bin/alembic upgrade head
log "جداول دیتابیس ساخته شدند ✔"

# ═══════════════════════════════════════════════════════════
step "مرحله ۶ — Seed و ساخت Admin"
# ═══════════════════════════════════════════════════════════
cd "${INSTALL_DIR}"
log "Seed اولیه Permission های سیستمی..."

# seed_permissions را با PYTHONPATH درست اجرا می‌کنیم
PYTHONPATH="${INSTALL_DIR}/backend" \
    "${INSTALL_DIR}/backend/.venv/bin/python" \
    -m scripts.seed_permissions

[[ -z "$ADMIN_PASSWORD" ]] && ADMIN_PASSWORD="$(openssl rand -base64 12 | tr -d '=+/' | head -c 12)"

log "ساخت کاربر Admin اولیه: ${ADMIN_USERNAME}"
PYTHONPATH="${INSTALL_DIR}/backend" \
    "${INSTALL_DIR}/backend/.venv/bin/python" \
    -m scripts.create_admin \
    --username "$ADMIN_USERNAME" \
    --password "$ADMIN_PASSWORD"

# ═══════════════════════════════════════════════════════════
step "مرحله ۷ — Build Frontend"
# ═══════════════════════════════════════════════════════════
cd "${INSTALL_DIR}/frontend"
log "نصب وابستگی‌های Frontend..."
echo "VITE_API_BASE_URL=/api/v1" > .env.production
npm install --silent --no-audit 2>/dev/null
log "Build کردن Frontend (ممکن است چند دقیقه طول بکشد)..."
npm run build --silent 2>/dev/null
log "Frontend build شد ✔"

# ═══════════════════════════════════════════════════════════
step "مرحله ۸ — سرویس systemd"
# ═══════════════════════════════════════════════════════════
log "ساخت Service systemd برای Backend..."
cat > /etc/systemd/system/faipco-backend.service << EOF
[Unit]
Description=FAIPCO Portal Backend (FastAPI)
Documentation=https://github.com/milad-mma/faipco-portal
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${INSTALL_DIR}/backend
EnvironmentFile=${INSTALL_DIR}/backend/.env
Environment="PATH=${INSTALL_DIR}/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=${INSTALL_DIR}/backend/.venv/bin/uvicorn app.main:app \\
    --host 127.0.0.1 \\
    --port ${BACKEND_PORT} \\
    --workers 2 \\
    --log-level info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=faipco-backend

[Install]
WantedBy=multi-user.target
EOF

# دسترسی‌ها
chown -R www-data:www-data "${INSTALL_DIR}"
chmod 600 "${INSTALL_DIR}/backend/.env"
chmod -R 755 "${INSTALL_DIR}/frontend/dist"

systemctl daemon-reload
systemctl enable faipco-backend --now
sleep 4

if systemctl is-active --quiet faipco-backend; then
    log "سرویس Backend فعال و در حال اجراست ✔"
else
    warn "سرویس Backend بلافاصله شروع نشد. لاگ آخر:"
    journalctl -u faipco-backend --no-pager -n 30
fi

# ═══════════════════════════════════════════════════════════
step "مرحله ۹ — پیکربندی Nginx"
# ═══════════════════════════════════════════════════════════
log "پیکربندی Nginx..."
SERVER_NAME="${DOMAIN:-_}"

cat > /etc/nginx/sites-available/faipco-portal << EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${SERVER_NAME};

    root ${INSTALL_DIR}/frontend/dist;
    index index.html;

    client_max_body_size 20M;
    access_log /var/log/nginx/faipco-access.log;
    error_log  /var/log/nginx/faipco-error.log;

    # Backend API
    location /api/ {
        proxy_pass         http://127.0.0.1:${BACKEND_PORT}/api/;
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_set_header   Connection        "";
        proxy_connect_timeout 60s;
        proxy_read_timeout    120s;
    }

    # React SPA
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Static assets with long cache
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Block hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF

ln -sf /etc/nginx/sites-available/faipco-portal /etc/nginx/sites-enabled/faipco-portal
rm -f /etc/nginx/sites-enabled/default

if nginx -t 2>/dev/null; then
    systemctl enable nginx --now
    systemctl reload nginx
    log "Nginx پیکربندی شد ✔"
else
    err "کانفیگ Nginx دارای خطاست: nginx -t"
fi

# ═══════════════════════════════════════════════════════════
step "مرحله ۱۰ — SSL (اختیاری)"
# ═══════════════════════════════════════════════════════════
if [[ "$SKIP_SSL" == "true" || -z "$DOMAIN" ]]; then
    warn "مرحله SSL رد شد. پرتال فقط روی HTTP در دسترس است."
    warn "برای فعال‌سازی SSL بعداً اجرا کنید: certbot --nginx -d ${DOMAIN:-yourdomain.com}"
else
    log "نصب SSL رایگان برای ${DOMAIN}..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot python3-certbot-nginx
    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
               -m "admin@${DOMAIN}" --redirect 2>/dev/null; then
        log "SSL برای ${DOMAIN} فعال شد ✔"
    else
        warn "صدور SSL ناموفق بود (DNS ممکن است هنوز به این سرور اشاره نکند)."
        warn "بعداً دستی اجرا کنید: certbot --nginx -d ${DOMAIN}"
    fi
fi

# ─── فایروال ──────────────────────────────────────────────
ufw allow OpenSSH      >/dev/null 2>&1 || true
ufw allow 'Nginx Full' >/dev/null 2>&1 || true
ufw --force enable     >/dev/null 2>&1 || true

# ═══════════════════════════════════════════════════════════
# خلاصه نصب
# ═══════════════════════════════════════════════════════════
SERVER_IP="$(hostname -I | awk '{print $1}')"
if [[ -n "$DOMAIN" && "$SKIP_SSL" != "true" ]]; then
    PORTAL_URL="https://${DOMAIN}"
else
    PORTAL_URL="http://${SERVER_IP}"
fi

BACKEND_OK=false; NGINX_OK=false
systemctl is-active --quiet faipco-backend && BACKEND_OK=true
systemctl is-active --quiet nginx && NGINX_OK=true

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   نصب FAIPCO Portal با موفقیت به پایان رسید ✅   ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  🌐  آدرس پرتال:       ${CYAN}${PORTAL_URL}${NC}"
echo -e "  📁  مسیر نصب:         ${INSTALL_DIR}"
echo -e "  📄  فایل تنظیمات:     ${INSTALL_DIR}/backend/.env"
echo ""
echo -e "  👤  نام کاربری Admin: ${YELLOW}${ADMIN_USERNAME}${NC}"
echo -e "  🔑  رمز عبور Admin:   ${YELLOW}${ADMIN_PASSWORD}${NC}"
echo ""
echo -e "  سرویس Backend:  $($BACKEND_OK && echo "${GREEN}فعال ✔${NC}" || echo "${RED}مشکل ✘${NC}")"
echo -e "  سرویس Nginx:   $($NGINX_OK   && echo "${GREEN}فعال ✔${NC}" || echo "${RED}مشکل ✘${NC}")"
echo ""
echo -e "${YELLOW}⚠  رمز عبور Admin را همین الان ذخیره کنید!${NC}"
echo ""
echo "  دستورات مفید:"
echo "  ──────────────────────────────────────────────"
echo "  systemctl status faipco-backend     # وضعیت Backend"
echo "  journalctl -u faipco-backend -f     # لاگ زنده"
echo "  systemctl restart faipco-backend    # ری‌استارت"
echo "  ${PORTAL_URL}/api/docs              # مستندات API"
echo ""
