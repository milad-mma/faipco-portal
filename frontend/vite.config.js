import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // injectManifest (نه generateSW پیش‌فرض): چون کد Push/Notification
      // کاملاً دستی خودمان را می‌خواهیم (src/sw.js)، نه یک Service Worker
      // خودکارساخته — فقط لیست Precache (که نام فایل‌هایش با هر Build
      // تغییر می‌کند) را Workbox خودکار داخلش تزریق می‌کند.
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.js",
      // چون ثبت Service Worker را خودمان دستی مدیریت می‌کنیم
      // (src/utils/serviceWorker.js — با منطق تشخیص نسخه جدید و Reload
      // خودکار)، از تزریق خودکار اسکریپت ثبت توسط این پلاگین صرف‌نظر می‌کنیم.
      injectRegister: null,
      // manifest.json را خودمان دستی نگه می‌داریم (public/manifest.json)
      // — چون از قبل کاملاً و دقیق تنظیم شده (RTL فارسی، آیکون‌های
      // Maskable و...)؛ نمی‌خواهیم این پلاگین یکی دیگر تولید/بازنویسی کند.
      manifest: false,
      injectManifest: {
        // باید حتماً js/css/html را شامل شود، وگرنه App Shell کامل
        // Precache نمی‌شود و در قطعی آفلاین با ChunkLoadError/صفحه سفید
        // مواجه می‌شویم.
        globPatterns: ["**/*.{js,css,html,svg,woff,woff2}"],
      },
      devOptions: {
        // فقط در Build واقعی فعال است — سرور Dev از HMR خودِ Vite استفاده
        // می‌کند، نیازی به Service Worker موقع توسعه نیست.
        enabled: false,
      },
    }),
  ],
  server: {
    port: 3000,
  },
  build: {
    outDir: "dist",
  },
});
