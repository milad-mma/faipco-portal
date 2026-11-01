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
- تنظیمات: `validate_settings` (حجم هر فایل ≤ `OA_SERVER_MAX_FILE_MB`=۲۴، مجموع ≥ حجم یک فایل، کل نامه ≥ مجموع نسخه، حداقل یک
  فرمت). `check_quota` برای سهمیه‌ی تعداد/مجموع هنگام پیوست به نامه (فاز ۳الف).
- چرخه: `uploading → rejected | scanning → clean | infected | scan_pending`؛ فقط clean قابل دانلود و permanent.

### اسکن (`services/oa_scanner.py`)
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
- نصب `clamav` و `clamav-daemon`؛ در `clamd.conf`: `StreamMaxLength 100M`، `AlertOLE2Macros yes`، `LocalSocketMode 666`؛
  دریافت اولین بانک با freshclam (اگر اینترنت نباشد، بعداً سرویس freshclam). هیچ‌کدام نصب را متوقف نمی‌کند.
- **حافظه:** clamd حدود ۱ تا ۱.۵ گیگابایت RAM مصرف می‌کند.

### تست
- `tests/test_oa_file_rules.py` (۱۱ تست): تنظیمات و سهمیه، پسوند ممنوع/خاموش، OOXML (جعلی، ماکرو، رمزدار)، Office قدیمی و ODF،
  ZIP (ممنوع، تودرتو، مسیر، bomb)، تصویر/متن/صوت/ویدیو، PDF، چرخه‌ی وضعیت، تجزیه‌ی پاسخ ClamAV، Storage (write-once، سقف حجم،
  حذف فایل نیمه‌کاره، مسیر خطرناک، قرنطینه).

### چک‌لیست سرور تست (فاز ۱الف)
1. بعد از آپدیت: `systemctl status clamav-daemon` فعال؛ صفحه‌ی «اسکنر و آزمایش آپلود» «اسکنر فعال است» و تاریخ بانک را نشان دهد.
2. آپلود PDF/DOCX/JPG سالم → «سالم» و دانلود با همان هش.
3. فایل آزمایشی EICAR (`eicar.txt`) → «آلوده (قرنطینه)» و بدون دکمه‌ی دانلود.
4. DOCX که پسوندش xlsx شده → رد «هم‌خوانی ندارد»؛ `.docm` یا DOCX با ماکرو → رد؛ `.exe` → رد «هرگز مجاز نیست».
5. ZIP خاموش → رد؛ روشن کردن ZIP در تنظیمات و آپلود ZIP حاوی exe → رد.
6. فایل بزرگ‌تر از سقف سایت → رد با پیام حجم.
7. `systemctl stop clamav-daemon` → آپلود «در انتظار اسکن»؛ start → حداکثر ۵ دقیقه بعد «سالم».
8. تغییر تنظیمات سایت A روی سایت B اثری نداشته باشد؛ کاربر با `automation.settings` فقط سایت A، سایت B را نبیند.
9. حجم هر فایل ۳۰ → خطای سقف سرور.

## فاز ۱ب — بکاپ (در دست ساخت)
بازنویسی جریانی، چند مقصد، دو حالت کلید، مجوزهای `backup.*` با مهاجرت `system.backup`، بازیابی هماهنگ (بخش ۱۰ سند).
