import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Card, Chip, CircularProgress, Stack, Typography } from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import { fetchProjectCheckStatus, runProjectChecks } from "../api/system";
import { monoFontSx } from "../theme";

const POLL_INTERVAL_MS = 2000;

/**
 * «بررسی سلامت پروژه» - اجرای scripts/check.sh از پنل با یک کلیک (طبق درخواست
 * کاربر). مسیرهای API را با مرجع مقایسه می‌کند، تست‌ها را اجرا می‌کند و
 * Migration ها را روی یک دیتابیس موقت از صفر تست می‌کند. فقط می‌خواند/تست
 * می‌کند؛ هیچ چیزی در پروژه یا دیتابیس واقعی تغییر نمی‌دهد.
 */
export default function ProjectChecksCard() {
  const [status, setStatus] = useState(null); // { log, is_running, is_passed, is_failed }
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const timerRef = useRef(null);
  const logRef = useRef(null);

  async function refresh() {
    try {
      const data = await fetchProjectCheckStatus();
      setStatus(data);
      return data;
    } catch {
      return null;
    }
  }

  function poll() {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      const data = await refresh();
      if (!data || data.is_running) poll();
    }, POLL_INTERVAL_MS);
  }

  useEffect(() => {
    refresh().then((data) => {
      if (data?.is_running) poll();
    });
    return () => clearTimeout(timerRef.current);
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [status?.log]);

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

  const running = starting || status?.is_running;
  const resultChip = status?.is_passed ? (
    <Chip label="همه بررسی‌ها موفق" color="success" size="small" />
  ) : status?.is_failed ? (
    <Chip label="بعضی بررسی‌ها شکست خورد" color="error" size="small" />
  ) : running ? (
    <Chip label="در حال اجرا..." color="info" size="small" />
  ) : null;

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: 3, mt: 3 }}>
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
            textAlign: "left",
          }}
        >
          {status.log.replace(/\x1b\[[0-9;]*m/g, "")}
        </Box>
      )}
    </Card>
  );
}
