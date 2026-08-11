# FAIPCO Portal

پرتال سازمانی برای مدیریت پرسنل، اطلاعیه‌ها، دسترسی‌ها و اتصال به دیتابیس‌های
چندگانه‌ی سایت‌های مختلف یک سازمان (چند کارخانه/شعبه، هرکدام با ساختار دیتابیس
پرسنلی متفاوت).

## فهرست

- [ویژگی‌ها](#ویژگی‌ها)
- [پشته فناوری](#پشته-فناوری)
- [ساختار پروژه](#ساختار-پروژه)
- [اجرای محلی (Development)](#اجرای-محلی-development)
- [راه‌اندازی Sync Engine](#راه‌اندازی-sync-engine)
- [سیستم اطلاعیه](#سیستم-اطلاعیه)
- [اطلاعیه فیش حقوقی (Payroll Notice)](#اطلاعیه-فیش-حقوقی-payroll-notice)
- [مدیریت پرسنل از پنل Admin](#مدیریت-پرسنل-از-پنل-admin)
- [دسترسی‌ها (RBAC)](#دسترسی‌ها-rbac)
- [نصب روی سرور Production](#نصب-روی-سرور-production)
- [محدودیت‌ها و تصمیم‌های آگاهانه طراحی](#محدودیت‌ها-و-تصمیم‌های-آگاهانه-طراحی)
- [کارهای باز / شناخته‌شده](#کارهای-باز--شناخته‌شده)
- [معماری](#معماری)

## ویژگی‌ها

- **Sync خودکار پرسنل** از دیتابیس‌های ناهمگون هر سایت (SQL Server / MySQL /
  PostgreSQL) — بدون نیاز به تغییر کد برای سایت جدید، فقط با تعریف Mapping
  ستون‌ها از پنل. فاصله زمانی اجرای خودکار از داخل پنل قابل تغییر است.
- **لاگین یکپارچه**: هم ورود مدیریتی (یوزرنیم/رمز عبور) و هم ورود پرسنل (کد
  پرسنلی + کد ملی) از یک فرم واحد.
- **اطلاعیه‌ها** با تعیین دقیق مخاطب: کل سازمان / یک سایت / یک یا چند واحد
  سازمانی / یک نقش / پرسنل خاص — همراه با آمار بازدید، Web Push، و حذف
  (Soft-Delete، با نگه‌داشتن رکورد در گزارش).
- **اطلاعیه فیش حقوقی**: آپلود یک فایل XML فیش حقوق (نقش `acc_manager`)،
  تطبیق خودکار با پرسنل از روی کد پرسنلی، و ارسال PDF جداگانه به هر نفر —
  هرکس فقط فیش خودش را می‌بیند.
- **RBAC چندلایه**: نقش‌های سراسری، نقش‌های محدود به یک سایت (Site-scoped)، و
  سرپرستی واحد سازمانی (بدون نیاز به تعریف نقش جداگانه).
- **مدیریت پرسنل از پنل**: فعال/غیرفعال کردن دستی، تعیین رمز عبور ورود.
- **PWA** با Push Notification (Web Push / VAPID) و به‌روزرسانی خودکار
  Service Worker بدون نیاز به خروج کاربر از حساب.
- **نصب یک‌دستوری** روی Ubuntu Server با `install.sh` (نصب یا آپدیت، به‌صورت
  خودکار تشخیص داده می‌شود).

## پشته فناوری

| لایه | تکنولوژی |
|---|---|
| Backend | FastAPI (Async) + SQLAlchemy 2 (Async) + Alembic |
| دیتابیس اصلی Portal | PostgreSQL |
| Auth | JWT (Access + Refresh با Sliding Window) |
| Scheduler | APScheduler (Sync خودکار پرسنل) |
| Frontend | React + MUI (RTL کامل با `stylis-plugin-rtl`) + Vite |
| Push | Web Push (VAPID) |
| PDF (فیش حقوقی) | ReportLab + arabic-reshaper + python-bidi |
| XLSX (فیش حقوقی) | openpyxl |
| Web Server تولید | Nginx (Reverse Proxy + Serve فایل‌های Frontend) |

## ساختار پروژه

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

## اجرای محلی (Development)

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

## راه‌اندازی Sync Engine

```bash
TOKEN="<access_token از /auth/login>"

# ۱. ساخت Site
curl -X POST http://localhost:8000/api/v1/sites \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "کارخانه ۱", "code": "SITE1"}'

# ۲. تعریف اتصال دیتابیس مبدأ (پسورد خودکار رمزنگاری و ذخیره می‌شود)
curl -X PUT http://localhost:8000/api/v1/sites/1/connection \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "db_type": "mssql", "host": "192.168.1.10", "port": 1433,
    "database_name": "HRDB", "username": "sa", "password": "SourceDbPass123"
  }'

# ۳. تعریف Mapping ستون‌ها (طبق ساختار واقعی جدول در آن Site)
curl -X PUT http://localhost:8000/api/v1/sites/1/mapping \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "table_name": "Personnel", "personnel_code_column": "Code",
    "national_code_column": "NationalID", "first_name_column": "Name",
    "last_name_column": "Family", "mobile_column": "Phone"
  }'

# ۴. تست اتصال، سپس اجرای دستی Sync
curl -X POST http://localhost:8000/api/v1/sync/1/test-connection -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/sync/1/run -H "Authorization: Bearer $TOKEN"

# ۵. مشاهده تاریخچه Sync
curl http://localhost:8000/api/v1/sync/1/logs -H "Authorization: Bearer $TOKEN"
```

برای سایتی که ستون‌هایش فرق دارد (مثلاً `employees`, `personnel_code`,
`national_code`, ...)، کافی است در مرحله ۳ مقادیر متفاوتی برای Mapping بفرستید —
**هیچ خط کدی تغییر نمی‌کند**.

### فاصله زمانی اجرای خودکار Sync

پیش‌فرض هر ۳۰ دقیقه (`SYNC_INTERVAL_MINUTES` در `.env`)، ولی از داخل پنل هم
قابل تغییر است — بدون نیاز به Restart سرور:

```bash
curl -X GET http://localhost:8000/api/v1/sync/settings -H "Authorization: Bearer $TOKEN"
curl -X PUT http://localhost:8000/api/v1/sync/settings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"interval_minutes": 15}'
```

مقدار جدید هم در دیتابیس (`system_settings`) ذخیره می‌شود (پس بعد از Restart هم
باقی می‌ماند) و هم بلافاصله روی Job در حال اجرا اعمال می‌شود. اگر `SYNC_ENABLED=false`
باشد، Sync خودکار اصلاً اجرا نمی‌شود (اجرای دستی از پنل همچنان کار می‌کند).

## سیستم اطلاعیه

```bash
curl -X POST http://localhost:8000/api/v1/notices \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "title": "اطلاعیه تعطیلی", "body": "روز پنج‌شنبه تعطیل است.", "priority": "high",
    "targets": [{"target_type": "site", "target_id": 1}, {"target_type": "role", "target_id": 1}]
  }'

curl -X POST http://localhost:8000/api/v1/notices/1/publish -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/v1/notices -H "Authorization: Bearer $TOKEN"       # نمای Admin (نیازمند notices.view)
curl http://localhost:8000/api/v1/notices/me -H "Authorization: Bearer $TOKEN"    # اطلاعیه‌های خودِ کاربر لاگین‌شده
```

`/notices/me` هوشمند است: بر اساس Site/Department/نقش‌های کاربر، فقط اطلاعیه‌های
واقعاً مرتبط را برمی‌گرداند — دقیقاً طبق طراحی `notice_targets`
(all / site / department / role / employee).

### حذف اطلاعیه

حذف همیشه **Soft-Delete** است:

```bash
curl -X DELETE http://localhost:8000/api/v1/notices/1 -H "Authorization: Bearer $TOKEN"
```

- بلافاصله از پنل همه‌ی کسانی که اطلاعیه را دریافت کرده بودند کنار می‌رود.
- رکورد فیزیکی هرگز پاک نمی‌شود — در گزارش «ارسالی من» و گزارش کامل Admin با
  برچسب «حذف شده» باقی می‌ماند (تا آمار بازدید از دست نرود).
- فقط خودِ فرستنده یا Admin اجازه حذف دارند.

## اطلاعیه فیش حقوقی (Payroll Notice)

نقش `acc_manager` («مدیر حسابداری»، تعریف‌شده در `scripts/seed_permissions.py`)
می‌تواند به‌جای نوشتن متن، یک فایل فیش حقوق آپلود کند — **هم XML و هم XLSX**
پشتیبانی می‌شود (بر اساس پسوند فایل خودکار تشخیص داده می‌شود):

```bash
curl -X POST http://localhost:8000/api/v1/notices/payroll \
  -H "Authorization: Bearer $TOKEN" \
  -F "title=فیش حقوق تیر ۱۴۰۵" \
  -F "body=" \
  -F "priority=normal" \
  -F "file=@payroll-export.xml"
```

**نحوه کار (کاملاً Generic — به نام فایل یا واحد خاصی وابسته نیست):**

1. فایل می‌تواند هر نامی داشته باشد و ریشه‌اش هر چیزی باشد؛ پارسر
   (`app/services/payroll_xml.py`) در هر عمقی از درخت دنبال تگ
   `<SalaryReceiptItem>` می‌گردد.
2. از هر رکورد، یک Attribute به نام `Code` (هرجای زیردرخت آن رکورد) به‌عنوان
   کد پرسنلی خوانده و با `Employee.personnel_code` تطبیق داده می‌شود.
3. **فقط** پرسنلی که کدشان پیدا شود، به‌صورت خودکار Target اطلاعیه
   (`NoticeTarget` از نوع `employee`) می‌شوند — انتخاب مخاطب کاملاً خودکار
   است، نه دستی.
4. برای هر پرسنل منطبق، فقط فیلدهای مربوط به خودش (`payroll_receipts`) ذخیره
   می‌شود؛ `GET /notices/{id}/payroll/mine` همیشه از روی
   `current_user.employee_id` فیلتر می‌کند — از این مسیر، دسترسی به فیش
   شخص دیگر ساختاراً غیرممکن است (نه فقط با Permission Check).
5. کدهایی که در XML بودند ولی در سیستم پیدا نشدند، در پاسخ همان درخواست
   گزارش می‌شوند (`missing_codes`) — ارسال نمی‌شوند.

پاسخ نمونه:

```json
{
  "notice_id": 42,
  "matched_employee_count": 87,
  "missing_codes": ["999999", "888888"],
  "invalid_row_count": 0
}
```

هر پرسنل PDF فیش خودش را از همان اطلاعیه در تب «دریافتی» دانلود می‌کند:

```bash
curl http://localhost:8000/api/v1/notices/42/payroll/mine -H "Authorization: Bearer $TOKEN" -o my-payroll.pdf
```

### ساختار واقعی فایل XML

فایل‌های واقعی معمولاً خروجی مستقیم یک گزارش‌ساز نوع SSRS/Telerik هستند —
یعنی به‌جای تگ‌های ساده مثل `<Amount>1000</Amount>`، مقدار و برچسب هر فیلد
به‌صورت **Attribute** (نه Element) روی گره‌های تودرتو (`Rectangle`, `Column`,
`Details`, ...) پخش شده‌اند. پارسر با یک الگوریتم heuristic این را می‌خواند:
- `Code` را در هر عمقی از رکورد پیدا می‌کند.
- زیردرخت‌هایی با نام `<SalaryReceipt*>` (مثل `SalaryReceiptPayment`،
  `SalaryReceiptDeduction`) را Section جدا در PDF می‌سازد.
- داخل هر Section، Attribute هایی با الگوی نام `TextboxN` / `Title` /
  `FactorTitleN` به‌عنوان «برچسب» و مقدار مجاورشان در ترتیب سند XML به‌عنوان
  «مقدار» جفت می‌شوند.

این heuristic برای فیلدهای اصلی فیش (حقوق پایه، کسورات، کارکرد، ...) قابل
اتکاست؛ فقط در چند ویجت خلاصه/جمع نهایی ممکن است ترتیب Attribute در XML با
ترتیب دیداری اصلی یکی نباشد — چون همان اعداد در بخش «کارکرد و جمع‌بندی» هم
با برچسب درست تکرار می‌شوند، این محدودیت عملاً بی‌اثر است. جزئیات کامل در
کامنت بالای `app/services/payroll_xml.py`.

### ساختار واقعی فایل XLSX (توصیه‌شده — دقیق‌تر از XML)

اگر امکانش هست، **XLSX را به XML ترجیح دهید** — همان گزارش SSRS وقتی به
Excel چاپ می‌شود، هر بخش (وام/کسور/مزایا/سایر) یک محدوده‌ی ستونی مجزا و
ثابت پیدا می‌کند و مقدار همیشه در ستون کوچک‌تر، برچسب در ستون بزرگ‌تر همان
سطر می‌آید — یعنی هیچ حدس‌زدنی لازم نیست (بر خلاف XML که برچسب/مقدار از
روی الگوی نام Attribute حدس زده می‌شود). با یک فایل واقعی ۲۰۱ رکوردی، پارسر
XLSX (`app/services/payroll_xlsx.py`) صفر خطای جفت‌سازی در بخش‌های اصلی
داشت (فقط نوار جمع‌بندی پایین فیش، که در XML هم همین محدودیت را دارد،
گاهی دقیق نیست — همان اعداد در بخش «سایر» درست تکرار می‌شوند).

الگوریتم: هر سلول برابر «کد پرسنلی:» شروع یک بلوک پرسنل جدید است؛ نزدیک‌ترین
سطر زیرش که شامل «وام»/«کسور»/«مزایا»/«سایر» باشد، محدوده ستونی هر Section
را مشخص می‌کند؛ داخل هر محدوده، اولین سلول غیرخالی هر سطر «مقدار» و آخرین
سلول غیرخالی همان سطر «برچسب» آن مقدار است.

### فونت فارسی برای PDF (معمولاً نیازی به اقدام دستی نیست)

تولید PDF از **ReportLab** استفاده می‌کند. کد به این ترتیب فونت مناسب را پیدا می‌کند:
1. اگر `PERSIAN_FONT_PATH` (پیش‌فرض:
   `backend/app/assets/fonts/Vazirmatn-Regular.ttf`) وجود داشته باشد، از همان استفاده می‌شود.
2. در غیر این‌صورت، به‌صورت خودکار دنبال **DejaVu Sans Condensed** می‌گردد
   (مسیر استاندارد `/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf`،
   و در نبودش DejaVu Sans معمولی) — این فونت‌ها معمولاً از قبل روی
   توزیع‌های اوبونتو/دبیان نصب‌اند و حروف فارسی/عربی را کامل دارند. نسخه
   Condensed عمداً در اولویت است چون فشرده‌تر است و اندازه‌بندی صفحه فیش
   حقوقی (طراحی‌شده برای جا شدن در یک صفحه، مطابق چیدمان اصلی گزارش با فونت
   Tahoma) به فضای کمتر نیاز دارد — پس **در بیشتر نصب‌ها بدون هیچ اقدام
   دستی، PDF فارسی هم درست نمایش داده می‌شود و هم در یک صفحه جا می‌شود**.
3. اگر هیچ‌کدام پیدا نشود، به فونت پیش‌فرض بدون پشتیبانی فارسی سقوط می‌کند
   (متن فارسی درست دیده نمی‌شود) و یک هشدار در Log ثبت می‌شود.

برای کیفیت بهتر تایپوگرافی (اختیاری)، همچنان توصیه می‌شود یک فونت اختصاصی
فارسی مثل [Vazirmatn](https://github.com/rastikerdar/vazirmatn) در مسیر بالا
قرار بگیرد — جزئیات در `backend/app/assets/fonts/README.md`.

همچنین اگر کتابخانه‌های `arabic-reshaper`/`python-bidi` (در `requirements.txt`)
به هر دلیلی روی سرور نصب نشوند، `app/services/simple_bidi.py` یک
پیاده‌سازی حداقلی و بدون‌وابستگی از Shaping/Bidi را به‌عنوان شبکه ایمنی
جایگزین می‌کند — یعنی تولید PDF فارسی هرگز کاملاً متوقف نمی‌شود.

### چیدمان دقیق PDF (تنظیم‌شده مطابق نمونه واقعی سازمان)

اندازه فونت‌ها، Padding، رنگ پس‌زمینه نوار مشخصات (`#d3d3d3`)، و مهم‌تر از
همه **عرض نامساوی ۴ ستون اصلی** (`وام`≈۱۹٪، `کسور`≈۲۱٪، `مزایا`≈۲۴٪،
`سایر`≈۳۶٪ از عرض صفحه) مستقیماً از CSS خروجی MHTML گزارش اصلی این سازمان
استخراج و در `payroll_pdf.py` اعمال شده‌اند — چون بدون این عرض نامساوی،
برچسب‌های طولانی ستون «سایر» (مثل «دستمزد و مزایای مشمول بیمه تامین
اجتماعی») می‌شکنند و کل فیش به ۲ صفحه سرریز می‌کند. این نسبت‌ها برای این
ساختار خاص گزارش (۴ ستون وام/کسور/مزایا/سایر) تنظیم شده‌اند؛ اگر سازمان
دیگری Section های متفاوتی داشته باشد، عرض به‌طور مساوی بین آن‌ها تقسیم
می‌شود.

جدول اصلی عمداً به‌صورت یک جدول **تخت** (نه تودرتو) با ۸ ستون (مقدار+برچسب
برای هرکدام از ۴ Section) ساخته شده، نه ۴ سلول که هرکدام یک جدول کامل
داخلش باشد — چون ReportLab نمی‌تواند محتوای یک جدول تودرتوی خیلی بلند
(مثل ستون «سایر» با ۳۰+ ردیف) را بین صفحات بشکند و در آن حالت، اگر فیش یک
پرسنل خاص طولانی‌تر از حد معمول باشد (مثلاً وام‌دار با موارد کسور بیشتر)،
کل تولید PDF متوقف می‌شد. با تست روی هر ۲۹۰ رکورد واقعی (۸۹ از XML + ۲۰۱ از
XLSX)، همه در دقیقاً یک صفحه جا شدند.

## مدیریت پرسنل از پنل Admin

از صفحه «پرسنل» (`/employees`)، دو وضعیت کاملاً مستقل از هم نمایش داده می‌شود:

- **«وضعیت Sync»** (فقط نمایشی): همان `is_active` که همیشه توسط Sync Engine و
  طبق Mapping هر Site محاسبه می‌شود (مثلاً از روی ستون `IsCut`). از پنل قابل
  ویرایش نیست — چون منبع حقیقت آن دیتابیس مبدأ است.
- **«فعال در پرتال»** (`is_enabled`, قابل تغییر با یک Switch): تصمیم دستی
  Admin، در ستونی کاملاً جدا ذخیره می‌شود که **هیچ اجرای Sync (خودکار یا
  دستی) هرگز آن را نمی‌خواند یا بازنویسی نمی‌کند**. یعنی اگر پرسنلی را از
  اینجا غیرفعال کنید، حتی اگر در منبع همچنان «فعال» باشد، تا وقتی خودتان
  دوباره فعالش نکنید غیرفعال می‌ماند.

وضعیت واقعیِ «آیا این پرسنل مجاز به ورود است؟» ترکیب هر دو است:
`is_active AND is_enabled`. غیرفعال‌کردن از پنل، بلافاصله حساب کاربری مرتبط
(در صورت وجود) را هم مسدود می‌کند — چه ورود با کد ملی باشد چه با رمز اختصاصی.

### رمز عبور اختصاصی

پیش‌فرض پرسنل با «کد پرسنلی + کد ملی» وارد می‌شود. از دو مسیر می‌توان رمز
عبور اختصاصی جایگزین آن تعیین کرد:

- **خودِ پرسنل** از منوی حساب کاربری، گزینه «تغییر رمز عبور» را می‌زند — برای
  اولین بار، «رمز عبور فعلی» همان کد ملی خودش است.
- **Admin** از صفحه «پرسنل»، روی آیکون 🔑 مقابل هر پرسنل کلیک می‌کند.

به‌محض تعیین رمز جدید (از هر دو مسیر):
- `has_custom_password=True` می‌شود و **کد ملی دیگر به‌عنوان روش ورود کار
  نمی‌کند** — فقط «کد پرسنلی + رمز عبور جدید» معتبر است.
- رمز عبور به‌طور کامل روی جدول `users` ذخیره می‌شود (نه `employees`)، پس با
  هیچ Sync ای پاک یا بازنویسی نمی‌شود.
- Admin هر وقت بخواهد می‌تواند از همان دیالوگ، رمز را عوض کند یا با «بازگشت
  به ورود با کد ملی» دوباره روش پیش‌فرض را فعال کند.

## دسترسی‌ها (RBAC)

- **superadmin**: دسترسی کامل به همه‌چیز. فقط کاربر `admin` که هنگام نصب
  ساخته می‌شود این نقش را دارد؛ از UI مدیریت دسترسی قابل انتصاب نیست.
- **site_manager**: نقش Site-scoped — هنگام انتصاب حتماً `site_id` داده
  می‌شود. می‌تواند کل سایت / واحدهای همان سایت / پرسنل همان سایت را برای
  اطلاعیه هدف بگیرد.
- **middle_manager**: نقش سراسری (بدون `site_id`) — می‌تواند هر واحد یا هر
  پرسنلی در کل سازمان را هدف بگیرد (نه Broadcast کامل).
- **acc_manager** («مدیر حسابداری»): فقط `notices.payroll` دارد — نمی‌تواند
  اطلاعیه متنی معمولی بسازد یا Site/Department انتخاب کند؛ تنها کاری که
  می‌کند آپلود XML فیش حقوقی است و مخاطبان کاملاً خودکار از روی همان فایل
  تعیین می‌شوند (بخش [اطلاعیه فیش حقوقی](#اطلاعیه-فیش-حقوقی-payroll-notice)).
- **سرپرست واحد**: نقش RBAC جداگانه‌ای نیست — کافی است از
  `PUT /departments/{id}/supervisor` مستقیماً سرپرست تعیین شود. یک نفر می‌تواند
  هم‌زمان سرپرست چند واحد باشد و/یا نقش `middle_manager` هم داشته باشد.

Permission های کامل (`employees.*`, `sites.*`, `sync.*`, `notices.*`,
`roles.manage`, `users.manage`) در `scripts/seed_permissions.py` تعریف شده‌اند
و با اجرای همان اسکریپت (Idempotent، اجرای چندباره بی‌خطر است) در دیتابیس Seed
می‌شوند.

## نصب روی سرور Production

روی یک Ubuntu Server (22.04 یا 24.04)، با دسترسی root:

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh | sudo bash
```

یا با آرگومان‌های دلخواه:

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh -o install.sh
sudo bash install.sh --domain portal.mycompany.com --admin-username admin
```

اسکریپت به‌صورت خودکار **نصب یا آپدیت** را تشخیص می‌دهد (بر اساس اینکه
`backend/.env` از قبل وجود دارد یا نه):

- **نصب تازه**: پیش‌نیازها (Python، Node.js، PostgreSQL، Nginx) → ساخت
  دیتابیس با پسورد تصادفی امن → Clone سورس → نصب وابستگی‌ها → تولید `.env` با
  کلیدهای امنیتی یکتا + کلیدهای VAPID → Migration ها → Build فرانت‌اند → سرویس
  systemd (`faipco-backend`) → پیکربندی Nginx → Seed اولیه + ساخت کاربر Admin
  → تنظیم فایروال (UFW).
- **آپدیت** (وقتی نصب قبلی پیدا شود): `.env`، پسورد دیتابیس، کلیدهای VAPID و
  خودِ دیتابیس **هرگز دست‌خورده نمی‌شوند** — فقط سورس رفرش، وابستگی‌ها دوباره
  نصب، Migration های جدید به‌صورت افزایشی اجرا (`alembic upgrade head`،
  هیچ‌وقت داده‌ای پاک نمی‌کند)، فرانت‌اند دوباره Build، و سرویس‌ها Restart
  می‌شوند. یعنی هر بار که روی GitHub Push می‌کنید، همین یک دستور برای Deploy
  کافی است.

**آرگومان‌های قابل استفاده:**

| آرگومان | توضیح | پیش‌فرض |
|---|---|---|
| `--domain` | دامنه پرتال (فقط برای CORS استفاده می‌شود) | ندارد (فقط IP سرور) |
| `--admin-username` | نام کاربری Admin اولیه (فقط نصب تازه) | `admin` |
| `--admin-password` | رمز عبور Admin اولیه (فقط نصب تازه) | `admin` |
| `--install-dir` | مسیر نصب روی سرور | `/var/www/html` |
| `--repo` | آدرس Git Repository | `github.com/milad-mma/faipco-portal` |
| `--branch` | Branch مورد استفاده | `main` |

⚠️ اگر `--admin-password` ندهید، پسورد پیش‌فرض `admin` است — حتماً بلافاصله
بعد از اولین ورود عوض کنید.

**نکته مهم درباره SSL**: این اسکریپت دیگر خودش SSL/Let's Encrypt را مدیریت
نمی‌کند — Nginx محلی همیشه روی HTTP ساده (پورت ۸۰) اجرا می‌شود و SSL باید توسط
یک Reverse Proxy خارجی (که از قبل روی سرور یا جلوی آن راه‌اندازی شده) تأمین
شود. آرگومان `--domain` فقط برای تنظیم صحیح CORS استفاده می‌شود.

نصب با Docker از پروژه حذف شده است؛ تنها روش پشتیبانی‌شده همین `install.sh` است.

## محدودیت‌ها و تصمیم‌های آگاهانه طراحی

این موارد **باگ نیستند** — تصمیم‌های طراحی آگاهانه‌اند که باید در نظر داشته باشید:

- **ورود پرسنل با کد ملی**: کد ملی به‌عنوان «رمز عبور» پیش‌فرض پرسنل استفاده
  می‌شود و به‌صورت Plaintext (نه Hash شده) با دیتابیس مقایسه می‌شود. این یک
  تصمیم UX رایج در پرتال‌های سازمانی داخلی است، ولی از نظر امنیتی ضعیف‌تر از
  رمز واقعی است (چون کد ملی معمولاً کاملاً محرمانه نیست). به همین دلیل، هم
  خودِ پرسنل و هم Admin می‌توانند رمز عبور اختصاصی تعیین کنند که کد ملی را
  به‌طور کامل به‌عنوان روش ورود غیرفعال می‌کند (بخش «مدیریت پرسنل از پنل Admin»).
- **Employee.is_active به‌طور کامل تحت مالکیت Sync Engine است** و Admin
  نباید و نمی‌تواند مستقیماً آن را تغییر دهد؛ برای فعال/غیرفعال‌کردن دستی از
  Admin، ستون کاملاً جدای `is_enabled` وجود دارد که Sync هرگز آن را نمی‌بیند.
- **Query های Sync Adapter، نام جدول/ستون را مستقیم Interpolate می‌کنند** (نه
  Parameterized) چون این مقادیر از `employee_mappings` (که فقط از پنل مدیریتی
  قابل تغییر است) می‌آیند، نه از ورودی کاربر نهایی. اگر در آینده اجازه تعریف
  Mapping به نقش‌های غیر-superadmin داده شود، این نکته باید بازبینی شود.
- **حذف اطلاعیه فقط Soft-Delete است**: رکورد هرگز فیزیکی پاک نمی‌شود (برای
  حفظ آمار بازدید در گزارش‌ها).
- **تطبیق کد پرسنلی فیش حقوقی سراسری است، نه محدود به یک Site**: چون XML
  فیش حقوقی هیچ اطلاعاتی درباره‌ی Site ندارد، تطبیق `Code` با
  `Employee.personnel_code` در کل سیستم انجام می‌شود. اگر (به‌ندرت) همان کد
  پرسنلی در دو Site مختلف تکراری باشد، فیش به هر دو نفر ارسال می‌شود — این
  یک محدودیت ذاتی فرمت XML ورودی است، نه باگ.
- **جفت‌سازی برچسب/مقدار XML فیش حقوقی یک Heuristic است**: چون فرمت واقعی
  XML (خروجی SSRS) هیچ نشانه صریحی ندارد که کدام Attribute «برچسب» و کدام
  «مقدار» است، `payroll_xml.py` بر اساس الگوی نام Attribute (`TextboxN`،
  `Title`، `FactorTitleN`) و نوع محتوا (عددی/متنی) حدس می‌زند. برای فیلدهای
  اصلی فیش (حقوق پایه، کسورات، کارکرد، ...) کاملاً قابل‌اتکاست و با فایل
  واقعی این سازمان (۸۹ رکورد) تست شده؛ فقط در نوار جمع‌بندی پایین فیش («جمع
  مزایا/کسور/اقساط وام») ممکن است ترتیب دقیق نباشد — چون همان اعداد در ستون
  «سایر» هم با برچسب درست تکرار می‌شوند، این محدودیت عملاً کم‌اثر است.
  جزئیات و استثناهای شناخته‌شده در کامنت بالای همان فایل مستند شده.

## کارهای باز / شناخته‌شده

موارد زیر هنوز پیاده‌سازی نشده‌اند:

1. لیست واحدهای سازمانی در دیالوگ «مدیریت دسترسی» گاهی خالی نمایش داده می‌شود.
2. تغییر سرپرستی واحد همین الان هم بلافاصله ذخیره می‌شود (بدون دکمه جدا)، ولی
   بازخورد بصری موفقیت (مثلاً یک پیام کوتاه) هنوز اضافه نشده.
3. ستون «واحد سازمانی» و امکان Sort بر اساس آن در صفحه «پرسنل» هنوز اضافه نشده.
4. در AppBar، به‌جای نام پرسنل، کد پرسنلی (`username`) نمایش داده می‌شود.
5. جعبه «سرپرستی‌های من» وقتی کاربر سرپرست هیچ واحدی نیست، حالت خالی مناسبی ندارد.

## معماری

جزئیات کامل معماری، دلایل انتخاب تکنولوژی‌ها، الگوی لایه‌بندی Backend، و طرح
داخلی Sync Engine در [`docs/architecture.md`](docs/architecture.md) آمده است.
