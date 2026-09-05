import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import EmailOutlinedIcon from "@mui/icons-material/EmailOutlined";
import { fetchSmtpSettings, testSmtpSettings, updateSmtpSettings } from "../api/system";

/**
 * تنظیمات SMTP سراسری - برای «فراموشی رمز عبور» (ارسال لینک بازنشانی)
 * و «ارسال بکاپ به ایمیل».
 *
 * رمز عبور هرگز از سرور برنمی‌گردد (فقط has_password بولی) - خالی‌گذاشتن
 * فیلد رمز در فرم یعنی «رمز قبلی حفظ شود».
 */
export default function SmtpSettings() {
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saveResult, setSaveResult] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [testAddress, setTestAddress] = useState("");
  const [testResult, setTestResult] = useState(null);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    fetchSmtpSettings()
      .then((data) => {
        setSettings(data);
        setForm({ ...data, password: "" });
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت تنظیمات با خطا مواجه شد."));
  }, []);

  function updateForm(patch) {
    setForm((prev) => ({ ...prev, ...patch }));
  }

  async function handleSave() {
    setIsSaving(true);
    setSaveResult(null);
    try {
      const payload = { ...form };
      if (!payload.password) delete payload.password;
      const updated = await updateSmtpSettings(payload);
      setSettings(updated);
      setForm({ ...updated, password: "" });
      setSaveResult({ success: true, message: "تنظیمات با موفقیت ذخیره شد." });
    } catch (err) {
      setSaveResult({ success: false, message: err.response?.data?.detail || "ذخیره تنظیمات با خطا مواجه شد." });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTest() {
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await testSmtpSettings(testAddress);
      setTestResult({ success: true, message: result.message });
    } catch (err) {
      setTestResult({ success: false, message: err.response?.data?.detail || "ارسال ایمیل آزمایشی با خطا مواجه شد." });
    } finally {
      setIsTesting(false);
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
        <EmailOutlinedIcon fontSize="small" />
        تنظیمات ایمیل (SMTP)
      </Typography>
      <Typography variant="body2" color="text.secondary">
        برای «فراموشی رمز عبور» و «ارسال بکاپ به ایمیل» استفاده می‌شود.
      </Typography>

      <FormControlLabel
        control={<Checkbox checked={form.enabled} onChange={(e) => updateForm({ enabled: e.target.checked })} />}
        label="سرویس ایمیل فعال باشد"
      />

      {form.enabled && (
        <Stack spacing={2} sx={{ pr: 3 }}>
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <TextField
              size="small"
              label="آدرس سرور SMTP (Host)"
              value={form.host || ""}
              onChange={(e) => updateForm({ host: e.target.value })}
              sx={{ minWidth: 220 }}
            />
            <TextField
              size="small"
              type="number"
              label="پورت"
              value={form.port}
              onChange={(e) => updateForm({ port: Number(e.target.value) })}
              sx={{ width: 110 }}
            />
            <TextField
              select
              size="small"
              label="نوع رمزنگاری"
              value={form.encryption_mode}
              onChange={(e) => updateForm({ encryption_mode: e.target.value })}
              sx={{ minWidth: 160 }}
            >
              <MenuItem value="starttls">STARTTLS (معمولاً پورت ۵۸۷)</MenuItem>
              <MenuItem value="ssl">SSL/TLS مستقیم (معمولاً پورت ۴۶۵)</MenuItem>
              <MenuItem value="none">بدون رمزنگاری</MenuItem>
            </TextField>
          </Stack>

          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <TextField
              size="small"
              label="نام کاربری"
              value={form.username || ""}
              onChange={(e) => updateForm({ username: e.target.value })}
              sx={{ minWidth: 200 }}
            />
            <TextField
              size="small"
              type="password"
              label="رمز عبور"
              value={form.password || ""}
              onChange={(e) => updateForm({ password: e.target.value })}
              placeholder={settings?.has_password ? "برای حفظ رمز قبلی خالی بگذارید" : ""}
              sx={{ minWidth: 200 }}
            />
          </Stack>

          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <TextField
              size="small"
              label="آدرس ایمیل فرستنده"
              value={form.from_address || ""}
              onChange={(e) => updateForm({ from_address: e.target.value })}
              placeholder="noreply@example.com"
              sx={{ minWidth: 220 }}
            />
            <TextField
              size="small"
              label="نام نمایشی فرستنده (اختیاری)"
              value={form.from_name || ""}
              onChange={(e) => updateForm({ from_name: e.target.value })}
              placeholder="پرتال سازمانی"
              sx={{ minWidth: 200 }}
            />
          </Stack>

          <Typography variant="body2" fontWeight={700} sx={{ mt: 1 }}>
            متن ایمیل «فراموشی رمز عبور»
          </Typography>
          <TextField
            size="small"
            label="عنوان ایمیل (اختیاری)"
            value={form.password_reset_email_subject || ""}
            onChange={(e) => updateForm({ password_reset_email_subject: e.target.value })}
            placeholder="بازنشانی رمز عبور - پرتال سازمانی"
            sx={{ maxWidth: 400 }}
          />
          <TextField
            size="small"
            multiline
            minRows={4}
            label="متن ایمیل (اختیاری)"
            value={form.password_reset_email_body || ""}
            onChange={(e) => updateForm({ password_reset_email_body: e.target.value })}
            placeholder={"همکار گرامی،\nبرای بازنشانی رمز عبور خود روی لینک زیر کلیک کنید:\n{reset_link}"}
            sx={{ maxWidth: 500 }}
          />
          <Typography variant="caption" color="text.secondary">
            اگر خالی بگذارید، یک متن پیش‌فرض استفاده می‌شود. عبارت{" "}
            <Box component="span" sx={{ fontFamily: "monospace" }}>
              {"{reset_link}"}
            </Box>{" "}
            در متن، با لینک واقعی بازنشانی جایگزین می‌شود — اگر آن را در متن خودتان قرار ندهید، لینک
            خودکار به انتهای پیام اضافه خواهد شد.
          </Typography>
        </Stack>
      )}

      {saveResult && <Alert severity={saveResult.success ? "success" : "error"}>{saveResult.message}</Alert>}

      <Box>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={isSaving}
          startIcon={isSaving ? <CircularProgress size={16} color="inherit" /> : null}
        >
          {isSaving ? "در حال ذخیره..." : "ذخیره تنظیمات"}
        </Button>
      </Box>

      {settings?.enabled && (
        <Stack spacing={1.5}>
          <Typography variant="body2" fontWeight={700}>
            ارسال ایمیل آزمایشی (با تنظیمات فعلاً ذخیره‌شده)
          </Typography>
          {testResult && <Alert severity={testResult.success ? "success" : "error"}>{testResult.message}</Alert>}
          <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap alignItems="center">
            <TextField
              size="small"
              label="ایمیل گیرنده تست"
              value={testAddress}
              onChange={(e) => setTestAddress(e.target.value)}
              sx={{ minWidth: 240 }}
            />
            <Button
              variant="outlined"
              size="small"
              onClick={handleTest}
              disabled={isTesting || !testAddress}
              startIcon={isTesting ? <CircularProgress size={14} /> : null}
            >
              ارسال ایمیل آزمایشی
            </Button>
          </Stack>
        </Stack>
      )}
    </Stack>
  );
}
