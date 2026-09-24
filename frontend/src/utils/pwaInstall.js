/**
 * مدیریت قابلیت «نصب اپلیکیشن» (Add to Home Screen / PWA Install).
 *
 * مرورگرهای مبتنی بر Chromium (اندروید، Chrome/Edge دسکتاپ) رویداد beforeinstallprompt را می‌فرستند؛
 * این فایل آن را نگه می‌دارد تا بعداً با دکمه‌ی نصب نمایش داده شود و با رویداد pwa-installable-changed
 * تغییر وضعیت را به UI خبر می‌دهد. Safari/iOS این API را ندارد و نصب فقط دستی از دکمه‌ی Share ممکن است.
 */

let deferredPrompt = null; // رویداد beforeinstallprompt نگه‌داشته‌شده برای نمایش بعدی
let isInstallable = false; // آیا مرورگر امکان نصب را اعلام کرده است

// جلوگیری از نمایش خودکار پنجره‌ی نصب، نگه‌داشتن رویداد و اطلاع به UI
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredPrompt = event;
  isInstallable = true;
  window.dispatchEvent(new CustomEvent("pwa-installable-changed"));
});

// پس از نصب برنامه، وضعیت نصب‌پذیری پاک و به UI اطلاع داده می‌شود
window.addEventListener("appinstalled", () => {
  deferredPrompt = null;
  isInstallable = false;
  window.dispatchEvent(new CustomEvent("pwa-installable-changed"));
});

// خروجی: true اگر برنامه به صورت نصب‌شده (standalone) اجرا شده باشد
export function isRunningStandalone() {
  return (
    window.matchMedia?.("(display-mode: standalone)")?.matches ||
    window.navigator.standalone === true // iOS Safari
  );
}

// خروجی: true اگر دستگاه iPhone/iPad/iPod باشد (برای نمایش راهنمای نصب دستی)
export function isIos() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
}

// خروجی: true اگر نصب ممکن باشد و برنامه از قبل نصب‌شده اجرا نشده باشد
export function getIsInstallable() {
  return isInstallable && !isRunningStandalone();
}

// پنجره‌ی نصب مرورگر را نمایش می‌دهد؛ خروجی: true اگر کاربر نصب را پذیرفت (رویداد فقط یک‌بار قابل استفاده است)
export async function promptPwaInstall() {
  if (!deferredPrompt) return false;
  deferredPrompt.prompt();
  const choice = await deferredPrompt.userChoice;
  deferredPrompt = null;
  isInstallable = false;
  window.dispatchEvent(new CustomEvent("pwa-installable-changed"));
  return choice.outcome === "accepted";
}
