import { Box, Typography } from "@mui/material";

/**
 * اسپلش‌اسکرین برند — پس‌زمینه سفید، لوگو وسط، و نام شرکت زیرش. تا وقتی اپ
 * واقعاً آماده است (نه یک تایمر ثابت دلخواه) روی صفحه اصلی برنامه
 * (App.jsx) نمایش داده می‌شود و بعد با یک Fade کوتاه محو می‌شود.
 *
 * دو نکته عمدی برای جلوگیری از «دیر ظاهرشدن لوگو/فونت»:
 *   - لوگو یک مسیر ثابت (public/faipco-logo.png) است، نه یک Import داخل
 *     JS — همراه با یک <link rel="preload"> در index.html، دانلودش همان
 *     لحظه شروع Parse شدن HTML آغاز می‌شود، نه بعد از کامل‌شدن باندل JS.
 *   - متن زیر لوگو عمداً از فونت سیستم استفاده می‌کند (نه فونت وزیرمتن
 *     سفارشی که باید دانلود شود) — چون این متن فقط چند ثانیه دیده می‌شود،
 *     نمایش فوری با فونت سیستم بهتر از یک تعویض فونت محسوس وسط اسپلش است.
 */
export default function SplashScreen({ visible }) {
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
        src="/faipco-logo.png"
        alt="FAIPCO"
        sx={{ width: { xs: 120, sm: 150 }, height: { xs: 120, sm: 150 }, objectFit: "contain" }}
      />
      <Box sx={{ textAlign: "center" }}>
        <Typography
          variant="subtitle1"
          fontWeight={700}
          sx={{ fontFamily: "Tahoma, sans-serif", color: "#000000" }}
        >
          شرکت تولیدی صنعتی فواد الیاف
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 0.5, fontFamily: "Tahoma, sans-serif" }}
        >
          سامانه مدیریت پرسنل
        </Typography>
      </Box>
    </Box>
  );
}
