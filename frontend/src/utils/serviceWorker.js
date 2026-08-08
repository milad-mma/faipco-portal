/**
 * ثبت Service Worker + تشخیص خودکار نسخه جدید بعد از هر Deploy.
 *
 * مشکلی که حل می‌کند: کاربری که از قبل وارد شده و تب برنامه را باز نگه
 * داشته، بعد از یک Update روی سرور همچنان کد قدیمی را در حافظه مرورگرش
 * اجرا می‌کند — چون SPA خودش به‌خودی خبر ندارد که نسخه جدیدی منتشر شده.
 *
 * راه‌حل: این فایل هر چند دقیقه یک‌بار از مرورگر می‌خواهد sw.js را دوباره
 * چک کند (به‌جای چرخه پیش‌فرض و کند خود مرورگر). چون خود sw.js از
 * skipWaiting()/clients.claim() استفاده می‌کند، هر نسخه جدید بلافاصله و
 * خودکار فعال و کنترل تب‌های باز را در دست می‌گیرد؛ همان لحظه (رویداد
 * controllerchange) صفحه یک‌بار Reload می‌شود — بدون این‌که localStorage
 * (و در نتیجه Login کاربر) پاک شود، فقط کدهای فرانت‌اند به‌روز می‌شوند.
 */
const UPDATE_CHECK_INTERVAL_MS = 5 * 60 * 1000; // هر ۵ دقیقه یک‌بار چک نسخه جدید

export function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", async () => {
    try {
      const registration = await navigator.serviceWorker.register("/sw.js");
      setInterval(() => {
        registration.update().catch(() => {});
      }, UPDATE_CHECK_INTERVAL_MS);
    } catch (err) {
      console.error("ثبت Service Worker ناموفق بود:", err);
    }
  });

  let hasReloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (hasReloaded) return; // جلوگیری از حلقه Reload در صورت چند بار fire شدن رویداد
    hasReloaded = true;
    window.location.reload();
  });
}
