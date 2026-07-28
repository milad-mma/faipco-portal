# FAIPCO Portal

پرتال سازمانی برای مدیریت پرسنل، اطلاعیه‌ها، دسترسی‌ها (RBAC) و همگام‌سازی خودکار
پرسنل از دیتابیس‌های مختلف سایت‌های سازمانی (SQL Server / MySQL / PostgreSQL).

## وضعیت پروژه

| مرحله | وضعیت |
|---|---|
| Backend Core (FastAPI) | ✅ |
| Database Models (Alembic) | ✅ |
| Authentication (JWT + RBAC) | ✅ |
| Employee Sync Engine | ✅ |
| Notification System | ✅ |
| Frontend Dashboard (React RTL) | ✅ |
| Installer (`install.sh`) | ✅ |
| Documentation | در حال تکمیل |

## نصب روی سرور (Production)

روی یک Ubuntu Server تازه (22.04 یا 24.04)، با دسترسی root:

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh | sudo bash
```

یا با دامنه و SSL خودکار:

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh -o install.sh
sudo bash install.sh --domain portal.mycompany.com --admin-username admin
```

اسکریپت به‌طور کامل خودکار انجام می‌دهد: نصب پیش‌نیازها (Python/Node/PostgreSQL/Nginx) →
ساخت دیتابیس → نصب Backend → تولید `.env` با کلیدهای امنیتی یکتا → Migration → Build
Frontend → Service systemd → Nginx → SSL رایگان (Let's Encrypt) → Seed + ساخت Admin →
فایروال. پروژه به‌صورت پیش‌فرض در `/var/www/html` نصب می‌شود.

در پایان، آدرس پرتال و اطلاعات ورود Admin روی صفحه چاپ می‌شود.

**آرگومان‌های قابل استفاده:**

| آرگومان | توضیح | پیش‌فرض |
|---|---|---|
| `--domain` | دامنه پرتال (برای SSL خودکار) | ندارد (فقط IP) |
| `--no-ssl` | رد کردن SSL حتی با وجود دامنه | — |
| `--admin-username` | نام کاربری Admin اولیه | `admin` |
| `--admin-password` | رمز عبور Admin (وگرنه تصادفی) | تصادفی |
| `--install-dir` | مسیر نصب روی سرور | `/var/www/html` |

**عیب‌یابی:** کل خروجی نصب همیشه در `/var/log/faipco-install.log` ذخیره می‌شود.
اگر نصب متوقف شد: `cat /var/log/faipco-install.log` را برای پیام خطای دقیق بررسی کنید.
سرویس‌های مفید بعد از نصب:
```bash
systemctl status faipco-backend     # وضعیت Backend
journalctl -u faipco-backend -f     # لاگ زنده Backend
nginx -t && systemctl status nginx  # وضعیت Nginx
```

## ساختار پروژه

```
faipco-portal/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Endpoint های API (auth, employees, sites, sync, notices)
│   │   ├── core/            # تنظیمات، امنیت/JWT، RBAC، Scheduler
│   │   ├── db/               # اتصال دیتابیس اصلی Portal
│   │   ├── models/           # مدل‌های SQLAlchemy
│   │   ├── schemas/          # مدل‌های Pydantic
│   │   ├── services/         # منطق تجاری
│   │   ├── repositories/     # لایه دسترسی به داده
│   │   ├── sync_engine/      # موتور همگام‌سازی پرسنل (Adapter های چند-دیتابیسی)
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                  # React Dashboard (RTL, MUI)
├── database/migrations/       # Alembic Migrations
├── scripts/                   # seed_permissions, create_admin, verify_models
├── docs/architecture.md       # مستندات معماری
└── install.sh                  # نصب یک‌دستوری روی سرور
```

## راه‌اندازی محلی (Development)

**Backend:**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # SECRET_KEY، DB_CREDENTIALS_ENCRYPTION_KEY و DATABASE_URL را تنظیم کنید

alembic upgrade head
cd .. && python -m scripts.seed_permissions
python -m scripts.create_admin --username admin --password 'StrongPass123!'

cd backend && uvicorn app.main:app --reload
```
مستندات API: `http://localhost:8000/api/docs`

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
سپس `http://localhost:3000` را باز کرده و با کاربر Admin بالا وارد شوید.

## مرور سریع API

```bash
# ورود
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"StrongPass123!"}' | jq -r .access_token)

# ساخت Site + اتصال دیتابیس + Mapping ستون‌ها
curl -X POST http://localhost:8000/api/v1/sites -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name":"کارخانه ۱","code":"SITE1"}'

curl -X PUT http://localhost:8000/api/v1/sites/1/connection -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{
    "db_type":"mssql","host":"192.168.1.10","port":1433,
    "database_name":"HRDB","username":"sa","password":"SourceDbPass123"}'

curl -X PUT http://localhost:8000/api/v1/sites/1/mapping -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{
    "table_name":"Personnel","personnel_code_column":"Code",
    "national_code_column":"NationalID","first_name_column":"Name",
    "last_name_column":"Family","mobile_column":"Phone"}'

# اجرای Sync و مشاهده لاگ
curl -X POST http://localhost:8000/api/v1/sync/1/run -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/v1/sync/1/logs -H "Authorization: Bearer $TOKEN"
```

برای Site دیگری با ساختار جدول متفاوت، فقط مقادیر مرحله Mapping را عوض کنید —
هیچ خط کدی تغییر نمی‌کند.

**اطلاعیه‌ها:** `POST /notices` (ایجاد) → `POST /notices/{id}/publish` (انتشار) →
`GET /notices/me` (اطلاعیه‌های مربوط به کاربر جاری، بر اساس Site/Department/Role/Employee خودش).

## نکات فنی کلیدی
- **RBAC:** هر Endpoint حساس با `require_permission("code")` محافظت می‌شود؛ `is_superuser`
  همیشه دسترسی کامل دارد.
- **رمزنگاری:** پسورد اتصال دیتابیس هر Site با کلید `DB_CREDENTIALS_ENCRYPTION_KEY` (Fernet)
  رمزنگاری می‌شود؛ پسورد کاربران با bcrypt هش می‌شود.
- **Sync Engine:** Plugin-based — افزودن دیتابیس جدید فقط نیاز به یک Adapter تازه دارد
  (`backend/app/sync_engine/adapters/`)، بدون تغییر در بقیه سیستم.
- **Frontend:** RTL واقعی با `stylis-plugin-rtl` + Refresh خودکار Token در `api/client.js`.

## معماری

جزئیات کامل تصمیمات معماری و طراحی Sync Engine در [`docs/architecture.md`](docs/architecture.md).

## لایسنس

طبق فایل [`LICENSE`](LICENSE).
