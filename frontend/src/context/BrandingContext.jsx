/**
 * کانتکست برندینگ سراسری (نام‌ها، عنوان‌ها، لوگوها و تنظیمات ظاهری هر جای نمایش).
 * تنظیمات را از سرور می‌خواند، عنوان تب، عنوان اپ در iOS و آیکون‌های favicon/apple-touch-icon را
 * به‌روز می‌کند و isLoading را برای نگه داشتن اسپلش تا رسیدن مقادیر واقعی فراهم می‌کند.
 */
import { createContext, useContext, useEffect, useState } from "react";
import {
  APP_LOGO_SMALL_URL,
  APP_LOGO_URL,
  FAVICON_URL,
  PWA_ICON_VARIANT_URL,
  SURFACE_LOGO_URL,
  fetchBranding,
} from "../api/system";
import { SURFACE_DEFAULTS } from "../config/brandingSurfaces";

const BrandingContext = createContext(null);

// مقادیر پیش‌فرض برندینگ؛ فقط وقتی Backend در دسترس نباشد (مثلاً بارگذاری اولیه‌ی آفلاین) استفاده می‌شوند.
// تا رسیدن مقادیر واقعی isLoading=true است و نباید بر اساس این پیش‌فرض‌ها چیزی رندر شود.
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
  authTitle: "",
  authSubtitle: "",
  // تنظیمات به تفکیک جای نمایش (لوگو/اندازه/مقیاس/قاب/فونت/رنگ)؛ سرور نسخه‌ی ادغام‌شده با پیش‌فرض‌ها را برمی‌گرداند
  surfaces: SURFACE_DEFAULTS,
  // آدرس لوگوی اختصاصی هر جای نمایش (فقط اگر آپلود شده باشد)
  surfaceLogoUrls: {},
};

/**
 * Provider برندینگ سراسری (قابل تغییر از «تنظیمات سامانه»)؛ ورودی: children.
 * مستقل از احراز هویت است (اسپلش و صفحه‌ی ورود هم به آن نیاز دارند) و بیرون از AuthProvider نصب می‌شود.
 * خروجی کانتکست: مقادیر برندینگ به همراه isLoading؛ App.jsx تا پایان isLoading اسپلش را نگه می‌دارد.
 */
export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState(DEFAULT_BRANDING);
  const [isLoading, setIsLoading] = useState(true);

  // یک‌بار هنگام mount: خواندن برندینگ از سرور، تبدیل به state و اعمال روی عنوان سند و آیکون‌ها
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
          authTitle: data.auth_title || "",
          authSubtitle: data.auth_subtitle || "",
          surfaces: { ...SURFACE_DEFAULTS, ...(data.surfaces || {}) }, // ادغام تنظیمات سرور روی پیش‌فرض‌ها
          // آدرس لوگوی اختصاصی فقط برای جای‌های نمایشی که لوگوی سفارشی آپلود شده دارند
          surfaceLogoUrls: Object.fromEntries(
            Object.keys(SURFACE_DEFAULTS)
              .filter((name) => data[`has_custom_surface_${name}`])
              .map((name) => [name, SURFACE_LOGO_URL(name)])
          ),
          appLogoUrl: data.has_custom_app_logo ? APP_LOGO_URL : DEFAULT_BRANDING.appLogoUrl,
          // لوگوی کوچک: نسخه‌ی کوچک سفارشی، در نبود آن لوگوی بزرگ سفارشی، و در غیر این صورت فایل پیش‌فرض
          appLogoSmallUrl: data.has_custom_app_logo_small
            ? APP_LOGO_SMALL_URL
            : data.has_custom_app_logo
              ? APP_LOGO_URL
              : DEFAULT_BRANDING.appLogoSmallUrl,
        });

        document.title = data.browser_title;

        // iOS/Safari برای برچسب آیکون «افزودن به صفحه اصلی» از این Meta Tag استفاده می‌کند، نه short_name در Manifest
        const appleTitleMeta = document.querySelector('meta[name="apple-mobile-web-app-title"]');
        if (appleTitleMeta) appleTitleMeta.setAttribute("content", data.manifest_short_name);

        // Favicon تب مرورگر: اگر favicon سفارشی یا آیکون PWA سفارشی وجود دارد، href تگ‌های <link rel="icon">
        // موجود در index.html به آدرس Backend تغییر می‌کند؛ در غیر این صورت فایل‌های ثابت پیش‌فرض می‌مانند.
        // برای apple-touch-icon نسخه‌ی تولیدشده‌ی apple-180 (پس‌زمینه‌ی پر، لوگو در ناحیه‌ی امن) استفاده می‌شود
        // چون iOS شفافیت را سیاه و گوشه‌ها را گرد می‌کند.
        if (data.has_custom_favicon) {
          document.querySelectorAll('link[rel="icon"]').forEach((link) => link.setAttribute("href", FAVICON_URL));
        } else if (data.has_custom_pwa_icon) {
          document.querySelectorAll('link[rel="icon"]').forEach((link) => {
            const sizes = link.getAttribute("sizes") || "";
            link.setAttribute("href", PWA_ICON_VARIANT_URL(sizes.startsWith("16") ? "favicon-16" : "favicon-32"));
          });
        }
        if (data.has_custom_pwa_icon) {
          document
            .querySelectorAll('link[rel="apple-touch-icon"]')
            .forEach((link) => link.setAttribute("href", PWA_ICON_VARIANT_URL("apple-180")));
        }
      })
      .catch(() => {
        // Backend در دسترس نیست (مثلاً بارگذاری آفلاین): مقادیر پیش‌فرض در state می‌مانند
        // و isLoading در finally بسته می‌شود تا برنامه در اسپلش گیر نکند
      })
      .finally(() => setIsLoading(false));
  }, []);

  return <BrandingContext.Provider value={{ ...branding, isLoading }}>{children}</BrandingContext.Provider>;
}

// هوک دسترسی به برندینگ؛ بیرون از Provider مقادیر پیش‌فرض با isLoading=true برمی‌گرداند
export function useBranding() {
  return useContext(BrandingContext) || { ...DEFAULT_BRANDING, isLoading: true };
}
