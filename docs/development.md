# راه‌اندازی و اجرای محلی (Development)


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

- مستندات API: http://localhost:8000/api/docs
- بررسی سلامت سرویس: http://localhost:8000/api/health

### اجرای Migration ها

Migration ها **ترتیبی و دستی** نوشته شده‌اند (نه با `alembic revision --autogenerate`)
تا کاملاً قابل پیش‌بینی و قابل بازبینی باشند:

```bash
# بررسی صحت مدل‌ها بدون نیاز به دیتابیس واقعی
bash scripts/verify_models.sh

cd backend
alembic upgrade head

cd ..
python -m scripts.seed_permissions   # Permission ها و نقش‌های سیستمی
python -m scripts.create_admin --username admin --password 'StrongPass123!'
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # در صورت نیاز VITE_API_BASE_URL را ویرایش کنید
npm run dev
```

سپس `http://localhost:3000` را باز کرده و با کاربر Admin وارد شوید.

### تست سریع API

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "StrongPass123!"}'

curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer <access_token>"
curl http://localhost:8000/api/v1/employees -H "Authorization: Bearer <access_token>"
```

### نحوه کار RBAC

هر Endpoint حساس با `Depends(require_permission("employees.view"))` محافظت می‌شود.
اگر کاربر `is_superuser=True` باشد همیشه دسترسی دارد؛ در غیر این‌صورت، Permission
های مؤثر کاربر (نقش‌های سراسری + نقش‌های مخصوص همان Site) از دیتابیس خوانده و
بررسی می‌شود. جزئیات کامل در [بخش دسترسی‌ها](#دسترسی‌ها-rbac).
