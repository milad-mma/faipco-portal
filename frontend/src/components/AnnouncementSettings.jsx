import { useEffect, useState } from "react";
import { Alert, Box, Button, CircularProgress, FormControlLabel, Stack, Switch, TextField, Typography } from "@mui/material";
import { fetchAnnouncementSettings, updateAnnouncementSettings } from "../api/announcement";
import LinkifiedText from "./LinkifiedText";

/**
 * ویرایشگر «اعلان تغییرات پرتال» برای ادمین.
 * بدون ورودی (props). فرم فعال/غیرفعال، عنوان و متن اعلان را همراه با پیش‌نمایش لینک‌ها رسم می‌کند
 * و با «ذخیره و انتشار» به سرور می‌فرستد.
 * با تغییر عنوان یا متن، سرور نسخه‌ی اعلان را بالا می‌برد و اعلان برای همه‌ی کاربران
 * (حتی کسانی که «دیگر نمایش نده» زده‌اند) دوباره نمایش داده می‌شود.
 */
export default function AnnouncementSettings() {
  const [form, setForm] = useState(null); // {enabled, title, body, version}؛ null = در حال بارگذاری
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(""); // پیام موفقیت ذخیره
  const [isSaving, setIsSaving] = useState(false);

  // بارگذاری تنظیمات فعلی؛ در صورت خطا فرم خالی نمایش داده می‌شود
  useEffect(() => {
    fetchAnnouncementSettings()
      .then(setForm)
      .catch((err) => {
        setError(err.response?.data?.detail || "دریافت تنظیمات اعلان با خطا مواجه شد.");
        setForm({ enabled: false, title: "", body: "", version: 0 });
      });
  }, []);

  // ذخیره‌ی فرم در سرور و نمایش شماره‌ی نسخه‌ی جدید اعلان
  async function handleSave() {
    setError("");
    setSaved("");
    setIsSaving(true);
    try {
      const result = await updateAnnouncementSettings(form);
      setForm(result);
      setSaved(
        result.version > 0
          ? `ذخیره شد (نسخه ${result.version.toLocaleString("fa-IR")}).`
          : "ذخیره شد."
      );
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره تنظیمات با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  // لودر تا زمان دریافت تنظیمات
  if (form === null) {
    return (
      <Stack alignItems="center" sx={{ py: 3 }}>
        <CircularProgress size={28} />
      </Stack>
    );
  }

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>
        اعلان تغییرات پرتال
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        این متن هنگام ورود کاربران به پرتال، در یک پنجره نمایش داده می‌شود. کاربر می‌تواند «بستن» بزند
        (دفعه بعد دوباره می‌بیند) یا «دیگر نمایش نده» را انتخاب کند.
      </Typography>

      {/* پیام‌های خطا و موفقیت */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {saved && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {saved}
        </Alert>
      )}

      {/* هشدار نمایش مجدد اعلان برای همه پس از تغییر */}
      <Alert severity="info" sx={{ mb: 2 }}>
        با تغییر عنوان یا متن، این اعلان برای <strong>همه کاربران</strong> دوباره نمایش داده می‌شود —
        حتی کسانی که قبلاً «دیگر نمایش نده» را زده بودند.
      </Alert>

      {/* فیلدهای فرم */}
      <Stack spacing={2}>
        <FormControlLabel
          control={
            <Switch
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              disabled={isSaving}
            />
          }
          label="نمایش اعلان هنگام ورود کاربران"
        />
        <TextField
          label="عنوان"
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          disabled={isSaving}
          size="small"
          fullWidth
        />
        <TextField
          label="متن اعلان"
          value={form.body}
          onChange={(e) => setForm({ ...form, body: e.target.value })}
          disabled={isSaving}
          multiline
          minRows={6}
          fullWidth
          helperText="شکست خطوط حفظ می‌شود. برای لینک: [متن لینک](https://example.com) یا مسیر داخلی پرتال مثل [درخواست مرخصی](/leave-requests)؛ آدرس خام https://... هم خودکار لینک می‌شود."
          inputProps={{ dir: "auto" }}
        />
        {/* پیش‌نمایش لینک‌ها؛ فقط وقتی متن شامل «[» یا آدرس http باشد نمایش داده می‌شود */}
        {/[\[]|https?:\/\//.test(form.body) && (
          <Box sx={{ p: 1.5, border: "1px dashed", borderColor: "divider", borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary">
              پیش‌نمایش
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", lineHeight: 2 }}>
              <LinkifiedText text={form.body} />
            </Typography>
          </Box>
        )}
        <Box>
          <Button variant="contained" onClick={handleSave} disabled={isSaving}>
            {isSaving ? "در حال ذخیره..." : "ذخیره و انتشار"}
          </Button>
        </Box>
      </Stack>
    </Box>
  );
}
