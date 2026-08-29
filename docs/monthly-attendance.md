# گزارش تردد ماهانه (کاراوب / Kara WorkFlow)

قابلیتی کاملاً مستقل از سیستم آزمایشی «ثبت ورود/خروج با GPS» — این یکی
مستقیماً از دستگاه‌های واقعی حضور و غیاب کارخانه می‌خواند (جدول
`DataFile` نرم‌افزار «کاراوب»)، از همان SQL Server هر سایت که برای Sync
پرسنل هم استفاده می‌شود.

## نکات کلیدی طراحی

- **بدون Permission**: طبق درخواست صریح، این گزارش نیاز به هیچ مجوز
  RBAC ندارد — هر پرسنلی خودکار دسترسی دارد، **مشروط به این‌که سایت
  خودش این قابلیت را فعال کرده باشد** (نه یک مجوز، یک قابلیت سطح Site).
- **جایگزینی کامل کارت‌های داشبورد**: کارت‌های «گزارش تردد» و «تردد
  امروز» در `PersonalDashboardPage.jsx` قبلاً به سیستم آزمایشی GPS
  (`can_clock_in_out`) وصل بودند؛ طبق تصمیم صریح، حالا کاملاً با این
  منبع جدید (`has_kara_workflow`) جایگزین شدند — سیستم GPS دیگر به این
  دو کارت وصل نیست (ولی خودش، صفحه `/attendance-clock`، دست‌نخورده باقی
  ماند).
- **امنیت**: `Emp_No` همیشه از `Employee` کاربر لاگین‌شده (سشن) خوانده
  می‌شود — هیچ پارامتر ورودی نمی‌تواند آن را Override کند. کوئری SQL
  کاملاً Parameterized است.

## معماری Backend

### فلگ سطح Site (نه Permission)

`Site.kara_workflow_enabled` (Migration 037، پیش‌فرض خاموش) — چون همه
سایت‌ها الزاماً از «کاراوب» استفاده نمی‌کنند. فقط برای سایتی با اتصال
از نوع SQL Server قابل‌فعال‌سازی است (`SiteService.set_kara_workflow_enabled`
این را اعتبارسنجی می‌کند). از پنل «سایت‌ها» → تنظیمات سایت → تب «گزارش
تردد ماهانه» قابل‌تغییر است.

### سرویس کوئری (`monthly_attendance_service.py`)

مستقل از Sync Engine (که برای «کل جدول را بگیر» طراحی شده) — یک اتصال
`pymssql` اختصاصی با کوئری Parameterized:

```sql
SELECT [Date], [Time], ROW_NUMBER() OVER (PARTITION BY [Date] ORDER BY [Time]) AS Seq
FROM [DataFile]
WHERE [Emp_No] = %(emp_no)s AND [Date] BETWEEN %(from_date)s AND %(to_date)s
```

منطق ورود/خروج کاملاً بر اساس ترتیب زمانی (`Seq` فرد=ورود، زوج=خروج) —
نه ستون `Direction` (که در داده واقعی همیشه ثابت است).

### توابع تاریخ شمسی جدید (`app/core/persian_date.py`)

- `jalali_days_in_month(year, month)`: تعداد واقعی روزهای یک ماه شمسی
  (شامل تشخیص کبیسه اسفند) — با تبدیل به میلادی و `timedelta` استاندارد
  پایتون (نه محاسبه دستی/هاردکد)، برای اطمینان کامل از صحت.
- `jalali_year_month_to_yyyymmdd_range(year, month)`: `(FromDate, ToDate)`
  به فرمت عددی `YYYYMMDD` — دقیقاً فرمت ستون `Date` در `DataFile`.

### Endpoint (`GET /monthly-attendance/report`)

- کاملاً در یک Router جدا (`endpoints/monthly_attendance.py`) — نه در
  `endpoints/attendance.py` (که مخصوص سیستم GPS است).
- `year`/`month` اختیاری — بدونشان، ماه شمسی جاری پیش‌فرض است.
- اگر سایت کاربر `kara_workflow_enabled` نداشته باشد یا اتصال دیتابیس
  تعریف نشده باشد، ۴۰۴ می‌دهد (نه تلاش برای اتصال و شکست با خطای خام).

### `has_kara_workflow` در `/auth/me`

از همان Query موجودی که `site_name`/`department_name` را هم می‌گیرد
(بدون Query اضافه) — `Site.kara_workflow_enabled` هم گرفته و به‌عنوان
یک فلگ ساده (نه Permission) در `UserOut` قرار می‌گیرد.

## Frontend

- **`MonthlyAttendanceReportPage.jsx`** (مسیر `/monthly-attendance`):
  جدول با ستون‌های ورود/خروج کاملاً پویا (بر اساس `max_pairs_in_month`)
  + `JalaliMonthYearFilter` (کامپوننت مشترک، همان الگوی گزارش ورود/خروج GPS).
- کارت «تردد امروز» در داشبورد: روز جاری شمسی را (با `gregorianToJalali`
  از `utils/jalaliDate.js` — همان تابع تبدیل تاریخ محلی موجود در پروژه،
  بدون کتابخانه خارجی) در آرایه `days` گزارش پیدا می‌کند و اولین
  ورود/آخرین خروج همان روز را نشان می‌دهد.
