import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Divider,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ScheduleOutlinedIcon from "@mui/icons-material/ScheduleOutlined";
import {
  fetchBackupSettings,
  runBackupNow,
  testFtpConnection,
  testSmbConnection,
  updateBackupSettings,
} from "../api/backup";

const WEEKDAY_LABELS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]; // ۰=دوشنبه...۶=یکشنبه

/**
 * تنظیمات «زمان‌بندی بکاپ + ارسال خودکار به سرور راه‌دور (SMB/FTP)» -
 * بخشی مستقل از صفحه پشتیبان‌گیری (که خودش دستی export/restore است).
 *
 * رمزهای عبور SMB/FTP هرگز از سرور برنمی‌گردند (فقط smb_has_password/
 * ftp_has_password بولی) - در فرم، خالی‌گذاشتن فیلد رمز یعنی «رمز قبلی
 * حفظ شود»؛ برای وارد‌کردن رمز جدید، باید صریحاً تایپ شود.
 */
export default function BackupScheduleSettings() {
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saveResult, setSaveResult] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [smbTestResult, setSmbTestResult] = useState(null);
  const [ftpTestResult, setFtpTestResult] = useState(null);
  const [isTestingSmb, setIsTestingSmb] = useState(false);
  const [isTestingFtp, setIsTestingFtp] = useState(false);
  const [isRunningNow, setIsRunningNow] = useState(false);
  const [runNowResult, setRunNowResult] = useState(null);

  useEffect(() => {
    loadSettings();
  }, []);

  function loadSettings() {
    fetchBackupSettings()
      .then((data) => {
        setSettings(data);
        setForm({ ...data, smb_password: "", ftp_password: "" });
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت تنظیمات ناموفق بود."));
  }

  function updateForm(patch) {
    setForm((prev) => ({ ...prev, ...patch }));
  }

  async function handleSave() {
    setIsSaving(true);
    setSaveResult(null);
    try {
      const payload = { ...form };
      if (!payload.smb_password) delete payload.smb_password;
      if (!payload.ftp_password) delete payload.ftp_password;
      const updated = await updateBackupSettings(payload);
      setSettings(updated);
      setForm({ ...updated, smb_password: "", ftp_password: "" });
      setSaveResult({ success: true, message: "تنظیمات ذخیره شد." });
    } catch (err) {
      setSaveResult({ success: false, message: err.response?.data?.detail || "ذخیره ناموفق بود." });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTestSmb() {
    setIsTestingSmb(true);
    setSmbTestResult(null);
    try {
      const result = await testSmbConnection({
        host: form.smb_host,
        share: form.smb_share,
        path: form.smb_path,
        username: form.smb_username,
        password: form.smb_password || undefined,
        domain: form.smb_domain,
      });
      setSmbTestResult({ success: true, message: result.message });
    } catch (err) {
      setSmbTestResult({ success: false, message: err.response?.data?.detail || "تست اتصال ناموفق بود." });
    } finally {
      setIsTestingSmb(false);
    }
  }

  async function handleTestFtp() {
    setIsTestingFtp(true);
    setFtpTestResult(null);
    try {
      const result = await testFtpConnection({
        host: form.ftp_host,
        port: form.ftp_port,
        username: form.ftp_username,
        password: form.ftp_password || undefined,
        path: form.ftp_path,
        use_tls: form.ftp_use_tls,
      });
      setFtpTestResult({ success: true, message: result.message });
    } catch (err) {
      setFtpTestResult({ success: false, message: err.response?.data?.detail || "تست اتصال ناموفق بود." });
    } finally {
      setIsTestingFtp(false);
    }
  }

  async function handleRunNow() {
    setIsRunningNow(true);
    setRunNowResult(null);
    try {
      const result = await runBackupNow();
      setRunNowResult({ success: true, message: result.message });
      loadSettings();
    } catch (err) {
      setRunNowResult({ success: false, message: err.response?.data?.detail || "اجرای بکاپ ناموفق بود." });
    } finally {
      setIsRunningNow(false);
    }
  }

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!form) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Stack spacing={3}>
      <Typography variant="subtitle2" fontWeight={700} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <ScheduleOutlinedIcon fontSize="small" />
        زمان‌بندی بکاپ خودکار و ارسال به سرور راه‌دور
      </Typography>

      {settings?.last_run_at && (
        <Alert severity={settings.last_run_success ? "success" : "error"}>
          آخرین اجرا: {new Date(settings.last_run_at).toLocaleString("fa-IR")} —{" "}
          {settings.last_run_message || (settings.last_run_success ? "موفق" : "ناموفق")}
        </Alert>
      )}

      <Stack spacing={2}>
        <FormControlLabel
          control={
            <Checkbox
              checked={form.schedule_enabled}
              onChange={(e) => updateForm({ schedule_enabled: e.target.checked })}
            />
          }
          label="زمان‌بندی بکاپ خودکار فعال باشد"
        />

        {form.schedule_enabled && (
          <Stack spacing={2} sx={{ pr: 3 }}>
            <TextField
              select
              size="small"
              label="نوع زمان‌بندی"
              value={form.schedule_type}
              onChange={(e) => updateForm({ schedule_type: e.target.value })}
              sx={{ maxWidth: 220 }}
            >
              <MenuItem value="daily">روزانه</MenuItem>
              <MenuItem value="weekly">هفتگی</MenuItem>
              <MenuItem value="interval">هر چند ساعت یک‌بار</MenuItem>
            </TextField>

            {(form.schedule_type === "daily" || form.schedule_type === "weekly") && (
              <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                {form.schedule_type === "weekly" && (
                  <TextField
                    select
                    size="small"
                    label="روز هفته"
                    value={form.schedule_weekday ?? ""}
                    onChange={(e) => updateForm({ schedule_weekday: Number(e.target.value) })}
                    sx={{ minWidth: 130 }}
                  >
                    {WEEKDAY_LABELS.map((label, idx) => (
                      <MenuItem key={idx} value={idx}>
                        {label}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
                <TextField
                  size="small"
                  type="number"
                  label="ساعت (۰ تا ۲۳)"
                  value={form.schedule_hour}
                  onChange={(e) => updateForm({ schedule_hour: Number(e.target.value) })}
                  inputProps={{ min: 0, max: 23 }}
                  sx={{ width: 130 }}
                />
                <TextField
                  size="small"
                  type="number"
                  label="دقیقه (۰ تا ۵۹)"
                  value={form.schedule_minute}
                  onChange={(e) => updateForm({ schedule_minute: Number(e.target.value) })}
                  inputProps={{ min: 0, max: 59 }}
                  sx={{ width: 130 }}
                />
              </Stack>
            )}

            {form.schedule_type === "interval" && (
              <TextField
                size="small"
                type="number"
                label="فاصله زمانی (ساعت)"
                value={form.schedule_interval_hours ?? ""}
                onChange={(e) => updateForm({ schedule_interval_hours: Number(e.target.value) })}
                inputProps={{ min: 1, max: 168 }}
                sx={{ width: 180 }}
              />
            )}
          </Stack>
        )}
      </Stack>

      <Divider />

      <Stack spacing={2}>
        <FormControlLabel
          control={
            <Checkbox checked={form.smb_enabled} onChange={(e) => updateForm({ smb_enabled: e.target.checked })} />
          }
          label="ارسال بکاپ به سرور SMB Share"
        />
        {form.smb_enabled && (
          <Stack spacing={2} sx={{ pr: 3 }}>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <TextField
                size="small"
                label="آدرس سرور (Host)"
                value={form.smb_host || ""}
                onChange={(e) => updateForm({ smb_host: e.target.value })}
                sx={{ minWidth: 200 }}
              />
              <TextField
                size="small"
                label="نام Share"
                value={form.smb_share || ""}
                onChange={(e) => updateForm({ smb_share: e.target.value })}
                sx={{ minWidth: 160 }}
              />
              <TextField
                size="small"
                label="مسیر داخل Share (اختیاری)"
                value={form.smb_path || ""}
                onChange={(e) => updateForm({ smb_path: e.target.value })}
                placeholder="backups/faipco"
                sx={{ minWidth: 200 }}
              />
            </Stack>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <TextField
                size="small"
                label="نام کاربری"
                value={form.smb_username || ""}
                onChange={(e) => updateForm({ smb_username: e.target.value })}
                sx={{ minWidth: 160 }}
              />
              <TextField
                size="small"
                type="password"
                label="رمز عبور"
                value={form.smb_password || ""}
                onChange={(e) => updateForm({ smb_password: e.target.value })}
                placeholder={settings?.smb_has_password ? "برای حفظ رمز قبلی خالی بگذارید" : ""}
                sx={{ minWidth: 200 }}
              />
              <TextField
                size="small"
                label="دامنه (اختیاری)"
                value={form.smb_domain || ""}
                onChange={(e) => updateForm({ smb_domain: e.target.value })}
                sx={{ minWidth: 140 }}
              />
            </Stack>
            {smbTestResult && (
              <Alert severity={smbTestResult.success ? "success" : "error"}>{smbTestResult.message}</Alert>
            )}
            <Box>
              <Button
                variant="outlined"
                size="small"
                onClick={handleTestSmb}
                disabled={isTestingSmb || !form.smb_host || !form.smb_share || !form.smb_username}
                startIcon={isTestingSmb ? <CircularProgress size={14} /> : null}
              >
                تست اتصال SMB
              </Button>
            </Box>
          </Stack>
        )}
      </Stack>

      <Divider />

      <Stack spacing={2}>
        <FormControlLabel
          control={
            <Checkbox checked={form.ftp_enabled} onChange={(e) => updateForm({ ftp_enabled: e.target.checked })} />
          }
          label="ارسال بکاپ به سرور FTP"
        />
        {form.ftp_enabled && (
          <Stack spacing={2} sx={{ pr: 3 }}>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <TextField
                size="small"
                label="آدرس سرور (Host)"
                value={form.ftp_host || ""}
                onChange={(e) => updateForm({ ftp_host: e.target.value })}
                sx={{ minWidth: 200 }}
              />
              <TextField
                size="small"
                type="number"
                label="پورت"
                value={form.ftp_port}
                onChange={(e) => updateForm({ ftp_port: Number(e.target.value) })}
                sx={{ width: 110 }}
              />
              <TextField
                size="small"
                label="مسیر (اختیاری)"
                value={form.ftp_path || ""}
                onChange={(e) => updateForm({ ftp_path: e.target.value })}
                placeholder="backups/faipco"
                sx={{ minWidth: 200 }}
              />
            </Stack>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="center">
              <TextField
                size="small"
                label="نام کاربری"
                value={form.ftp_username || ""}
                onChange={(e) => updateForm({ ftp_username: e.target.value })}
                sx={{ minWidth: 160 }}
              />
              <TextField
                size="small"
                type="password"
                label="رمز عبور"
                value={form.ftp_password || ""}
                onChange={(e) => updateForm({ ftp_password: e.target.value })}
                placeholder={settings?.ftp_has_password ? "برای حفظ رمز قبلی خالی بگذارید" : ""}
                sx={{ minWidth: 200 }}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={form.ftp_use_tls}
                    onChange={(e) => updateForm({ ftp_use_tls: e.target.checked })}
                  />
                }
                label="اتصال رمزنگاری‌شده (FTPS) — توصیه‌شده"
              />
            </Stack>
            {ftpTestResult && (
              <Alert severity={ftpTestResult.success ? "success" : "error"}>{ftpTestResult.message}</Alert>
            )}
            <Box>
              <Button
                variant="outlined"
                size="small"
                onClick={handleTestFtp}
                disabled={isTestingFtp || !form.ftp_host || !form.ftp_username}
                startIcon={isTestingFtp ? <CircularProgress size={14} /> : null}
              >
                تست اتصال FTP
              </Button>
            </Box>
          </Stack>
        )}
      </Stack>

      <Divider />

      <Stack spacing={2}>
        <Typography variant="body2" fontWeight={700}>
          نگهداری بکاپ‌های قدیمی روی سرور راه‌دور
        </Typography>
        <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="center">
          <TextField
            select
            size="small"
            label="روش نگهداری"
            value={form.retention_mode}
            onChange={(e) => updateForm({ retention_mode: e.target.value })}
            sx={{ minWidth: 220 }}
          >
            <MenuItem value="count">فقط N بکاپ آخر نگه داشته شود</MenuItem>
            <MenuItem value="days">فقط بکاپ‌های N روز اخیر نگه داشته شود</MenuItem>
          </TextField>
          {form.retention_mode === "count" ? (
            <TextField
              size="small"
              type="number"
              label="تعداد بکاپ نگه‌داشته‌شده"
              value={form.retention_count}
              onChange={(e) => updateForm({ retention_count: Number(e.target.value) })}
              inputProps={{ min: 1 }}
              sx={{ width: 200 }}
            />
          ) : (
            <TextField
              size="small"
              type="number"
              label="تعداد روز نگه‌داری"
              value={form.retention_days}
              onChange={(e) => updateForm({ retention_days: Number(e.target.value) })}
              inputProps={{ min: 1 }}
              sx={{ width: 200 }}
            />
          )}
        </Stack>
      </Stack>

      {saveResult && <Alert severity={saveResult.success ? "success" : "error"}>{saveResult.message}</Alert>}

      <Stack direction="row" spacing={1.5}>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={isSaving}
          startIcon={isSaving ? <CircularProgress size={16} color="inherit" /> : null}
        >
          {isSaving ? "در حال ذخیره..." : "ذخیره تنظیمات"}
        </Button>
        <Button
          variant="outlined"
          onClick={handleRunNow}
          disabled={isRunningNow || !(form.smb_enabled || form.ftp_enabled)}
          startIcon={isRunningNow ? <CircularProgress size={16} /> : null}
        >
          {isRunningNow ? "در حال اجرا..." : "اجرای فوری بکاپ الان"}
        </Button>
      </Stack>
      {runNowResult && <Alert severity={runNowResult.success ? "success" : "error"}>{runNowResult.message}</Alert>}
    </Stack>
  );
}
