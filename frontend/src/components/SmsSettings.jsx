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
import SmsOutlinedIcon from "@mui/icons-material/SmsOutlined";
import { fetchSmsSettings, testSmsSettings, updateSmsSettings } from "../api/system";

/**
 * فرم تنظیمات پیامک (ippanel Edge API) برای «فراموشی رمز عبور از طریق پیامک» (کد تأیید ۶ رقمی).
 * بدون ورودی (props)؛ تنظیمات را از سرور می‌خواند، ذخیره می‌کند و امکان ارسال پیامک آزمایشی دارد.
 * API Key هرگز از سرور برنمی‌گردد (فقط has_api_key بولی)؛ خالی گذاشتن فیلد یعنی مقدار قبلی حفظ شود.
 */
export default function SmsSettings() {
  const [settings, setSettings] = useState(null);  // آخرین تنظیمات ذخیره‌شده‌ی سرور (برای has_api_key)
  const [form, setForm] = useState(null);  // مقادیر در حال ویرایش؛ null = هنوز بارگذاری نشده
  const [error, setError] = useState("");  // خطای دریافت اولیه؛ در صورت وجود فقط همین نمایش داده می‌شود
  const [saveResult, setSaveResult] = useState(null);  // نتیجه‌ی ذخیره: { success, message } | null
  const [isSaving, setIsSaving] = useState(false);
  const [testMobile, setTestMobile] = useState("");  // شماره موبایل مقصد پیامک آزمایشی
  const [testResult, setTestResult] = useState(null);  // نتیجه‌ی ارسال آزمایشی: { success, message } | null
  const [isTesting, setIsTesting] = useState(false);

  // دریافت تنظیمات هنگام mount؛ فیلد API Key در فرم خالی شروع می‌شود
  useEffect(() => {
    fetchSmsSettings()
      .then((data) => {
        setSettings(data);
        setForm({ ...data, api_key: "" });
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت تنظیمات با خطا مواجه شد."));
  }, []);

  // ادغام تغییرات جزئی در فرم
  function updateForm(patch) {
    setForm((prev) => ({ ...prev, ...patch }));
  }

  // ذخیره‌ی تنظیمات؛ اگر API Key خالی باشد از payload حذف می‌شود تا مقدار قبلی سرور بماند
  async function handleSave() {
    setIsSaving(true);
    setSaveResult(null);
    try {
      const payload = { ...form };
      if (!payload.api_key) delete payload.api_key;
      const updated = await updateSmsSettings(payload);
      setSettings(updated);
      setForm({ ...updated, api_key: "" });
      setSaveResult({ success: true, message: "تنظیمات با موفقیت ذخیره شد." });
    } catch (err) {
      setSaveResult({ success: false, message: err.response?.data?.detail || "ذخیره تنظیمات با خطا مواجه شد." });
    } finally {
      setIsSaving(false);
    }
  }

  // ارسال پیامک آزمایشی به شماره‌ی واردشده و نمایش نتیجه
  async function handleTest() {
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await testSmsSettings(testMobile);
      setTestResult({ success: true, message: result.message });
    } catch (err) {
      setTestResult({ success: false, message: err.response?.data?.detail || "ارسال پیامک آزمایشی با خطا مواجه شد." });
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
        <SmsOutlinedIcon fontSize="small" />
        تنظیمات پیامک (ippanel)
      </Typography>
      <Typography variant="body2" color="text.secondary">
        برای «فراموشی رمز عبور از طریق پیامک» استفاده می‌شود.
      </Typography>

      {/* فعال/غیرفعال کردن ارسال پیامک */}
      <FormControlLabel
        control={<Checkbox checked={form.enabled} onChange={(e) => updateForm({ enabled: e.target.checked })} />}
        label="ارسال پیامک فعال باشد"
      />

      {/* فیلدهای تنظیمات فقط در حالت فعال */}
      {form.enabled && (
        <Stack spacing={2} sx={{ pr: 3 }}>
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <TextField
              size="small"
              type="password"
              label="API Key"
              value={form.api_key || ""}
              onChange={(e) => updateForm({ api_key: e.target.value })}
              placeholder={settings?.has_api_key ? "برای حفظ مقدار قبلی خالی بگذارید" : ""}
              sx={{ minWidth: 260 }}
            />
            <TextField
              size="small"
              label="شماره فرستنده"
              value={form.from_number || ""}
              onChange={(e) => updateForm({ from_number: e.target.value })}
              placeholder="+983000505"
              sx={{ minWidth: 180 }}
            />
          </Stack>

          {/* روش ارسال: الگو (Pattern) یا متن آزاد (Webservice) */}
          <TextField
            select
            size="small"
            label="روش ارسال"
            value={form.sending_type}
            onChange={(e) => updateForm({ sending_type: e.target.value })}
            sx={{ maxWidth: 260 }}
          >
            <MenuItem value="pattern">الگو (Pattern) — توصیه‌شده برای کد تأیید</MenuItem>
            <MenuItem value="webservice">متن آزاد (Webservice)</MenuItem>
          </TextField>

          {/* در حالت الگو کد الگو، در حالت متن آزاد قالب متن پیام با {code} */}
          {form.sending_type === "pattern" ? (
            <TextField
              size="small"
              label="کد الگو (Pattern Code)"
              value={form.pattern_code || ""}
              onChange={(e) => updateForm({ pattern_code: e.target.value })}
              helperText="از پنل ippanel، بعد از ساخت و تأییدشدن یک الگو (مثلاً «کد تأیید شما: #code#») به دست می‌آید"
              sx={{ maxWidth: 400 }}
            />
          ) : (
            <TextField
              size="small"
              label="متن پیام"
              value={form.webservice_message_template || ""}
              onChange={(e) => updateForm({ webservice_message_template: e.target.value })}
              placeholder="کد تأیید بازنشانی رمز عبور شما: {code}"
              helperText="عبارت {code} با کد تأیید واقعی جایگزین می‌شود"
              sx={{ maxWidth: 400 }}
            />
          )}

          {/* ارسال پیامک آزمایشی */}
          {testResult && <Alert severity={testResult.success ? "success" : "error"}>{testResult.message}</Alert>}
          <Stack direction="row" spacing={1.5} alignItems="center">
            <TextField
              size="small"
              label="موبایل تست"
              value={testMobile}
              onChange={(e) => setTestMobile(e.target.value)}
              placeholder="09123456789"
              sx={{ minWidth: 200 }}
            />
            <Button
              variant="outlined"
              size="small"
              onClick={handleTest}
              disabled={isTesting || !testMobile}
              startIcon={isTesting ? <CircularProgress size={14} /> : null}
            >
              ارسال پیامک آزمایشی
            </Button>
          </Stack>
        </Stack>
      )}

      {/* نتیجه‌ی ذخیره و دکمه‌ی ذخیره */}
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
    </Stack>
  );
}
