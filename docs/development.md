# راه‌اندازی و اجرای محلی (Development)

پیش‌نیازها: Python 3 (همراه venv)، Node.js 18 یا بالاتر (نصب‌کننده Production نسخه 20 نصب می‌کند)،
PostgreSQL. برای اتصال به دیتابیس SQL Server سایت‌ها، `pymssql` نیاز به FreeTDS دارد
(`freetds-dev` روی Ubuntu).

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# SECRET_KEY: openssl rand -hex 32
# DB_CREDENTIALS_ENCRYPTION_KEY: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# DATABASE_URL را با اطلاعات PostgreSQL خودتان تنظیم کنید

uvicorn app.main:app --reload
```

- مستندات API: http://localhost:8000/api/docs (فقط وقتی `DEBUG=true` — مقدار پیش‌فرض در `.env.example`)
- بررسی سلامت سرویس: http://localhost:8000/api/health

**متغیرهای محیطی** (`backend/app/core/config.py`):

| متغیر | توضیح |
|---|---|
| `DATABASE_URL` | اتصال PostgreSQL اصلی (`postgresql+asyncpg://...`) — الزامی |
| `SECRET_KEY` | کلید امضای JWT — الزامی |
| `DB_CREDENTIALS_ENCRYPTION_KEY` | کلید Fernet برای رمزهای ذخیره‌شده (اتصال سایت‌ها، SMTP، SMS، بکاپ راه‌دور) — الزامی |
| `DEBUG` / `APP_ENV` | نمایش Swagger و حالت اجرا |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | عمر توکن‌ها (پیش‌فرض ۶۰ دقیقه / ۳۰ روز) |
| `CORS_ORIGINS` | فهرست Origin های مجاز (JSON) |
| `FRONTEND_URL` | برای ساخت لینک ایمیل بازنشانی رمز |
| `SYNC_ENABLED` / `SYNC_INTERVAL_MINUTES` | Sync خودکار (فاصله واقعی از پنل هم قابل‌تغییر است) |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CLAIMS_EMAIL` | Web Push — با `python -m scripts.generate_vapid_keys` تولید کنید؛ بدون آن Push غیرفعال است |
| `APP_VERSION` | نسخه نمایشی (در Production توسط `install.sh` از تگ Git پر می‌شود) |

### اجرای Migration ها

Migration ها **ترتیبی و دستی** نوشته شده‌اند (نه با `alembic revision --autogenerate`)
تا کاملاً قابل پیش‌بینی و قابل بازبینی باشند. فایل‌ها در `database/migrations/versions/`
با شماره ترتیبی (`001_…` تا `078_…`) هستند؛ Migration جدید با شماره بعدی و
`down_revision` برابر آخرین شماره ساخته می‌شود.

```bash
# بررسی صحت مدل‌ها بدون نیاز به دیتابیس واقعی
bash scripts/verify_models.sh

cd backend
alembic upgrade head

cd ..
python -m scripts.seed_permissions   # Permission ها و نقش‌های سیستمی (تکرارپذیر)
python -m scripts.create_admin --username admin --password 'StrongPass123!'
```

### تست‌ها

تست‌های واحد (بدون نیاز به دیتابیس) برای منطق‌های خالص در `backend/tests/` هستند:

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL (پیش‌فرض http://localhost:8000/api/v1)
npm run dev            # سرور توسعه روی پورت 3000
```

سپس `http://localhost:3000` را باز کرده و با کاربر Admin وارد شوید.
Service Worker در حالت Dev غیرفعال است؛ برای تست PWA از `npm run build` و
`npm run preview` استفاده کنید. کلید عمومی VAPID در زمان اجرا از
`GET /api/v1/push/vapid-public-key` خوانده می‌شود.

### تست سریع API

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "StrongPass123!"}'

curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer <access_token>"
curl http://localhost:8000/api/v1/employees -H "Authorization: Bearer <access_token>"
```

### نحوه کار RBAC

هر Endpoint حساس با `Depends(require_permission("employees.view"))` (یا Dependency های
سایت‌محور در `app/core/site_permission_deps.py`) محافظت می‌شود. اگر کاربر
`is_superuser=True` باشد همیشه دسترسی دارد؛ در غیر این‌صورت، Permission های مؤثر
کاربر (نقش‌های سراسری + نقش‌های مخصوص همان Site) از دیتابیس خوانده و بررسی می‌شود.
در Frontend، مسیرها در `src/App.jsx` با `PermissionRoute` و فلگ‌های `can_*` کاربر
(از `/auth/me`) محافظت می‌شوند و منوها فقط از `src/config/navItems.jsx` تعریف
می‌شوند. جزئیات کامل در [`rbac.md`](rbac.md) و [`role-management.md`](role-management.md).
