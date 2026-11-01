// صف تلاش دوباره‌ی ارسال‌های ناموفق بکاپ (GET /backup/retry-queue). اگر صف خالی باشد چیزی نشان نمی‌دهد.
// هر ردیف: فایل بکاپ، مقصدهای منتظر با تعداد تلاش، زمان تلاش بعدی و آخرین خطا؛ دکمه‌های «تلاش دوباره الان» و «حذف از صف».
import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import ReplayOutlinedIcon from "@mui/icons-material/ReplayOutlined";
import { discardRetryItem, fetchRetryQueue, runRetryQueueNow } from "../api/backup";
import { toPersianDigits } from "../utils/searchText";

export default function BackupRetryQueue({ refreshKey, onChanged }) {
  const [queue, setQueue] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null); // { success, message }

  const load = useCallback(() => {
    fetchRetryQueue().then(setQueue).catch(() => setQueue(null));
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function handleRunNow() {
    setBusy(true);
    setMessage(null);
    try {
      const data = await runRetryQueueNow();
      setMessage({ success: true, message: data.message });
      // نتیجه در پس‌زمینه آماده می‌شود؛ چند ثانیه بعد دوباره خوانده می‌شود
      setTimeout(() => {
        load();
        onChanged?.();
      }, 8000);
    } catch (err) {
      setMessage({ success: false, message: err.response?.data?.detail || "تلاش دوباره شروع نشد." });
    } finally {
      setBusy(false);
    }
  }

  async function handleDiscard(filename) {
    setMessage(null);
    try {
      await discardRetryItem(filename);
      load();
    } catch (err) {
      setMessage({ success: false, message: err.response?.data?.detail || "حذف از صف ناموفق بود." });
    }
  }

  if (!queue?.items?.length) return message ? <Alert severity={message.success ? "success" : "error"}>{message.message}</Alert> : null;

  return (
    <Alert severity="warning" icon={<ReplayOutlinedIcon />}>
      <Typography variant="body2" fontWeight={700} sx={{ mb: 1 }}>
        ارسال‌های منتظر تلاش دوباره
      </Typography>
      <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1.5 }}>
        این فایل‌ها به بعضی مقصدها نرسیدند و خودکار دوباره فرستاده می‌شوند (حداکثر {toPersianDigits(queue.max_attempts)} تلاش با
        فاصله‌ی بیشتر).
      </Typography>
      <Stack spacing={1.5}>
        {queue.items.map((item) => (
          <Box key={item.filename}>
            <Typography variant="body2" sx={{ direction: "ltr", textAlign: "right" }}>
              {item.filename}
            </Typography>
            {item.destinations.map((d) => (
              <Typography key={d.kind} variant="caption" component="div" color="text.secondary">
                {d.label}: تلاش {toPersianDigits(d.attempts)} — بعدی {new Date(d.next_at).toLocaleString("fa-IR")}
                {d.last_error ? ` — خطا: ${d.last_error}` : ""}
              </Typography>
            ))}
            <Button size="small" color="inherit" onClick={() => handleDiscard(item.filename)} sx={{ mt: 0.5 }}>
              حذف از صف
            </Button>
          </Box>
        ))}
      </Stack>
      {message && (
        <Alert severity={message.success ? "success" : "error"} sx={{ mt: 1.5 }}>
          {message.message}
        </Alert>
      )}
      <Button
        variant="outlined"
        color="inherit"
        onClick={handleRunNow}
        disabled={busy}
        startIcon={busy ? <CircularProgress size={14} /> : <ReplayOutlinedIcon />}
        sx={{ mt: 1.5, height: 40 }}
      >
        تلاش دوباره همین الان
      </Button>
    </Alert>
  );
}
