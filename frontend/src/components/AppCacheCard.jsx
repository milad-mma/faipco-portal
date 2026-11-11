// کارت نوسازی نسخه ذخیره‌شده اپ (مجوز system.cache_bust) — صفحه بررسی و اعمال آپدیت.
// سرور پس از تغییر کامل sw.js یک رویداد آنی می‌فرستد؛ اعلان کاربران فقط پس از
// waiting شدن Worker نمایش داده می‌شود. حذف همه کش‌ها یا تغییر فوری آیکون تضمین نیست.
import { useState } from "react";
import { Alert, Button, CircularProgress, Typography } from "@mui/material";
import CachedOutlinedIcon from "@mui/icons-material/CachedOutlined";
import { bustAppCache } from "../api/system";

export default function AppCacheCard() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // { success, message } | null

  async function handleClick() {
    setResult(null);
    setBusy(true);
    try {
      const data = await bustAppCache();
      setResult({ success: true, realtimeSent: data.realtime_sent !== false, message: data.message });
    } catch (err) {
      setResult({ success: false, message: err.response?.data?.detail || "درخواست نوسازی نسخه ذخیره‌شده با خطا مواجه شد." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>
        نوسازی نسخه ذخیره‌شده پرتال برای کاربران
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        برای زمانی که نسخه ذخیره‌شده پرتال در مرورگر یا اپ اندروید به‌روز نشده است. پس از ثبت درخواست،
        به کاربران آنلاین رویداد نوسازی ارسال می‌شود و فقط بعد از نصب کامل Service Worker اعلان نمایش می‌یابد.
        کاربران آفلاین هنگام بازگشت به برنامه بررسی می‌شوند. اطلاعات شخصی و نشست کاربران از سمت سرور حذف نمی‌شود؛
        به‌روزرسانی فوری آیکون نصب‌شده در اندروید تضمین‌شده نیست.
      </Typography>
      {result && (
        <Alert severity={result.success ? (result.realtimeSent ? "success" : "warning") : "error"} sx={{ mb: 2 }}>
          {result.message}
        </Alert>
      )}
      <Button
        variant="outlined"
        startIcon={busy ? <CircularProgress size={18} /> : <CachedOutlinedIcon />}
        onClick={handleClick}
        disabled={busy}
      >
        {busy ? "در حال ثبت درخواست..." : "اعلان نوسازی به کاربران"}
      </Button>
    </>
  );
}
