/**
 * پیکربندی Vite: پلاگین React و vite-plugin-pwa (Service Worker دستی src/sw.js با استراتژی injectManifest)،
 * پورت سرور توسعه و پوشه‌ی خروجی Build.
 */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// شناسه‌ی هر Build (زمان ساخت): داخل کد (__APP_BUILD__) و در dist/version.json؛ صفحه‌ی باز هر ۳۰ ثانیه version.json
// را می‌خواند و اگر عوض شده بود فوراً پیام «نسخه جدید پرتال آماده است» را نشان می‌دهد (src/utils/serviceWorker.js)
const APP_BUILD = String(Date.now());

function versionFile() {
  return {
    name: "faipco-version-file",
    apply: "build",
    generateBundle() {
      this.emitFile({ type: "asset", fileName: "version.json", source: JSON.stringify({ build: APP_BUILD }) });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  define: {
    __APP_BUILD__: JSON.stringify(APP_BUILD),
  },
  plugins: [
    react(),
    versionFile(),
    VitePWA({
      // injectManifest: Service Worker دستی src/sw.js (با کد Push/Notification) استفاده می‌شود
      // و Workbox فقط فهرست Precache (که نام فایل‌هایش با هر Build تغییر می‌کند) را داخل آن تزریق می‌کند
      strategies: "injectManifest",
      srcDir: "src", // پوشه‌ی فایل Service Worker
      filename: "sw.js", // نام فایل Service Worker در ورودی و خروجی
      // اسکریپت ثبت خودکار تزریق نمی‌شود؛ ثبت و تشخیص نسخه‌ی جدید در src/utils/serviceWorker.js انجام می‌شود
      injectRegister: null,
      // manifest توسط پلاگین تولید نمی‌شود؛ فایل دستی public/manifest.json (RTL فارسی، آیکون‌های Maskable و ...) استفاده می‌شود
      manifest: false,
      injectManifest: {
        // الگوی فایل‌های Precache؛ js/css/html برای پوسته‌ی کامل برنامه لازم‌اند تا در قطعی اینترنت
        // ChunkLoadError/صفحه‌ی سفید رخ ندهد
        globPatterns: ["**/*.{js,css,html,svg,woff,woff2}"],
      },
      devOptions: {
        // Service Worker در سرور توسعه غیرفعال است و فقط در Build ساخته می‌شود
        enabled: false,
      },
    }),
  ],
  server: {
    port: 3000, // پورت سرور توسعه
  },
  build: {
    outDir: "dist", // پوشه‌ی خروجی Build
  },
});
