// کارت «پاک‌کردن کش اپلیکیشن برای همه کاربران» (مجوز system.cache_bust) — صفحه‌ی «بررسی و اعمال آپدیت».
// سرور یک برچسب زمانی به انتهای sw.js اضافه می‌کند؛ مرورگر هر کاربر (حداکثر تا یک دقیقه برای صفحه‌ی باز، یا در بازدید بعدی)
// Service Worker تازه را می‌گیرد و پیام «نسخه جدید آماده است» را نشان می‌دهد؛ با زدن «بارگذاری»، کش قبلی پاک و اپ تازه بارگذاری می‌شود.
import { useState } from "react";
import { Alert, Button, CircularProgress, Typography } from "@mui/material";
import DeleteSweepOutlinedIcon from "@mui/icons-material/DeleteSweepOutlined";
import { bustAppCache } from "../api/system";

export default function AppCacheCard() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // { success, message } | null

  async function handleClick() {
    setResult(null);
    setBusy(true);
    try {
      const data = await bustAppCache();
      setResult({ success: true, message: data.message });
    } catch (err) {
      setResult({ success: false, message: err.response?.data?.detail || "پاک‌کردن کش با خطا مواجه شد." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>
        پاک‌کردن کش اپلیکیشن برای همه کاربران
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        برای وقتی که صفحه یا آیکون قدیمی روی گوشی یا مرورگر کسی مانده است. هیچ داده‌ای پاک نمی‌شود و کسی از حساب خارج
        نمی‌شود؛ هر کاربر پیام «نسخه جدید آماده است» را می‌بیند و با زدن «بارگذاری»، اپ از نو دریافت می‌شود.
      </Typography>
      {result && (
        <Alert severity={result.success ? "success" : "error"} sx={{ mb: 2 }}>
          {result.message}
        </Alert>
      )}
      <Button
        variant="outlined"
        startIcon={busy ? <CircularProgress size={18} /> : <DeleteSweepOutlinedIcon />}
        onClick={handleClick}
        disabled={busy}
      >
        {busy ? "در حال اعمال..." : "پاک‌کردن کش برای همه کاربران"}
      </Button>
    </>
  );
}
