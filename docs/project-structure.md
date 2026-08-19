# ساختار پروژه

```
faipco-portal/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/     # auth, employees, sites, sync, notices, departments,
│   │   │                         # users, push, attendance, hr, backup, system
│   │   ├── core/                 # config, security (JWT/bcrypt), deps (RBAC), scheduler,
│   │   │                         # rate_limit (DB-backed), ip_allowlist, persian_date
│   │   ├── db/                   # اتصال دیتابیس اصلی Portal
│   │   ├── models/                # مدل‌های SQLAlchemy
│   │   ├── schemas/                # مدل‌های Pydantic ورودی/خروجی API
│   │   ├── services/                # منطق تجاری — از جمله backup_service،
│   │   │                            # update_service، gps_attendance_service،
│   │   │                            # birthday_greetings_service، payroll_* ،
│   │   │                            # attendance_card_*
│   │   ├── repositories/            # لایه دسترسی به داده (User/Employee)
│   │   ├── sync_engine/             # Adapter های PostgreSQL/MySQL/MSSQL + Sync Service
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                      # React Dashboard (RTL, MUI, PWA)
│   └── src/
│       ├── api/                   # یک فایل به‌ازای هر ماژول Backend
│       ├── components/            # Layout، Dialog های مشترک، Protected/AdminRoute،
│       │                          # PermissionRoute، NoticeReportTable (کارتی روی موبایل)
│       ├── context/                # AuthContext، ThemeModeContext
│       ├── pages/                  # از جمله: Dashboard، Employees، Sites، Sync، Notices،
│       │                           # NoticeReports، Access، BulkRoleAssignment، Backup،
│       │                           # Update، IpAllowlist، AttendanceClock،
│       │                           # ClockInOutReport، PresenceReport، BirthdayMessages
│       └── utils/                  # Service Worker، Push، نصب PWA، presenceSocket (WebSocket)
├── database/migrations/           # Alembic Migrations (ترتیبی، نه Autogenerate)
├── scripts/                        # seed_permissions, create_admin, generate_vapid_keys
├── docs/                            # همین مستندات — نگاه کنید README.md برای فهرست کامل
└── install.sh                       # نصب/آپدیت یک‌دستوری روی Ubuntu Server (هم از
                                      # خط‌فرمان، هم از دکمه «آپدیت» داخل پنل)
```
