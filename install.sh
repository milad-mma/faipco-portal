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
# Optional arguments:
#   --domain example.com          Domain name (for Nginx + automatic SSL)
#   --no-ssl                      Skip the SSL step even if a domain is given
#   --admin-username admin        Initial admin username (default: admin)
#   --admin-password '...'        Admin password (default: admin — change it for production)
#   --install-dir /var/www/html   Install path (default: /var/www/html)
#   --repo <git-url>              Repository URL
#   --branch main                 Branch to use
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
SKIP_SSL="false"
DB_NAME="faipco_portal"
DB_USER="faipco_user"
BACKEND_PORT=8000
LOG_FILE="/var/log/faipco-install.log"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
log()   { echo -e "${GREEN}[FAIPCO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }
stage() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

# ---------- Parse arguments ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --no-ssl) SKIP_SSL="true"; shift ;;
    --admin-username) ADMIN_USERNAME="$2"; shift 2 ;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    --branch) REPO_BRANCH="$2"; shift 2 ;;
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

# ---------- Create swap if RAM is low ----------
ensure_swap() {
  local total_mem_mb existing_swap_mb
  total_mem_mb="$(free -m | awk '/^Mem:/{print $2}')"
  existing_swap_mb="$(free -m | awk '/^Swap:/{print $2}')"

  if [[ "$total_mem_mb" -lt 2000 && "$existing_swap_mb" -lt 1 ]]; then
    warn "Server RAM is low (${total_mem_mb}MB) and no swap is active — creating a temporary swap file."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
    grep -q "^/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
    log "Swap enabled successfully."
  fi
}

install_prerequisites() {
  log "Updating package lists and installing prerequisites..."
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
      log "Node.js is already installed: $(node -v)"
      return
    fi
  fi
  log "Installing Node.js 20.x..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
}

install_postgresql() {
  if ! command -v psql >/dev/null 2>&1; then
    log "Installing PostgreSQL..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql postgresql-contrib
  else
    log "PostgreSQL is already installed."
  fi
  systemctl enable --now postgresql

  DB_PASSWORD="$(openssl rand -hex 16)"

  log "Setting up the Portal user and database in PostgreSQL..."
  if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
    sudo -u postgres psql -c "ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" >/dev/null
  else
    sudo -u postgres psql -c "CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';" >/dev/null
  fi

  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" >/dev/null
  fi
}

# ---------- Unconditionally reset the schema before every migration ----------
# Instead of guessing whether a previous run left things half-done (which can
# miss cases — e.g. only an orphaned type with no tables), we always drop and
# recreate the whole schema. This guarantees migrations run from a clean state
# every time and the "already exists" error can never happen again.
#
# Note: since the Portal has no real customer data at this stage (initial
# install/reinstall), this is safe. For a real upgrade on a server with real
# data, don't rerun install.sh from scratch — just run `alembic upgrade head`
# on its own instead.
reset_schema() {
  log "Resetting the database schema to guarantee a clean migration..."
  sudo -u postgres psql -d "$DB_NAME" -c \
    "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO ${DB_USER}; GRANT ALL ON SCHEMA public TO public;" >/dev/null
}

fetch_source() {
  if [[ -f "./backend/app/main.py" ]]; then
    log "Running from inside the repository; using local source at $(pwd)."
    INSTALL_DIR="$(pwd)"
    return
  fi

  log "Fetching source from ${REPO_URL} (branch: ${REPO_BRANCH}) into ${INSTALL_DIR}..."
  mkdir -p "$INSTALL_DIR"

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
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  deactivate
  log "Backend dependencies installed"
}

generate_env() {
  log "Generating .env file with unique security keys..."
  local secret_key fernet_key
  secret_key="$(openssl rand -hex 32)"
  fernet_key="$("$INSTALL_DIR/backend/.venv/bin/python" -c \
    "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")"

  # کلیدهای VAPID برای Web Push — یک‌بار تولید و برای همیشه ثابت می‌مانند.
  # در متغیرهای Global (بدون local) ذخیره می‌شوند تا build_frontend هم به آن‌ها دسترسی داشته باشد.
  local vapid_keys
  vapid_keys="$(cd "$INSTALL_DIR" && "$INSTALL_DIR/backend/.venv/bin/python" -m scripts.generate_vapid_keys)"
  VAPID_PUBLIC_KEY="$(echo "$vapid_keys" | sed -n '1p')"
  VAPID_PRIVATE_KEY="$(echo "$vapid_keys" | sed -n '2p')"

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
VAPID_PUBLIC_KEY=${VAPID_PUBLIC_KEY}
VAPID_PRIVATE_KEY=${VAPID_PRIVATE_KEY}
VAPID_CLAIMS_EMAIL=admin@${DOMAIN:-example.com}
EOF
  chmod 600 "$INSTALL_DIR/backend/.env"
  log ".env file created"
}

run_migrations() {
  reset_schema
  log "Running Alembic migrations..."
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
  log "Configuring Nginx..."
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
    warn "Skipping SSL (no domain given, or --no-ssl was passed). The portal is only reachable over HTTP."
    return
  fi
  log "Installing free SSL (Let's Encrypt) for domain ${DOMAIN}..."
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot python3-certbot-nginx
  if ! certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@${DOMAIN}" --redirect; then
    warn "Automatic SSL issuance failed (the domain's DNS may not point to this server yet)."
    warn "You can run it manually later: certbot --nginx -d ${DOMAIN}"
  fi
}

seed_and_create_admin() {
  log "Seeding initial permissions and system roles..."
  cd "$INSTALL_DIR"
  # shellcheck disable=SC1091
  source backend/.venv/bin/activate
  python -m scripts.seed_permissions

  log "Creating the initial admin user..."
  python -m scripts.create_admin --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD"
  deactivate

  if [[ "$ADMIN_PASSWORD" == "admin" ]]; then
    warn "The admin password is set to the default 'admin' — change it right after your first login."
  fi
}

configure_firewall() {
  log "Configuring firewall (UFW)..."
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
  echo -e " FAIPCO Portal installed successfully  ✅"
  echo -e "==============================================${NC}"
  echo -e " Portal URL:      ${url}"
  echo -e " Admin username:  ${ADMIN_USERNAME}"
  echo -e " Admin password:  ${ADMIN_PASSWORD}"
  echo -e " Install path:    ${INSTALL_DIR}"
  echo -e " Config file:     ${INSTALL_DIR}/backend/.env"
  echo -e " Full install log: ${LOG_FILE}"
  echo ""
  echo -e "${YELLOW}⚠ If you used the default password, change it right after logging in.${NC}"
  echo ""
  echo " Useful commands:"
  echo "   systemctl status faipco-backend    # Backend service status"
  echo "   journalctl -u faipco-backend -f    # Live backend logs"
  echo "   systemctl restart faipco-backend   # Restart backend after editing .env"
  echo ""
}

main() {
  require_root
  setup_logging
  log "Starting FAIPCO Portal installation... (full log saved to ${LOG_FILE})"

  stage "Step 1 - Installing prerequisites"
  ensure_swap
  install_prerequisites
  install_nodejs
  install_postgresql

  stage "Step 2 - Fetching source code"
  fetch_source

  stage "Step 3 - Setting up backend"
  setup_backend

  stage "Step 4 - Generating .env file"
  generate_env

  stage "Step 5 - Database migrations"
  run_migrations

  stage "Step 6 - Building frontend"
  build_frontend

  stage "Step 7 - Configuring services"
  configure_systemd
  configure_nginx
  setup_ssl

  stage "Step 8 - Admin user and security"
  seed_and_create_admin
  configure_firewall

  print_summary
}

main "$@"
