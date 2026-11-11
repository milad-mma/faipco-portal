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
      setResult({ success: false, message: err.response?.data?.detail || "درخواست تازه‌سازی پرتال انجام نشد. دوباره تلاش کنید." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>
        تازه‌سازی برنامه برای کاربران
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        اگر برخی کاربران هنوز صفحه‌های قدیمی پرتال را می‌بینند، از این گزینه استفاده کنید.
        پس از آماده‌شدن فایل‌های برنامه، اعلان «سامانه آماده به روزرسانی است» برای کاربران نمایش داده می‌شود.
        برنامه فقط با انتخاب «به روزرسانی» توسط خود کاربر دوباره باز می‌شود. حساب کاربری و اطلاعات ثبت‌شده حذف نمی‌شوند.
        تغییر فوری آیکون نصب‌شده در اندروید تضمین‌شده نیست.
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
        {busy ? "در حال ثبت درخواست..." : "اعلان تازه‌سازی به کاربران"}
      </Button>
    </>
  );
}
