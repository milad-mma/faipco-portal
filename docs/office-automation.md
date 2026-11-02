# اتوماسیون اداری — یادداشت پیاده‌سازی

سند مرجع طراحی: `docs/office-automation-spec.md` (نسخه ۲.۶، تأیید کاربر ۱۴۰۵/۰۸/۰۹). این فایل فقط آنچه **پیاده‌سازی شده** را
ثبت می‌کند.

## فاز ۱الف — فایل، پیوست و تنظیمات (Migration 131)

### جدول‌ها
- `oa_files`: متادیتای فایل‌های بیرون از دیتابیس — `storage_key` (نسبی)، نام اصلی، حجم، `detected_format`، `content_type`،
  `sha256`، بارگذارنده، سایت، `purpose` (attachment/test)، `status` (چرخه‌ی ۶.۵)، `state` (temp/permanent)، دلیل رد، نتیجه و
  نسخه‌ی بانک اسکن، تعداد تلاش اسکن.
- `oa_attachment_settings`: یک ردیف برای هر سایت (نبود ردیف = مقدار اولیه).
- `oa_audit_events`: ثبت وقایع فقط‌افزودنی (تنظیمات، آپلود، رد، اسکن مجدد، دانلود، حذف موقت، پاک‌سازی).
- مجوزها: `automation.access` (از فاز ۳الف استفاده می‌شود)، `automation.settings` (سایت‌محور). به هیچ نقشی داده نمی‌شوند.

### Storage (`services/oa_storage.py`)
- پوشه‌ی خصوصی `OA_STORAGE_DIR` (پیش‌فرض `/var/lib/faipco/oa-files`، مالک www-data، 0700) بیرون از پوشه‌ی برنامه تا آپدیت پاکش نکند.
- `tmp/<uuid>.part` (دریافت جریانی با سقف حجم و هش هم‌زمان) → `objects/YYYY/MM/<uuid>` (write-once، 0400) →
  در صورت آلودگی `quarantine/<uuid>`. کلید خارج از ریشه رد می‌شود. رابط ساده تا بعداً S3-سازگار جایگزین شود.

### بررسی فایل (`core/oa_file_rules.py`)
- فهرست بسته‌ی ۱۸ فرمت با بررسی‌کننده؛ روشن در شروع: PDF، DOCX، XLSX، PPTX، JPG، PNG، WEBP، TIFF، TXT، CSV. قابل روشن کردن:
  DOC/XLS/PPT (بدون ماکرو)، ODT/ODS، ZIP، MP3، MP4.
- پسوندهای همیشه ممنوع (`FORBIDDEN_EXTENSIONS`: اجرایی/اسکریپت، HTML، SVG، XML، Office ماکرودار، ایمیج دیسک) با هیچ تنظیمی
  باز نمی‌شوند.
- نوع واقعی با پسوند مقایسه می‌شود (پسوند جعلی رد):
  - PDF با `document_sanitizer.check_pdf` (رمزدار/جاوااسکریپت/فایل جاسازی‌شده رد)؛
  - OOXML: ساختار ZIP، `[Content_Types].xml` و پوشه‌ی مخصوص نوع، رد `vbaProject.bin`/macroEnabled، رد OOXML رمزدار (OLE با
    EncryptionInfo)؛
  - Office قدیمی: OLE، رد جریان `_VBA_PROJECT` و رمزدار (لایه‌ی دوم: `AlertOLE2Macros` در ClamAV)؛
  - ODF: `mimetype`، رد ماکرو (Basic/Scripts) و رمزدار؛
  - ZIP: حداکثر ۱۰۰۰ فایل، ۱ گیگابایت باز‌شده و نسبت ۲۰۰ (ZIP bomb)، رد رمزدار، مسیر `..`، فایل ممنوع، ZIP تودرتو و فرمت خاموش؛
  - تصویر: امضای فایل + `Pillow.verify` + سقف ۲۰۰ مگاپیکسل؛
  - متن/CSV: بدون بایت NUL و کدگذاری UTF-8 یا Windows-1256؛
  - MP3/MP4: امضای فایل.
- تنظیمات: `validate_settings` (حجم هر فایل ≤ «سقف آپلود سرور» منهای ۱ (docs/upload-limit.md)، مجموع ≥ حجم یک فایل، کل نامه ≥ مجموع نسخه، حداقل یک
  فرمت). `check_quota` برای سهمیه‌ی تعداد/مجموع هنگام پیوست به نامه (فاز ۳الف).
- چرخه: `uploading → rejected | scanning → clean | infected | scan_pending`؛ فقط clean قابل دانلود و permanent.

### اسکن ویروس — اختیاری (`services/oa_scanner.py`، `services/oa_clamav.py`)
- **تصمیم کاربر (۱۴۰۵/۰۸/۱۱):** دریافت بانک ClamAV از ایران مسدود است (CDN خطای 403 و قفل ۲۴ ساعته‌ی freshclam). پس اسکن ویروس
  تنظیم سراسری `oa.scan_enabled` (جدول system_settings، **پیش‌فرض خاموش**) است و ClamAV دیگر در install.sh خودکار نصب نمی‌شود.
  - خاموش: بعد از بررسی نوع/ساختار، فایل `clean` با `scanned_at` خالی = «سالم (بدون اسکن ویروس)». همان سطح ماژول‌های بیمه و
    مشخصات خانوادگی (آن‌ها هم آنتی‌ویروس ندارند)، به‌علاوه‌ی بررسی ماکرو/رمز/ZIP.
  - روشن کردن فقط ادمین کل و فقط وقتی clamd پاسخ می‌دهد (`PUT /automation/settings/scan`)؛ سپس Job اسکن، فایل‌های «بدون اسکن» را
    هم در پس‌زمینه اسکن می‌کند (اگر اسکنر در دسترس نباشد، این فایل‌ها قفل نمی‌شوند و clean می‌مانند).
  - خاموش کردن: scan_pending ها «سالم (بدون اسکن ویروس)» می‌شوند.
- **نصب و راه‌اندازی از پنل** (فقط ادمین کل): کارت «اسکن ویروس با ClamAV» در تب اسکنر — نصب و راه‌اندازی، دریافت/به‌روزرسانی بانک،
  روشن کردن، خاموش کردن. `POST /automation/clamav/{install|update-db|start|stop}` ← `scripts/clamav.sh` در Unit موقت
  `faipco-clamav` با systemd-run به‌عنوان root (چهار قانون sudoers ثابت در install.sh)؛ لاگ `/var/log/faipco-clamav.log` با
  نشانگرهای `[CLAMAV] START/RESULT` و نمایش در پنل. `update-db` قفل cool-down قبلی (`/var/lib/clamav/freshclam.dat`) را برمی‌دارد
  تا با برقراری VPN همان لحظه تلاش شود. بدون بانک، clamd روشن نمی‌شود و سرویس‌ها خاموش می‌مانند.
- RAM: clamd روشن حدود ۱ تا ۱.۵ گیگابایت (بانک در حافظه)؛ «خاموش کردن» هر دو سرویس clamd و freshclam را disable می‌کند = بدون مصرف.
- clamd روی `OA_CLAMD_SOCKET` (پیش‌فرض `/var/run/clamav/clamd.ctl`) با INSTREAM؛ `scan_db_version` ثبت می‌شود.
- clamd در دسترس نیست یا خطا داد → `scan_pending`؛ Job `oa_scan_retry` هر ۵ دقیقه (Advisory Lock) دوباره امتحان می‌کند.
- بانک قدیمی‌تر از ۷ روز = هشدار در پنل (اسکن متوقف نمی‌شود — بخش ۱۲، قطع اینترنت).

### پاک‌سازی
- Job `oa_temp_cleanup` هر ۶ ساعت: فایل‌های `state=temp` قدیمی‌تر از `OA_TEMP_RETENTION_HOURS` (۴۸) و ردیف‌هایشان حذف می‌شوند.
  همان Advisory Lock بکاپ را می‌گیرد تا هم‌زمان با بکاپ اجرا نشود (بخش ۱۰.۲). فایل permanent هرگز حذف خودکار ندارد.

### API (`/api/v1/automation`، همه با `automation.settings` همان سایت)
- `GET /settings/attachments` — فهرست فرمت‌ها، ممنوع‌ها، سقف سرور، مقدار اولیه + تنظیمات سایت‌های مجاز.
- `PUT /settings/attachments/{site_id}` — ذخیره (خطای فارسی برای مقدار نامعتبر؛ تغییرات با مقدار قبلی/جدید در وقایع).
- `GET /settings/status` — ClamAV (نسخه، بانک، تاریخ بانک، قدیمی بودن)، فضای دیسک، تعداد فایل‌ها به تفکیک وضعیت.
- `POST /files/test-upload` (فرم: site_id، file) — آزمایش آپلود با تنظیمات سایت؛ فایل موقت.
- `GET /files/mine`، `GET /files/{id}/download` (فقط clean، جریانی، `nosniff`، `attachment`)، `DELETE /files/{id}` (فقط موقت).
- فاز ۱: فقط بارگذارنده فایل خودش را می‌بیند؛ از فاز ۳الف دسترسی فایل از `can()` نامه می‌آید.

### رابط
- منوی «اتوماسیون اداری ← تنظیمات اتوماسیون» (`/automation/settings`، فلگ `can_manage_automation_settings`).
- تب «پیوست‌ها»: انتخاب سایت، سه کارت تعداد/حجم (نامه، ارجاع/اقدام، کل نامه)، چک‌باکس فرمت‌ها، متن ممنوع‌ها، سقف سرور.
- تب «اسکنر و آزمایش آپلود»: وضعیت ClamAV و دیسک، آزمایش آپلود، فهرست فایل‌های آزمایشی با دانلود/حذف.

### نصب (`install.sh` ← `setup_office_automation_files`، در نصب و آپدیت)
- ساخت `/var/lib/faipco/oa-files/{tmp,objects,quarantine}` با مالک www-data.
- ClamAV خودکار نصب نمی‌شود؛ `scripts/clamav.sh install` (از پنل) بسته‌ها را نصب و در `clamd.conf` تنظیم می‌کند:
  `StreamMaxLength 100M`، `AlertOLE2Macros yes`، `LocalSocketMode 666`.
- نسخه‌ی قبلی (۱الف اول) ClamAV را خودکار نصب می‌کرد؛ روی سروری که آن نسخه نصب شده، بسته‌ها هستند ولی بدون بانک خاموش‌اند.

### تست
- `tests/test_oa_file_rules.py` (۱۱ تست): تنظیمات و سهمیه، پسوند ممنوع/خاموش، OOXML (جعلی، ماکرو، رمزدار)، Office قدیمی و ODF،
  ZIP (ممنوع، تودرتو، مسیر، bomb)، تصویر/متن/صوت/ویدیو، PDF، چرخه‌ی وضعیت، تجزیه‌ی پاسخ ClamAV، Storage (write-once، سقف حجم،
  حذف فایل نیمه‌کاره، مسیر خطرناک، قرنطینه).

### چک‌لیست سرور تست (فاز ۱الف)
1. اسکن خاموش (پیش‌فرض): آپلود PDF/DOCX/JPG سالم → «سالم (بدون اسکن ویروس)» و دانلود با همان هش.
2. با VPN: «دریافت/به‌روزرسانی بانک» یا «نصب و راه‌اندازی» → «با موفقیت انجام شد»؛ «روشن کردن»؛ سپس سوییچ اسکن را روشن کنید.
   فایل‌های قبلی «بدون اسکن» تا ۵ دقیقه بعد اسکن شوند.
3. با اسکن روشن، فایل آزمایشی EICAR (`eicar.txt`) → «آلوده (قرنطینه)» و بدون دکمه‌ی دانلود.
4. DOCX که پسوندش xlsx شده → رد «هم‌خوانی ندارد»؛ `.docm` یا DOCX با ماکرو → رد؛ `.exe` → رد «هرگز مجاز نیست».
5. ZIP خاموش → رد؛ روشن کردن ZIP در تنظیمات و آپلود ZIP حاوی exe → رد.
6. فایل بزرگ‌تر از سقف سایت → رد با پیام حجم.
7. اسکن روشن و `systemctl stop clamav-daemon` → آپلود «در انتظار اسکن»؛ start → حداکثر ۵ دقیقه بعد «سالم». «خاموش کردن» از پنل
   → `free -h` کاهش حدود ۱ گیگابایت.
8. تغییر تنظیمات سایت A روی سایت B اثری نداشته باشد؛ کاربر با `automation.settings` فقط سایت A، سایت B را نبیند.
9. حجم هر فایل ۳۰ → خطای سقف سرور.

## فاز ۱ب — بکاپ — جزئیات در `docs/backup.md`
به تصمیم کاربر ساده شد: همان ZIP قبلی + فایل‌های آپلودی اتوماسیون (snapshot مشترک با دیتابیس، تطبیق هش) + رمز اختیاری AES-256؛
بازیابی هماهنگ دیتابیس و فایل‌ها با برگشت در شکست؛ مجوز همان `system.backup`. مقصدهای پوشه‌ی محلی، SFTP و S3، بررسی سالم
رسیدن و صف تلاش دوباره (Migration 135) اضافه شدند.

## فاز ۲ — قالب و پیش‌نویس نامه (Migration 136)

### داده و قواعد
- `oa_templates` / `oa_template_versions`: قالب مخصوص یک سایت؛ هر ذخیره یک نسخه‌ی تغییرناپذیر با `layouts = {A4, A5}`
  (حاشیه‌ها، قلم، سربرگ: لوگو/عنوان/زیرعنوان/نمایش شماره-تاریخ-پیوست/ارتفاع، پابرگ: متن/ارتفاع). قواعد: `core/oa_letter_rules.py`.
- `oa_letters` / `oa_letter_versions`: فاز ۲ فقط پیش‌نویس شخصی (status=draft، فقط سازنده)؛ نسخه‌ی ۱ با status=editing؛ قفل
  خوش‌بینانه `row_version` (409)؛ `content_hash` در هر ذخیره.
- متن نامه همیشه در سرور با فهرست مجاز پاک‌سازی می‌شود (`core/oa_html.py`): p، h2، h3، strong، em، u، s، فهرست، جدول، blockquote،
  br، span؛ فقط `dir`، `colspan/rowspan` و `style: text-align`.
- **سربرگ/پابرگ با کد HTML (اختیاری):** `header.html` و `footer.html` هر اندازه؛ اگر پر باشد به‌جای سربرگ/پابرگ ساده نمایش
  داده می‌شود. پاک‌ساز جدا (`core/oa_template_html.py`): div/span/p/h1-3/strong/b/em/i/u/small/br/hr/جدول/img؛ فقط style درون‌خطی
  با فهرست بسته‌ی ویژگی‌های CSS (بدون url/expression/position)؛ img فقط `src="{{logo}}"`. جای‌نگهدارها: {{logo}} {{title}}
  {{subtitle}} {{site}} {{number}} {{date}} {{attachment}} {{page}} {{pages}} — در مرورگر با مقدار escape‌شده جایگزین می‌شوند.
- لوگو: فایل اتوماسیون با purpose=template، فقط PNG/JPG/WEBP (مستقل از فرمت‌های پیوست سایت)؛ با ذخیره در نسخه‌ی قالب permanent.

### API (`endpoints/automation_letters.py`)
- قالب (`automation.templates` همان سایت): `GET/POST /automation/templates`، `PUT /automation/templates/{id}`،
  `GET …/{id}/versions`، `POST /automation/templates/logo`، `GET /automation/templates/logo/{file_id}` (templates یا compose).
- پیش‌نویس (`automation.compose` همان سایت): `GET /automation/compose/options`، `GET/POST /automation/drafts`،
  `GET/PUT/DELETE /automation/drafts/{id}`.
- پرچم‌های کاربر: `can_oa_compose`، `can_oa_templates`.

### رابط
- «پیش‌نویس‌های من» (`/automation/drafts`) و ویرایشگر (`/automation/drafts/:id`): TipTap (فقط امکانات مجاز پاک‌ساز)، ذخیره‌ی
  خودکار ۳ ثانیه بعد از آخرین تغییر و Ctrl+S، هشدار بستن صفحه، پیش‌نمایش صفحه‌ای A4/A5 به میلی‌متر با شمار صفحه و پیشنهاد A4
  وقتی A5 بیش از یک صفحه شود، چاپ مرورگر (`@page` بدون حاشیه).
- «قالب‌های نامه» (`/automation/templates`): فهرست، فرم چیدمان جدا برای A4/A5، لوگو، پیش‌نمایش زنده با متن نمونه.
- پیش‌نمایش: صفحه‌ها زیر هم؛ کوچک‌نمایی با `zoom` (نه transform) و ابعاد/حاشیه‌ها در style درون‌خطی، چون افزونه‌ی RTL برنامه
  چپ/راستِ sx را جابه‌جا می‌کند.
- محدودیت: شکستن صفحه در پیش‌نمایش و چاپ ساده است (ممکن است یک خط بین دو صفحه نصف شود)؛ نسخه‌ی رسمی PDF در فاز ارسال.

### تست
- `tests/test_oa_letters.py`: پاک‌ساز HTML، چیدمان، content_hash. فرانت‌اند فقط eslint (بسته‌های TipTap در محیط توسعه نصب نشدند؛
  روی سرور با `npm install`).

### چک‌لیست سرور تست (فاز ۲)
1. alembic 136؛ ساخت فرانت با بسته‌های `@tiptap/*`.
2. به نقش آزمایشی `automation.templates` و `automation.compose` برای یک سایت بدهید.
3. قالب جدید با لوگو و عنوان → ذخیره (نسخه‌ی ۱) → تغییر حاشیه → ذخیره (نسخه‌ی ۲).
4. نامه‌ی جدید با همان قالب → متن با جدول و تیتر → چند ثانیه صبر → «ذخیره شد».
5. همان پیش‌نویس در دو تب: ذخیره در تب اول، تغییر در تب دوم → پیام «در جای دیگری تغییر کرده».
6. A5 با متن طولانی → هشدار و دکمه‌ی «A4 شود»؛ چاپ → صفحه‌ها اندازه‌ی واقعی.
7. کاربر دیگر (حتی با compose) پیش‌نویس شما را نمی‌بیند؛ آدرس مستقیم → «پیش‌نویس یافت نشد».
