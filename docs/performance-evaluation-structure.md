# ساختار ارزیابی عملکرد (Evaluation Organizational Structure)

مشخص می‌کند چه کسی مجاز به ارزیابی چه کسی است - اولین بخش از سیستم
جامع «ارزیابی عملکرد پرسنل». این سند فقط همین بخش (ساختار سازمانی
ارزیابی) را پوشش می‌دهد؛ دوره‌ها/فرم‌ها/سوالات/امتیازدهی در جلسات
بعدی ساخته می‌شوند.

## چرا یک انتساب کاملاً جدا، نه استفاده از RBAC یا سرپرست موجود

طبق تصمیم صریح کاربر، این ماژول از نام یا مجوز نقش‌های RBAC موجود
استفاده نمی‌کند - چون نقش‌ها (و حتی نامشان) در پنل مدیریت قابل تغییرند
و برای این منظور قابل‌اتکا نیستند. همچنین از Department.supervisor_user_id
موجود هم استفاده نمی‌کند - چون آن فیلد برای هدف‌گیری اطلاعیه‌ها
استفاده می‌شود و باید کاملاً مستقل از سرپرستِ ارزیابی باشد.

به‌جای این‌ها، پنج جدول اختصاصی این ماژول، یک انتساب کاملاً صریح و
مستقل نگه می‌دارند.

## سلسله‌مراتب (طبق تصمیم صریح کاربر)

```
مدیر سایت (چند نفر مجاز)
    -> ارزیابی: سرپرست‌های همه واحدهای همان سایت + سایر مدیران همان سایت
      (اگر فردی هم‌زمان هر دو باشد، فقط یک‌بار ظاهر می‌شود - Union)

سرپرست واحد
    -> اگر آن واحد سرشیفت ندارد: همه پرسنل واحد
    -> اگر آن واحد حداقل یک سرشیفت دارد: فقط سرشیفت‌ها (نه پرسنل عادی)

سرشیفت واحد (اختیاری، فقط اگر تعریف شود)
    -> فقط زیرمجموعه‌ی اختصاصی خودش (پرسنل بین سرشیفت‌های یک واحد
      تقسیم می‌شوند - هر پرسنل فقط زیر یک سرشیفت)
    -> سرشیفت‌های یک واحد هرگز نمی‌توانند یکدیگر را ارزیابی کنند
```

## مدل‌ها (app/models/evaluation.py، Migration 050)

| جدول | نقش |
|---|---|
| evaluation_department_supervisors | سرپرست هر واحد (حداکثر یک نفر - department_id یکتا) |
| evaluation_site_managers | مدیران هر سایت (چند نفر مجاز) |
| evaluation_other_managers | سایر مدیرانی که مدیر سایت ارزیابی می‌کند |
| evaluation_shift_leads | سرشیفت‌های هر واحد (اختیاری، چند نفر مجاز) |
| evaluation_shift_assignments | تعیین می‌کند هر پرسنل عادی زیرمجموعه کدام سرشیفت است (employee_id یکتا) |

همه به Employee وصل می‌شوند (نه مستقیماً User) - چون انتخاب همیشه از
بین «پرسنل» در UI انجام می‌شود.

## ساخت خودکار حساب کاربری

طبق تصمیم صریح کاربر: اگر پرسنلی که به‌عنوان سرپرست/مدیر سایت/سرشیفت
انتخاب می‌شود هنوز حساب کاربری نداشته باشد، به‌صورت خودکار ساخته
می‌شود - با استفاده مستقیم از تابع موجود
UserRepository.get_or_create_employee_user (همان مکانیزم اولین ورود
پرسنل با کد پرسنلی/کد ملی؛ کد جدیدی برای این منظور نوشته نشد).

## الگوریتم Resolve (app/core/evaluation_rules.py)

تابع خالص resolve_evaluation_target_ids - بدون هیچ وابستگی به
دیتابیس (دقیقاً مثل الگوی app/core/backup_schedule_logic.py) - برای
قابل‌تست‌بودن بدون نیاز به یک دیتابیس واقعی. نُه تست واحد
(tests/test_evaluation_rules.py) همه قوانین بالا را (شامل مهم‌ترین
سناریو: «وقتی واحد سرشیفت دارد، سرپرست فقط سرشیفت‌ها را می‌بیند» و
«سرشیفت‌ها هرگز یکدیگر را نمی‌بینند») تأیید می‌کنند.

خواندن داده خام از دیتابیس (برای تغذیه این الگوریتم خالص) در
app/services/evaluation_structure_service.py::get_evaluation_targets
انجام می‌شود.

## نکته امنیتی مهم — Site Isolation

برخلاف اکثر Endpoint های پروژه که site_id مستقیماً در Path/Query
دارند (و می‌توانند از الگوی ساده require_permission(..., site_scoped=True)
استفاده کنند)، بیشتر Endpoint های این ماژول بر اساس department_id/
manager_id/shift_lead_id کار می‌کنند - یعنی site_id باید ابتدا از
طریق همان رکورد Resolve شود. برای همین یک تابع کمکی مشترک
(_require_site_permission در evaluation_structure.py) نوشته شد که:

1. ابتدا site_id واقعی را از رکورد مربوطه پیدا می‌کند (مثلاً از
   department.site_id).
2. سپس با get_sites_with_permission (همان تابع موجود پروژه، در
   app/core/site_access.py) بررسی می‌کند کاربر دقیقاً برای همان
   site_id مجوز performance.structure.manage را دارد.

این از یک باگ واقعی جلوگیری می‌کند: اگر از require_permission(site_scoped=True)
مستقیم استفاده می‌شد (که فقط site_id مستقیم در Path/Query را می‌بیند)،
کاربری با این مجوز فقط برای Site A، می‌توانست سرپرست یک واحد در Site B
را هم تغییر دهد - چون Endpoint اصلاً site_id ای در مسیرش نداشت که
بشود آن را چک کرد.

## Endpoint ها (prefix=/performance)

| Method | Path | توضیح |
|---|---|---|
| GET | /performance/sites/{site_id}/structure | کل ساختار یک سایت (یک درخواست، برای رندر UI) |
| PUT/DELETE | /performance/departments/{department_id}/supervisor | تعیین/حذف سرپرست واحد |
| POST/DELETE | /performance/sites/{site_id}/managers، /performance/managers/{manager_id} | مدیران سایت |
| POST/DELETE | /performance/sites/{site_id}/other-managers، /performance/other-managers/{manager_id} | سایر مدیران |
| POST/DELETE | /performance/departments/{department_id}/shift-leads، /performance/shift-leads/{shift_lead_id} | سرشیفت‌ها |
| PUT/DELETE | /performance/shift-assignments، /performance/shift-assignments/{employee_id} | تخصیص پرسنل به سرشیفت |

مجوز: performance.structure.manage (Migration 050 آن را Seed می‌کند).

## Frontend

- EvaluationStructurePage.jsx (مسیر /performance/structure): انتخاب
  سایت، مدیریت مدیران سایت/سایر مدیران، و یک Accordion برای هر واحد
  (سرپرست، سرشیفت‌ها، جدول تخصیص پرسنل به سرشیفت‌ها).
- EmployeePicker.jsx: کامپوننت انتخابگر پرسنل با جست‌وجوی زنده،
  قابل‌محدودسازی به یک سایت/واحد مشخص - قابل‌استفاده مجدد برای بقیه
  بخش‌های آینده این ماژول.
- منو: «ارزیابی عملکرد» ← «ساختار ارزیابی» (فقط با مجوز
  performance.structure.manage؛ فلگ can_manage_performance_structure
  در /auth/me).

## اعتبارسنجی‌های اعمال‌شده در Service Layer

- سرپرست/مدیر سایت/سایر مدیر/سرشیفت باید از پرسنل همان Site باشند.
- سرشیفت باید از پرسنل همان Department باشد.
- پرسنلی که زیرمجموعه یک سرشیفت است، نمی‌تواند هم‌زمان خودش هم سرشیفت
  باشد (و برعکس) - جلوگیری از تناقض سلسله‌مراتبی.
- تخصیص پرسنل به سرشیفت فقط برای پرسنل همان واحدِ آن سرشیفت مجاز است.

## مراحل بعدی (هنوز پیاده‌سازی نشده)

طبق طرح گسترده‌تر (سند شخصی‌سازی‌شده قبلی)، مراحل بعدی که روی همین
ساختار سوار می‌شوند: دوره‌های ارزیابی، فرم‌ها/دسته‌بندی‌ها/سوالات،
جریان انجام ارزیابی (Draft->Submit)، محاسبه امتیاز وزن‌دار، گزارش‌ها و
Dashboard. get_evaluation_targets (که همین حالا آماده و تست‌شده است)
مستقیماً توسط جریان انجام ارزیابی در آن مراحل استفاده خواهد شد.

## دور دوم — محتوای ارزیابی: دوره‌ها و فرم‌ها (Migration 051)

مرحله بعدی طبق نقشه‌راه - «چه چیزی پرسیده می‌شود و در چه بازه زمانی».
کاملاً مستقل از «چه کسی چه کسی را ارزیابی می‌کند» (دور اول، بالا).

### مدل‌ها (app/models/evaluation_content.py - فایل جدا از evaluation.py)

| مدل | توضیح |
|---|---|
| EvaluationPeriod | دوره ارزیابی؛ site_id=None یعنی «همه سایت‌ها» |
| EvaluationForm | فرم؛ با Versioning ساده (version + parent_form_id) |
| EvaluationCategory | دسته‌بندی سوالات، با وزن (٪ از فرم) |
| EvaluationQuestion | سوال؛ ۷ نوع (single_choice/multiple_choice/rating/yes_no/text/number/date)، با وزن (٪ از دسته‌بندی) |
| EvaluationQuestionOption | گزینه پاسخ با امتیاز Dynamic - حتی yes_no از این استفاده می‌کند (دو گزینه بله/خیر با امتیاز دلخواه) تا منطق امتیازدهی یکسان بماند |

### اعتبارسنجی وزن (app/core/evaluation_rules.py::validate_form_weights)

تابعی کاملاً خالص (بدون I/O) - فقط هنگام فعال‌کردن فرم (نه در حالت
Draft، که ممکن است ناقص باشد) اجرا می‌شود: مجموع وزن دسته‌بندی‌های فعال
باید ۱۰۰ باشد؛ داخل هر دسته‌بندی فعال، مجموع وزن سوالات فعال هم باید
۱۰۰ باشد. شش تست واحد (`tests/test_evaluation_rules.py`) این منطق را
تأیید می‌کنند.

### Historical Integrity

بعد از فعال‌شدن یک فرم/دوره، دیگر Hard-Delete یا ویرایش مستقیم مجاز
نیست (فقط تغییر وضعیت). برای تغییر محتوای یک فرم فعال، از «نسخه جدید»
(`duplicate_as_new_version`) استفاده می‌شود - یک کپی کامل Draft با
`version` افزایش‌یافته و `parent_form_id` به فرم اصلی؛ فرم اصلی (و
ارزیابی‌های احتمالی مرتبط با آن در آینده) دست‌نخورده باقی می‌ماند.

### Endpoint ها

- `prefix=/performance/periods`: CRUD کامل + تغییر وضعیت
- `prefix=/performance/forms`: CRUD فرم + `/duplicate` (نسخه جدید) +
  `/categories`، `/categories/{id}/questions` (تودرتو)

مجوزها: `performance.periods.manage`، `performance.forms.manage` - با
همان الگوی `require_site_permission` (رکوردهای «سراسری» با site_id=None
فقط با مجوز سراسری قابل‌مدیریت‌اند، نه یک مجوز site-scoped محدود).

### Frontend

- `EvaluationPeriodsPage.jsx`: فهرست + دیالوگ ساخت/ویرایش (با
  `JalaliDateTimePicker` موجود) + تغییر وضعیت inline.
- `EvaluationFormsPage.jsx`: فهرست فرم‌ها + دکمه «نسخه جدید».
- `EvaluationFormBuilderPage.jsx`: فرم‌ساز تودرتو - هر دسته‌بندی یک
  Accordion، هر سوال یک ویرایشگر کامل (نوع، وزن، اجباری/فعال، گزینه‌های
  Dynamic برای انواع نیازمند گزینه). دکمه «فعال‌سازی فرم» خطاهای
  اعتبارسنجی وزن را مستقیم از Backend نمایش می‌دهد.
- منو: زیرمنوهای «دوره‌های ارزیابی» و «فرم‌های ارزیابی» به «ارزیابی
  عملکرد» اضافه شدند - با همان الگوی «نمایش والد اگر حداقل یکی از
  زیرمجموعه‌ها مجاز باشد» که برای «مدیریت دسترسی» موجود بود.

## جمع‌بندی پیشرفت

| مرحله | وضعیت |
|---|---|
| ساختار سازمانی (چه کسی چه کسی را ارزیابی می‌کند) | ✅ |
| محتوا (دوره‌ها، فرم‌ها، دسته‌بندی‌ها، سوالات) | ✅ |
| جریان انجام ارزیابی (Assignment Generation، Draft→Submit) | ⏳ باقی‌مانده |
| محاسبه امتیاز نهایی | ⏳ باقی‌مانده |
| گزارش‌ها و Dashboard | ⏳ باقی‌مانده |

## رفع باگ حیاتی — صفحه سفید هنگام باز کردن «ساختار ارزیابی»

**علامت گزارش‌شده**: باز کردن صفحه «ساختار ارزیابی» کل صفحه را سفید
می‌کرد.

**علت اصلی**: `EvaluationStructureService.get_site_structure` (و پنج
متد دیگر همین سرویس - `set_department_supervisor`، `add_site_manager`،
`add_other_manager`، `add_shift_lead`، `set_shift_assignment`) به
رابطه `employee` روی `EvaluationSiteManager`/`EvaluationOtherManager`/
`EvaluationDepartmentSupervisor`/`EvaluationShiftLead`/
`EvaluationShiftAssignment` دسترسی پیدا می‌کردند **بدون این‌که از قبل
با `selectinload(...)` بارگذاری شده باشد**. در یک Session ناهمگام
(Async SQLAlchemy)، دسترسی به یک رابطه Lazy-load نشده بدون Greenlet
فعال، خطای `MissingGreenlet` می‌دهد - یک خطای ۵۰۰ خام از Backend.

مشکل دومی هم همراهش بود: خودِ Endpoint اصلاً `response_model` نداشت -
یعنی حتی اگر رابطه درست بارگذاری می‌شد، FastAPI مجبور بود اشیای خام
SQLAlchemy را مستقیم JSON کند (که معمولاً شکست می‌خورد یا داده داخلی
نامربوط برمی‌گرداند). یک مشکل سوم هم پیدا شد: Schema (`SiteStructureOut`)
یک فیلد اجباری `site_name` داشت که سرویس اصلاً برنمی‌گرداند.

هر سه مشکل باعث خطای ۵۰۰ از Backend می‌شدند؛ چون هیچ Error Boundary ای
در React برای این صفحه تعریف نشده بود، نتیجه یک صفحه کاملاً سفید بود
(نه یک پیام خطای قابل‌فهم).

**راه‌حل**:
1. همه Query های `get_site_structure` با `selectinload(...)` رابطه
   `employee` را از قبل بار می‌کنند.
2. متدهای Create/Update به‌جای `db.refresh(obj)` ساده (که فقط ستون‌های
   خودِ Object را تازه می‌کند، نه رابطه‌ها)، بعد از `commit()` دوباره با
   `selectinload` Query می‌زنند - با یک نکته فنی مهم: چون `commit()`
   شیء را Expire می‌کند، خواندن `obj.id` بعد از آن هم می‌توانست همین
   خطا را بدهد؛ برای همین `id` بلافاصله بعد از `flush()` (نه `commit()`)
   خوانده می‌شود.
3. `site_name` به خروجی سرویس اضافه شد (با یک بررسی صریح که خودِ سایت
   وجود دارد - وگرنه پیام خطای واضح «سایت موردنظر یافت نشد»، نه یک ۵۰۰
   خام).
4. `response_model` مناسب به تمام Endpoint های این ماژول اضافه شد.

⚠️ همین دقیقاً همان کلاس باگ در `evaluation_form_service.py` هم پیدا و
رفع شد (`add_category`/`update_category` به `questions` تودرتو دسترسی
می‌کردند بدون `selectinload`).

**درس کلی برای بقیه این ماژول (و آینده پروژه)**: هر متد سرویسی که یک
Object را بعد از Create/Update برمی‌گرداند، باید صراحتاً بررسی شود که
آیا Schema خروجی (`response_model`) به رابطه‌ای نیاز دارد که در همان
Query نهایی `selectinload` نشده - این دقیقاً همان اصل کلی «Async ORM:
از دسترسی به رابطه Lazy-load شده بعد از flush() خودداری کن» است که از
قبل هم برای این پروژه شناخته‌شده بود، ولی این‌جا در یک ماژول تازه دوباره
تکرار شده بود.

## اصلاح — جست‌وجوی سرپرست واحد در کل سایت (نه فقط همان واحد)

طبق بازخورد صریح: در عمل ممکن است سرپرست یک واحد به‌طور سیستمی (در
دیتابیس Sync-شده) عضو همان واحد ثبت نشده باشد. همچنین، طبق همان الگوی
قبلی این پروژه، باید امکان این باشد که یک نفر هم‌زمان سرپرست چند واحد
مختلف باشد.

**بررسی کردم و متوجه شدم Backend از قبل هیچ‌کدام از این دو محدودیت را
اعمال نمی‌کرد** - `set_department_supervisor` فقط بررسی می‌کند پرسنل
انتخاب‌شده متعلق به همان *سایت* باشد (نه همان واحد)، و هیچ Constraint
یکتایی روی `employee_id` وجود ندارد (فقط `department_id` یکتاست) - یعنی
همان یک نفر می‌تواند در چند ردیف مختلف (برای چند واحد مختلف) به‌عنوان
سرپرست ثبت شود.

محدودیت واقعی فقط در **Frontend** بود:
`EmployeePicker` مخصوص «سرپرست واحد» با `departmentIds={[department.id]}`
جست‌وجو را به همان واحد محدود می‌کرد. این محدودیت حذف شد - حالا فقط
`siteId` پاس داده می‌شود، یعنی جست‌وجو در کل پرسنل همان سایت انجام
می‌شود.

⚠️ این تغییر فقط برای **سرپرست واحد** اعمال شد - انتخابگر «سرشیفت»
عمداً همچنان به همان واحد محدود مانده (`departmentIds={[department.id]}`
بدون تغییر)، چون طبق طراحی قبلی سرشیفت باید واقعاً عضو همان واحد باشد
(هم منطقاً - چون قرار است بخشی از پرسنل همان واحد را ارزیابی کند - و
هم به‌صراحت در Backend اعتبارسنجی می‌شود: `add_shift_lead` رد می‌کند
اگر `employee.department_id != department_id`).

## دور سوم — جریان انجام ارزیابی (Migration 052) + کارت داشبورد

سومین و آخرین لایه اصلی سیستم ارزیابی - خودِ عمل «ارزیابی‌کردن».

### مدل‌ها (app/models/evaluation_process.py)

| مدل | توضیح |
|---|---|
| EvaluationAssignment | «X باید Y را برای دوره P با فرم F ارزیابی کند» - تولید خودکار |
| Evaluation | فرم پرشده - با Historical Snapshot کامل (نام/کد پرسنلی/سایت/واحد در لحظه شروع) |
| EvaluationAnswer | پاسخ هر سوال - با Snapshot متن/نوع سوال |

### تولید Assignment (app/services/evaluation_assignment_service.py)

برای یک دوره + فرم، با استفاده مستقیم از get_evaluation_targets (لایه
اول)، برای همه پرسنل واجد شرایط (همان سایت دوره، یا همه اگر دوره
سراسری است)، Assignment های جدید ساخته می‌شوند - قابل اجرای مکرر
(Idempotent؛ UniqueConstraint از تکرار جلوگیری می‌کند) - دقیقاً طبق
همان اصل «Dynamic بودن» طرح اولیه: با تغییر ساختار سازمانی، فقط کافی
است دوباره اجرا شود.

### محاسبه امتیاز (app/core/evaluation_rules.py)

دو تابع خالص جدید: calculate_option_based_question_score (میانگین
امتیاز گزینه‌های انتخاب‌شده) و calculate_weighted_average (جمع‌بندی
وزنی - هم برای سوال‌ها→دسته‌بندی، هم دسته‌بندی‌ها→فرم، با همان تابع).
برای سوالات متن/عدد/تاریخ (بدون گزینه)، امتیاز بر اساس «پاسخ داده شده
یا نه» است (۱۰۰ یا ۰) - تا در همان فرمول یکسان جمع‌بندی شوند. پنج تست
واحد جدید (مجموعاً حالا ۲۰ تست در test_evaluation_rules.py).

### جریان (app/services/evaluation_process_service.py)

start_evaluation (ساخت/ادامه Draft با Snapshot) → save_answers (ذخیره
پیش‌نویس، بدون امتیازدهی) → submit_evaluation (اعتبارسنجی سوالات
اجباری + محاسبه امتیاز نهایی + قفل‌شدن). هر سه عملیات، مالکیت
Assignment/Evaluation را نسبت به کاربر جاری تأیید می‌کنند - هرگز فقط
به یک ID معتبر اعتماد نمی‌شود.

### ⚠️ درس تکرارشونده - همان کلاس باگ صفحه سفید، این‌بار در start_evaluation

موقع پیاده‌سازی، متوجه شدم start_evaluation هم رابطه assignment را
بدون selectinload برمی‌گرداند - علاوه بر آن، فهمیدم روش «رفع» قبلی
(refresh() بعد از commit()) به‌تنهایی کافی نیست، چون commit() خودِ
Object را هم Expire می‌کند؛ حتی assignment ای که دستی روی evaluation
ست شود، بعد از commit همچنان Expired است. رفع نهایی: بعد از commit،
همیشه یک Query تازه با selectinload صریح - نه تلاش برای استفاده مجدد
از یک Object قبل از commit.

### Endpoint ها (prefix=/performance)

- POST /performance/periods/{period_id}/generate-assignments (Admin - مجوز performance.assignments.manage)
- GET /performance/my-evaluations، POST /performance/assignments/{id}/start
- PUT /performance/evaluations/{id}/answers، POST /performance/evaluations/{id}/submit
- GET /performance/my-results، GET /performance/my-dashboard-summary

⚠️ برخلاف بقیه این ماژول، این Endpoint ها (به‌جز generate-assignments)
هیچ Permission خاصی نمی‌خواهند - فقط داشتن حساب متصل به یک Employee؛
چون مجاز بودن از روی جدول‌های ساختار سازمانی (لایه اول) تعیین می‌شود،
نه RBAC.

### Frontend

- کاشی داشبورد (PerformanceEvaluationToolCard.jsx) - جایگزین «به‌زودی»
  قبلی؛ امتیاز آخرین ارزیابی + Badge تعداد در انتظار.
- MyPerformancePage.jsx (مسیر /my-performance) - دو تب: نتایج من / ارزیابی پرسنل من.
- EvaluationFillPage.jsx (مسیر /my-performance/evaluate/:assignmentId) -
  رندر Dynamic فرم بر اساس نوع هر سوال، ذخیره پیش‌نویس، ثبت نهایی.
- دیالوگ «تولید انتساب» در EvaluationPeriodsPage.jsx.

## جمع‌بندی نهایی - هر سه لایه اصلی کامل شدند

| لایه | وضعیت |
|---|---|
| ساختار سازمانی (چه کسی چه کسی را ارزیابی می‌کند) | ✅ |
| محتوا (دوره‌ها، فرم‌ها) | ✅ |
| جریان انجام ارزیابی (Assignment، Draft→Submit، امتیازدهی) | ✅ |
| گزارش‌های مدیریتی و Dashboard تجمیعی (نه فقط کارت شخصی) | ⏳ باقی‌مانده |
