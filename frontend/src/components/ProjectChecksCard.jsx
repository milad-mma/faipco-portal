import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Card, Chip, CircularProgress, Stack, Typography } from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import { fetchProjectCheckStatus, runProjectChecks } from "../api/system";
import { monoFontSx } from "../theme";

const POLL_INTERVAL_MS = 2000;  // فاصله‌ی دریافت وضعیت در حین اجرای بررسی‌ها

/**
 * کارت «بررسی سلامت پروژه» در پنل مدیریت سیستم؛ بدون ورودی (props).
 * با یک کلیک scripts/check.sh را روی سرور اجرا می‌کند: مسیرهای API را با مرجع مقایسه، تست‌ها را اجرا
 * و Migrationها را روی یک دیتابیس موقت از صفر تست می‌کند؛ چیزی در پروژه یا دیتابیس واقعی تغییر نمی‌کند.
 * خروجی: وضعیت نتیجه (Chip)، دکمه‌ی اجرا و باکس لاگ زنده که تا پایان اجرا به‌صورت دوره‌ای به‌روز می‌شود.
 */
export default function ProjectChecksCard() {
  const [status, setStatus] = useState(null); // { log, is_running, is_passed, is_failed }
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);  // در حال ارسال درخواست شروع اجرا
  const timerRef = useRef(null);  // شناسه‌ی setTimeout دریافت دوره‌ای وضعیت
  const logRef = useRef(null);  // ارجاع به باکس لاگ برای اسکرول خودکار به انتها

  // وضعیت فعلی اجرا را از سرور می‌خواند؛ در صورت خطا null برمی‌گرداند
  async function refresh() {
    try {
      const data = await fetchProjectCheckStatus();
      setStatus(data);
      return data;
    } catch {
      return null;
    }
  }

  // دریافت دوره‌ای وضعیت: تا وقتی اجرا ادامه دارد (یا دریافت خطا داد) دوباره زمان‌بندی می‌شود
  function poll() {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      const data = await refresh();
      if (!data || data.is_running) poll();
    }, POLL_INTERVAL_MS);
  }

  // هنگام mount وضعیت فعلی خوانده می‌شود و اگر اجرایی در جریان باشد، دریافت دوره‌ای شروع می‌شود؛ هنگام unmount تایمر پاک می‌شود
  useEffect(() => {
    refresh().then((data) => {
      if (data?.is_running) poll();
    });
    return () => clearTimeout(timerRef.current);
  }, []);

  // با هر تغییر لاگ، باکس لاگ به انتها اسکرول می‌شود
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [status?.log]);

  // شروع اجرای بررسی‌ها روی سرور و آغاز دریافت دوره‌ای وضعیت
  async function handleRun() {
    setError("");
    setStarting(true);
    try {
      await runProjectChecks();
      setStatus({ log: "", is_running: true, is_passed: false, is_failed: false });
      poll();
    } catch (err) {
      setError(err.response?.data?.detail || "اجرای بررسی با خطا مواجه شد.");
    } finally {
      setStarting(false);
    }
  }

  const running = starting || status?.is_running;  // در حال شروع یا اجرا روی سرور
  // Chip نتیجه: موفق / ناموفق / در حال اجرا
  const resultChip = status?.is_passed ? (
    <Chip label="همه بررسی‌ها موفق" color="success" size="small" />
  ) : status?.is_failed ? (
    <Chip label="بعضی بررسی‌ها شکست خورد" color="error" size="small" />
  ) : running ? (
    <Chip label="در حال اجرا..." color="info" size="small" />
  ) : null;

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: 3, mt: 3 }}>
      {/* عنوان کارت و Chip نتیجه */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
        <CheckCircleOutlineIcon fontSize="small" color="action" />
        <Typography variant="subtitle1" fontWeight={700} sx={{ flex: 1 }}>
          بررسی سلامت پروژه
        </Typography>
        {resultChip}
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        مسیرهای API با مرجع مقایسه می‌شوند، تست‌ها اجرا می‌شوند و همه Migration ها روی یک دیتابیس موقت از صفر
        تست می‌شوند. چیزی در پروژه یا دیتابیس واقعی تغییر نمی‌کند؛ معمولاً کمتر از یک دقیقه طول می‌کشد. بعد از هر
        آپدیت اجرا کنید.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Button
        variant="contained"
        startIcon={running ? <CircularProgress size={18} color="inherit" /> : <CheckCircleOutlineIcon />}
        onClick={handleRun}
        disabled={running}
      >
        {running ? "در حال بررسی..." : "اجرای بررسی‌ها"}
      </Button>

      {/* باکس لاگ اجرا (چپ‌به‌راست)؛ کدهای رنگ ANSI از متن حذف می‌شوند */}
      {status?.log && (
        <Box
          ref={logRef}
          dir="ltr"
          sx={{
            ...monoFontSx,
            mt: 2,
            p: 1.5,
            maxHeight: 320,
            overflow: "auto",
            fontSize: 12,
            whiteSpace: "pre-wrap",
            bgcolor: "action.hover",
            borderRadius: 1,
          }}
          // direction/textAlign در style خطی تنظیم شده، نه sx؛ چون stylis-plugin-rtl مقادیر sx را قرینه می‌کند
          style={{ direction: "ltr", textAlign: "left" }}
        >
          {status.log.replace(/\x1b\[[0-9;]*m/g, "")}
        </Box>
      )}
    </Card>
  );
}
