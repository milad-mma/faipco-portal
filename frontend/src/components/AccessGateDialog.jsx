import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from "@mui/material";
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
export default function AccessGateDialog({ open, gate, count, message, onClose }) {
  const navigate = useNavigate();
  const isNotices = gate !== "pending_evaluations";

  const body =
    message ||
    (isNotices
      ? `برای دسترسی به این بخش، ابتدا باید ${(count || 0).toLocaleString("fa-IR")} اطلاعیه خوانده‌نشده خود را مطالعه کنید.`
      : `برای دسترسی به این بخش، ابتدا باید ${(count || 0).toLocaleString("fa-IR")} ارزیابی انجام‌نشده خود را تکمیل کنید.`);

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
      </DialogContent>
      <DialogActions>
        {/* بستن دیالوگ کاربر را به بقیه بخش‌ها برمی‌گرداند - قفل کل برنامه نیست. */}
        <Button onClick={onClose}>بستن</Button>
        <Button
          variant="contained"
          onClick={() => {
            onClose();
            navigate(isNotices ? "/notices" : "/my-performance?tab=1");
          }}
        >
          {isNotices ? "مشاهده اطلاعیه‌ها" : "انجام ارزیابی‌ها"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
