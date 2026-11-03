// فوتر «طراحی و توسعه» با گرادیان کارت مشخصات پرسنل داشبورد و متن سفید — فقط در «پنل کاربری» (/profile) و نمای ادمین.
import { Box } from "@mui/material";

export default function CreditFooter({ sx }) {
  return (
    <Box
      component="footer"
      sx={{
        background: "linear-gradient(90deg, #185E95 0%, #2E84AA 100%)",
        color: "#fff",
        textAlign: "center",
        borderRadius: 2,
        py: 1.5,
        px: 2,
        fontSize: 12,
        fontWeight: 600,
        ...sx,
      }}
    >
      طراحی و توسعه: میلاد محمدعلی‌زاده
    </Box>
  );
}
