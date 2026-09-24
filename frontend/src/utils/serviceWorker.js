/**
 * ثبت Service Worker و تشخیص نسخه‌ی جدید پس از هر Deploy، با تأیید دستی کاربر.
 *
 * نسخه‌ی جدید در حالت "waiting" می‌ماند و فقط رویداد سفارشی `faipco-update-ready` پخش می‌شود؛
 * پنل پیام «نسخه جدید آماده است» را نشان می‌دهد و کاربر زمان بارگذاری را انتخاب می‌کند (`applyPendingUpdate()`)
 * تا محتوای ذخیره‌نشده‌ی فرم‌ها با Reload خودکار از دست نرود.
 * `localStorage` (و در نتیجه ورود کاربر) در این فرآیند دست‌نخورده می‌ماند و فقط کدهای فرانت‌اند به‌روز می‌شوند.
 */
const UPDATE_CHECK_INTERVAL_MS = 5 * 60 * 1000; // فاصله‌ی بررسی نسخه‌ی جدید وقتی برنامه باز است (۵ دقیقه)
export const UPDATE_READY_EVENT = "faipco-update-ready"; // نام رویداد window که آماده بودن نسخه‌ی جدید را اعلام می‌کند

let waitingRegistration = null; // registration دارای نسخه‌ی در انتظار، برای ارسال SKIP_WAITING

// registration را نگه می‌دارد و رویداد آماده بودن نسخه‌ی جدید را پخش می‌کند
function notifyUpdateReady(registration) {
  waitingRegistration = registration;
  window.dispatchEvent(new CustomEvent(UPDATE_READY_EVENT));
}

/** اعمال نسخه‌ی جدید (دکمه‌ی «بارگذاری نسخه جدید»): پاک کردن Cache Storage و ارسال SKIP_WAITING به نسخه‌ی در انتظار. */
export async function applyPendingUpdate() {
  // پیش از فعال‌سازی نسخه‌ی جدید، همه‌ی Cache Storage (فایل‌های Precache نسخه‌ی قبلی) پاک می‌شود
  // تا هیچ فایل قدیمی سرو نشود؛ localStorage جداست و دست‌نخورده می‌ماند (کاربر از حساب خارج نمی‌شود)
  // و Service Worker جدید کش خود را از نو می‌سازد
  try {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map((name) => caches.delete(name)));
  } catch (err) {
    console.error("پاک‌سازی Cache Storage ناموفق بود (ادامه می‌دهیم):", err);
  }

  if (waitingRegistration?.waiting) {
    waitingRegistration.waiting.postMessage({ type: "SKIP_WAITING" });
  }
}

/**
 * پس از load صفحه /sw.js را ثبت می‌کند، نسخه‌ی در انتظار یا تازه نصب‌شده را اعلام می‌کند،
 * به صورت دوره‌ای و با برگشت به برنامه به‌روزرسانی را بررسی می‌کند و پس از تعویض کنترل‌کننده صفحه را Reload می‌کند.
 */
export function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", async () => {
    try {
      const registration = await navigator.serviceWorker.register("/sw.js");

      // اگر از قبل نسخه‌ای در حالت waiting وجود دارد (و این اولین نصب نیست)، آماده بودن آن اعلام می‌شود
      if (registration.waiting && navigator.serviceWorker.controller) {
        notifyUpdateReady(registration);
      }

      // با پیدا شدن نسخه‌ی تازه، پس از رسیدن به حالت "installed" و فقط اگر SW دیگری صفحه را کنترل می‌کرده
      // (یعنی به‌روزرسانی است نه اولین نصب)، آماده بودن نسخه اعلام می‌شود
      registration.addEventListener("updatefound", () => {
        const newWorker = registration.installing;
        if (!newWorker) return;
        newWorker.addEventListener("statechange", () => {
          if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
            notifyUpdateReady(registration);
          }
        });
      });

      // بررسی دوره‌ای وجود نسخه‌ی جدید؛ خطای شبکه نادیده گرفته می‌شود
      setInterval(() => {
        registration.update().catch(() => {});
      }, UPDATE_CHECK_INTERVAL_MS);

      // بررسی فوری به‌روزرسانی هنگام برگشت کاربر به برنامه (از پس‌زمینه یا تب دیگر) با رویداد visibilitychange
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          registration.update().catch(() => {});
        }
      });
    } catch (err) {
      console.error("ثبت Service Worker ناموفق بود:", err);
    }
  });

  // Reload صفحه فقط وقتی کنترل‌کننده عوض شود، یعنی پس از تأیید کاربر با applyPendingUpdate()
  let hasReloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (hasReloaded) return; // جلوگیری از حلقه Reload در صورت چند بار fire شدن رویداد
    hasReloaded = true;
    window.location.reload();
  });
}
