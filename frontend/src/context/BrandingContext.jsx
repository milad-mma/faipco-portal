import { createContext, useContext, useEffect, useState } from "react";
import { APP_LOGO_URL, FAVICON_URL, fetchBranding } from "../api/system";

const BrandingContext = createContext(null);

// مقادیر پیش‌فرض — دقیقاً همان چیزی که قبلاً همه‌جای پروژه Hard-code بود؛
// همین‌ها تا قبل از رسیدن پاسخ Backend (و هروقت لوگوی سفارشی تنظیم نشده
// باشد) نمایش داده می‌شوند — یعنی هیچ صفحه‌ای هرگز خالی/بی‌نام/بی‌لوگو
// دیده نمی‌شود.
const DEFAULT_BRANDING = {
  browserTitle: "پرتال سازمانی پرسنل فایپکو",
  manifestShortName: "فایپکو",
  manifestDescription: "پرتال سازمانی مدیریت پرسنل و اطلاع‌رسانی",
  splashTitle: "شرکت تولیدی صنعتی فواد الیاف",
  splashSubtitle: "سامانه مدیریت پرسنل",
  loginTitle: "سامانه مدیریت پرسنل فایپکو",
  loginSubtitle: "شرکت تولیدی صنعتی فواد الیاف",
  appLogoUrl: "/faipco-logo.png",
};

/**
 * برندینگ سراسری قابل‌تغییر از پنل («تنظیمات سامانه» → نام‌ها/لوگوها) —
 * قابلیت‌های عمومی، مستقل از احراز هویت (اسپلش‌اسکرین و صفحه ورود هم به
 * این نیاز دارند)، پس این Provider بیرون از AuthProvider نصب می‌شود.
 *
 * ⚠️ appLogoUrl همیشه به Endpoint پویای Backend اشاره می‌کند (نه مستقیم به
 * فایل پیش‌فرض) — اگر Admin هنوز لوگویی آپلود نکرده باشد، آن Endpoint
 * ۴۰۴ می‌دهد و کامپوننت‌های مصرف‌کننده (که همگی یک onError دارند) به‌طور
 * خودکار به همان فایل پیش‌فرض ثابت (`/faipco-logo.png`) برمی‌گردند.
 *
 * ⚠️ آیکون Manifest (PWA، برای صفحه اصلی گوشی) و Favicon (تب مرورگر) در
 * این Context نیستند — چون مصرف‌شان مستقیماً HTML استاتیک (Manifest از
 * طریق Backend، Favicon از طریق <link> در index.html) است، نه یک
 * Component React؛ فقط همین‌جا (پایین) به‌صورت مستقیم DOM را به‌روز
 * می‌کنیم.
 */
export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState(DEFAULT_BRANDING);

  useEffect(() => {
    fetchBranding()
      .then((data) => {
        setBranding({
          browserTitle: data.browser_title,
          manifestShortName: data.manifest_short_name,
          manifestDescription: data.manifest_description,
          splashTitle: data.splash_title,
          splashSubtitle: data.splash_subtitle,
          loginTitle: data.login_title,
          loginSubtitle: data.login_subtitle,
          appLogoUrl: data.has_custom_app_logo ? APP_LOGO_URL : DEFAULT_BRANDING.appLogoUrl,
        });

        document.title = data.browser_title;

        // ⚠️ iOS/Safari برای برچسب آیکون «افزودن به صفحه اصلی» بیشتر به
        // همین Meta Tag خاص تکیه می‌کند تا short_name داخل Manifest.
        const appleTitleMeta = document.querySelector('meta[name="apple-mobile-web-app-title"]');
        if (appleTitleMeta) appleTitleMeta.setAttribute("content", data.manifest_short_name);

        // Favicon (تب مرورگر) — اگر سفارشی تنظیم شده، همان چهار <link>
        // آیکونِ موجود در index.html را همین‌جا با JS به آدرس Backend
        // عوض می‌کنیم؛ اگر نشده، دست‌نخورده (فایل‌های ثابت پیش‌فرض) می‌مانند.
        if (data.has_custom_favicon) {
          document.querySelectorAll('link[rel="icon"], link[rel="apple-touch-icon"]').forEach((link) => {
            link.setAttribute("href", FAVICON_URL);
          });
        }
      })
      .catch(() => {
        // اگر Backend در دسترس نبود (مثلاً همان لحظه اول بارگذاری آفلاین)،
        // همان مقادیر پیش‌فرض کاملاً کافی‌اند — نیازی به نمایش خطا نیست.
      });
  }, []);

  return <BrandingContext.Provider value={branding}>{children}</BrandingContext.Provider>;
}

export function useBranding() {
  return useContext(BrandingContext) || DEFAULT_BRANDING;
}
