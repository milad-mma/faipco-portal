import { useEffect, useState } from "react";
import { Alert, Box, Button, CircularProgress, Grid, Slider, Stack, TextField, Typography } from "@mui/material";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import { PWA_ICON_VARIANT_URL, updatePwaIconSettings } from "../api/system";

/**
 * تنظیم آیکون‌های نصب (PWA) - طبق درخواست کاربر: لوگو روی اندروید/iOS/ویندوز
 * نه خیلی کوچک باشد نه خیلی بزرگ. سرور از یک تصویر، نسخه‌های استاندارد
 * می‌سازد (pwa_icon_service.py)؛ اینجا مقیاس و پس‌زمینه تنظیم و نتیجه هر
 * پلتفرم همان‌طور که واقعاً دیده می‌شود پیش‌نمایش می‌شود:
 *   اندروید: maskable، بریده‌شده به دایره (رایج‌ترین شکل)
 *   iOS: apple-touch-icon، گوشه‌گرد، بدون شفافیت
 *   ویندوز/کروم دسکتاپ: "any"، بدون برش
 */
function PlatformPreview({ label, src, radius, bg }) {
  return (
    <Stack alignItems="center" spacing={0.75}>
      <Box sx={{ width: 96, height: 96, borderRadius: radius, overflow: "hidden", bgcolor: bg, boxShadow: 1 }}>
        <img src={src} alt="" width={96} height={96} style={{ display: "block" }} />
      </Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Stack>
  );
}

export default function PwaIconSettings({ initial, hasIcon }) {
  const [values, setValues] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [previewVersion, setPreviewVersion] = useState(0);

  useEffect(() => setValues(initial), [initial]);

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      await updatePwaIconSettings(values);
      setPreviewVersion((v) => v + 1);
      setMessage({ severity: "success", text: "ذخیره شد. آیکون‌های تولیدشده به‌روز شدند." });
    } catch (err) {
      setMessage({ severity: "error", text: err.response?.data?.detail || "ذخیره با خطا مواجه شد." });
    } finally {
      setSaving(false);
    }
  }

  if (!hasIcon) {
    return (
      <Alert severity="info">
        بعد از آپلود «آیکون نصب (PWA)» در بخش لوگوها، اینجا می‌توانید مقیاس و پس‌زمینه آیکون را برای اندروید، iOS و
        ویندوز تنظیم و پیش‌نمایش کنید. برای بهترین نتیجه فایل PNG مربعی ۵۱۲×۵۱۲ با پس‌زمینه شفاف آپلود کنید.
      </Alert>
    );
  }

  const v = `${previewVersion}-${values.icon_scale}-${values.maskable_scale}-${values.background}-${values.any_background}`;
  // پیش‌نمایش با مقادیر ذخیره‌شده سرور رندر می‌شود؛ تا ذخیره نشود، نسخه قبلی دیده می‌شود
  return (
    <Box>
      <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
        آیکون نصب در هر پلتفرم
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 2 }}>
        از یک تصویر، نسخه مخصوص هر پلتفرم ساخته می‌شود. اندروید آیکون را دایره/گوشه‌گرد می‌بُرد و iOS شفافیت را سیاه
        می‌کند؛ به همین دلیل برای آن‌ها لوگو کوچک‌تر و روی پس‌زمینه پر قرار می‌گیرد. بعد از ذخیره، پیش‌نمایش‌ها به‌روز
        می‌شوند.
      </Typography>

      <Stack direction="row" spacing={3} justifyContent="center" flexWrap="wrap" useFlexGap sx={{ mb: 3 }}>
        <PlatformPreview label="اندروید" src={PWA_ICON_VARIANT_URL("maskable-192", v)} radius="50%" bg="transparent" />
        <PlatformPreview label="iOS" src={PWA_ICON_VARIANT_URL("apple-180", v)} radius="22%" bg="transparent" />
        <PlatformPreview label="ویندوز / دسکتاپ" src={PWA_ICON_VARIANT_URL("any-192", v)} radius={2} bg="action.hover" />
      </Stack>

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6}>
          <Typography variant="caption" color="text.secondary">
            اندازه لوگو در اندروید و iOS: {values.maskable_scale}٪ بوم
          </Typography>
          <Slider size="small" value={values.maskable_scale} min={30} max={90} onChange={(_, val) => setValues({ ...values, maskable_scale: val })} />
          <Typography variant="caption" color="text.disabled">
            ناحیه امن اندروید حدود ۸۰٪ است؛ ۶۰ تا ۷۰٪ معمولاً بهترین نتیجه را می‌دهد.
          </Typography>
        </Grid>
        <Grid item xs={12} sm={6}>
          <Typography variant="caption" color="text.secondary">
            اندازه لوگو در ویندوز / دسکتاپ: {values.icon_scale}٪ بوم
          </Typography>
          <Slider size="small" value={values.icon_scale} min={30} max={100} onChange={(_, val) => setValues({ ...values, icon_scale: val })} />
        </Grid>
        <Grid item xs={12} sm={6}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Box component="input" type="color" value={/^#[0-9a-fA-F]{6}$/.test(values.background) ? values.background : "#ffffff"} onChange={(e) => setValues({ ...values, background: e.target.value })} sx={{ width: 36, height: 36, p: 0, border: "1px solid", borderColor: "divider", borderRadius: 1, bgcolor: "transparent" }} />
            <TextField size="small" fullWidth label="پس‌زمینه اندروید / iOS" value={values.background} onChange={(e) => setValues({ ...values, background: e.target.value })} inputProps={{ dir: "ltr", style: { textAlign: "left" } }} />
          </Stack>
        </Grid>
        <Grid item xs={12} sm={6}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Box component="input" type="color" value={/^#[0-9a-fA-F]{6}$/.test(values.any_background) ? values.any_background : "#ffffff"} onChange={(e) => setValues({ ...values, any_background: e.target.value })} sx={{ width: 36, height: 36, p: 0, border: "1px solid", borderColor: "divider", borderRadius: 1, bgcolor: "transparent" }} />
            <TextField size="small" fullWidth label="پس‌زمینه ویندوز / دسکتاپ" value={values.any_background} onChange={(e) => setValues({ ...values, any_background: e.target.value })} placeholder="خالی = شفاف" inputProps={{ dir: "ltr", style: { textAlign: "left" } }} />
            {values.any_background && (
              <Button size="small" onClick={() => setValues({ ...values, any_background: "" })}>
                شفاف
              </Button>
            )}
          </Stack>
        </Grid>
      </Grid>

      {message && (
        <Alert severity={message.severity} sx={{ mt: 2 }}>
          {message.text}
        </Alert>
      )}
      <Button sx={{ mt: 2 }} variant="contained" startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />} disabled={saving} onClick={handleSave}>
        ذخیره
      </Button>
    </Box>
  );
}
