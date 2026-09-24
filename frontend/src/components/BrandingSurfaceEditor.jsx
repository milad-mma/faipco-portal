/**
 * ویرایشگر برندینگ یک «جای نمایش» (splash، login، auth، sidebar، profile) در تنظیمات سامانه:
 * لوگو (پیش‌فرض/اختصاصی/هیچ)، اندازه‌ی موبایل/دسکتاپ، مقیاس، قاب، عنوان و زیرعنوان با اندازه
 * و رنگ جداگانه، پس‌زمینه و پیش‌نمایش زنده.
 * شامل کامپوننت‌های کمکی ColorField، SliderField و SurfacePreview.
 */
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  FormControlLabel,
  Grid,
  MenuItem,
  Slider,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import { deleteLogo, resetBrandingSurface, updateBranding, updateBrandingSurface, uploadLogo } from "../api/system";
import { useBranding } from "../context/BrandingContext";
import BrandLogo, { surfaceTitleSx } from "./BrandLogo";

// حداکثر اندازه‌ی لوگو (px) در اسلایدرها به تفکیک جای نمایش
const SIZE_MAX = { splash: 300, login: 120, auth: 120, sidebar: 80, profile: 160 };

/**
 * فیلد رنگ: انتخابگر رنگ مرورگر + فیلد متنی برای مقدار دلخواه (hex یا rgba).
 * ورودی: label، value، onChange و allowEmpty (خالی = رنگ پیش‌فرض تم).
 */
function ColorField({ label, value, onChange, allowEmpty }) {
  // انتخابگر رنگ فقط hex شش‌رقمی می‌پذیرد؛ برای مقادیر دیگر سفید نشان داده می‌شود
  const isHex = /^#[0-9a-fA-F]{6}$/.test(value || "");
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Box
        component="input"
        type="color"
        value={isHex ? value : "#ffffff"}
        onChange={(e) => onChange(e.target.value)}
        sx={{ width: 36, height: 36, p: 0, border: "1px solid", borderColor: "divider", borderRadius: 1, bgcolor: "transparent", cursor: "pointer" }}
      />
      <TextField
        size="small"
        label={label}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={allowEmpty ? "پیش‌فرض تم" : "#RRGGBB یا rgba(...)"}
        fullWidth
        inputProps={{ dir: "ltr", style: { textAlign: "left" } }} // style درون‌خطی عمداً استفاده شده تا stylis-plugin-rtl آن را برنگرداند و مقدار چپ‌چین بماند
      />
    </Stack>
  );
}

// اسلایدر عددی با برچسب و نمایش مقدار فعلی به‌همراه واحد
function SliderField({ label, value, min, max, unit = "px", onChange }) {
  return (
    <Box>
      <Stack direction="row" justifyContent="space-between">
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="caption" fontWeight={700}>
          {Number(value).toLocaleString("fa-IR")} {unit}
        </Typography>
      </Stack>
      <Slider size="small" value={Number(value)} min={min} max={max} onChange={(_, v) => onChange(v)} />
    </Box>
  );
}

/**
 * پیش‌نمایش زنده‌ی جای نمایش با مقادیر ذخیره‌نشده.
 * ورودی: surface، cfg (تنظیمات در حال ویرایش)، title، subtitle و previewLogoUrl.
 * برای login/auth/sidebar لوگو و متن کنار هم (ردیفی) و برای بقیه زیر هم و وسط‌چین نمایش داده می‌شوند.
 */
function SurfacePreview({ surface, cfg, title, subtitle, previewLogoUrl }) {
  const dark = cfg.title_color && cfg.title_color.toLowerCase().startsWith("#f"); // رنگ عنوان روشن (#f...) = پس‌زمینه‌ی پیش‌فرض تیره لازم است
  const isRow = surface === "login" || surface === "auth" || surface === "sidebar";
  return (
    <Box
      sx={{
        borderRadius: 2,
        border: "1px solid",
        borderColor: "divider",
        background: cfg.background || (dark ? "#3476ad" : "background.paper"),
        p: 2.5,
        minHeight: 120,
        display: "flex",
        flexDirection: isRow ? "row" : "column",
        alignItems: "center",
        justifyContent: isRow ? "flex-start" : "center",
        gap: 1.5,
        textAlign: isRow ? "start" : "center",
      }}
    >
      <BrandLogo surface={surface} override={cfg} previewLogoUrl={previewLogoUrl} alt="" />
      <Box sx={{ minWidth: 0 }}>
        {cfg.show_title && (
          <Typography noWrap sx={{ color: cfg.title_color || "primary.main", ...surfaceTitleSx(cfg, "title") }}>
            {title || "عنوان"}
          </Typography>
        )}
        {cfg.show_subtitle && (
          <Typography noWrap sx={{ color: cfg.subtitle_color || "text.secondary", ...surfaceTitleSx(cfg, "subtitle") }}>
            {subtitle || "زیرعنوان"}
          </Typography>
        )}
      </Box>
    </Box>
  );
}

/**
 * ویرایشگر اصلی یک جای نمایش.
 * ورودی: meta (key، label، hint، titleKey و subtitleKey برای کلیدهای متن در تنظیمات برندینگ)،
 * initialConfig (تنظیمات فعلی جای نمایش)، initialTitle و initialSubtitle.
 * ذخیره در دو مرحله است: متن‌ها با updateBranding و بقیه با updateBrandingSurface؛ سپس صفحه
 * رفرش می‌شود تا BrandingContext (که فقط یک‌بار در شروع دریافت می‌شود) مقادیر جدید را بگیرد.
 */
export default function BrandingSurfaceEditor({ meta, initialConfig, initialTitle, initialSubtitle }) {
  const branding = useBranding();
  const [cfg, setCfg] = useState(initialConfig); // تنظیمات در حال ویرایش جای نمایش
  const [title, setTitle] = useState(initialTitle || "");
  const [subtitle, setSubtitle] = useState(initialSubtitle || "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null); // {severity, text} پیام نتیجه
  const [logoFile, setLogoFile] = useState(null); // فایل لوگوی انتخاب‌شده که هنوز آپلود نشده
  const [logoPreview, setLogoPreview] = useState(null); // object URL فایل انتخاب‌شده برای پیش‌نمایش
  const [logoBusy, setLogoBusy] = useState(false);
  const fileRef = useRef(null);
  const hasCustomLogo = Boolean(branding.surfaceLogoUrls?.[meta.key]); // آیا لوگوی اختصاصی برای این جای نمایش آپلود شده است

  // همگام‌سازی فرم با تنظیمات اولیه در صورت تغییر آن از والد
  useEffect(() => setCfg(initialConfig), [initialConfig]);

  // سازنده‌ی setter برای یک کلید تنظیمات: set("frame")(value)
  const set = (key) => (value) => setCfg((prev) => ({ ...prev, [key]: value }));

  // ذخیره‌ی متن‌ها (خالی = null یعنی مقدار پیش‌فرض) و تنظیمات جای نمایش، سپس رفرش صفحه
  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const textPayload = { [meta.titleKey]: title.trim() || null };
      if (meta.subtitleKey) textPayload[meta.subtitleKey] = subtitle.trim() || null;
      await updateBranding(textPayload);
      await updateBrandingSurface(meta.key, cfg);
      setMessage({ severity: "success", text: "ذخیره شد — صفحه برای اعمال تازه می‌شود..." });
      setTimeout(() => window.location.reload(), 800);
    } catch (err) {
      setMessage({ severity: "error", text: err.response?.data?.detail || "ذخیره با خطا مواجه شد." });
    } finally {
      setSaving(false);
    }
  }

  // بازگرداندن تنظیمات این جای نمایش به پیش‌فرض و رفرش صفحه
  async function handleReset() {
    setSaving(true);
    setMessage(null);
    try {
      await resetBrandingSurface(meta.key);
      setMessage({ severity: "success", text: "به پیش‌فرض برگشت — صفحه تازه می‌شود..." });
      setTimeout(() => window.location.reload(), 800);
    } catch (err) {
      setMessage({ severity: "error", text: err.response?.data?.detail || "بازنشانی با خطا مواجه شد." });
      setSaving(false);
    }
  }

  // آپلود لوگوی اختصاصی، تنظیم منبع لوگو روی custom و رفرش صفحه
  async function handleLogoUpload() {
    if (!logoFile) return;
    setLogoBusy(true);
    setMessage(null);
    try {
      await uploadLogo(`surface-${meta.key}`, logoFile);
      await updateBrandingSurface(meta.key, { ...cfg, logo_source: "custom" });
      setMessage({ severity: "success", text: "لوگوی اختصاصی آپلود شد — صفحه تازه می‌شود..." });
      setTimeout(() => window.location.reload(), 800);
    } catch (err) {
      setMessage({ severity: "error", text: err.response?.data?.detail || "آپلود لوگو با خطا مواجه شد." });
      setLogoBusy(false);
    }
  }

  // حذف لوگوی اختصاصی، برگرداندن منبع لوگو به default و رفرش صفحه
  async function handleLogoDelete() {
    setLogoBusy(true);
    try {
      await deleteLogo(`surface-${meta.key}`);
      await updateBrandingSurface(meta.key, { logo_source: "default" });
      setTimeout(() => window.location.reload(), 500);
    } catch (err) {
      setMessage({ severity: "error", text: err.response?.data?.detail || "حذف لوگو با خطا مواجه شد." });
      setLogoBusy(false);
    }
  }

  const sizeMax = SIZE_MAX[meta.key] || 200; // سقف اسلایدرهای اندازه‌ی لوگو

  return (
    <Box>
      <Typography variant="subtitle1" fontWeight={700}>
        {meta.label}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 2 }}>
        {meta.hint}
      </Typography>

      {/* پیش‌نمایش زنده */}
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
        پیش‌نمایش (اندازه دسکتاپ؛ در موبایل اندازه‌های موبایل اعمال می‌شوند)
      </Typography>
      <SurfacePreview surface={meta.key} cfg={cfg} title={title} subtitle={subtitle} previewLogoUrl={logoPreview} />

      {/* بخش لوگو: منبع، آپلود/حذف لوگوی اختصاصی، اندازه‌ها، مقیاس و قاب */}
      <Divider sx={{ my: 2.5 }}>
        <Typography variant="caption">لوگو</Typography>
      </Divider>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6}>
          <TextField select size="small" fullWidth label="منبع لوگو" value={cfg.logo_source} onChange={(e) => set("logo_source")(e.target.value)}>
            <MenuItem value="default">لوگوی عمومی</MenuItem>
            <MenuItem value="custom" disabled={!hasCustomLogo && !logoFile}>
              لوگوی اختصاصی این بخش{!hasCustomLogo ? " (آپلود نشده)" : ""}
            </MenuItem>
            <MenuItem value="none">بدون لوگو</MenuItem>
          </TextField>
        </Grid>
        {cfg.logo_source === "default" && (
          <Grid item xs={12} sm={6}>
            <TextField select size="small" fullWidth label="کدام لوگوی عمومی" value={cfg.default_logo} onChange={(e) => set("default_logo")(e.target.value)}>
              <MenuItem value="app_logo">لوگوی بزرگ</MenuItem>
              <MenuItem value="app_logo_small">لوگوی کوچک</MenuItem>
            </TextField>
          </Grid>
        )}
        <Grid item xs={12}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
            <Button component="label" size="small" variant="outlined" startIcon={<CloudUploadOutlinedIcon />}>
              انتخاب لوگوی اختصاصی
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/svg+xml"
                hidden
                onChange={(e) => {
                  // انتخاب فایل: پیش‌نمایش فوری و تغییر منبع لوگو به custom (آپلود با دکمه‌ی «آپلود»)
                  const f = e.target.files?.[0];
                  if (!f) return;
                  setLogoFile(f);
                  setLogoPreview(URL.createObjectURL(f));
                  set("logo_source")("custom");
                }}
              />
            </Button>
            <Button size="small" variant="contained" disabled={!logoFile || logoBusy} onClick={handleLogoUpload} startIcon={logoBusy ? <CircularProgress size={14} color="inherit" /> : null}>
              آپلود
            </Button>
            {hasCustomLogo && (
              <Button size="small" color="error" disabled={logoBusy} startIcon={<DeleteOutlineOutlinedIcon />} onClick={handleLogoDelete}>
                حذف لوگوی اختصاصی
              </Button>
            )}
          </Stack>
        </Grid>
        {/* تنظیمات اندازه و قاب فقط وقتی لوگو نمایش داده می‌شود */}
        {cfg.logo_source !== "none" && (
          <>
            <Grid item xs={12} sm={4}>
              <SliderField label="اندازه در موبایل" value={cfg.logo_size_mobile} min={8} max={sizeMax} onChange={set("logo_size_mobile")} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <SliderField label="اندازه در دسکتاپ" value={cfg.logo_size_desktop} min={8} max={sizeMax} onChange={set("logo_size_desktop")} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <SliderField label="مقیاس تصویر داخل کادر" value={cfg.logo_scale} min={25} max={300} unit="٪" onChange={set("logo_scale")} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField select size="small" fullWidth label="قاب دور لوگو" value={cfg.frame} onChange={(e) => set("frame")(e.target.value)}>
                <MenuItem value="none">بدون قاب</MenuItem>
                <MenuItem value="circle">دایره</MenuItem>
                <MenuItem value="rounded">مربع گوشه‌گرد</MenuItem>
              </TextField>
            </Grid>
            {cfg.frame !== "none" && (
              <>
                <Grid item xs={12} sm={4}>
                  <ColorField label="رنگ قاب" value={cfg.frame_color} onChange={set("frame_color")} />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <SliderField label="فاصله لوگو تا لبه قاب" value={cfg.frame_padding} min={0} max={80} onChange={set("frame_padding")} />
                </Grid>
              </>
            )}
          </>
        )}
      </Grid>

      {/* بخش متن‌ها: عنوان و زیرعنوان با نمایش، اندازه، ضخامت و رنگ */}
      <Divider sx={{ my: 2.5 }}>
        <Typography variant="caption">متن‌ها</Typography>
      </Divider>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={8}>
          <TextField size="small" fullWidth label="عنوان" value={title} onChange={(e) => setTitle(e.target.value)} inputProps={{ maxLength: 100 }} placeholder={meta.key === "auth" ? "خالی = عنوان صفحه ورود" : ""} />
        </Grid>
        <Grid item xs={12} sm={4}>
          <FormControlLabel control={<Switch checked={cfg.show_title} onChange={(e) => set("show_title")(e.target.checked)} />} label="نمایش عنوان" />
        </Grid>
        <Grid item xs={12} sm={4}>
          <SliderField label="اندازه عنوان (موبایل)" value={cfg.title_size_mobile} min={8} max={64} onChange={set("title_size_mobile")} />
        </Grid>
        <Grid item xs={12} sm={4}>
          <SliderField label="اندازه عنوان (دسکتاپ)" value={cfg.title_size_desktop} min={8} max={64} onChange={set("title_size_desktop")} />
        </Grid>
        <Grid item xs={12} sm={4}>
          {/* ضخامت فونت به نزدیک‌ترین مضرب ۱۰۰ گرد می‌شود */}
          <SliderField label="ضخامت عنوان" value={cfg.title_weight} min={300} max={900} unit="" onChange={(v) => set("title_weight")(Math.round(v / 100) * 100)} />
        </Grid>
        <Grid item xs={12} sm={6}>
          <ColorField label="رنگ عنوان" value={cfg.title_color} onChange={set("title_color")} allowEmpty />
        </Grid>
        {/* فیلدهای زیرعنوان فقط برای جای نمایش‌هایی که زیرعنوان دارند */}
        {meta.subtitleKey && (
          <>
            <Grid item xs={12} sm={8}>
              <TextField size="small" fullWidth label="زیرعنوان" value={subtitle} onChange={(e) => setSubtitle(e.target.value)} inputProps={{ maxLength: 100 }} placeholder={meta.key === "auth" ? "خالی = زیرعنوان صفحه ورود" : ""} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControlLabel control={<Switch checked={cfg.show_subtitle} onChange={(e) => set("show_subtitle")(e.target.checked)} />} label="نمایش زیرعنوان" />
            </Grid>
            <Grid item xs={12} sm={4}>
              <SliderField label="اندازه زیرعنوان (موبایل)" value={cfg.subtitle_size_mobile} min={8} max={48} onChange={set("subtitle_size_mobile")} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <SliderField label="اندازه زیرعنوان (دسکتاپ)" value={cfg.subtitle_size_desktop} min={8} max={48} onChange={set("subtitle_size_desktop")} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <ColorField label="رنگ زیرعنوان" value={cfg.subtitle_color} onChange={set("subtitle_color")} allowEmpty />
            </Grid>
          </>
        )}
      </Grid>

      {/* بخش پس‌زمینه: مقدار CSS دلخواه (رنگ یا gradient) */}
      <Divider sx={{ my: 2.5 }}>
        <Typography variant="caption">پس‌زمینه</Typography>
      </Divider>
      <TextField
        size="small"
        fullWidth
        label="رنگ یا گرادیان پس‌زمینه (CSS)"
        value={cfg.background || ""}
        onChange={(e) => set("background")(e.target.value)}
        placeholder="مثلاً #1468A7 یا linear-gradient(110deg, #3476ad, #2b91a5) — خالی = پیش‌فرض"
        inputProps={{ dir: "ltr", style: { textAlign: "left" }, maxLength: 300 }} // style درون‌خطی عمداً برای چپ‌چین ماندن (بدون برگردان RTL)
      />

      {/* پیام نتیجه و دکمه‌های ذخیره/بازنشانی */}
      {message && (
        <Alert severity={message.severity} sx={{ mt: 2 }}>
          {message.text}
        </Alert>
      )}
      <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
        <Button variant="contained" startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />} disabled={saving} onClick={handleSave}>
          ذخیره
        </Button>
        <Button variant="text" color="inherit" startIcon={<RefreshOutlinedIcon />} disabled={saving} onClick={handleReset}>
          بازگشت به پیش‌فرض
        </Button>
      </Stack>
    </Box>
  );
}
