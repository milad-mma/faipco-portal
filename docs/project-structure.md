# ساختار پروژه

```
faipco-portal/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── router.py              # روتر مرکزی (پیشوند /api/v1)
│   │   │   └── endpoints/             # auth, employees, departments, sites, sync,
│   │   │                              # mapping_suggestions, notices, users, push,
│   │   │                              # attendance (GPS + WebSocket حضور), monthly_attendance,
│   │   │                              # hr (تبریک تولد), vehicles, feedback,
│   │   │                              # evaluation_structure/periods/forms/process/reports,
│   │   │                              # leave_requests, leave_requests_admin,
│   │   │                              # access_gate, announcement, backup, system
│   │   ├── core/                      # config، security (JWT/bcrypt/Fernet)، deps و
│   │   │                              # site_permission_deps (RBAC)، site_access، scheduler،
│   │   │                              # rate_limit (DB-backed)، ip_allowlist، geo، persian_date،
│   │   │                              # persian_text_normalize، profanity_filter،
│   │   │                              # evaluation_rules، leave_request_rules، backup_schedule_logic
│   │   ├── db/                        # اتصال دیتابیس اصلی Portal (session.py)
│   │   ├── models/                    # مدل‌های SQLAlchemy (یک فایل به‌ازای هر حوزه)
│   │   ├── schemas/                   # مدل‌های Pydantic ورودی/خروجی API
│   │   ├── services/                  # منطق تجاری — خلاصه در جدول زیر
│   │   ├── repositories/              # user_repository (دسترسی داده User/Employee)
│   │   ├── sync_engine/               # adapters/ (PostgreSQL/MySQL/MSSQL) + adapter_factory + sync_service
│   │   ├── assets/                    # فونت PDF (Tahoma.ttf) و لوگوی پیش‌فرض
│   │   ├── data/                      # prohibited_phrases_seed.txt (فیلتر الفاظ نامناسب)
│   │   └── main.py                    # نقطه ورود FastAPI + /api/health
│   ├── tests/                         # تست‌های pytest برای منطق‌های خالص core/services
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env.example
├── database/migrations/versions/      # Alembic Migrations ترتیبی و دستی (001 … 078)
├── frontend/                          # React Dashboard (RTL, MUI, PWA)
│   ├── public/                        # manifest.json، آیکون‌ها، splash، لوگو
│   ├── vite.config.js                 # Vite + vite-plugin-pwa (injectManifest)
│   ├── .env.example
│   └── src/
│       ├── App.jsx                    # تعریف همه مسیرها (Route) و محافظ‌های دسترسی
│       ├── config/navItems.jsx        # منبع واحد آیتم‌های منو (منوی کناری + «دسترسی‌های ویژه»)
│       ├── api/                       # یک فایل به‌ازای هر ماژول Backend (client.js = Axios)
│       ├── components/                # Layout، Protected/Admin/PermissionRoute، SiteNoticeReportRoute،
│       │                              # AccessGateDialog، AnnouncementDialog، MandatoryPasswordChangeGuard،
│       │                              # SchemaDiscoveryDialog، تنظیمات SMTP/SMS/بکاپ/پیش‌نیاز/اعلان،
│       │                              # UsageStatsCard، ServerStatsCard، BirthdayReactionBar،
│       │                              # انتخابگرهای تاریخ/ساعت جلالی، پلاک خودرو، EmployeePicker و...
│       ├── context/                   # AuthContext، BrandingContext، ThemeModeContext، OnlineStatusContext
│       ├── hooks/                     # useAccessGateStatus، useOnlineStatus
│       ├── pages/                     # صفحات — خلاصه در جدول زیر
│       ├── utils/                     # serviceWorker، push، pwaInstall، presenceSocket (WebSocket)،
│       │                              # geolocation، jalaliDate، attendanceGrouping، tableSort، roleLabels
│       ├── sw.js                      # Service Worker (با vite-plugin-pwa ساخته می‌شود)
│       ├── theme.js / rtlCache.js     # تم MUI و کش RTL
│       └── main.jsx
├── scripts/                           # seed_permissions، create_admin، generate_vapid_keys،
│                                      # verify_models.sh، pentest-live.sh
├── docs/                              # همین مستندات
├── install.sh                         # نصب/آپدیت یک‌دستوری روی Ubuntu Server (هم از خط‌فرمان،
│                                      # هم از دکمه «آپدیت» داخل پنل)
└── install-pgadmin.sh                 # نصب اختیاری pgAdmin 4 (نگاه کنید pgadmin.md)
```

## Service های Backend (خلاصه)

| حوزه | فایل‌ها در `app/services/` |
|---|---|
| احراز هویت و کاربران | `auth_service`، `password_reset_service`، `email_service`، `sms_service`، `user_management_service` |
| پرسنل و سازمان | `department_service`، `site_service`، `employee_contact_service` (Write-back ایمیل/موبایل)، `employee_cleanup_service`، `image_watermark` |
| نگاشت داینامیک | `schema_discovery_service`، `mapping_suggestion_service` |
| اطلاعیه‌ها | `notice_service`، `access_gate_service`، `push_service` |
| فیش حقوقی/کارکرد | `payroll_service`، `payroll_xml`، `payroll_pdf`، `payroll_xlsx`، `payroll_common`، `attendance_card_service`، `attendance_card_xlsx`، `attendance_card_pdf`، `simple_bidi` |
| تردد و حضور | `gps_attendance_service`، `monthly_attendance_service`، `kara_attendance_overlay` |
| مرخصی/ماموریت و کاراوب | `leave_request_service`، `leave_request_structure_service`، `leave_request_xlsx`، `kara_schema`، `kara_attendance_writeback` |
| ارزیابی عملکرد | `evaluation_structure_service`، `evaluation_period_service`، `evaluation_form_service`، `evaluation_assignment_service`، `evaluation_process_service`، `evaluation_reports_service`، `evaluation_report_xlsx` |
| سایر ماژول‌ها | `feedback_service`، `vehicle_service`، `birthday_greetings_service`، `birthday_reaction_service` |
| سیستم | `system_settings_service` (تنظیمات/برندینگ)، `backup_service`، `backup_settings_service`، `remote_backup_service`، `update_service`، `cache_service`، `usage_stats_service`، `server_stats_service` |

## صفحات Frontend (خلاصه)

| گروه | صفحات در `src/pages/` |
|---|---|
| ورود | `LoginPage`، `ForgotPasswordPage`، `ResetPasswordPage` |
| پرسنل (همه کاربران) | `PersonalDashboardPage` (`/my-dashboard`)، `ProfilePage`، `NoticesPage`، `NewNoticePage`، `FeedbackSubmitPage`، `MyVehiclesPage`، `LeaveRequestPage` (درخواست‌های من + کارتابل)، `MyPerformancePage`، `EvaluationFillPage`، `AttendanceClockPage`، `MonthlyAttendanceReportPage` |
| مدیریت سازمان | `DashboardPage`، `EmployeesPage`، `DepartmentsPage`، `SitesPage`، `SiteSettingsPage`، `SyncPage` |
| گزارش‌ها | `NoticeReportsPage`، `FeedbackReportPage`، `VehiclesReportPage`، `PresenceReportPage`، `ClockInOutReportPage`، `LeaveRequestsAdminListPage` |
| تنظیمات ماژول‌ها | `LeaveRequestStructurePage`، `BirthdayMessagesPage`، `EvaluationStructurePage`، `EvaluationPeriodsPage`، `EvaluationFormsPage`، `EvaluationFormBuilderPage`، `EvaluationReportsPage` |
| دسترسی و سیستم | `AccessManagementPage`، `RoleManagementPage`، `BulkRoleAssignmentPage`، `IpAllowlistPage`، `SystemSettingsPage`، `BackupPage`، `UpdatePage`، `NotFoundPage` |
