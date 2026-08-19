/**
 * ثبت Service Worker + تشخیص نسخه جدید بعد از هر Deploy — با تأیید دستی
 * کاربر، نه Reload خودکار بی‌هشدار.
 *
 * چرا دستی: نسخه‌های قبلی این فایل، به‌محض پیداشدن نسخه جدید، بلافاصله و
 * خودکار صفحه را Reload می‌کردند. مشکلش: اگر دقیقاً همان لحظه کاربر یک فرم
 * طولانی (مثلاً نوشتن یک اطلاعیه) باز داشته باشد، همان لحظه محتوای
 * ذخیره‌نشده از دست می‌رفت. حالا نسخه جدید در حالت "waiting" می‌ماند و فقط
 * یک رویداد سفارشی (`faipco-update-ready`) پخش می‌شود — پنل یک پیام کوچک
 * «نسخه جدید آماده است» نشان می‌دهد و کاربر خودش تصمیم می‌گیرد کِی
 * بارگذاری کند (`applyPendingUpdate()`).
 *
 * `localStorage` (و در نتیجه ورود کاربر) در این فرآیند هرگز دست‌نخورده
 * می‌ماند — فقط کدهای فرانت‌اند به‌روز می‌شوند.
 */
const UPDATE_CHECK_INTERVAL_MS = 5 * 60 * 1000; // هر ۵ دقیقه یک‌بار چک نسخه جدید (وقتی اپ باز است)
export const UPDATE_READY_EVENT = "faipco-update-ready";

let waitingRegistration = null;

function notifyUpdateReady(registration) {
  waitingRegistration = registration;
  window.dispatchEvent(new CustomEvent(UPDATE_READY_EVENT));
}

/** از UI (دکمه «بارگذاری نسخه جدید») صدا زده می‌شود. */
export function applyPendingUpdate() {
  if (waitingRegistration?.waiting) {
    waitingRegistration.waiting.postMessage({ type: "SKIP_WAITING" });
  }
}

export function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", async () => {
    try {
      const registration = await navigator.serviceWorker.register("/sw.js");

      // اگر همین لحظه یک نسخه در حالت waiting از قبل موجود باشد (مثلاً
      // کاربر یک‌بار قبلاً همین صفحه را باز کرده بود و همان‌جا هنوز مانده)
      if (registration.waiting && navigator.serviceWorker.controller) {
        notifyUpdateReady(registration);
      }

      // وقتی یک نسخه تازه پیدا/نصب می‌شود، تا وقتی به حالت "installed"
      // نرسیده صبر می‌کنیم — و فقط اگر از قبل یک SW دیگر واقعاً در حال
      // کنترل صفحه بوده (یعنی این اولین نصب نیست، بلکه یک آپدیت است)،
      // اطلاع می‌دهیم.
      registration.addEventListener("updatefound", () => {
        const newWorker = registration.installing;
        if (!newWorker) return;
        newWorker.addEventListener("statechange", () => {
          if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
            notifyUpdateReady(registration);
          }
        });
      });

      setInterval(() => {
        registration.update().catch(() => {});
      }, UPDATE_CHECK_INTERVAL_MS);

      // بلافاصله چک کن — نه فقط وقتی اپ همیشه باز مانده — دقیقاً همان لحظه‌ای
      // که کاربر به اپ برمی‌گردد (از پس‌زمینه، یا با باز کردن دوباره بعد از
      // بسته‌شدن کامل). visibilitychange روی این حالت‌ها هم fire می‌شود، نه
      // فقط تعویض بین تب‌های یک مرورگر.
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          registration.update().catch(() => {});
        }
      });
    } catch (err) {
      console.error("ثبت Service Worker ناموفق بود:", err);
    }
  });

  // این‌جا (نه در لحظه پیداشدن آپدیت) واقعاً Reload می‌شود — یعنی فقط بعد
  // از اینکه کاربر خودش با applyPendingUpdate() تأیید کرده باشد.
  let hasReloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (hasReloaded) return; // جلوگیری از حلقه Reload در صورت چند بار fire شدن رویداد
    hasReloaded = true;
    window.location.reload();
  });
}
