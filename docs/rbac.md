# دسترسی‌ها (RBAC)

## ⚠️ اصل بنیادین: ایزوله‌سازی چندسایتی

این پروژه از ابتدا **چندسایته** طراحی شده — هر Site پرسنل، مدیر، و واحدهای
سازمانی جدای خودش را دارد (و معمولاً حتی به یک دیتابیس منبع کاملاً جدا هم
وصل است، از طریق Sync Engine). قانون کلی: کسی که فقط نقش Site-scoped دارد
(مثل `site_manager` یا `hr-manager` وقتی برای یک Site خاص انتصاب شده)
**هرگز نباید هیچ داده‌ای از سایت دیگر ببیند** — نه پرسنل، نه گزارش، نه
اطلاعیه — مگر Admin واقعی (`is_superuser`).

این قانون در `app/core/site_access.py` (دو تابع مشترک،
`get_accessible_site_ids` و `get_sites_with_permission`) پیاده‌سازی شده و
باید در **هر** Endpoint جدیدی که داده پرسنل/گزارش را برمی‌گرداند و site_id
در Path/Query مشخصی ندارد، استفاده شود — نه `require_permission` ساده (که
بدون `site_scoped=True` فقط می‌پرسد «آیا این مجوز را برای *هر* سایتی
دارد؟» و داده را به سایت خاصی محدود نمی‌کند، و site_scoped=True هم فقط
وقتی site_id مستقیم در URL باشد کار می‌کند).

### ابزارهای مشترک بررسی دسترسی (Backend)

| ابزار | فایل | کاربرد |
|---|---|---|
| `require_permission(code)` | `core/deps.py` | «آیا کاربر این مجوز را از *هر* انتصابی (سراسری یا هر سایتی) دارد؟» — از `get_all_permission_codes` استفاده می‌کند |
| `require_permission(code, site_scoped=True)` | `core/deps.py` | فقط وقتی `site_id` در Path/Query است؛ از `get_permission_codes(user, site_id)` (انتصاب سراسری + همان سایت) |
| `require_superuser` | `core/deps.py` | فقط Admin واقعی؛ هیچ Permission Code ای قبول نمی‌شود |
| `get_accessible_site_ids` | `core/site_access.py` | قاعده کلی «کدام سایت‌ها» (نقش سایتی + سرپرستی واحد + سایت خودِ پرسنل) |
| `get_sites_with_permission` | `core/site_access.py` | سایت‌هایی که کاربر *همین* مجوز را برایشان دارد (`None` = نامحدود) |
| `get_sites_with_permission_prefix` | `core/site_access.py` | همان، برای خانواده مجوزهای پیشونددار (مثل `leave_requests.view.type.`) |
| `require_site_permission(db, user, site_id, code)` | `core/site_permission_deps.py` | وقتی `site_id` باید از خودِ رکورد (دوره/فرم/نوع مرخصی/…) Resolve شود؛ رکورد سراسری (`site_id=None`) فقط با مجوز سراسری |

Admin واقعی (`is_superuser`) در همه این ابزارها بدون هیچ بررسی عبور می‌کند.

**نکته طراحی مهم**: اگر کاربری **حداقل یک نقش سراسری** (بدون `site_id`)
داشته باشد (مثل `middle_manager`، یا `hr-manager`/`acc_manager` وقتی
سراسری انتصاب شده‌اند)، به **همه** سایت‌ها دسترسی پیدا می‌کند — چون این
نقش‌ها ذاتاً برای کار بین‌سایتی طراحی شده‌اند. اگر روزی نقش سراسری جدیدی
اضافه کردید که **نباید** بین‌سایتی باشد، حتماً همین‌جا (`site_access.py`)
هم بازبینی شود.

⚠️ از وقتی `site_id` برای انتصاب تکی نقش اجباری شده
(`AssignRoleIn.site_ids`، حداقل یک سایت)، انتصاب سراسری جدید فقط از
داده‌های قدیمی/Migration می‌آید — جزئیات در
[`role-management.md`](role-management.md).

### ⚠️ باگ‌های واقعی کشف و رفع‌شده (۲۰۲۶-۰۸)

با یک بازبینی کامل، چند Endpoint پیدا شد که این قانون را رعایت نمی‌کردند —
همه رفع شدند:

1. **`GET /employees` کاملاً باز بود**: فقط چک می‌کرد کاربر لاگین باشد، نه
   اینکه واقعاً به آن سایت دسترسی داشته باشد. یعنی هر کاربر لاگین‌شده‌ای
   (حتی یک پرسنل عادی سایت A) می‌توانست با `?site_id=X` کد ملی، شماره
   موبایل، و مشخصات کامل پرسنل هر سایت دیگری را ببیند — چون این Endpoint
   عمداً برای جست‌وجوی گیرنده اطلاعیه باز گذاشته شده بود، ولی هیچ محدودیت
   سایتی روی همان جست‌وجو اعمال نمی‌کرد (فقط جلوی *ارسال* واقعی را
   می‌گرفت، نه جلوی *دیدن*).
2. **`attendance.view_clock_records` و `attendance.view_logs`** بدون
   `site_scoped=True` چک می‌شدند — یعنی اگر با این مجوز Site-scoped
   انتصاب می‌شدید، اصلاً هیچ گزارشی نمی‌دیدید (بیش‌ازحد محدود)؛ اگر
   سراسری انتصاب می‌شدید، گزارش همه سایت‌ها را می‌دیدید (بیش‌ازحد باز).
3. **`/employees/count`، `/employees/portal-disabled-count`،
   `/employees/birthdays-today`** هم همان مشکل `GET /employees` را داشتند
   (حساسیت کمتر — فقط شمار یا نام/واحد، نه کد ملی — ولی برای هم‌خوانی
   کامل رفع شدند).

بررسی شد و **درست** تشخیص داده شد (بدون نیاز به تغییر): هدف‌گیری اطلاعیه
(`_can_target`)، گزارش اطلاعیه سایتی (`/notices/site-report`)، مدیریت
دستی رکورد ورود/خروج، عکس پرسنل، انتصاب سرپرست واحد، انتصاب دسته‌جمعی نقش.
لیست سایت‌ها/واحدها عمداً باز مانده — چون فقط نام/کد است (داده حساس نیست).

## نقش‌های پیش‌فرض

نقش‌ها داده‌اند نه کد — Admin می‌تواند از پنل «مدیریت نقش/مجوز» مجوزهای
هر نقش (به‌جز superadmin) را تغییر دهد یا نقش جدید بسازد. فهرست زیر
وضعیت *پیش‌فرض* پس از Seed/Migration است:

- **superadmin**: همه Permission های Seed. در عمل دسترسی کامل از فلگ
  `User.is_superuser` می‌آید (نه از خودِ این نقش) — همه بررسی‌ها برای
  `is_superuser` از قبل True برمی‌گردانند. این نقش از UI/API نه قابل
  انتصاب است، نه ویرایش، نه حذف، و در فهرست نقش‌ها نمایش داده نمی‌شود.
- **site_manager**: نقش Site-scoped — هنگام انتصاب حتماً `site_id` داده
  می‌شود. می‌تواند کل سایت / واحدهای همان سایت / پرسنل همان سایت را برای
  اطلاعیه هدف بگیرد. همچنین منوی «گزارش اطلاعیه‌ها» را می‌بیند — نه گزارش
  کامل Admin، بلکه فقط اطلاعیه‌هایی که به سایت(های) تحت مدیریتش رسیده، از
  هر فرستنده‌ای (نگاه کنید [`docs/notices.md`](notices.md)).
- **middle_manager**: نقش سراسری (بدون `site_id`) — می‌تواند هر واحد یا هر
  پرسنلی در کل سازمان را هدف بگیرد (نه Broadcast کامل).
- **acc_manager** («مدیر حسابداری»): `notices.payroll` (+ `notices.view`) — نمی‌تواند
  اطلاعیه متنی معمولی بسازد یا Site/Department انتخاب کند؛ تنها کاری که
  می‌کند آپلود XML فیش حقوقی است و مخاطبان کاملاً خودکار از روی همان فایل
  تعیین می‌شوند.
- **hr-manager** («مدیر منابع انسانی»): اطلاعیه فیش کارکرد (با آپلود اکسل،
  دقیقاً هم‌ساختار acc_manager) می‌سازد، گزارش ورود/خروج آزمایشی GPS
  پرسنل سایت(های) انتصاب را می‌بیند و می‌تواند رکورد ورود/خروج را دستی اضافه/ویرایش/حذف
  کند (`attendance.manage_clock_records`)، و پیام‌های تبریک تولد (متن‌ها +
  ساعت ارسال) را مدیریت می‌کند.
- **attendance-pilot**: پرسنل مجاز به استفاده از «ثبت ورود/خروج آزمایشی»
  مبتنی بر GPS — یک قابلیت آزمایشی؛ ثبت ورود/خروج رسمی همچنان از طریق
  دستگاه‌های تعبیه‌شده در کارخانه انجام می‌شود. معمولاً با
  [انتصاب دسته‌جمعی](#انتصاب-دسته‌جمعی-نقش) به همه پرسنل یک سایت داده می‌شود.
- **حراست** (Migration `032`، `is_system=False`): به‌طور پیش‌فرض فقط
  `vehicles.view_all`. در عمل معمولاً مجوزهای به‌تفکیک نوع مرخصی
  (`leave_requests.view.type.*`) هم به آن داده می‌شود.
- **سرپرست واحد**: نقش RBAC جداگانه‌ای نیست — با
  `PUT /departments/{id}/supervisor` (مجوز `users.manage`) یا از «ساختار
  ارزیابی» (`PUT /performance/departments/{id}/supervisor`، مجوز
  `performance.structure.manage`) تعیین می‌شود. سرپرستی واحد هم در
  `get_accessible_site_ids` سایت آن واحد را قابل‌دسترسی می‌کند و هم اجازه
  ارسال اطلاعیه به همان واحد را (بدون هیچ نقشی) می‌دهد. یک نفر می‌تواند
  هم‌زمان سرپرست چند واحد باشد و/یا نقش دیگری هم داشته باشد.
- **ارزیاب عملکرد / تأییدکننده مرخصی**: این‌ها هم نقش RBAC نیستند — از
  ساختار ارزیابی (سرپرست/مدیر/سرشیفت) و تنظیمات مرخصی (تأییدکننده واحد،
  مسئول منابع انسانی سایت) می‌آیند. مجوز `performance.evaluate` در
  دیتابیس هست ولی در هیچ کدی چک نمی‌شود.

## انتصاب دسته‌جمعی نقش

از پنل («مدیریت دسترسی» → «انتصاب دسته‌جمعی نقش»)، یک نقش را هم‌زمان به
همه پرسنل **فعال** یک سایت و/یا یک واحد سازمانی خاص (یا فهرست مشخصی از
`employee_ids`) اختصاص می‌دهد — بدون نیاز به انتخاب یکی‌یکی
(`POST /users/bulk-assign-role`، مجوز `users.manage`). قبل از اعمال،
تعداد دقیق پرسنل مطابق فیلتر نشان داده می‌شود. پرسنلی که هنوز هیچ‌وقت
وارد پرتال نشده هم مشکلی ندارد؛ حساب کاربری‌اش همان لحظه خودکار ساخته
می‌شود (همان منطق ساخت حساب هنگام اولین ورود موفق).

- انتصاب هرگز سراسری نیست: اگر فیلتر `site_id` داده شود همان روی
  انتصاب ذخیره می‌شود، وگرنه سایت خودِ هر پرسنل.
- غیر-Admin فقط برای سایت/واحد/پرسنلِ داخل سایت‌های `users.manage` خودش.
- پاسخ: `assigned_count`، `already_had_count`، `not_found_count`، `total_matched`.

## فهرست کامل Permission ها

دو منبع دارند:

- **`scripts/seed_permissions.py`** (Idempotent): مجوزهای پایه + نقش‌های
  superadmin/site_manager/middle_manager/acc_manager/hr-manager/attendance-pilot.
- **Migration ها** (`database/migrations/versions`): هر مجوزی که بعداً
  اضافه شده (ستون «منبع» پایین).

⚠️ Seed به‌روز نیست: مجوزهای Migration ها را ندارد، و هنوز
`notices.target.role` را دارد که Migration `036` حذفش کرده — اجرای دوباره
Seed آن را (بی‌اثر) برمی‌گرداند. توضیحات «فقط superadmin» در Seed هم
منسوخ‌اند (Migration `036` در دیتابیس اصلاحشان کرد) — همه مجوزها به هر
نقشی قابل‌تخصیص‌اند.

فلگ‌ها در `GET /auth/me` (`AuthService.get_me`) از
`get_all_permission_codes` (بدون فیلتر سایت) محاسبه می‌شوند و فقط
منو/مسیر Frontend را کنترل می‌کنند؛ محدودسازی داده به سایت همیشه سمت
سرور انجام می‌شود. برای `is_superuser` همه فلگ‌ها True است.

| کد | منبع | فلگ `/auth/me` | کجا اعمال می‌شود |
|---|---|---|---|
| `employees.view` | Seed / 033 | `can_view_employees` | فقط منو/مسیر «پرسنل»؛ خودِ `GET /employees` با `get_accessible_site_ids` محدود می‌شود، نه این مجوز |
| `employees.create` | Seed / 033 | `can_create_employees` | `POST /employees` (سایت‌محور) |
| `employees.update` | Seed | `can_update_employees` | `PATCH /employees/{id}` |
| `sites.view` | Seed | `can_view_sites` (یا `sites.manage`) | صفحه «سایت‌ها» فقط‌خواندنی |
| `sites.manage` | Seed | `can_manage_sites` | ساخت/ویرایش/حذف سایت، اتصال دیتابیس، Schema Discovery، نگاشت ستون پرسنل/تردد، ساخت واحد، «تنظیمات مرخصی/ماموریت» (نگاشت، نوع‌ها، تأییدکننده، مسئول HR) |
| `sync.view` | Seed | `can_view_sync` | وضعیت/تاریخچه Sync |
| `sync.run` | Seed | `can_run_sync` | اجرای دستی Sync یک سایت |
| `sync.manage` | Seed | `can_manage_sync` | فاصله Sync خودکار، فعال/غیرفعال‌کردن اتصال سایت |
| `notices.view` | Seed | — | `GET /notices`، `/notices/admin-report`، `/notices/stats-summary`، دیدن خوانندگان هر اطلاعیه |
| `notices.create` | Seed | — | ⚠️ هیچ‌جا چک نمی‌شود (اجازه ارسال از `notices.target.*` می‌آید) |
| `notices.target.all` | Seed | — | اطلاعیه به کل سازمان |
| `notices.target.site` / `.department` / `.employee` | Seed | — | هدف‌گیری سایت/واحد/پرسنل — سایت‌محور |
| `notices.payroll` | Seed | — | `POST /notices/payroll` (فیش حقوقی) |
| `notices.attendance_card` | Seed | — | `POST /notices/attendance-card` (فیش کارکرد) |
| `notices.site_report` | 035 | `can_view_site_notice_report` | «گزارش اطلاعیه‌ها» (`/notices/site-report`) — سایت‌محور |
| `roles.manage` | Seed | `can_manage_roles` | منوی «مدیریت نقش/مجوز» + `GET /users/roles` |
| `users.manage` | Seed | `can_manage_users` | «مدیریت دسترسی»، انتصاب تکی/دسته‌جمعی نقش، `/users/permissions` و CRUD `/users/role-catalog`، سرپرست واحد، تعیین/حذف رمز پرسنل، پاک‌سازی پرسنل غیرفعالِ بی‌سابقه — سایت‌محور |
| `system.backup` | Seed | `can_manage_backup` | پشتیبان‌گیری/بازیابی، آمار مصرف/سرور، `check-update`/`apply-update`/`update-status` |
| `system.cache_bust` | Seed | `can_bust_cache` | `POST /system/cache-bust` |
| `system.ip_allowlist` | Seed | `can_manage_ip_allowlist` | «رنج‌های IP مجاز» + متن پیام مسدودی |
| `system.settings` | 034 | `can_manage_system_settings` | «تنظیمات سامانه»: پس‌زمینه ورود، برندینگ/لوگو، SMTP، پیامک |
| `attendance.clock_in_out` | Seed | `can_clock_in_out` | ثبت ورود/خروج آزمایشی GPS + WebSocket حضور |
| `attendance.view_logs` | Seed | `can_view_attendance_logs` | «پرسنل آنلاین» — سایت‌محور |
| `attendance.view_clock_records` | Seed | `can_view_clock_records` | «گزارش ورود و خروج» — سایت‌محور |
| `attendance.manage_clock_records` | Seed | `can_manage_clock_records` | افزودن/ویرایش/حذف دستی رکورد ورود/خروج |
| `hr.birthday_messages` | Seed | `can_manage_birthday_messages` | «پیام‌های تبریک تولد» (`/hr/birthday-*`) |
| `vehicles.view_all` | 032 | `can_view_vehicles_report` | «خودروهای پرسنل» — سایت‌محور |
| `vehicles.manage` | 032 | `can_manage_vehicles` | ویرایش/حذف خودروی هر پرسنل |
| `feedback.view` | 040 | `can_view_feedback` | «انتقادات و پیشنهادات» سایت(های) انتصاب |
| `feedback.view_all` | 040 | `can_view_feedback` | همان، کل سازمان |
| `performance.structure.manage` | 050 | `can_manage_performance_structure` | «ساختار ارزیابی» — سایت‌محور |
| `performance.periods.manage` | 051 | `can_manage_performance_periods` | «دوره‌های ارزیابی» — سایت‌محور |
| `performance.forms.manage` | 051 | `can_manage_performance_forms` | «فرم‌های ارزیابی» — سایت‌محور |
| `performance.assignments.manage` | 052 | `can_manage_performance_assignments` | تولید انتساب‌های یک دوره |
| `performance.reports.view` | 053 | `can_view_performance_reports` | «گزارش‌های مدیریتی» ارزیابی — سایت‌محور |
| `performance.evaluate` | 052 | — | ⚠️ در دیتابیس هست، هیچ‌جا چک نمی‌شود |
| `leave_requests.view` | 056 | `can_view_leave_requests` | فهرست/خروجی Excel همه درخواست‌های مرخصی/ماموریت یک سایت |
| `leave_requests.manage` | 056 | `can_manage_leave_requests` | همان + ویرایش/حذف مدیریتی درخواست |
| `leave_requests.view.type.<عنوان>` | 065/066 + خودکار | `can_view_leave_requests`، `leave_requests_type_restricted` | فقط درخواست‌های تصمیم‌گیری‌شده همان نوع؛ بدون فیلتر تاریخ و بدون Excel |

### مجوزهای پویای نوع مرخصی

`leave_requests.view.type.<عنوان>` (فاصله‌های عنوان → `_`، مثلاً
`leave_requests.view.type.تردد_فراموش_شده`) به‌ازای هر **عنوان** نوع
درخواست یک‌بار ساخته می‌شود — نه به‌ازای هر سایت. هر بار نوع جدیدی ساخته
یا عنوانش عوض شود، `LeaveRequestStructureService._ensure_permission_for_title`
مجوز متناظر را خودکار می‌سازد. سایت‌بندی مثل بقیه از `UserRole.site_id`
هنگام انتصاب نقش می‌آید. جزئیات: [`leave-requests.md`](leave-requests.md).

### چیزهایی که مجوز RBAC ندارند (فقط `is_superuser`)

- **UI**: «داشبورد» (`/`) و «بررسی و اعمال آپدیت» (`/update`)
  (`adminOnly` در `config/navItems.jsx`). ⚠️ Endpoint های آپدیت سمت سرور
  فقط `system.backup` می‌خواهند.
- **Backend (`require_superuser`)**: تنظیمات «پیش‌نیازهای دسترسی»
  (`/access-gate/settings`)، تنظیمات «اعلان تغییرات پرتال»
  (`/announcement/settings`)، حذف پیام انتقاد/پیشنهاد و فهرست کلمات
  نامناسب (`/feedback/prohibited-phrases`).

### منوها

`frontend/src/config/navItems.jsx` تنها منبع منوهاست (هم منوی کناری
`Layout.jsx`، هم «دسترسی‌های ویژه» در `ProfilePage.jsx`). هر آیتم با
`check(user)` روی فلگ‌های بالا، و مسیرها در `App.jsx` با `PermissionRoute`
(یا `AdminRoute` برای دو صفحه بالا) محافظت می‌شوند.

## پیش‌نیازهای دسترسی (Access Gate)

یک لایه مستقل از RBAC: حتی با مجوز کامل، دیدن فیش حقوقی/کارکرد، گزارش
تردد، ثبت مرخصی/ماموریت و نتیجه ارزیابی ممکن است تا خواندن اطلاعیه‌های
خوانده‌نشده یا تکمیل ارزیابی‌های معوق قفل باشد (۱۰ کلید
`access_gate.{gate}.{feature}`، پیش‌فرض همه خاموش، فقط Admin تنظیم
می‌کند، Admin واقعی هرگز قفل نمی‌شود). مستند کامل در
[`notices.md`](notices.md) (بخش «پیش‌نیازهای دسترسی»).

## قانون قدرت رمز عبور و اجبار به تغییر

هر رمز عبور جدید (چه خودِ کاربر تغییرش بدهد، چه Admin برای یک پرسنل تعیین
کند، چه هنگام ساخت اولین حساب Admin) باید حداقل ۱۰ کاراکتر باشد و شامل
حرف کوچک انگلیسی، حرف بزرگ انگلیسی، و عدد باشد
(`backend/app/core/security.py: validate_password_strength`).

یک فیلد جداگانه `must_change_password` روی هر کاربر هست — وقتی True باشد،
کاربر بعد از ورود موفق تا تغییر رمز به بقیه پنل دسترسی ندارد (یک Dialog
اجباری و غیرقابل‌بستن نشان داده می‌شود). این فیلد در این موارد True
می‌شود:

- Admin برای یک پرسنل مستقیماً رمز تعیین کند (چون خودِ پرسنل انتخابش نکرده)
- حساب Admin با رمزی ساخته شود که قانون بالا را رعایت نمی‌کند (مثلاً رمز
  پیش‌فرض نصب) — `scripts/create_admin.py`
- حساب‌های **موجود** (نصب‌های قبل از این قابلیت) که واقعاً یک رمز عبور
  کاربر-تعیین‌شده دارند (`is_superuser` یا `has_custom_password`) — یک‌بار،
  توسط Migration `024`، چون هش رمزهای موجود یک‌طرفه است و نمی‌شود از رمز
  فعلی فهمید ضعیف بوده یا نه؛ به‌جای حدس‌زدن، همه این حساب‌ها یک‌بار مجبور
  به تعیین رمز جدید مطابق قانون تازه می‌شوند.
- **هر پرسنلی که هنوز رمز اختصاصی تعیین نکرده و همچنان با کد ملی وارد
  می‌شود** — چون کد ملی خودش یک اعتبار ضعیف است (جاهای زیادی در دسترس است،
  قابل تغییر/چرخش نیست). این مقدار برخلاف موارد بالا در دیتابیس ذخیره
  نمی‌شود، بلکه هر بار در `AuthService.get_me()` محاسبه می‌شود — چون هیچ
  Migration ای برای «همه پرسنلی که هنوز حساب کاربری نساخته‌اند» عملی
  نیست (حساب‌شان فقط موقع اولین ورود واقعی خودکار ساخته می‌شود).
