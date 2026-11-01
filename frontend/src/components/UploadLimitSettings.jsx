/**
 * «سقف آپلود سرور» (فقط ادمین کل): حداکثر حجم هر درخواست آپلود در nginx همین سرور. با ذخیره، اسکریپت
 * scripts/nginx-upload-limit.sh تنظیم nginx را عوض، تست (nginx -t) و reload می‌کند؛ در خطا مقدار قبلی برمی‌گردد.
 * سقف حجم هر فایل در تنظیمات پیوست اتوماسیون = این مقدار منهای ۱ مگابایت. جزئیات: docs/upload-limit.md
 */
import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, CircularProgress, Stack, TextField, Typography } from "@mui/material";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import { fetchUploadLimit, saveUploadLimit } from "../api/system";
import { toPersianDigits } from "../utils/searchText";

function errorText(err, fallback) {
  const detail = err?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

export default function UploadLimitSettings() {
  const [state, setState] = useState(null);
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [showLog, setShowLog] = useState(false);

  const load = useCallback(() => {
    fetchUploadLimit()
      .then((d) => {
        setState(d);
        setValue((prev) => (prev === "" ? String(d.limit_mb) : prev));
      })
      .catch((err) => setError(errorText(err, "دریافت سقف آپلود با خطا مواجه شد.")));
  }, []);

  useEffect(load, [load]);

  // تا وقتی اعمال روی سرور در حال اجراست، هر ۲ ثانیه وضعیت تازه شود
  useEffect(() => {
    if (!state?.job?.running) return undefined;
    const t = window.setTimeout(load, 2000);
    return () => window.clearTimeout(t);
  }, [state, load]);

  async function handleSave() {
    setError("");
    const mb = Number(String(value).replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)));
    setSaving(true);
    try {
      await saveUploadLimit(mb);
      setTimeout(load, 1500);
    } catch (err) {
      setError(errorText(err, "ذخیره‌ی سقف آپلود با خطا مواجه شد."));
    } finally {
      setSaving(false);
    }
  }

  if (!state) return error ? <Alert severity="error">{error}</Alert> : <CircularProgress size={22} />;
  const job = state.job || {};
  const mismatch = state.applied_mb != null && state.applied_mb !== state.limit_mb && !job.running;

  return (
    <Box>
      <Typography variant="subtitle1" fontWeight={700}>
        سقف آپلود سرور
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        حداکثر حجم هر آپلود در nginx همین سرور (برای همه‌ی ماژول‌ها). حجم هر فایل در تنظیمات پیوست اتوماسیون حداکثر این
        مقدار منهای ۱ مگابایت است — الان {toPersianDigits(state.portal_max_file_mb)} مگابایت. سقف‌های خود ماژول‌ها (مثلاً
        مدارک بیمه ۱۰ مگابایت) جدا هستند.
      </Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "flex-start" }}>
        <TextField
          size="small"
          label="سقف آپلود (مگابایت)"
          value={value}
          onChange={(e) => setValue(e.target.value.replace(/[^\d۰-۹]/g, ""))}
          inputProps={{ inputMode: "numeric" }}
          helperText={`بین ${toPersianDigits(state.min_mb)} و ${toPersianDigits(state.max_mb)}`}
          sx={{ width: 220, "& .MuiInputBase-root": { height: 40 } }}
        />
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving || job.running}
          startIcon={saving || job.running ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />}
          sx={{ height: 40 }}
        >
          ذخیره و اعمال روی سرور
        </Button>
      </Stack>
      <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
        مقدار فعلی در nginx: {state.applied_mb != null ? `${toPersianDigits(state.applied_mb)} مگابایت` : "نامشخص (یک بار آپدیت پرتال لازم است)"}
      </Typography>
      {job.running && <Alert severity="info" sx={{ mt: 1.5 }}>در حال اعمال روی nginx…</Alert>}
      {!job.running && job.result === "ok" && !mismatch && (
        <Alert severity="success" sx={{ mt: 1.5 }}>سقف آپلود روی سرور اعمال شد.</Alert>
      )}
      {!job.running && job.result === "fail" && (
        <Alert severity="error" sx={{ mt: 1.5 }} action={<Button size="small" color="inherit" onClick={() => setShowLog((v) => !v)}>گزارش</Button>}>
          اعمال روی nginx ناموفق بود؛ مقدار قبلی nginx حفظ شد.
        </Alert>
      )}
      {mismatch && job.result !== "fail" && (
        <Alert severity="warning" sx={{ mt: 1.5 }}>
          مقدار ثبت‌شده ({toPersianDigits(state.limit_mb)}) با مقدار nginx ({toPersianDigits(state.applied_mb)}) یکی نیست؛ دوباره «ذخیره و اعمال» را بزنید.
        </Alert>
      )}
      {showLog && job.log && (
        <Box component="pre" dir="ltr" sx={{ whiteSpace: "pre-wrap", fontSize: 12, mt: 1, p: 1, bgcolor: "action.hover", borderRadius: 1 }}>
          {job.log}
        </Box>
      )}
      {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
    </Box>
  );
}
