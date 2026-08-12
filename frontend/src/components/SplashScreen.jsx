import { Box, Typography } from "@mui/material";
import faipcoLogo from "../assets/faipco-logo.png";

/**
 * اسپلش‌اسکرین برند — پس‌زمینه سفید، لوگو وسط، و نام شرکت زیرش. حدود ۲ ثانیه
 * روی صفحه اصلی برنامه (App.jsx) نمایش داده می‌شود و بعد با یک Fade کوتاه
 * محو می‌شود. هم در حالت نصب‌شده (PWA/Standalone) و هم در مرورگر عادی دیده
 * می‌شود، تا اولین تجربه‌ی باز کردن اپ همیشه یکدست و برندشده باشد.
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
        src={faipcoLogo}
        alt="FAIPCO"
        sx={{ width: { xs: 120, sm: 150 }, height: { xs: 120, sm: 150 }, objectFit: "contain" }}
      />
      <Box sx={{ textAlign: "center" }}>
        <Typography variant="subtitle1" fontWeight={700} color="#16324F">
          شرکت تولیدی صنعتی فواد الیاف
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          FAIPCO Portal
        </Typography>
      </Box>
    </Box>
  );
}
