import { Box } from "@mui/material";
import { useBranding } from "../context/BrandingContext";

/**
 * لوگوی یک «جای نمایش» (surface) طبق تنظیمات برندینگ همان جا:
 * منبع لوگو (پیش‌فرض/اختصاصی/هیچ)، اندازه‌ی موبایل و دسکتاپ، مقیاس و قاب.
 * ورودی: surface (کلید جای نمایش)، alt، override (مقادیر ذخیره‌نشده برای پیش‌نمایش زنده)،
 * previewLogoUrl (آدرس موقت لوگوی انتخاب‌شده برای پیش‌نمایش) و sx (استایل اضافه روی کادر بیرونی).
 * خروجی: تصویر لوگو (با یا بدون قاب)، یا null اگر منبع لوگو «هیچ» باشد.
 * مقیاس (logo_scale) فقط خود تصویر را داخل کادرش بزرگ/کوچک می‌کند و چیدمان صفحه را تغییر نمی‌دهد.
 * این فایل توابع کمکی surfaceTitleSx و desktopPanelBackground را هم export می‌کند.
 */
export default function BrandLogo({ surface, alt = "", override, previewLogoUrl, sx }) {
  const branding = useBranding();
  const cfg = { ...(branding.surfaces?.[surface] || {}), ...(override || {}) }; // تنظیمات ذخیره‌شده + مقادیر پیش‌نمایش
  if (cfg.logo_source === "none") return null;

  // انتخاب آدرس تصویر: پیش‌نمایش ← لوگوی اختصاصی این جای نمایش ← لوگوی پیش‌فرض (کوچک یا اصلی)
  let src = previewLogoUrl;
  if (!src) {
    if (cfg.logo_source === "custom" && branding.surfaceLogoUrls?.[surface]) {
      src = branding.surfaceLogoUrls[surface];
    } else {
      src = cfg.default_logo === "app_logo_small" ? branding.appLogoSmallUrl : branding.appLogoUrl;
    }
  }

  const size = { xs: cfg.logo_size_mobile, md: cfg.logo_size_desktop };
  const scale = (cfg.logo_scale || 100) / 100; // درصد مقیاس به ضریب
  // تصویر لوگو؛ در صورت خطای بارگذاری یک‌بار به لوگوی پیش‌فرض /faipco-logo.png برمی‌گردد
  const img = (
    <Box
      component="img"
      src={src}
      alt={alt}
      onError={(e) => {
        e.currentTarget.onerror = null;
        e.currentTarget.src = "/faipco-logo.png";
      }}
      sx={{
        width: size,
        height: size,
        objectFit: "contain",
        display: "block",
        flexShrink: 0,
        transform: scale !== 1 ? `scale(${scale})` : undefined,
        transformOrigin: "center",
      }}
    />
  );

  // بدون قاب: فقط کادر ساده دور تصویر
  if (cfg.frame === "none") return <Box sx={{ flexShrink: 0, ...sx }}>{img}</Box>;

  const pad = cfg.frame_padding || 0; // فاصله‌ی داخلی قاب که به اندازه‌ی لوگو اضافه می‌شود
  // قاب دایره یا مربع گردگوشه با رنگ پس‌زمینه‌ی قابل‌تنظیم
  return (
    <Box
      sx={{
        width: { xs: cfg.logo_size_mobile + pad, md: cfg.logo_size_desktop + pad },
        height: { xs: cfg.logo_size_mobile + pad, md: cfg.logo_size_desktop + pad },
        borderRadius: cfg.frame === "circle" ? "50%" : 3,
        bgcolor: cfg.frame_color || "#FFFFFF",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        overflow: "hidden",
        ...sx,
      }}
    >
      {img}
    </Box>
  );
}

/** استایل متن عنوان/زیرعنوان یک جای نمایش (اندازه به تفکیک موبایل/دسکتاپ + رنگ + وزن) */
export function surfaceTitleSx(cfg, kind = "title") {
  const sizeM = cfg[`${kind}_size_mobile`];
  const sizeD = cfg[`${kind}_size_desktop`];
  const color = cfg[`${kind}_color`];
  return {
    fontSize: { xs: sizeM, md: sizeD },
    ...(color ? { color } : {}),
    ...(kind === "title" ? { fontWeight: cfg.title_weight || 700 } : {}),
  };
}

/** پس‌زمینه‌ی پنل کناری دسکتاپ ورود؛ رنگ ساده هم به شکل gradient برگردانده می‌شود تا در کنار لایه‌ی بافت نقطه‌ای (چند لایه background) معتبر باشد */
export function desktopPanelBackground(background) {
  const value = background || "linear-gradient(145deg,#3476ad 0%,#2b91a5 100%)";
  return value.includes("gradient") ? value : `linear-gradient(${value}, ${value})`;
}
