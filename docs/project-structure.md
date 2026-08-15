# ساختار پروژه


```
faipco-portal/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # auth, employees, sites, sync, notices, departments, users, push
│   │   ├── core/                # config, security (JWT/bcrypt), deps (RBAC), scheduler
│   │   ├── db/                  # اتصال دیتابیس اصلی Portal
│   │   ├── models/               # مدل‌های SQLAlchemy
│   │   ├── schemas/              # مدل‌های Pydantic ورودی/خروجی API
│   │   ├── services/             # منطق تجاری
│   │   ├── repositories/         # لایه دسترسی به داده (User/Employee)
│   │   ├── sync_engine/          # Adapter های PostgreSQL/MySQL/MSSQL + Sync Service
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                     # React Dashboard (RTL, MUI, PWA)
│   └── src/
│       ├── api/                  # یک فایل به‌ازای هر ماژول Backend
│       ├── components/           # Layout، Dialog های مشترک، ProtectedRoute/AdminRoute
│       ├── context/               # AuthContext
│       ├── pages/                 # Login، Dashboard، Employees، Sites، Sync، Notices، Access
│       └── utils/                 # Service Worker، Push، نصب PWA
├── database/migrations/          # Alembic Migrations (ترتیبی، نه Autogenerate)
├── scripts/                       # seed_permissions, create_admin, generate_vapid_keys, verify_models
├── docs/architecture.md          # دلایل انتخاب تکنولوژی و طراحی داخلی
└── install.sh                     # نصب/آپدیت یک‌دستوری روی Ubuntu Server
```
