/**
 * تشخیص اجرای پرتال داخل اپ اندروید FAIPCO (TWA) و ارتباط با بخش بومی اپ (docs/android-app.md).
 *
 * - اپ پرتال را با آدرس /?source=android-app باز می‌کند؛ این نشانه در localStorage می‌ماند (در TWA حافظه‌ی
 *   مرورگر مخصوص همین سایت است). document.referrer هم در اولین باز شدن android-app://ir.faipco.portal است.
 * - پرتال با آدرس intent:// بخش بومی اپ را باز می‌کند (اتصال گوشی با کد یک‌بارمصرف، یا بررسی دسترسی‌ها).
 */
export const ANDROID_PACKAGE = "ir.faipco.portal";
const APP_FLAG_KEY = "faipco_android_app";

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

// داخل اپ اندروید اجرا می‌شود؟ (فقط روی گوشی اندروید معتبر است)
export function isAndroidApp() {
  return isAndroidUa() && safeGet(APP_FLAG_KEY) === "1";
}

// مرورگر گوشی اندروید، بیرون از اپ
export function isAndroidBrowser() {
  return isAndroidUa() && !isAndroidApp();
}

function openIntent(path, params = {}) {
  const query = new URLSearchParams(params).toString();
  window.location.href = `intent://${path}${query ? `?${query}` : ""}#Intent;scheme=faipco;package=${ANDROID_PACKAGE};end`;
}

// باز کردن بخش بومی اپ برای اتصال این گوشی به حساب با کد یک‌بارمصرف
export function openNativePairing(code) {
  openIntent("pair", { code });
}

// باز کردن راهنمای دسترسی‌های بخش بومی (گوشی از قبل متصل است)
export function openNativeSetup() {
  openIntent("setup");
}
