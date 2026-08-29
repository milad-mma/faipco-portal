import { Box, Typography } from "@mui/material";
import { useBranding } from "../context/BrandingContext";

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
  const { appLogoUrl, splashTitle, splashSubtitle, isLoading } = useBranding();
  return (
    <Box
      sx={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        backgroundColor: "#FFFFFF",
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
          <Box
            component="img"
            src={appLogoUrl}
            alt={splashTitle}
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = "/faipco-logo.png";
            }}
            sx={{ width: { xs: 120, sm: 150 }, height: { xs: 120, sm: 150 }, objectFit: "contain" }}
          />
          <Box sx={{ textAlign: "center" }}>
            <Typography
              variant="subtitle1"
              fontWeight={700}
              sx={{ fontFamily: "Tahoma, sans-serif", color: "#000000" }}
            >
              {splashTitle}
            </Typography>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mt: 0.5, fontFamily: "Tahoma, sans-serif" }}
            >
              {splashSubtitle}
            </Typography>
          </Box>
        </>
      )}
    </Box>
  );
}
