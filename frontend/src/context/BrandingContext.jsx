import { createContext, useContext, useEffect, useState } from "react";
import { APP_LOGO_URL, fetchBranding } from "../api/system";

const BrandingContext = createContext(null);

// مقادیر پیش‌فرض — دقیقاً همان چیزی که قبلاً همه‌جای پروژه Hard-code بود؛
// همین‌ها تا قبل از رسیدن پاسخ Backend (و هروقت لوگوی سفارشی تنظیم نشده
// باشد) نمایش داده می‌شوند — یعنی هیچ صفحه‌ای هرگز خالی/بی‌نام/بی‌لوگو
// دیده نمی‌شود.
const DEFAULT_BRANDING = {
  name: "پرتال سازمانی پرسنل فایپکو",
  shortName: "فایپکو",
  description: "پرتال سازمانی مدیریت پرسنل و اطلاع‌رسانی",
  logoUrl: "/faipco-logo.png",
};

/**
 * برندینگ سراسری قابل‌تغییر از پنل («تنظیمات سامانه» → لوگو/نام اپ) —
 * قابلیت‌های عمومی، مستقل از احراز هویت (اسپلش‌اسکرین و صفحه ورود هم به
 * این نیاز دارند)، پس این Provider بیرون از AuthProvider نصب می‌شود.
 *
 * ⚠️ logoUrl همیشه به Endpoint پویای Backend اشاره می‌کند (نه مستقیم به
 * فایل پیش‌فرض) — اگر Admin هنوز لوگویی آپلود نکرده باشد، آن Endpoint
 * ۴۰۴ می‌دهد و کامپوننت‌های مصرف‌کننده (که همگی یک onError دارند) به‌طور
 * خودکار به همان فایل پیش‌فرض ثابت (`/faipco-logo.png`) برمی‌گردند.
 */
export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState(DEFAULT_BRANDING);

  useEffect(() => {
    fetchBranding()
      .then((data) => {
        setBranding({
          name: data.name,
          shortName: data.short_name,
          description: data.description,
          logoUrl: data.has_custom_logo ? APP_LOGO_URL : DEFAULT_BRANDING.logoUrl,
        });
        document.title = data.name;
        // ⚠️ iOS/Safari برای برچسب آیکون «افزودن به صفحه اصلی» بیشتر به
        // همین Meta Tag خاص تکیه می‌کند تا short_name داخل Manifest — پس
        // این هم باید همین‌جا (نه فقط در Manifest پویای Backend) به‌روز
        // شود، وگرنه نصب‌های iOS همیشه اسم پیش‌فرض قدیمی را نشان می‌دادند.
        const appleTitleMeta = document.querySelector('meta[name="apple-mobile-web-app-title"]');
        if (appleTitleMeta) appleTitleMeta.setAttribute("content", data.short_name);
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
