import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from "@mui/material";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import { useNavigate } from "react-router-dom";

/**
 * ⚠️ طبق درخواست صریح کاربر: به‌جای بنر داخل صفحه، یک دیالوگ مودال که
 * جلوی ادامه کار را می‌گیرد - ولی با بستنش، کاربر همچنان به بقیه بخش‌ها
 * دسترسی دارد (قفل کل برنامه نیست، فقط همان کار مشروط).
 *
 * دو راه ورود دارد:
 *   ۱. پیشگیرانه - صفحه با دانستن وضعیت، قبل از شروع کار بازش می‌کند.
 *   ۲. واکنشی - وقتی سرور ۴۰۳ می‌دهد (مثلاً هنگام دانلود فیش)، به‌جای
 *      پیام خطای مبهم، همین دیالوگ با متن راهنما باز می‌شود.
 */
export default function AccessGateDialog({ open, gate, count, message, byPeriod, onClose }) {
  const navigate = useNavigate();
  const isNotices = gate !== "pending_evaluations";

  // ⚠️ وقتی تعداد واقعی در دسترس نیست (مثلاً دیالوگ از یک پاسخ ۴۰۳ باز
  // شده و سرور متنی نداده)، عدد ساختگی «۰» نمایش داده نمی‌شود - چون
  // «۰ اطلاعیه خوانده‌نشده» هم غلط است هم گیج‌کننده. در آن حالت متن
  // عمومی و بدون عدد نشان داده می‌شود.
  const hasCount = typeof count === "number" && count > 0;
  const countText = hasCount ? `${count.toLocaleString("fa-IR")} ` : "";

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
        <Typography variant="body2" sx={{ lineHeight: 1.9 }}>
          {body}
        </Typography>
        {/* ⚠️ تفکیک به‌ازای دوره - تا کاربر بداند کار ناتمامش مربوط به
            کدام دوره ارزیابی است، نه فقط یک عدد کل. */}
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
        {/* بستن دیالوگ کاربر را به بقیه بخش‌ها برمی‌گرداند - قفل کل برنامه نیست. */}
        <Button onClick={onClose}>بستن</Button>
        <Button
          variant="contained"
          onClick={() => {
            onClose();
            // ⚠️ رفع باگ: قبلاً "?tab=1" بود، ولی صفحه ارزیابی کلیدِ تب را
            // می‌خواند نه شماره را - indexOf("1") منفی می‌شد و کاربر به تب
            // «نتایج» می‌رفت، نه «پرسنل من» که باید کارش را آنجا انجام دهد.
            navigate(isNotices ? "/notices" : "/my-performance?tab=personnel");
          }}
        >
          {isNotices ? "مشاهده اطلاعیه‌ها" : "انجام ارزیابی‌ها"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
