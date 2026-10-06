/**
 * تشخیص اجرای پرتال داخل اپ اندروید FAIPCO (TWA) و ارتباط با بخش بومی اپ (docs/android-app.md).
 *
 * - اپ پرتال را با آدرس /?source=android-app باز می‌کند و document.referrer در اولین باز شدن
 *   android-app://ir.faipco.portal است. این نشانه در sessionStorage همان تب نگه داشته می‌شود، نه localStorage:
 *   TWA حافظه‌ی سایت را با Chrome معمولی گوشی مشترک دارد و با localStorage، Chrome هم بعد از یک‌بار باز کردن اپ
 *   «داخل اپ» حساب می‌شد (قفل مرورگر دور زده می‌شد). sessionStorage مخصوص همان پنجره است و با reload می‌ماند.
 *   localStorage فقط «این گوشی اپ را دارد» را نگه می‌دارد (برای راهنماها، نه تشخیص داخل اپ).
 * - اتصال خودکار: اپ یک کد تصادفی در آدرس (#link=...) می‌فرستد؛ پرتال بعد از ورود کاربر آن را به حساب او وصل
 *   می‌کند (MobileAppPrompt) و بخش بومی اپ خودش توکن دستگاه را می‌گیرد. کد فقط وقتی پذیرفته می‌شود که صفحه واقعاً
 *   از اپ باز شده باشد (document.referrer = android-app://ir.faipco.portal)، تا لینکِ فرستاده‌شده توسط دیگری
 *   گوشی او را به حساب شما وصل نکند.
 * - پرتال با آدرس intent:// بخش بومی اپ را باز می‌کند (اتصال دستی با کد یک‌بارمصرف، یا بررسی دسترسی‌ها).
 */
export const ANDROID_PACKAGE = "ir.faipco.portal";
const APP_FLAG_KEY = "faipco_android_app"; // localStorage: این گوشی حداقل یک‌بار پرتال را از اپ باز کرده
const APP_SESSION_KEY = "faipco_android_app_session"; // sessionStorage: همین پنجره داخل اپ است
const LINK_KEY = "faipco_device_link"; // sessionStorage: کد اتصال خودکار تا بعد از ورود کاربر

function safeGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* حافظه در دسترس نیست */
  }
}

// یک‌بار در شروع برنامه (main.jsx) صدا زده می‌شود
export function detectAndroidApp() {
  try {
    const params = new URLSearchParams(window.location.search);
    const fromApp =
      params.get("source") === "android-app" || String(document.referrer || "").startsWith(`android-app://${ANDROID_PACKAGE}`);
    if (fromApp) safeSet(APP_FLAG_KEY, "1");
    // «داخل اپ» فقط با referrer اپ (Chrome آن را هنگام باز کردن TWA می‌گذارد)؛ پارامتر source را هر کسی می‌تواند در
    // نوار آدرس Chrome بنویسد و با آن قفل مرورگر را دور بزند
    if (String(document.referrer || "").startsWith(`android-app://${ANDROID_PACKAGE}`)) {
      try {
        sessionStorage.setItem(APP_SESSION_KEY, "1");
      } catch {
        /* بدون حافظه: فقط همین بارگذاری (پایین) */
      }
      inAppThisLoad = true;
    }
    // کد اتصال خودکار در بخش # آدرس (به سرور فرستاده و در لاگ ثبت نمی‌شود)
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const link = hash.get("link");
    if (link) {
      const reallyFromApp = String(document.referrer || "").startsWith(`android-app://${ANDROID_PACKAGE}`);
      if (reallyFromApp && /^[A-Za-z0-9_-]{16,100}$/.test(link)) {
        try {
          sessionStorage.setItem(LINK_KEY, link);
        } catch {
          /* بدون حافظه: اتصال دستی */
        }
      }
      hash.delete("link");
      const rest = hash.toString();
      window.history.replaceState(null, "", window.location.pathname + window.location.search + (rest ? `#${rest}` : ""));
    }
    if (params.get("source") === "android-app") {
      params.delete("source");
      const query = params.toString();
      window.history.replaceState(null, "", window.location.pathname + (query ? `?${query}` : "") + window.location.hash);
    }
  } catch {
    /* بدون تشخیص */
  }
}

const isAndroidUa = () => /android/i.test(navigator.userAgent || "");
let inAppThisLoad = false; // پشتیبان وقتی sessionStorage در دسترس نیست

function sessionInApp() {
  try {
    return sessionStorage.getItem(APP_SESSION_KEY) === "1";
  } catch {
    return false;
  }
}

// داخل اپ اندروید اجرا می‌شود؟ (فقط روی گوشی اندروید معتبر است)
export function isAndroidApp() {
  return isAndroidUa() && (inAppThisLoad || sessionInApp());
}

// این گوشی قبلاً اپ را باز کرده (احتمالاً نصب است)؛ فقط برای متن راهنما
export function hasOpenedAndroidApp() {
  return safeGet(APP_FLAG_KEY) === "1";
}

// همین صفحه را داخل اپ باز می‌کند (EntryActivity لینک‌های https پرتال را می‌گیرد و دسترسی‌ها را چک می‌کند)؛
// اپ نصب نباشد ← صفحه‌ی عمومی دانلود. باید در پاسخ به لمس کاربر صدا زده شود (Chrome بدون لمس اپ را باز نمی‌کند).
export function openPortalInApp(path = window.location.pathname + window.location.search) {
  const fallback = encodeURIComponent(`${window.location.origin}/app`);
  window.location.href =
    `intent://${window.location.host}${path}#Intent;scheme=https;package=${ANDROID_PACKAGE};` +
    `S.browser_fallback_url=${fallback};end`;
}

// مرورگر گوشی اندروید، بیرون از اپ
export function isAndroidBrowser() {
  return isAndroidUa() && !isAndroidApp();
}

// اگر اپ نصب‌شده این بخش را نداشته باشد (مثلاً نسخه‌ی قدیمی بدون بخش بومی)، Chrome به‌جای Play Store
// به همین صفحه با app_outdated=1 برمی‌گردد و راهنمای نصب نسخه‌ی جدید نمایش داده می‌شود.
function openIntent(path, params = {}) {
  const query = new URLSearchParams(params).toString();
  const fallback = encodeURIComponent(`${window.location.origin}/mobile-app?app_outdated=1`);
  window.location.href =
    `intent://${path}${query ? `?${query}` : ""}#Intent;scheme=faipco;package=${ANDROID_PACKAGE};` +
    `S.browser_fallback_url=${fallback};end`;
}

// باز کردن بخش بومی اپ برای اتصال این گوشی به حساب با کد یک‌بارمصرف
export function openNativePairing(code) {
  openIntent("pair", { code });
}

// باز کردن راهنمای دسترسی‌های بخش بومی (گوشی از قبل متصل است)
export function openNativeSetup() {
  openIntent("setup");
}

// کد اتصال خودکار؛ null اگر نباشد (بعد از ارسال موفق با clearDeviceLink پاک می‌شود)
export function peekDeviceLink() {
  try {
    return sessionStorage.getItem(LINK_KEY);
  } catch {
    return null;
  }
}

export function clearDeviceLink() {
  try {
    sessionStorage.removeItem(LINK_KEY);
  } catch {
    /* بدون حافظه */
  }
}
