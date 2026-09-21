# اعلان تغییرات پرتال (Portal Announcement)

دیالوگی که هنگام ورود کاربر به پرتال، «تغییرات اخیر» را نشان می‌دهد. متن
آن را Admin واقعی می‌نویسد. خلاصه کوتاه در [`docs/features.md`](features.md)
هم هست؛ این فایل جزئیات کامل است.

⚠️ این قابلیت با [سیستم اطلاعیه](notices.md) فرق دارد: هیچ Target،
Push، گزارش بازدید یا آرشیوی ندارد — فقط یک متن سراسری برای همه کاربران
لاگین‌شده است.

## Endpoint ها (`app/api/v1/endpoints/announcement.py`، پیشوند `/announcement`)

| مسیر | دسترسی | کار |
|---|---|---|
| `GET /announcement/current` | هر کاربر لاگین‌شده | اعلان فعلی + `should_show` برای همین کاربر |
| `POST /announcement/dismiss` | هر کاربر لاگین‌شده | «دیگر نمایش نده» — نسخه فعلی روی کاربر ثبت می‌شود |
| `GET /announcement/settings` | فقط Admin واقعی (`require_superuser`) | خواندن تنظیمات |
| `PUT /announcement/settings` | فقط Admin واقعی | ذخیره `{enabled, title, body}` |

```bash
curl http://localhost:8000/api/v1/announcement/current -H "Authorization: Bearer $TOKEN"
# {"enabled": true, "title": "...", "body": "...", "version": 3, "should_show": true}

curl -X PUT http://localhost:8000/api/v1/announcement/settings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"enabled": true, "title": "تغییرات اخیر پرتال", "body": "- مورد اول\n- مورد دوم"}'
```

## ذخیره‌سازی

- محتوا در جدول عمومی `system_settings` (بدون جدول جدید)، با چهار کلید:
  `announcement_enabled` (`"true"`/`"false"`)، `announcement_title`،
  `announcement_body`، `announcement_version` (عدد صحیح، پیش‌فرض ۰) —
  `SystemSettingsService.get_announcement` / `set_announcement`.
- **Migration 071** (`071_announcement_dismissal`): ستون
  `users.dismissed_announcement_version` (Integer، NOT NULL، پیش‌فرض ۰).

چرا روی خودِ کاربر و نه `localStorage`: با عوض‌کردن مرورگر یا دستگاه،
اعلانی که قبلاً رد شده نباید دوباره ظاهر شود.

## منطق نمایش (سمت سرور)

```python
should_show = enabled and body.strip() != "" and user.dismissed_announcement_version < version
```

تصمیم در Backend گرفته می‌شود (نه در کلاینت) تا منطق در یک جا بماند.
اعلان با متن خالی هرگز نمایش داده نمی‌شود، حتی اگر فعال باشد.

### چرا «نسخه» و نه یک Boolean ساده

اگر فقط یک فلگ بولی بود، کاربری که یک‌بار «دیگر نمایش نده» می‌زد **هرگز
هیچ اعلان بعدی** را نمی‌دید. `set_announcement` هر بار که **عنوان یا متن**
عوض شود، `version` را یکی بالا می‌برد؛ پس اعلان جدید برای همه — حتی
ردکنندگان قبلی — دوباره نمایش داده می‌شود.

⚠️ صرفاً خاموش/روشن‌کردن اعلان (بدون تغییر محتوا) نسخه را بالا نمی‌برد —
کسی که قبلاً رد کرده، با روشن‌کردن دوباره همان متن، آن را نمی‌بیند.

⚠️ `dismiss` همیشه **نسخه فعلی سرور** را ثبت می‌کند (نه نسخه‌ای که کاربر
دیده). اگر ادمین بین بازشدن دیالوگ و کلیک کاربر متن را عوض کند، نسخه جدید
هم رد‌شده حساب می‌شود.

## Frontend

- **`components/AnnouncementDialog.jsx`**: داخل `Layout.jsx` نصب شده —
  یعنی روی همه صفحات لاگین‌شده، یک‌بار در هر mount شدن Layout (ورود یا
  بارگذاری کامل صفحه)، `GET /announcement/current` را می‌گیرد و فقط اگر
  `should_show` باشد باز می‌شود. عنوان خالی → «تغییرات اخیر پرتال».
  - **بستن**: فقط دیالوگ را می‌بندد؛ دفعه بعد دوباره نمایش داده می‌شود.
  - **دیگر نمایش نده**: `POST /announcement/dismiss` — حتی اگر درخواست
    خطا بدهد، دیالوگ بسته می‌شود تا کاربر گیر نکند.
  - متن به‌صورت **متن ساده** رندر می‌شود (نه HTML — بدون امکان تزریق
    اسکریپت) و شکست خطوط حفظ می‌شود (`white-space: pre-wrap`).
  - خطای دریافت اعلان بی‌صدا نادیده گرفته می‌شود — قابلیت جانبی نباید
    ورود به پرتال را مختل کند.
- **`components/AnnouncementSettings.jsx`**: ویرایشگر ادمین (سوییچ
  فعال/غیرفعال، عنوان، متن چندخطی، دکمه «ذخیره و انتشار» که شماره نسخه را
  هم نشان می‌دهد). این ویرایشگر در **صفحه به‌روزرسانی** (`UpdatePage.jsx`،
  مسیر `/update`، فقط Admin واقعی) قرار دارد، نه در «تنظیمات سامانه» — چون
  معمولاً بلافاصله بعد از اعمال یک آپدیت، ادمین می‌خواهد تغییرات را اعلام
  کند.
