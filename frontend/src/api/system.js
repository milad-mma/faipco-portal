/**
 * توابع و آدرس‌های API تنظیمات سیستم.
 * برندینگ و لوگوها، پس‌زمینه‌ی صفحه‌ی ورود، نسخه و به‌روزرسانی، آمار مصرف و سرور، بررسی‌های پروژه،
 * پاک‌سازی کش، فهرست مجاز IP و تنظیمات SMTP و پیامک.
 */
import { apiClient } from "./client";

// آدرس مستقیم تصاویر برای استفاده در <img src=...>؛ این مسیرها بدون احراز هویت در دسترس‌اند
// چون تگ img هدر Authorization مربوط به apiClient را ارسال نمی‌کند
export const LOGIN_BACKGROUND_URL = `${apiClient.defaults.baseURL}/system/login-background`;
// لوگوهای مستقل، هرکدام برای یک مصرف متفاوت (لوگوی اپ، نسخه‌ی کوچک، آیکون PWA، favicon)
export const APP_LOGO_URL = `${apiClient.defaults.baseURL}/system/logo/app-logo`;
export const APP_LOGO_SMALL_URL = `${apiClient.defaults.baseURL}/system/logo/app-logo-small`;
export const PWA_ICON_URL = `${apiClient.defaults.baseURL}/system/logo/pwa-icon`;
export const FAVICON_URL = `${apiClient.defaults.baseURL}/system/logo/favicon`;

// GET /system/branding؛ خروجی: تنظیمات برندینگ (نام، رنگ‌ها و تنظیمات هر بخش)
export async function fetchBranding() {
  const { data } = await apiClient.get("/system/branding");
  return data;
}

// PUT /system/branding؛ ذخیره‌ی تنظیمات برندینگ؛ خروجی: برندینگ به‌روزشده
export async function updateBranding(payload) {
  const { data } = await apiClient.put("/system/branding", payload);
  return data;
}

// آدرس لوگوی اختصاصی یک بخش (surface) از برندینگ
export const SURFACE_LOGO_URL = (surface) => `${apiClient.defaults.baseURL}/system/logo/surface-${surface}`;
// آدرس یک اندازه/نوع از آیکون PWA؛ version برای شکستن کش مرورگر به انتهای آدرس اضافه می‌شود
export const PWA_ICON_VARIANT_URL = (variant, version = "") =>
  `${apiClient.defaults.baseURL}/system/pwa-icon/${variant}.png${version ? `?v=${version}` : ""}`;

// PUT /system/branding/surfaces/{surface}؛ ذخیره‌ی مقادیر یک بخش برندینگ؛ خروجی: برندینگ به‌روزشده
export async function updateBrandingSurface(surface, values) {
  const { data } = await apiClient.put(`/system/branding/surfaces/${surface}`, { values });
  return data;
}

// DELETE /system/branding/surfaces/{surface}؛ بازگرداندن یک بخش به مقادیر پیش‌فرض؛ خروجی: برندینگ به‌روزشده
export async function resetBrandingSurface(surface) {
  const { data } = await apiClient.delete(`/system/branding/surfaces/${surface}`);
  return data;
}

// PUT /system/branding/pwa-icon؛ ذخیره‌ی تنظیمات آیکون PWA؛ خروجی: برندینگ به‌روزشده
export async function updatePwaIconSettings(values) {
  const { data } = await apiClient.put("/system/branding/pwa-icon", { values });
  return data;
}

// POST /system/logo/{slug}؛ آپلود فایل لوگو (slug: app-logo، pwa-icon، favicon و ...)؛ خروجی: پاسخ سرور
export async function uploadLogo(slug, file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post(`/system/logo/${slug}`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

// DELETE /system/logo/{slug}؛ حذف لوگوی آپلودشده
export async function deleteLogo(slug) {
  await apiClient.delete(`/system/logo/${slug}`);
}

// POST /system/login-background؛ آپلود تصویر پس‌زمینه‌ی صفحه‌ی ورود؛ خروجی: پاسخ سرور
export async function uploadLoginBackground(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post("/system/login-background", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

// DELETE /system/login-background؛ حذف تصویر پس‌زمینه‌ی صفحه‌ی ورود
export async function deleteLoginBackground() {
  await apiClient.delete("/system/login-background");
}

// GET /system/version؛ خروجی: رشته‌ی نسخه‌ی فعلی برنامه
export async function fetchAppVersion() {
  const { data } = await apiClient.get("/system/version", { timeout: 5000 });
  return data.version;
}

// GET /system/usage-stats؛ خروجی: تعداد درخواست‌ها به تفکیک تاریخ و ساعت
export async function fetchUsageStats() {
  const { data } = await apiClient.get("/system/usage-stats");
  return data; // [{ date, hour, request_count }]
}

// GET /system/server-stats؛ خروجی: سری زمانی مصرف CPU، RAM و دیسک سرور
export async function fetchServerStats() {
  const { data } = await apiClient.get("/system/server-stats");
  return data; // [{ recorded_at, cpu_percent, ram_percent, ram_used_mb, ram_total_mb, disk_percent, disk_used_gb, disk_total_gb }]
}

// GET /system/check-update؛ خروجی: نسخه‌ی فعلی و آخرین نسخه‌ی منتشرشده و وجود به‌روزرسانی
export async function checkForUpdate() {
  const { data } = await apiClient.get("/system/check-update", { timeout: 15000 });
  return data; // { checked, current_version, latest_version, has_update, release_url }
}

// POST /system/apply-update با عبارت تأیید و رمز عبور؛ شروع نصب به‌روزرسانی؛ خروجی: پاسخ سرور
export async function applyUpdate(confirmPhrase, password) {
  const formData = new FormData();
  formData.append("confirm", confirmPhrase);
  formData.append("password", password);
  const { data } = await apiClient.post("/system/apply-update", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

// GET /system/update-status؛ خروجی: لاگ و وضعیت اجرای به‌روزرسانی
export async function fetchUpdateStatus() {
  // Timeout کوتاه تا در زمان Stop/Start سرویس، درخواست سریع خطا دهد و فوراً دوباره تلاش شود
  const { data } = await apiClient.get("/system/update-status", { timeout: 5000 });
  return data; // { log, is_running, is_finished, is_failed }
}

// POST /system/run-checks؛ شروع اجرای بررسی‌های پروژه؛ خروجی: پاسخ سرور
export async function runProjectChecks() {
  const { data } = await apiClient.post("/system/run-checks");
  return data;
}

// GET /system/check-status؛ خروجی: لاگ و وضعیت اجرای بررسی‌ها
export async function fetchProjectCheckStatus() {
  const { data } = await apiClient.get("/system/check-status", { timeout: 5000 });
  return data; // { log, is_running, is_passed, is_failed }
}

// POST /system/cache-bust؛ تغییر نسخه‌ی کش تا کلاینت‌ها فایل‌های جدید را بگیرند؛ خروجی: نتیجه و نسخه
export async function bustAppCache() {
  const { data } = await apiClient.post("/system/cache-bust");
  return data; // { success, version, message }
}

// GET /system/ip-allowlist؛ خروجی: فعال بودن، متن فهرست و تعداد رنج‌های IP مجاز
export async function fetchIpAllowlistState() {
  const { data } = await apiClient.get("/system/ip-allowlist", { timeout: 60_000 });
  return data; // { enabled, text, count }
}

// PUT /system/ip-allowlist؛ ذخیره‌ی فعال بودن و متن فهرست IP مجاز؛ خروجی: وضعیت ذخیره‌شده
export async function saveIpAllowlistState({ enabled, text }) {
  const { data } = await apiClient.put(
    "/system/ip-allowlist",
    { enabled, text },
    { timeout: 60_000 } // فهرست‌های خیلی بزرگ (مثلاً فایروال با هزاران رنج) ممکن است بیشتر طول بکشد
  );
  return data; // { enabled, text, count }
}

// GET /system/ip-blocked-message؛ خروجی: پیام نمایشی به کاربران با IP غیرمجاز
export async function fetchIpBlockedMessage() {
  const { data } = await apiClient.get("/system/ip-blocked-message");
  return data.message;
}

// PUT /system/ip-blocked-message؛ ذخیره‌ی پیام IP غیرمجاز؛ خروجی: پیام ذخیره‌شده
export async function updateIpBlockedMessage(message) {
  const { data } = await apiClient.put("/system/ip-blocked-message", { message });
  return data.message;
}

// GET /system/smtp-settings؛ خروجی: تنظیمات سرور ایمیل (SMTP)
export async function fetchSmtpSettings() {
  const { data } = await apiClient.get("/system/smtp-settings");
  return data;
}

// PUT /system/smtp-settings؛ ذخیره‌ی تنظیمات SMTP؛ خروجی: تنظیمات ذخیره‌شده
export async function updateSmtpSettings(payload) {
  const { data } = await apiClient.put("/system/smtp-settings", payload);
  return data;
}

// POST /system/smtp-settings/test؛ ارسال ایمیل آزمایشی به آدرس داده‌شده؛ خروجی: نتیجه‌ی تست
export async function testSmtpSettings(toAddress) {
  const { data } = await apiClient.post(
    "/system/smtp-settings/test",
    { to_address: toAddress },
    { timeout: 30000 }
  );
  return data;
}

// GET /system/sms-settings؛ خروجی: تنظیمات سرویس پیامک
export async function fetchSmsSettings() {
  const { data } = await apiClient.get("/system/sms-settings");
  return data;
}

// PUT /system/sms-settings؛ ذخیره‌ی تنظیمات پیامک؛ خروجی: تنظیمات ذخیره‌شده
export async function updateSmsSettings(payload) {
  const { data } = await apiClient.put("/system/sms-settings", payload);
  return data;
}

// POST /system/sms-settings/test؛ ارسال پیامک آزمایشی به شماره‌ی داده‌شده؛ خروجی: نتیجه‌ی تست
export async function testSmsSettings(toMobile) {
  const { data } = await apiClient.post(
    "/system/sms-settings/test",
    { to_mobile: toMobile },
    { timeout: 30000 }
  );
  return data;
}
