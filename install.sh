#!/usr/bin/env bash
# ============================================================
# FAIPCO Portal — نصب خودکار روی Ubuntu Server (22.04 / 24.04)
#
# اجرا (نصب مستقیم از GitHub):
#   curl -fsSL https://raw.githubusercontent.com/USER/faipco-portal/main/install.sh | sudo bash
#
# یا به‌صورت محلی (وقتی ریپازیتوری از قبل Clone شده):
#   sudo bash install.sh
#
# آرگومان‌های اختیاری:
#   --domain example.com       دامنه (برای Nginx + SSL خودکار)
#   --no-ssl                   رد کردن مرحله SSL حتی اگر دامنه داده شده
#   --admin-username admin     نام کاربری Admin اولیه (پیش‌فرض: admin)
#   --admin-password '...'     رمز عبور Admin (اگر ندهید، تصادفی تولید می‌شود)
#   --install-dir /opt/xyz     مسیر نصب (پیش‌فرض: /opt/faipco-portal)
#   --repo <git-url>           آدرس ریپازیتوری (پیش‌فرض: همین ریپازیتوری)
#   --branch main              Branch مورد نظر
# ============================================================
set -euo pipefail

# ---------- مقادیر پیش‌فرض ----------
REPO_URL="${FAIPCO_REPO_URL:-https://github.com/USER/faipco-portal.git}"
REPO_BRANCH="${FAIPCO_BRANCH:-main}"
INSTALL_DIR="${FAIPCO_INSTALL_DIR:-/opt/faipco-portal}"
DOMAIN="${FAIPCO_DOMAIN:-}"
ADMIN_USERNAME="${FAIPCO_ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${FAIPCO_ADMIN_PASSWORD:-}"
SKIP_SSL="false"
DB_NAME="faipco_portal"
DB_USER="faipco_user"
BACKEND_PORT=8000

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[FAIPCO]${NC} $1"; }
warn() { echo -e "${YELLOW}[هشدار]${NC} $1"; }
err()  { echo -e "${RED}[خطا]${NC} $1" >&2; }

# ---------- پارس آرگومان‌ها ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --no-ssl) SKIP_SSL="true"; shift ;;
    --admin-username) ADMIN_USERNAME="$2"; shift 2 ;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    --branch) REPO_BRANCH="$2"; shift 2 ;;
    *) err "آرگومان ناشناخته: $1"; exit 1 ;;
  esac
done

require_root() {
  if [[ $EUID -ne 0 ]]; then
    err "این اسکریپت باید با دسترسی root یا sudo اجرا شود. مثال: sudo bash install.sh"
    exit 1
  fi
}

install_prerequisites() {
  log "به‌روزرسانی لیست پکیج‌ها و نصب پیش‌نیازها..."
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    curl git build-essential software-properties-common \
    python3 python3-venv python3-pip python3-dev \
    libpq-dev unixodbc unixodbc-dev freetds-dev freetds-bin \
    nginx ufw openssl ca-certificates
}

install_nodejs() {
  if command -v node >/dev/null 2>&1; then
    local major_version
    major_version="$(node -v | grep -oE '^v[0-9]+' | tr -d v)"
    if [[ "$major_version" -ge 18 ]]; then
      log "Node.js از قبل نصب است: $(node -v)"
      return
    fi
  fi
  log "نصب Node.js 20.x..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
}

install_postgresql() {
  if ! command -v psql >/dev/null 2>&1; then
    log "نصب PostgreSQL..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql postgresql-contrib
  else
    log "PostgreSQL از قبل نصب است."
  fi
  systemctl enable --now postgresql

  DB_PASSWORD="$(openssl rand -hex 16)"

  log "تنظیم کاربر و دیتابیس Portal در PostgreSQL..."
  if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
    sudo -u postgres psql -c "ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" >/dev/null
  else
    sudo -u postgres psql -c "CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';" >/dev/null
  fi

  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" >/dev/null
  fi
}

fetch_source() {
  if [[ -f "./backend/app/main.py" ]]; then
    log "اجرا از داخل ریپازیتوری تشخیص داده شد؛ از سورس محلی ($(pwd)) استفاده می‌شود."
    INSTALL_DIR="$(pwd)"
  else
    log "دریافت سورس از ${REPO_URL} (branch: ${REPO_BRANCH}) در ${INSTALL_DIR}..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    if [[ -d "$INSTALL_DIR/.git" ]]; then
      git -C "$INSTALL_DIR" fetch origin "$REPO_BRANCH"
      git -C "$INSTALL_DIR" reset --hard "origin/${REPO_BRANCH}"
    else
      git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
    fi
  fi
}

setup_backend() {
  log "ساخت Virtual Environment و نصب وابستگی‌های Backend..."
  cd "$INSTALL_DIR/backend"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
  deactivate
}

generate_env() {
  log "تولید فایل .env با کلیدهای امنیتی یکتا..."
  local secret_key fernet_key
  secret_key="$(openssl rand -hex 32)"
  fernet_key="$("$INSTALL_DIR/backend/.venv/bin/python" -c \
    "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")"

  local cors_origin="http://localhost"
  if [[ -n "$DOMAIN" ]]; then
    cors_origin="https://${DOMAIN}"
  fi

  cat > "$INSTALL_DIR/backend/.env" <<EOF
APP_NAME=FAIPCO Portal
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
SECRET_KEY=${secret_key}
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
DB_CREDENTIALS_ENCRYPTION_KEY=${fernet_key}
CORS_ORIGINS=["${cors_origin}"]
SYNC_ENABLED=true
SYNC_INTERVAL_MINUTES=30
EOF
  chmod 600 "$INSTALL_DIR/backend/.env"
}

run_migrations() {
  log "اجرای Migration های دیتابیس (Alembic)..."
  cd "$INSTALL_DIR/backend"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  alembic upgrade head
  deactivate
}

build_frontend() {
  log "نصب وابستگی‌ها و Build کردن Frontend (ممکن است چند دقیقه طول بکشد)..."
  cd "$INSTALL_DIR/frontend"
  echo "VITE_API_BASE_URL=/api/v1" > .env
  npm install --silent
  npm run build --silent
}

configure_systemd() {
  log "ساخت Service systemd برای Backend..."
  cat > /etc/systemd/system/faipco-backend.service <<EOF
[Unit]
Description=FAIPCO Portal Backend (FastAPI)
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${INSTALL_DIR}/backend
Environment="PATH=${INSTALL_DIR}/backend/.venv/bin"
ExecStart=${INSTALL_DIR}/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT} --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  chown -R www-data:www-data "$INSTALL_DIR"

  systemctl daemon-reload
  systemctl enable faipco-backend >/dev/null
  systemctl restart faipco-backend
}

configure_nginx() {
  log "پیکربندی Nginx..."
  local server_name="${DOMAIN:-_}"

  cat > /etc/nginx/sites-available/faipco-portal <<EOF
server {
    listen 80;
    server_name ${server_name};

    root ${INSTALL_DIR}/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

  ln -sf /etc/nginx/sites-available/faipco-portal /etc/nginx/sites-enabled/faipco-portal
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl reload nginx
}

setup_ssl() {
  if [[ "$SKIP_SSL" == "true" || -z "$DOMAIN" ]]; then
    warn "مرحله SSL رد شد (دامنه‌ای داده نشده یا --no-ssl فعال است). پرتال فقط روی HTTP در دسترس است."
    return
  fi
  log "نصب SSL رایگان (Let's Encrypt) برای دامنه ${DOMAIN}..."
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot python3-certbot-nginx
  if ! certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@${DOMAIN}" --redirect; then
    warn "صدور خودکار SSL ناموفق بود (احتمالاً DNS دامنه هنوز به این سرور اشاره نمی‌کند)."
    warn "بعداً می‌توانید دستی اجرا کنید: certbot --nginx -d ${DOMAIN}"
  fi
}

seed_and_create_admin() {
  log "Seed اولیه Permission ها و نقش‌های سیستمی..."
  cd "$INSTALL_DIR"
  # shellcheck disable=SC1091
  source backend/.venv/bin/activate
  python -m scripts.seed_permissions

  if [[ -z "$ADMIN_PASSWORD" ]]; then
    ADMIN_PASSWORD="$(openssl rand -base64 12)"
  fi
  log "ساخت کاربر Admin اولیه..."
  python -m scripts.create_admin --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD"
  deactivate
}

configure_firewall() {
  log "تنظیم فایروال (UFW)..."
  ufw allow OpenSSH >/dev/null 2>&1 || true
  ufw allow 'Nginx Full' >/dev/null 2>&1 || true
  ufw --force enable >/dev/null 2>&1 || true
}

print_summary() {
  local url="http://$(hostname -I | awk '{print $1}')"
  if [[ -n "$DOMAIN" ]]; then
    if [[ "$SKIP_SSL" == "true" ]]; then
      url="http://${DOMAIN}"
    else
      url="https://${DOMAIN}"
    fi
  fi

  echo ""
  echo -e "${GREEN}=============================================="
  echo -e " نصب FAIPCO Portal با موفقیت به پایان رسید ✅"
  echo -e "==============================================${NC}"
  echo -e " آدرس پرتال:        ${url}"
  echo -e " نام کاربری Admin:   ${ADMIN_USERNAME}"
  echo -e " رمز عبور Admin:     ${ADMIN_PASSWORD}"
  echo -e " مسیر نصب:           ${INSTALL_DIR}"
  echo -e " فایل تنظیمات:        ${INSTALL_DIR}/backend/.env"
  echo ""
  echo -e "${YELLOW}⚠ این رمز عبور را همین الان در جای امنی ذخیره کنید — دیگر نمایش داده نمی‌شود.${NC}"
  echo ""
  echo " دستورات مفید:"
  echo "   systemctl status faipco-backend    # وضعیت سرویس Backend"
  echo "   journalctl -u faipco-backend -f    # مشاهده لاگ زنده Backend"
  echo "   systemctl restart faipco-backend   # ری‌استارت Backend بعد از تغییر .env"
  echo ""
}

main() {
  require_root
  log "شروع نصب FAIPCO Portal..."
  install_prerequisites
  install_nodejs
  install_postgresql
  fetch_source
  setup_backend
  generate_env
  run_migrations
  build_frontend
  configure_systemd
  configure_nginx
  setup_ssl
  seed_and_create_admin
  configure_firewall
  print_summary
}

main "$@"
