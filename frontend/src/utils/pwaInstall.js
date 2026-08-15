/**
 * مدیریت قابلیت «نصب اپلیکیشن» (Add to Home Screen / PWA Install).
 *
 * مرورگرهای مبتنی بر Chromium (اندروید، دسکتاپ Chrome/Edge) رویداد
 * beforeinstallprompt را می‌فرستند که می‌شود بعداً به‌صورت برنامه‌ریزی‌شده
 * صداش زد. Safari/iOS اصلاً از این API پشتیبانی نمی‌کند — نصب آنجا فقط
 * دستی از طریق دکمه Share امکان‌پذیر است، پس فقط راهنمای متنی نشان می‌دهیم.
 */

let deferredPrompt = null;
let isInstallable = false;

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredPrompt = event;
  isInstallable = true;
  window.dispatchEvent(new CustomEvent("pwa-installable-changed"));
});

window.addEventListener("appinstalled", () => {
  deferredPrompt = null;
  isInstallable = false;
  window.dispatchEvent(new CustomEvent("pwa-installable-changed"));
});

export function isRunningStandalone() {
  return (
    window.matchMedia?.("(display-mode: standalone)")?.matches ||
    window.navigator.standalone === true // iOS Safari
  );
}

export function isIos() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
}

export function getIsInstallable() {
  return isInstallable && !isRunningStandalone();
}

export async function promptPwaInstall() {
  if (!deferredPrompt) return false;
  deferredPrompt.prompt();
  const choice = await deferredPrompt.userChoice;
  deferredPrompt = null;
  isInstallable = false;
  window.dispatchEvent(new CustomEvent("pwa-installable-changed"));
  return choice.outcome === "accepted";
}
