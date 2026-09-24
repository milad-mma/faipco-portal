import { Box, Typography } from "@mui/material";
import { useBranding } from "../context/BrandingContext";
import BrandLogo, { surfaceTitleSx } from "./BrandLogo";

/**
 * اسپلش‌اسکرین برند: پس‌زمینه (پیش‌فرض سفید)، لوگو در وسط و عنوان/زیرعنوان زیر آن.
 * ورودی: visible؛ App.jsx آن را تا آماده شدن واقعی برنامه نمایش می‌دهد و با false شدن، با Fade محو می‌شود.
 * متن زیر لوگو از فونت سیستم (Tahoma) استفاده می‌کند تا بدون انتظار برای دانلود فونت سفارشی فوراً نمایش داده شود.
 * تا وقتی برندینگ از سرور نرسیده (isLoading)، هیچ لوگو/متنی نشان داده نمی‌شود (فقط پس‌زمینه)
 * تا مقدار پیش‌فرض قبل از مقدار واقعی دیده نشود.
 */
export default function SplashScreen({ visible }) {
  const { splashTitle, splashSubtitle, isLoading, surfaces } = useBranding();
  const cfg = surfaces.splash;  // تنظیمات ظاهری سطح splash از برندینگ
  return (
    <Box
      sx={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: cfg.background || "#FFFFFF",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 2.5,
        opacity: visible ? 1 : 0,
        pointerEvents: visible ? "auto" : "none",
        transition: "opacity 0.4s ease",
      }}
    >
      {/* لوگو و عنوان‌ها فقط پس از رسیدن برندینگ از سرور */}
      {!isLoading && (
        <>
          <BrandLogo surface="splash" alt={splashTitle} />
          <Box sx={{ textAlign: "center" }}>
            {cfg.show_title && (
              <Typography sx={{ fontFamily: "Tahoma, sans-serif", ...surfaceTitleSx(cfg, "title") }}>
                {splashTitle}
              </Typography>
            )}
            {cfg.show_subtitle && (
              <Typography sx={{ mt: 0.5, fontFamily: "Tahoma, sans-serif", ...surfaceTitleSx(cfg, "subtitle") }}>
                {splashSubtitle}
              </Typography>
            )}
          </Box>
        </>
      )}
    </Box>
  );
}
