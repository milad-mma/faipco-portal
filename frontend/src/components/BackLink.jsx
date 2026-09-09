import { Button } from "@mui/material";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { useNavigate } from "react-router-dom";

/**
 * دکمه/لینک «بازگشت» یکسان برای همه صفحاتی که از یک صفحه دیگر (داشبورد،
 * یا هر صفحه‌ی مرتبط دیگری) باز می‌شوند - طبق اصل کلی صریح کاربر: هر
 * صفحه‌ای که از صفحه‌ی دیگری باز می‌شود و با آن مرتبط است، باید راه
 * برگشت مشخص داشته باشد؛ نه صرفاً به دکمه Back مرورگر متکی باشد (که اگر
 * کاربر مستقیم لینک را باز کرده باشد یا Refresh کرده باشد، اصلاً تاریخچه‌ای
 * برای برگشتن ندارد).
 *
 * ⚠️ عمداً از navigate(to) با مسیر مشخص استفاده می‌کند - نه navigate(-1)
 * (که به تاریخچه مرورگر متکی است و در آن سناریوها کار نمی‌کند).
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
