import { Box, Typography } from "@mui/material";
import { useBranding } from "../context/BrandingContext";
import BrandLogo, { surfaceTitleSx } from "./BrandLogo";

/**
 * اسپلش‌اسکرین برند — پس‌زمینه سفید، لوگو وسط، و نام شرکت زیرش. تا وقتی اپ
 * واقعاً آماده است (نه یک تایمر ثابت دلخواه) روی صفحه اصلی برنامه
 * (App.jsx) نمایش داده می‌شود و بعد با یک Fade کوتاه محو می‌شود.
 *
 * نکته عمدی برای جلوگیری از «دیر ظاهرشدن لوگو/فونت»:
 *   - متن زیر لوگو عمداً از فونت سیستم استفاده می‌کند (نه فونت وزیرمتن
 *     سفارشی که باید دانلود شود) — چون این متن فقط چند ثانیه دیده می‌شود،
 *     نمایش فوری با فونت سیستم بهتر از یک تعویض فونت محسوس وسط اسپلش است.
 *
 * ⚠️ طبق درخواست صریح: تا وقتی برندینگ واقعی از سرور نرسیده (isLoading)،
 * این کامپوننت عمداً هیچ لوگو/متنی نشان نمی‌دهد (فقط پس‌زمینه سفید خالی)
 * — نه مقدار پیش‌فرض. این‌طور هرگز «اول لوگو/متن پیش‌فرض دیده شود، بعد
 * با مقدار واقعی جایگزین شود» اتفاق نمی‌افتد. App.jsx هم اسپلش را تا
 * وقتی همین isLoading تمام نشود کنار نمی‌زند، پس در عمل این حالت خالی
 * فقط یک لحظه کوتاه (مدت خودِ درخواست شبکه) دیده می‌شود.
 */
export default function SplashScreen({ visible }) {
  const { splashTitle, splashSubtitle, isLoading, surfaces } = useBranding();
  const cfg = surfaces.splash;
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
