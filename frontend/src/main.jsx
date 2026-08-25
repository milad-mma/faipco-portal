import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { CacheProvider } from "@emotion/react";
// فونت وزیرمتن — کاملاً محلی/آفلاین با @fontsource/vazirmatn به‌عنوان یک
// وابستگی معمولی npm نصب و در زمان Build (نه در زمان اجرا) دانلود می‌شود؛
// خروجی نهایی (frontend/dist) کاملاً خودکفاست، بدون هیچ درخواست به بیرون.
// ⚠️ وزن ۸۰۰ (Extra-Bold) هم لازم است — چند جای پروژه (مثلاً عنوان صفحه
// ورود) صریحاً fontWeight={800} استفاده می‌کنند؛ بدون این فایل، مرورگر
// یا از یک Bold ساختگی (Synthetic Bold با کیفیت پایین‌تر) استفاده می‌کرد،
// یا (بدتر) دوباره وسوسه می‌شد از یک CDN بیرونی این وزن را بگیرد.
import "@fontsource/vazirmatn/400.css";
import "@fontsource/vazirmatn/500.css";
import "@fontsource/vazirmatn/600.css";
import "@fontsource/vazirmatn/700.css";
import "@fontsource/vazirmatn/800.css";
import { rtlCache } from "./rtlCache";
import { ThemeModeProvider } from "./context/ThemeModeContext";
import { AuthProvider } from "./context/AuthContext";
import { OnlineStatusProvider } from "./context/OnlineStatusContext";
import { registerServiceWorker } from "./utils/serviceWorker";
import "./utils/pwaInstall"; // ثبت زودهنگام listener رویداد beforeinstallprompt
import UpdatePrompt from "./components/UpdatePrompt";
import MandatoryPasswordChangeGuard from "./components/MandatoryPasswordChangeGuard";
import OfflineBanner from "./components/OfflineBanner";
import App from "./App";

registerServiceWorker();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <CacheProvider value={rtlCache}>
      <ThemeModeProvider>
        {/* بیرون از BrowserRouter/AuthProvider — چون AuthContext هم به همین
            وضعیت اتصال نیاز دارد (برای تلاش خودکار دوباره وقتی اینترنت
            برمی‌گردد)، و این یک نگرانی کاملاً سراسری/مستقل از مسیر است. */}
        <OnlineStatusProvider>
          <BrowserRouter>
            <AuthProvider>
              <App />
              {/* در سطح ریشه (نه داخل Layout) تا حتی توی صفحه ورود هم دیده شود */}
              <UpdatePrompt />
              <MandatoryPasswordChangeGuard />
              <OfflineBanner />
            </AuthProvider>
          </BrowserRouter>
        </OnlineStatusProvider>
      </ThemeModeProvider>
    </CacheProvider>
  </React.StrictMode>
);
