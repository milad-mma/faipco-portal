#!/usr/bin/env bash
# ============================================================
# FAIPCO Portal — نصب خودکار روی Ubuntu Server (22.04 / 24.04)
#
# اجرا (نصب مستقیم از GitHub):
#   curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh | sudo bash
#
# یا به‌صورت محلی (وقتی ریپازیتوری از قبل Clone شده):
#   sudo bash install.sh
#
# آرگومان‌های اختیاری:
#   --domain example.com          دامنه (برای Nginx + SSL خودکار)
#   --no-ssl                      رد کردن مرحله SSL حتی اگر دامنه داده شده
#   --admin-username admin        نام کاربری Admin اولیه (پیش‌فرض: admin)
#   --admin-password '...'        رمز عبور Admin (پیش‌فرض: admin — برای Production عوضش کنید)
#   --install-dir /var/www/html   مسیر نصب (پیش‌فرض: /var/www/html)
#   --repo <git-url>              آدرس ریپازیتوری
#   --branch main                 Branch مورد نظر
#
# لاگ کامل این نصب همیشه در /var/log/faipco-install.log ذخیره می‌شود —
# در صورت بروز هر مشکلی، همان فایل را برای Troubleshooting بررسی کنید.
# ============================================================
set -euo pipefail

# ---------- مقادیر پیش‌فرض ----------
REPO_URL="${FAIPCO_REPO_URL:-https://github.com/milad-mma/faipco-portal.git}"
REPO_BRANCH="${FAIPCO_BRANCH:-main}"
INSTALL_DIR="${FAIPCO_INSTALL_DIR:-/var/www/html}"
DOMAIN="${FAIPCO_DOMAIN:-}"
ADMIN_USERNAME="${FAIPCO_ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${FAIPCO_ADMIN_PASSWORD:-admin}"
SKIP_SSL="false"
DB_NAME="faipco_portal"
DB_USER="faipco_user"
BACKEND_PORT=8000
LOG_FILE="/var/log/faipco-install.log"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
log()   { echo -e "${GREEN}[FAIPCO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[هشدار]${NC} $1"; }
err()   { echo -e "${RED}[خطا]${NC} $1" >&2; }
stage() { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

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

# ---------- ثبت کامل خروجی در فایل لاگ (برای Troubleshooting) ----------
setup_logging() {
  touch "$LOG_FILE"
  exec > >(tee -a "$LOG_FILE") 2>&1
}

# اگر هر دستوری با خطا مواجه شود، دقیقاً بگو کدام خط بوده — به‌جای توقف بی‌صدا
on_error() {
  local exit_code=$?
  local line_no=$1
  err "نصب در خط ${line_no} با خطا متوقف شد (کد خروج: ${exit_code})."
  err "برای مشاهده جزئیات کامل: cat ${LOG_FILE}"
  exit "$exit_code"
}
trap 'on_error $LINENO' ERR

# ---------- ایجاد Swap در صورت کمبود RAM ----------
ensure_swap() {
  local total_mem_mb existing_swap_mb
  total_mem_mb="$(free -m | awk '/^Mem:/{print $2}')"
  existing_swap_mb="$(free -m | awk '/^Swap:/{print $2}')"

  if [[ "$total_mem_mb" -lt 2000 && "$existing_swap_mb" -lt 1 ]]; then
    warn "RAM سرور کم است (${total_mem_mb}MB) و Swap فعال نیست — فایل Swap موقت ساخته می‌شود."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
    grep -q "^/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
    log "Swap با موفقیت فعال شد."
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
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
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

# ---------- پاک‌سازی خودکار دیتابیس نیمه‌کاره از یک اجرای قبلی ناموفق ----------
# اگر جدول‌هایی در دیتابیس هست ولی جدول alembic_version نیست، یعنی یک اجرای
# قبلی وسط Migration متوقف شده (مثلاً به‌خاطر مشکل بعدی مثل Build فرانت‌اند).
# در این حالت، تلاش دوباره برای اجرای همان Migration خطای «از قبل وجود دارد»
# می‌دهد (برای Enum/Type ها). پس اسکیمای ناقص را کامل پاک می‌کنیم تا Migration
# از صفر و تمیز اجرا شود. این کار هیچ داده‌ای را که واقعاً استفاده شده از بین
# نمی‌برد، چون فقط زمانی اجرا می‌شود که Migration قبلی اصلاً کامل نشده باشد.
reset_stale_schema_if_needed() {
  local has_alembic_version has_other_tables
  has_alembic_version="$(sudo -u postgres psql -d "$DB_NAME" -tAc \
    "SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version'" 2>/dev/null || true)"
  has_other_tables="$(sudo -u postgres psql -d "$DB_NAME" -tAc \
    "SELECT 1 FROM information_schema.tables WHERE table_schema='public' LIMIT 1" 2>/dev/null || true)"

  if [[ -z "$has_alembic_version" && -n "$has_other_tables" ]]; then
    warn "دیتابیس شامل جدول‌های ناقص از یک اجرای قبلی ناموفق است — پاک‌سازی و آماده‌سازی مجدد..."
    sudo -u postgres psql -d "$DB_NAME" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO ${DB_USER}; GRANT ALL ON SCHEMA public TO public;" >/dev/null
    log "اسکیمای دیتابیس پاک‌سازی شد و آماده Migration تازه است."
  fi
}

fetch_source() {
  if [[ -f "./backend/app/main.py" ]]; then
    log "اجرا از داخل ریپازیتوری تشخیص داده شد؛ از سورس محلی ($(pwd)) استفاده می‌شود."
    INSTALL_DIR="$(pwd)"
    return
  fi

  log "دریافت سورس از ${REPO_URL} (branch: ${REPO_BRANCH}) در ${INSTALL_DIR}..."
  mkdir -p "$INSTALL_DIR"

  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "سورس از قبل در ${INSTALL_DIR} وجود دارد. به‌روزرسانی..."
    git -C "$INSTALL_DIR" fetch origin "$REPO_BRANCH"
    git -C "$INSTALL_DIR" reset --hard "origin/${REPO_BRANCH}"
  else
    if [[ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
      warn "پوشه ${INSTALL_DIR} از قبل محتوا دارد (مثلاً صفحه پیش‌فرض Nginx) — پاک‌سازی می‌شود..."
      find "$INSTALL_DIR" -mindepth 1 -delete
    fi
    git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
  log "سورس‌کد آماده است در: ${INSTALL_DIR}"
}

setup_backend() {
  log "ساخت Virtual Environment و نصب وابستگی‌های Backend..."
  cd "$INSTALL_DIR/backend"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  deactivate
  log "وابستگی‌های Backend نصب شدند"
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
  log "فایل .env ساخته شد"
}

run_migrations() {
  log "اجرای Alembic migrations..."
  reset_stale_schema_if_needed
  cd "$INSTALL_DIR/backend"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  alembic upgrade head
  deactivate
}

build_frontend() {
  log "نصب وابستگی‌های Frontend..."
  cd "$INSTALL_DIR/frontend"
  echo "VITE_API_BASE_URL=/api/v1" > .env

  # نکته: از --silent استفاده نمی‌کنیم چون خروجی خطا را هم مخفی می‌کند
  npm install --no-fund --no-audit

  log "Build کردن Frontend (ممکن است چند دقیقه طول بکشد)..."
  npm run build
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

  log "ساخت کاربر Admin اولیه..."
  python -m scripts.create_admin --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD"
  deactivate

  if [[ "$ADMIN_PASSWORD" == "admin" ]]; then
    warn "رمز عبور Admin روی مقدار پیش‌فرض 'admin' است — حتماً بعد از اولین ورود آن را عوض کنید."
  fi
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
  echo -e " لاگ کامل نصب:        ${LOG_FILE}"
  echo ""
  echo -e "${YELLOW}⚠ اگر از رمز پیش‌فرض استفاده کردید، همین الان بعد از ورود عوضش کنید.${NC}"
  echo ""
  echo " دستورات مفید:"
  echo "   systemctl status faipco-backend    # وضعیت سرویس Backend"
  echo "   journalctl -u faipco-backend -f    # مشاهده لاگ زنده Backend"
  echo "   systemctl restart faipco-backend   # ری‌استارت Backend بعد از تغییر .env"
  echo ""
}

main() {
  require_root
  setup_logging
  log "شروع نصب FAIPCO Portal... (لاگ کامل در ${LOG_FILE} ذخیره می‌شود)"

  stage "مرحله ۱ — نصب پیش‌نیازها"
  ensure_swap
  install_prerequisites
  install_nodejs
  install_postgresql

  stage "مرحله ۲ — دریافت سورس‌کد"
  fetch_source

  stage "مرحله ۳ — راه‌اندازی Backend"
  setup_backend

  stage "مرحله ۴ — تولید فایل .env"
  generate_env

  stage "مرحله ۵ — Migration های دیتابیس"
  run_migrations

  stage "مرحله ۶ — Build کردن Frontend"
  build_frontend

  stage "مرحله ۷ — پیکربندی سرویس‌ها"
  configure_systemd
  configure_nginx
  setup_ssl

  stage "مرحله ۸ — کاربر Admin و امنیت"
  seed_and_create_admin
  configure_firewall

  print_summary
}

main "$@"
