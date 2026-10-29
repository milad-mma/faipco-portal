/**
 * ثبت Service Worker و تشخیص نسخه‌ی جدید پس از هر Deploy، با تأیید دستی کاربر.
 *
 * نسخه‌ی جدید در حالت "waiting" می‌ماند و فقط رویداد سفارشی `faipco-update-ready` پخش می‌شود؛
 * پنل پیام «نسخه جدید آماده است» را نشان می‌دهد و کاربر زمان بارگذاری را انتخاب می‌کند (`applyPendingUpdate()`)
 * تا محتوای ذخیره‌نشده‌ی فرم‌ها با Reload خودکار از دست نرود.
 * `localStorage` (و در نتیجه ورود کاربر) در این فرآیند دست‌نخورده می‌ماند و فقط کدهای فرانت‌اند به‌روز می‌شوند.
 *
 * تشخیص سریع: هر Build یک شناسه دارد (__APP_BUILD__ داخل کد و /version.json کنار فایل‌ها؛ vite.config.js). صفحه‌ی باز
 * هر ۳۰ ثانیه، با برگشت به برنامه و با وصل شدن اینترنت version.json را (بدون Cache) می‌خواند؛ اگر شناسه عوض شده بود
 * پیام همان لحظه نمایش داده می‌شود — بدون منتظر ماندن برای دانلود کامل Service Worker جدید — و دکمه‌ی «بارگذاری» اگر
 * نسخه‌ی جدید هنوز نصب نشده، چند ثانیه صبر می‌کند و در نهایت با پاک کردن Cache و Service Worker صفحه را تازه بارگذاری می‌کند.
 */
const UPDATE_CHECK_INTERVAL_MS = 60 * 1000; // بررسی Service Worker جدید (درخواست شرطی سبک)
const VERSION_CHECK_INTERVAL_MS = 30 * 1000; // بررسی version.json
const INSTALL_WAIT_MS = 20 * 1000; // حداکثر انتظار برای نصب نسخه‌ی جدید پس از کلیک «بارگذاری»
const CURRENT_BUILD = typeof __APP_BUILD__ !== "undefined" ? __APP_BUILD__ : null; // eslint-disable-line no-undef
export const UPDATE_READY_EVENT = "faipco-update-ready"; // نام رویداد window که آماده بودن نسخه‌ی جدید را اعلام می‌کند

let waitingRegistration = null; // registration دارای نسخه‌ی در انتظار، برای ارسال SKIP_WAITING
let swRegistration = null; // registration فعلی (برای update و انتظار نصب)
let announced = false; // پیام فقط یک بار پخش شود

// registration را نگه می‌دارد و رویداد آماده بودن نسخه‌ی جدید را پخش می‌کند
function notifyUpdateReady(registration) {
  if (registration) waitingRegistration = registration;
  if (announced) return;
  announced = true;
  window.dispatchEvent(new CustomEvent(UPDATE_READY_EVENT));
}

// version.json سرور را با شناسه‌ی همین Build مقایسه می‌کند؛ تفاوت = نسخه‌ی جدید Deploy شده
async function checkDeployedVersion() {
  if (!CURRENT_BUILD || announced) return;
  try {
    const res = await fetch(`/version.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    if (data?.build && String(data.build) !== CURRENT_BUILD) {
      notifyUpdateReady(null);
      swRegistration?.update().catch(() => {}); // دانلود Service Worker جدید هم‌زمان شروع شود
    }
  } catch {
    // قطعی شبکه: دفعه‌ی بعد
  }
}

// تا timeout صبر می‌کند تا نسخه‌ی جدید در حالت waiting قرار بگیرد
function waitForWaiting(registration, timeout) {
  return new Promise((resolve) => {
    if (!registration) return resolve(null);
    if (registration.waiting) return resolve(registration.waiting);
    const timer = setTimeout(() => resolve(registration.waiting || null), timeout);
    const watch = (worker) =>
      worker?.addEventListener("statechange", () => {
        if (worker.state === "installed") {
          clearTimeout(timer); // eslint-disable-line no-undef
          resolve(registration.waiting || worker);
        }
      });
    watch(registration.installing);
    registration.addEventListener("updatefound", () => watch(registration.installing));
    registration.update().catch(() => {});
  });
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

  const registration = waitingRegistration || swRegistration;
  const waiting = registration?.waiting || (await waitForWaiting(registration, INSTALL_WAIT_MS));
  if (waiting) {
    waiting.postMessage({ type: "SKIP_WAITING" }); // Reload با controllerchange
    return;
  }
  // نسخه‌ی جدید نصب نشد (یا Service Worker نیست): بارگذاری کامل از شبکه
  try {
    const registrations = await navigator.serviceWorker?.getRegistrations?.();
    await Promise.all((registrations || []).map((r) => r.unregister()));
  } catch {
    // ادامه
  }
  window.location.reload();
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
      swRegistration = registration;

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
      setInterval(checkDeployedVersion, VERSION_CHECK_INTERVAL_MS); // eslint-disable-line no-undef
      checkDeployedVersion(); // همان لحظه‌ی باز شدن (صفحه‌ای که از Cache قدیمی آمده فوراً پیام می‌گیرد)

      // بررسی فوری به‌روزرسانی هنگام برگشت کاربر به برنامه (از پس‌زمینه یا تب دیگر) یا وصل شدن دوباره‌ی اینترنت
      const checkNow = () => {
        registration.update().catch(() => {});
        checkDeployedVersion();
      };
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") checkNow();
      });
      window.addEventListener("focus", checkNow);
      window.addEventListener("online", checkNow);
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
