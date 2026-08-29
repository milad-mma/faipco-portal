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
 * ⚠️ لوگو/نام از BrandingContext می‌آید — قابل‌تغییر از پنل «تنظیمات
 * سامانه». مقدار پیش‌فرض همان Context (`/faipco-logo.png` + نام پیش‌فرض)
 * دقیقاً همان چیزی است که تا قبل از برگشتن پاسخ Backend نمایش داده
 * می‌شود، پس هیچ تأخیر/چشمک‌زدن اضافه‌ای نسبت به قبل ایجاد نمی‌شود.
 */
export default function SplashScreen({ visible }) {
  const { appLogoUrl, splashTitle, splashSubtitle } = useBranding();
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
    </Box>
  );
}
