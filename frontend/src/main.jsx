/**
 * نقطه‌ی ورود برنامه: ثبت Service Worker، بارگذاری فونت‌های محلی وزیرمتن
 * و رندر درخت Providerها (کش RTL، تم، وضعیت اتصال، برندینگ، مسیریاب، احراز هویت) به همراه App.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { CacheProvider } from "@emotion/react";
// فونت وزیرمتن به صورت محلی از پکیج @fontsource/vazirmatn؛ فایل‌ها در زمان Build در خروجی قرار می‌گیرند
// و برنامه به هیچ منبع بیرونی درخواست نمی‌دهد.
// وزن ۸۰۰ برای جاهایی که fontWeight={800} دارند (مثل عنوان صفحه‌ی ورود) لازم است تا مرورگر Bold ساختگی نسازد.
import "@fontsource/vazirmatn/400.css";
import "@fontsource/vazirmatn/500.css";
import "@fontsource/vazirmatn/600.css";
import "@fontsource/vazirmatn/700.css";
import "@fontsource/vazirmatn/800.css";
import { rtlCache } from "./rtlCache";
import { ThemeModeProvider } from "./context/ThemeModeContext";
import { AuthProvider } from "./context/AuthContext";
import { OnlineStatusProvider } from "./context/OnlineStatusContext";
import { BrandingProvider } from "./context/BrandingContext";
import { registerServiceWorker } from "./utils/serviceWorker";
import "./utils/pwaInstall"; // ثبت زودهنگام listener رویداد beforeinstallprompt
import UpdatePrompt from "./components/UpdatePrompt";
import MandatoryPasswordChangeGuard from "./components/MandatoryPasswordChangeGuard";
import OfflineBanner from "./components/OfflineBanner";
import App from "./App";

registerServiceWorker(); // ثبت Service Worker برای Precache و Push

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <CacheProvider value={rtlCache}>
      <ThemeModeProvider>
        {/* وضعیت اتصال بیرون از BrowserRouter/AuthProvider است چون AuthContext برای تلاش دوباره پس از وصل شدن اینترنت به آن نیاز دارد */}
        <OnlineStatusProvider>
          <BrandingProvider>
            <BrowserRouter>
              <AuthProvider>
                <App />
                {/* اعلان نسخه‌ی جدید، الزام تغییر رمز و بنر آفلاین در سطح ریشه (نه داخل Layout) تا در صفحه‌ی ورود هم دیده شوند */}
                <UpdatePrompt />
                <MandatoryPasswordChangeGuard />
                <OfflineBanner />
              </AuthProvider>
            </BrowserRouter>
          </BrandingProvider>
        </OnlineStatusProvider>
      </ThemeModeProvider>
    </CacheProvider>
  </React.StrictMode>
);
