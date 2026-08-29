import { createContext, useContext, useEffect, useState } from "react";
import { APP_LOGO_SMALL_URL, APP_LOGO_URL, FAVICON_URL, fetchBranding } from "../api/system";

const BrandingContext = createContext(null);

// مقادیر پیش‌فرض — فقط برای زمانی که Backend اصلاً در دسترس نباشد (مثلاً
// بارگذاری اولیه در حالت آفلاین) استفاده می‌شوند؛ در حالت عادی، تا وقتی
// مقادیر واقعی از سرور نرسیده باشند، isLoading=true است و هیچ‌جای پروژه
// نباید بر اساس این پیش‌فرض‌ها چیزی رندر کند — دقیقاً برای جلوگیری از
// «اول متن پیش‌فرض دیده شود، بعد با متن واقعی جایگزین شود».
const DEFAULT_BRANDING = {
  browserTitle: "پرتال سازمانی پرسنل فایپکو",
  manifestShortName: "فایپکو",
  splashTitle: "شرکت تولیدی صنعتی فواد الیاف",
  splashSubtitle: "سامانه مدیریت پرسنل",
  loginTitle: "سامانه مدیریت پرسنل فایپکو",
  loginSubtitle: "شرکت تولیدی صنعتی فواد الیاف",
  sidebarTitle: "فایپکو",
  profileTitle: "شرکت تولیدی صنعتی فواد الیاف",
  profileSubtitle: "سامانه مدیریت پرسنل فایپکو",
  appLogoUrl: "/faipco-logo.png",
  appLogoSmallUrl: "/faipco-logo.png",
};

/**
 * برندینگ سراسری قابل‌تغییر از پنل («تنظیمات سامانه» → نام‌ها/لوگوها) —
 * قابلیت‌های عمومی، مستقل از احراز هویت (اسپلش‌اسکرین و صفحه ورود هم به
 * این نیاز دارند)، پس این Provider بیرون از AuthProvider نصب می‌شود.
 *
 * ⚠️ طبق درخواست صریح: قبلاً این Provider بلافاصله مقادیر پیش‌فرض
 * Hard-code شده را نشان می‌داد و بعد از رسیدن پاسخ Backend، آن‌ها را با
 * مقادیر واقعی *جایگزین* می‌کرد — یعنی کاربر یک لحظه متن/عنوان اشتباه
 * (پیش‌فرض) می‌دید و بعد می‌دید عوض شد. این رفتار عمداً حذف شد: حالا
 * isLoading هم در اختیار مصرف‌کننده‌ها قرار می‌گیرد؛ App.jsx تا وقتی این
 * isLoading هم تمام نشود، اسپلش‌اسکرین را کنار نمی‌زند — یعنی وقتی صفحه
 * ورود/داشبورد/اسپلش واقعاً روی صفحه دیده می‌شوند، مقادیر برندینگ از
 * قبل واقعی و نهایی‌اند، نه پیش‌فرض در حال جایگزینی.
 */
export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState(DEFAULT_BRANDING);
  const [isLoading, setIsLoading] = useState(true);

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
          sidebarTitle: data.sidebar_title,
          profileTitle: data.profile_title,
          profileSubtitle: data.profile_subtitle,
          appLogoUrl: data.has_custom_app_logo ? APP_LOGO_URL : DEFAULT_BRANDING.appLogoUrl,
          // ⚠️ اگر لوگوی کوچک اختصاصی تنظیم نشده باشد، از همان لوگوی
          // بزرگ (نه فایل پیش‌فرض جدا) استفاده می‌شود — چون یک لوگوی
          // سفارشی بزرگ که هنوز نسخه کوچک ندارد، باز هم بهتر از فایل
          // پیش‌فرض کلی است.
          appLogoSmallUrl: data.has_custom_app_logo_small
            ? APP_LOGO_SMALL_URL
            : data.has_custom_app_logo
              ? APP_LOGO_URL
              : DEFAULT_BRANDING.appLogoSmallUrl,
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
        // Backend در دسترس نبود (مثلاً بارگذاری اولیه آفلاین) — همان
        // مقادیر پیش‌فرض از ابتدا در state هست؛ فقط isLoading را می‌بندیم
        // تا اپ گیر نکند (بهتر از نمایش پیش‌فرض، نمایش هیچ‌چیز تا ابد است).
      })
      .finally(() => setIsLoading(false));
  }, []);

  return <BrandingContext.Provider value={{ ...branding, isLoading }}>{children}</BrandingContext.Provider>;
}

export function useBranding() {
  return useContext(BrandingContext) || { ...DEFAULT_BRANDING, isLoading: true };
}
