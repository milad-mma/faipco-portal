import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from "@mui/material";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import { useNavigate } from "react-router-dom";

/**
 * دیالوگ «دسترسی مشروط»: به کاربر اعلام می‌کند که برای استفاده از یک بخش، ابتدا باید
 * اطلاعیه‌های خوانده‌نشده را بخواند یا ارزیابی‌های انجام‌نشده را تکمیل کند.
 * ورودی: open، gate (نوع پیش‌نیاز: unread_notices یا pending_evaluations)، count (تعداد موارد ناتمام)،
 * message (متن سرور؛ در صورت وجود جایگزین متن پیش‌فرض)، byPeriod (تفکیک ارزیابی‌ها بر اساس دوره) و onClose.
 * خروجی: یک Dialog با متن راهنما و دکمه‌ی رفتن به صفحه‌ی اطلاعیه‌ها یا ارزیابی‌ها.
 * بستن دیالوگ فقط همان کار مشروط را متوقف می‌کند و بقیه‌ی بخش‌ها در دسترس می‌مانند.
 * هم پیش از شروع کار (وقتی صفحه وضعیت را می‌داند) و هم پس از پاسخ ۴۰۳ سرور باز می‌شود.
 */
export default function AccessGateDialog({ open, gate, count, message, byPeriod, onClose }) {
  const navigate = useNavigate();
  const isNotices = gate !== "pending_evaluations"; // هر مقداری غیر از ارزیابی، حالت اطلاعیه در نظر گرفته می‌شود

  // عدد فقط وقتی در متن می‌آید که تعداد مثبت معلوم باشد؛ در غیر این صورت
  // (مثلاً باز شدن از پاسخ ۴۰۳ بدون تعداد) متن عمومی و بدون عدد نمایش داده می‌شود.
  const hasCount = typeof count === "number" && count > 0;
  const countText = hasCount ? `${count.toLocaleString("fa-IR")} ` : "";

  // متن بدنه: پیام سرور در اولویت است، وگرنه متن پیش‌فرض بر اساس نوع پیش‌نیاز
  const body =
    message ||
    (isNotices
      ? `برای دسترسی به این بخش، ابتدا باید ${countText}اطلاعیه خوانده‌نشده خود را مطالعه کنید.`
      : `برای دسترسی به این بخش، ابتدا باید ${countText}ارزیابی انجام‌نشده خود را تکمیل کنید.`);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1}>
          <WarningAmberOutlinedIcon color="warning" />
          <Typography fontWeight={700}>دسترسی مشروط</Typography>
        </Stack>
      </DialogTitle>
      <DialogContent>
        {/* متن اصلی راهنما */}
        <Typography variant="body2" sx={{ lineHeight: 1.9 }}>
          {body}
        </Typography>
        {/* فهرست دوره‌های ارزیابی و تعداد موارد ناتمام هر دوره (فقط برای پیش‌نیاز ارزیابی) */}
        {!isNotices && byPeriod?.length > 0 && (
          <Box sx={{ mt: 1.5, pt: 1.5, borderTop: "1px solid", borderColor: "divider" }}>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.75 }}>
              دوره‌های مربوطه:
            </Typography>
            <Stack spacing={0.5}>
              {byPeriod.map((p) => (
                <Stack key={p.period_title} direction="row" justifyContent="space-between" spacing={1}>
                  <Typography variant="body2">{p.period_title}</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>
                    {p.count.toLocaleString("fa-IR")} مورد
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        {/* بستن دیالوگ کاربر را به بقیه‌ی بخش‌ها برمی‌گرداند؛ کل برنامه قفل نمی‌شود */}
        <Button onClick={onClose}>بستن</Button>
        <Button
          variant="contained"
          onClick={() => {
            onClose();
            // صفحه‌ی ارزیابی تب را با کلید آن (personnel) می‌خواند، نه با شماره؛
            // این آدرس کاربر را مستقیم به تب «پرسنل من» می‌برد.
            navigate(isNotices ? "/notices" : "/my-performance?tab=personnel");
          }}
        >
          {isNotices ? "مشاهده اطلاعیه‌ها" : "انجام ارزیابی‌ها"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
