#!/usr/bin/env bash
# ============================================================
# FAIPCO Portal — Automated installer for Ubuntu Server (22.04 / 24.04)
#
# Run (install directly from GitHub):
#   curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh | sudo bash
#
# Or locally (when the repository is already cloned):
#   sudo bash install.sh
#
# This script auto-detects whether it's a FRESH install or an UPDATE of an
# existing installation (by checking if backend/.env already exists at the
# install path). In UPDATE mode: the existing .env (secrets, DB password,
# VAPID keys, etc.) and the database are NEVER touched or wiped — only the
# source code is refreshed, dependencies reinstalled, new migrations applied
# additively (alembic upgrade head), the frontend rebuilt, and services
# restarted. This is safe to run every time you push to GitHub and want to
# deploy the latest version to your server.
#
# Optional arguments:
#   --domain example.com          Public domain (only used for CORS — SSL is handled by an
#                                  external reverse proxy, this installer no longer manages it)
#   --admin-username admin        Initial admin username (default: admin) — only used on fresh installs
#   --admin-password '...'        Admin password (default: admin) — only used on fresh installs
#   --install-dir /var/www/html   Install path (default: /var/www/html)
#   --repo <git-url>              Repository URL
#   --branch main                 Branch to use
#   --reverse-proxy-ip <IP>        IP of your external SSL reverse proxy — if given,
#                                  restricts ports 80/443 (via UFW) so only that IP can
#                                  reach this server directly. IMPORTANT: use the IP that
#                                  THIS server actually sees as the connection source —
#                                  if your proxy is on a separate private network (common
#                                  2-tier setup), that's the proxy's LOCAL/private IP, not
#                                  its public internet-facing IP (this server never sees
#                                  the public IP directly in that case). Without this,
#                                  anyone who finds this server's own IP can forge
#                                  X-Forwarded-For headers and bypass IP-based restrictions
#                                  (like the IP allowlist / anti-VPN feature) — confirmed
#                                  by a live pentest. Strongly recommended if you have an
#                                  external reverse proxy.
#
# Backup/restore is handled entirely from the Admin panel (پشتیبان‌گیری) —
# there is no command-line restore option anymore. This installer only sets
# up/updates the running application.
#
# The full install log is always saved to /var/log/faipco-install.log —
# check that file for troubleshooting if anything goes wrong.
# ============================================================
set -euo pipefail

# ---------- Defaults ----------
REPO_URL="${FAIPCO_REPO_URL:-https://github.com/milad-mma/faipco-portal.git}"
REPO_BRANCH="${FAIPCO_BRANCH:-main}"
INSTALL_DIR="${FAIPCO_INSTALL_DIR:-/var/www/html}"
DOMAIN="${FAIPCO_DOMAIN:-}"
ADMIN_USERNAME="${FAIPCO_ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${FAIPCO_ADMIN_PASSWORD:-admin}"
REVERSE_PROXY_IP="${FAIPCO_REVERSE_PROXY_IP:-}"
DB_NAME="faipco_portal"
DB_USER="faipco_user"
BACKEND_PORT=8000
LOG_FILE="/var/log/faipco-install.log"
IS_UPDATE="false"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
log()   { echo -e "${GREEN}[FAIPCO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }
stage() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

# ---------- Parse arguments ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --admin-username) ADMIN_USERNAME="$2"; shift 2 ;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    --branch) REPO_BRANCH="$2"; shift 2 ;;
    --reverse-proxy-ip) REVERSE_PROXY_IP="$2"; shift 2 ;;
    *) err "Unknown argument: $1"; exit 1 ;;
  esac
done

require_root() {
  if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root or with sudo. Example: sudo bash install.sh"
    exit 1
  fi
}

# ---------- Log everything to a file (for troubleshooting) ----------
setup_logging() {
  touch "$LOG_FILE"
  exec > >(tee -a "$LOG_FILE") 2>&1
}

# If any command fails, report exactly which line — instead of failing silently
on_error() {
  local exit_code=$?
  local line_no=$1
  err "Install failed at line ${line_no} (exit code: ${exit_code})."
  err "For full details: cat ${LOG_FILE}"
  exit "$exit_code"
}
trap 'on_error $LINENO' ERR

ensure_swap() {
  # روی سرورهای کم‌حافظه (مثلاً ۱ گیگابایت RAM)، نصب وابستگی‌ها (npm install،
  # ساخت فرانت‌اند با Vite، pip install) می‌تواند به‌قدری حافظه مصرف کند که
  # OOM Killer فرآیند نصب را بی‌دلیل از وسط بکشد. اگر سرور Swap فعال ندارد،
  # یک فایل Swap ۲ گیگابایتی می‌سازیم تا این ریسک را از بین ببریم.
  if swapon --show | grep -q .; then
    log "Swap از قبل فعال است — رد می‌شویم."
    return
  fi

  local mem_total_kb
  mem_total_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
  if [[ "$mem_total_kb" -ge 2097152 ]]; then
    log "RAM سیستم کافی است (بیش از ۲ گیگابایت) — نیازی به Swap نیست."
    return
  fi

  log "RAM محدود شناسایی شد و Swap فعال نیست — در حال ساخت یک فایل Swap ۲ گیگابایتی..."
  if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
  fi
  swapon /swapfile 2>/dev/null || true
  if ! grep -q '^/swapfile' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
  fi
  log "Swap فعال شد."
}

install_prerequisites() {
  log "Updating package lists and installing prerequisites..."
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    curl git build-essential software-properties-common \
    python3 python3-venv python3-pip python3-dev \
    libpq-dev unixodbc unixodbc-dev freetds-dev freetds-bin \
    nginx ufw openssl ca-certificates unzip
}

install_nodejs() {
  if command -v node >/dev/null 2>&1; then
    local major_version
    major_version="$(node -v | grep -oE '^v[0-9]+' | tr -d v)"
    if [[ "$major_version" -ge 18 ]]; then
      log "Node.js is already installed: $(node -v)"
      return
    fi
  fi
  log "Installing Node.js 20.x..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
}

install_postgresql() {
  if command -v psql >/dev/null 2>&1; then
    log "PostgreSQL is already installed: $(psql --version)"
  else
    log "Installing PostgreSQL..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql postgresql-contrib
  fi
  systemctl enable postgresql >/dev/null 2>&1 || true
  systemctl start postgresql
}

setup_database() {
  log "Setting up PostgreSQL role and database..."

  # اگر نصب موجودی از قبل هست، پسورد فعلی دیتابیس را از همان .env می‌خوانیم
  # تا با آن هماهنگ بمانیم — هرگز پسورد یک نصب موجود را عوض نمی‌کنیم (طبق
  # همان قانون کلی این اسکریپت: در حالت Update، هیچ Secret ای دست‌نخورده نمی‌ماند).
  DB_PASSWORD=""
  if [[ -f "$INSTALL_DIR/backend/.env" ]]; then
    DB_PASSWORD="$(grep '^DATABASE_URL=' "$INSTALL_DIR/backend/.env" 2>/dev/null | sed -E 's#.*://[^:]+:([^@]+)@.*#\1#')"
  fi
  if [[ -z "$DB_PASSWORD" ]]; then
    DB_PASSWORD="$(openssl rand -hex 16)"
  fi

  local role_exists db_exists
  role_exists="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'")"
  db_exists="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'")"

  if [[ "$role_exists" == "1" ]]; then
    sudo -u postgres psql -c "ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" >/dev/null
  else
    sudo -u postgres psql -c "CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';" >/dev/null
  fi

  if [[ "$db_exists" != "1" ]]; then
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" >/dev/null
  fi

  # نکته حیاتی: مالکیت خودِ دیتابیس با CREATE DATABASE ... OWNER تنظیم
  # می‌شود، ولی Schema "public" داخلش از روی Template کپی می‌شود و معمولاً
  # همچنان مالکش کاربر postgres می‌ماند، نه ${DB_USER} — یعنی بدون این خط،
  # ${DB_USER} نمی‌تواند حتی روی همین Schema عملیات‌های ساده‌ای مثل COMMENT
  # (که در بازیابی کامل بکاپ لازم می‌شود) انجام بدهد. این خط Idempotent است
  # (روی یک نصب موجود هم بی‌خطر دوباره اجرا می‌شود).
  sudo -u postgres psql -d "${DB_NAME}" -c "ALTER SCHEMA public OWNER TO ${DB_USER};" >/dev/null
}

fetch_source() {
  if [[ -f "./backend/app/main.py" ]]; then
    log "Running from inside the repository; using local source at $(pwd)."
    INSTALL_DIR="$(pwd)"
    return
  fi

  log "Fetching source from ${REPO_URL} (branch: ${REPO_BRANCH}) into ${INSTALL_DIR}..."
  mkdir -p "$INSTALL_DIR"

  # از Git 2.35.2 به بعد، اگر مالک پوشه با کاربری که git را اجرا می‌کند
  # (اینجا معمولاً root، چون این اسکریپت با sudo اجرا می‌شود) فرق داشته
  # باشد، git با خطای "detected dubious ownership" کار را متوقف می‌کند —
  # یک قابلیت امنیتی برای جلوگیری از سوءاستفاده در مسیرهای مشترک. چون این
  # مسیر (${INSTALL_DIR}) کاملاً تحت مدیریت خودِ همین اسکریپت نصب است، اینجا
  # این هشدار بی‌مورد است — صریحاً به‌عنوان مسیر امن معرفی می‌شود تا هرگز
  # نیازی به دخالت دستی کاربر (git config --add safe.directory ...) نباشد.
  git config --global --add safe.directory "$INSTALL_DIR"

  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Source already exists at ${INSTALL_DIR}. Updating..."
    git -C "$INSTALL_DIR" fetch origin "$REPO_BRANCH"
    git -C "$INSTALL_DIR" reset --hard "origin/${REPO_BRANCH}"
  else
    if [[ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
      warn "Directory ${INSTALL_DIR} already has content (e.g. Nginx's default page) — clearing it..."
      find "$INSTALL_DIR" -mindepth 1 -delete
    fi
    git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
  log "Source code ready at: ${INSTALL_DIR}"
}

setup_backend() {
  log "Creating virtual environment and installing backend dependencies..."
  cd "$INSTALL_DIR/backend"
  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  deactivate
  log "Backend dependencies installed"
}

generate_env() {
  if [[ -f "$INSTALL_DIR/backend/.env" ]]; then
    log "Existing .env found — keeping current settings (secrets, DB password, VAPID keys unchanged)."
    if grep -q "^VAPID_PUBLIC_KEY=" "$INSTALL_DIR/backend/.env"; then
      VAPID_PUBLIC_KEY="$(grep '^VAPID_PUBLIC_KEY=' "$INSTALL_DIR/backend/.env" | cut -d= -f2-)"
    else
      # نصب قدیمی‌تر که هنوز VAPID نداشت — فقط همین کلیدهای جدید را اضافه می‌کنیم
      log "Adding missing VAPID keys for Web Push to the existing .env..."
      local vapid_keys
      vapid_keys="$(cd "$INSTALL_DIR" && "$INSTALL_DIR/backend/.venv/bin/python" -m scripts.generate_vapid_keys)"
      VAPID_PUBLIC_KEY="$(echo "$vapid_keys" | sed -n '1p')"
      VAPID_PRIVATE_KEY="$(echo "$vapid_keys" | sed -n '2p')"
      {
        echo "VAPID_PUBLIC_KEY=${VAPID_PUBLIC_KEY}"
        echo "VAPID_PRIVATE_KEY=${VAPID_PRIVATE_KEY}"
        echo "VAPID_CLAIMS_EMAIL=admin@${DOMAIN:-example.com}"
      } >> "$INSTALL_DIR/backend/.env"
    fi
    return
  fi

  log "Generating .env file with unique security keys (fresh install)..."
  local secret_key fernet_key
  secret_key="$(openssl rand -hex 32)"
  fernet_key="$("$INSTALL_DIR/backend/.venv/bin/python" -c \
    "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")"

  local vapid_keys
  vapid_keys="$(cd "$INSTALL_DIR" && "$INSTALL_DIR/backend/.venv/bin/python" -m scripts.generate_vapid_keys)"
  VAPID_PUBLIC_KEY="$(echo "$vapid_keys" | sed -n '1p')"
  VAPID_PRIVATE_KEY="$(echo "$vapid_keys" | sed -n '2p')"

  # چون فرانت‌اند همیشه با مسیرهای نسبی (/api/v1/...) به بک‌اند وصل می‌شود و
  # هر دو از همین Nginx سرو می‌شوند، همیشه Same-Origin است؛ CORS محدودکننده
  # واقعی ایجاد نمی‌کند. برای جلوگیری از قطعی غیرمنتظره، همه Origin مجازند.
  local cors_origin="*"

  cat > "$INSTALL_DIR/backend/.env" <<EOF
APP_NAME=FAIPCO Portal
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
SECRET_KEY=${secret_key}
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
DB_CREDENTIALS_ENCRYPTION_KEY=${fernet_key}
CORS_ORIGINS=["${cors_origin}"]
SYNC_ENABLED=true
SYNC_INTERVAL_MINUTES=30
VAPID_PUBLIC_KEY=${VAPID_PUBLIC_KEY}
VAPID_PRIVATE_KEY=${VAPID_PRIVATE_KEY}
VAPID_CLAIMS_EMAIL=admin@${DOMAIN:-example.com}
EOF
  chmod 600 "$INSTALL_DIR/backend/.env"
  log ".env file created"
}

run_migrations() {
  log "Running Alembic migrations (additive — never drops existing data)..."
  cd "$INSTALL_DIR/backend"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  alembic upgrade head
  deactivate
}

build_frontend() {
  log "Installing frontend dependencies..."
  cd "$INSTALL_DIR/frontend"
  cat > .env <<EOF
VITE_API_BASE_URL=/api/v1
VITE_VAPID_PUBLIC_KEY=${VAPID_PUBLIC_KEY}
EOF

  # Note: we don't use --silent because it also hides error output
  npm install --no-fund --no-audit

  log "Building frontend (this may take a few minutes)..."
  npm run build
}

configure_systemd() {
  log "Creating systemd service for the backend..."
  cat > /etc/systemd/system/faipco-backend.service <<EOF
[Unit]
Description=FAIPCO Portal Backend (FastAPI)
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${INSTALL_DIR}/backend
Environment="PATH=${INSTALL_DIR}/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=${INSTALL_DIR}/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT} --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  chown -R www-data:www-data "$INSTALL_DIR"

  # اجازه محدود و دقیق (فقط همین یک دستور ثابت، بدون رمز) به www-data
  # می‌دهیم — نه برای stop/start مستقیم، بلکه برای اجرای اسکریپت Restore
  # داخل یک Scope کاملاً جدا و مستقل از systemd (systemd-run). این حیاتی
  # است: اگر آن اسکریپت مستقیم زیرمجموعه‌ی خودِ faipco-backend.service اجرا
  # می‌شد (حتی با setsid)، وقتی خودش دستور «متوقف‌کردن faipco-backend» را
  # صادر می‌کرد، systemd کل Cgroup آن سرویس — از جمله خودِ همین اسکریپت را
  # هم می‌کشت (چون setsid فقط از Session/Process Group جدا می‌کند، نه از
  # Cgroup) — دقیقاً همان چیزی که باعث شد Restore درست بعد از خط «در حال
  # توقف سرویس» بی‌صدا متوقف شود. با systemd-run، اسکریپت در یک Scope کاملاً
  # جدا (و به‌عنوان root) اجرا می‌شود که از این Cgroup Kill در امان است.
  cat > /etc/sudoers.d/faipco-backend-restart <<'EOF'
www-data ALL=(root) NOPASSWD: /usr/bin/systemd-run --unit=faipco-restore --collect /bin/sh /tmp/faipco-restore-run.sh
EOF
  chmod 440 /etc/sudoers.d/faipco-backend-restart
  visudo -c -f /etc/sudoers.d/faipco-backend-restart >/dev/null || {
    err "sudoers rule for faipco-backend-restart failed validation — removing it (in-panel restore won't work; you'll need to restore manually around a stop/start of faipco-backend)."
    rm -f /etc/sudoers.d/faipco-backend-restart
  }

  systemctl daemon-reload
  systemctl enable faipco-backend >/dev/null
  systemctl restart faipco-backend
}

configure_nginx() {
  log "Configuring Nginx..."
  # این Nginx محلی همیشه روی HTTP ساده (پورت ۸۰) کار می‌کند. SSL توسط یک
  # Reverse Proxy خارجی که از قبل راه‌اندازی شده مدیریت می‌شود (نه این اسکریپت).
  # server_name روی "_" و listen روی default_server تنظیم می‌شود تا هم از
  # طریق دامنه (پشت Reverse Proxy) و هم مستقیماً از طریق IP محلی در دسترس باشد.
  #
  # قوانین Cache-Control اینجا حیاتی‌اند برای این‌که بعد از هر Update، کاربرانی
  # که پنل را باز نگه داشته‌اند، نسخه جدید را (بدون خروج از حساب) ببینند:
  #   - sw.js / manifest.json / index.html: هرگز Cache نشوند (no-cache یعنی
  #     همیشه با سرور Revalidate شوند) — چون همین‌ها هستند که باید فوراً
  #     نسخه جدید را معرفی کنند.
  #   - فایل‌های داخل assets/ (خروجی Vite با نام Hash‌دار مثل index-a1b2c3.js):
  #     برای همیشه Cache می‌شوند، چون هر Build جدید نام‌فایل جدیدی تولید
  #     می‌کند — نیازی به Revalidate نیست و کاربر همیشه خودکار فایل جدید
  #     را می‌گیرد (چون index.html تازه، به نام جدید اشاره می‌کند).
  # نگاشت استاندارد Nginx برای پشتیبانی WebSocket: فقط وقتی درخواست واقعاً
  # Upgrade باشد (مثل اتصال presence-ws)، هدر Connection را به "upgrade"
  # تنظیم می‌کند؛ برای بقیه درخواست‌های HTTP معمولی دست‌نخورده می‌ماند. این
  # باید در سطح http{} تعریف شود (نه داخل server{})، پس در conf.d جداگانه است.
  mkdir -p /etc/nginx/conf.d
  cat > /etc/nginx/conf.d/faipco-websocket-map.conf <<'EOF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
EOF

  cat > /etc/nginx/sites-available/faipco-portal <<EOF
server {
    listen 80 default_server;
    server_name _;

    # نسخه دقیق Nginx را توی هدر Server مخفی می‌کند — کمک کوچکی به Attacker
    # که نداند دقیقاً کدام نسخه/آسیب‌پذیری‌های شناخته‌شده را امتحان کند.
    server_tokens off;

    # هدرهای امنیتی پایه — برای همه پاسخ‌ها (چه فایل‌های فرانت‌اند، چه API).
    # Strict-Transport-Security این‌جا (روی HTTP ساده) اثری روی همین لایه
    # ندارد، ولی چون این هدر از طریق پروکسی خارجی (که HTTPS واقعی را ترمینال
    # می‌کند) به مرورگر می‌رسد، همچنان مؤثر است — مگر پروکسی خارجی هدرها را
    # صریحاً حذف کند.
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # پیش‌فرض Nginx فقط ۱ مگابایت است — برای آپلود فیش حقوقی (XLSX سازمان‌های
    # بزرگ می‌تواند چند مگابایت باشد) باید بیشتر باشد.
    client_max_body_size 25m;

    root ${INSTALL_DIR}/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # پشتیبانی از WebSocket (مثلاً /api/v1/attendance/presence-ws) — بدون
        # این خطوط، Nginx فقط HTTP معمولی رد می‌کند و Handshake وب‌ساکت
        # شکست می‌خورد. این‌ها فقط وقتی درخواست واقعاً Upgrade باشد فعال
        # می‌شوند، پس درخواست‌های HTTP معمولی تحت تأثیر قرار نمی‌گیرند.
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_read_timeout 600s;
    }

    location = /sw.js {
        default_type application/javascript;
        add_header Cache-Control "no-cache, must-revalidate";
        try_files \$uri =404;
    }

    location = /manifest.json {
        # نکته مهم برای نصب PWA در اندروید: mime.types پیش‌فرض Nginx شامل
        # پسوند json نیست، پس بدون این خط، manifest.json با Content-Type
        # اشتباه (معمولاً text/plain یا application/octet-stream) فرستاده
        # می‌شود. کروم در این حالت گاهی هنگام "Install" به‌جای ساخت WebAPK
        # واقعی، فقط یک میان‌بر معمولی (با نشان خودِ کروم روی آیکون) می‌سازد.
        default_type application/manifest+json;
        add_header Cache-Control "no-cache, must-revalidate";
        try_files \$uri =404;
    }

    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
        try_files \$uri =404;
    }

    location / {
        add_header Cache-Control "no-cache, must-revalidate";
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

  ln -sf /etc/nginx/sites-available/faipco-portal /etc/nginx/sites-enabled/faipco-portal
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl reload nginx
}

seed_and_create_admin() {
  log "Seeding permissions and system roles (safe to repeat — only adds what's missing)..."
  cd "$INSTALL_DIR"
  # shellcheck disable=SC1091
  source backend/.venv/bin/activate
  python -m scripts.seed_permissions

  if [[ "$IS_UPDATE" == "true" ]]; then
    log "Existing installation — skipping admin creation (your current admin account and password are untouched)."
  else
    log "Creating the initial admin user..."
    python -m scripts.create_admin --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD"
  fi
  deactivate
}

configure_firewall() {
  log "Configuring firewall (UFW)..."
  ufw allow OpenSSH >/dev/null 2>&1 || true

  if [[ -n "$REVERSE_PROXY_IP" ]]; then
    # حیاتی: بدون این، هرکسی که مستقیماً IP این سرور را بداند (نه فقط
    # دامنه) می‌تواند هدرهای X-Forwarded-For جعلی بفرستد و محدودیت‌هایی
    # مثل «رنج‌های IP مجاز» (ضدVPN) را کاملاً دور بزند — چون سرور فقط به
    # این هدر اعتماد می‌کند و نمی‌تواند خودش تشخیص بدهد این هدر واقعاً از
    # همان پروکسی خارجی معتبر آمده یا مستقیماً توسط یک مهاجم جعل شده است.
    # این یافته واقعی از یک تست نفوذ زنده تأیید شد.
    log "Restricting ports 80/443 to only the reverse proxy IP (${REVERSE_PROXY_IP})..."
    ufw allow from "$REVERSE_PROXY_IP" to any port 80 >/dev/null 2>&1 || true
    ufw allow from "$REVERSE_PROXY_IP" to any port 443 >/dev/null 2>&1 || true
  else
    warn "No --reverse-proxy-ip given — ports 80/443 remain open to the whole internet."
    warn "If you have an external SSL reverse proxy in front of this server, re-run with:"
    warn "  sudo bash install.sh --reverse-proxy-ip <its-IP>"
    warn "Otherwise, anyone who finds this server's direct IP can bypass IP-based restrictions"
    warn "(like the IP allowlist / anti-VPN feature) by connecting directly and forging headers."
    ufw allow 'Nginx Full' >/dev/null 2>&1 || true
  fi

  ufw --force enable >/dev/null 2>&1 || true
}

print_summary() {
  local ip_url="http://$(hostname -I | awk '{print $1}')"
  local domain_note=""
  if [[ -n "$DOMAIN" ]]; then
    domain_note=" Public URL (via your reverse proxy): https://${DOMAIN}\n"
  fi

  echo ""
  echo -e "${GREEN}=============================================="
  if [[ "$IS_UPDATE" == "true" ]]; then
    echo -e " FAIPCO Portal updated successfully  ✅"
  else
    echo -e " FAIPCO Portal installed successfully  ✅"
  fi
  echo -e "==============================================${NC}"
  echo -e "$domain_note Local/IP URL:    ${ip_url}"
  if [[ "$IS_UPDATE" == "true" ]]; then
    echo -e " Admin account:   unchanged — use your existing username/password"
  else
    echo -e " Admin username:  ${ADMIN_USERNAME}"
    echo -e " Admin password:  ${ADMIN_PASSWORD}"
  fi
  echo -e " Install path:    ${INSTALL_DIR}"
  echo -e " Config file:     ${INSTALL_DIR}/backend/.env"
  echo -e " Full install log: ${LOG_FILE}"
  echo ""
  if [[ "$IS_UPDATE" != "true" && "$ADMIN_PASSWORD" == "admin" ]]; then
    echo -e "${YELLOW}⚠ You're using the default password 'admin' — change it right after logging in.${NC}"
    echo ""
  fi
  echo " Useful commands:"
  echo "   systemctl status faipco-backend    # Backend service status"
  echo "   journalctl -u faipco-backend -f    # Live backend logs"
  echo "   systemctl restart faipco-backend   # Restart backend after editing .env"
  echo ""
}

main() {
  require_root
  setup_logging

  log "Starting FAIPCO Portal installer... (full log saved to ${LOG_FILE})"

  stage "Step 1 - Installing prerequisites"
  ensure_swap
  install_prerequisites
  install_nodejs
  install_postgresql

  stage "Step 2 - Fetching source code"
  fetch_source

  if [[ -f "$INSTALL_DIR/backend/.env" ]]; then
    IS_UPDATE="true"
    log "Existing installation detected at ${INSTALL_DIR} — running in UPDATE mode."
    log "Your .env, database, and current settings will NOT be touched."
  fi

  stage "Step 3 - Setting up backend"
  setup_backend
  setup_database

  stage "Step 4 - Generating .env file"
  generate_env

  stage "Step 5 - Database migrations"
  run_migrations

  stage "Step 6 - Building frontend"
  build_frontend

  stage "Step 7 - Configuring services"
  configure_systemd
  configure_nginx

  stage "Step 8 - Admin user and security"
  seed_and_create_admin
  configure_firewall

  print_summary
}

main "$@"
