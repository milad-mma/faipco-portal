import { Box } from "@mui/material";
import { useBranding } from "../context/BrandingContext";

/**
 * لوگوی یک «جای نمایش» طبق تنظیمات همان جا (تنظیمات سامانه ← برندینگ):
 * منبع لوگو (پیش‌فرض/اختصاصی/هیچ)، اندازه موبایل و دسکتاپ، مقیاس، و قاب.
 *
 * مقیاس (logo_scale) فقط خودِ تصویر را داخل کادرش بزرگ/کوچک می‌کند و چیدمان
 * صفحه را به هم نمی‌زند (برای لوگوهایی با حاشیه سفید زیاد یا خیلی فشرده).
 *
 * override: برای پیش‌نمایش زنده در صفحه تنظیمات (مقادیر ذخیره‌نشده).
 */
export default function BrandLogo({ surface, alt = "", override, previewLogoUrl, sx }) {
  const branding = useBranding();
  const cfg = { ...(branding.surfaces?.[surface] || {}), ...(override || {}) };
  if (cfg.logo_source === "none") return null;

  let src = previewLogoUrl;
  if (!src) {
    if (cfg.logo_source === "custom" && branding.surfaceLogoUrls?.[surface]) {
      src = branding.surfaceLogoUrls[surface];
    } else {
      src = cfg.default_logo === "app_logo_small" ? branding.appLogoSmallUrl : branding.appLogoUrl;
    }
  }

  const size = { xs: cfg.logo_size_mobile, md: cfg.logo_size_desktop };
  const scale = (cfg.logo_scale || 100) / 100;
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

  if (cfg.frame === "none") return <Box sx={{ flexShrink: 0, ...sx }}>{img}</Box>;

  const pad = cfg.frame_padding || 0;
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

/** پس‌زمینه پنل کناری دسکتاپ ورود: یک رنگ ساده هم به‌شکل gradient تا کنار بافت نقطه‌ای بنشیند */
export function desktopPanelBackground(background) {
  const value = background || "linear-gradient(145deg,#3476ad 0%,#2b91a5 100%)";
  return value.includes("gradient") ? value : `linear-gradient(${value}, ${value})`;
}
