import { Button } from "@mui/material";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { useNavigate } from "react-router-dom";

/**
 * دکمه‌ی «بازگشت» یکسان برای صفحاتی که از صفحه‌ی دیگری (مثلاً داشبورد) باز می‌شوند.
 * ورودی: to (مسیر مقصد) و label (متن دکمه؛ پیش‌فرض «بازگشت به داشبورد»).
 * خروجی: یک Button کوچک با آیکن فلش که با navigate(to) به مسیر مشخص می‌رود؛ از navigate(-1)
 * استفاده نمی‌شود تا با باز کردن مستقیم لینک یا Refresh (بدون تاریخچه‌ی مرورگر) هم کار کند.
 */
export default function BackLink({ to, label = "بازگشت به داشبورد" }) {
  const navigate = useNavigate();
  return (
    <Button
      size="small"
      startIcon={<ArrowForwardIcon sx={{ transform: "scaleX(-1)" }} />}
      onClick={() => navigate(to)}
      sx={{ mb: 2 }}
    >
      {label}
    </Button>
  );
}
