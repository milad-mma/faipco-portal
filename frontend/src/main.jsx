import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { CacheProvider } from "@emotion/react";
// فونت وزیرمتن — قبلاً از cdn.jsdelivr.net لود می‌شد (یعنی این پروژه بدون
// اینترنت اصلاً لود نمی‌شد). حالا با @fontsource/vazirmatn به‌عنوان یک
// وابستگی معمولی npm نصب و در زمان Build (نه در زمان اجرا) دانلود می‌شود؛
// خروجی نهایی (frontend/dist) کاملاً خودکفاست، بدون هیچ درخواست به بیرون.
import "@fontsource/vazirmatn/400.css";
import "@fontsource/vazirmatn/500.css";
import "@fontsource/vazirmatn/600.css";
import "@fontsource/vazirmatn/700.css";
import { rtlCache } from "./rtlCache";
import { ThemeModeProvider } from "./context/ThemeModeContext";
import { AuthProvider } from "./context/AuthContext";
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
        <BrowserRouter>
          <AuthProvider>
            <App />
            {/* در سطح ریشه (نه داخل Layout) تا حتی توی صفحه ورود هم دیده شود */}
            <UpdatePrompt />
            <MandatoryPasswordChangeGuard />
            <OfflineBanner />
          </AuthProvider>
        </BrowserRouter>
      </ThemeModeProvider>
    </CacheProvider>
  </React.StrictMode>
);
