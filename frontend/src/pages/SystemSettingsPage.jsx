// صفحه‌ی تنظیمات سامانه (تنظیمات سراسری پرتال).
// آپلود لوگوها، آیکون PWA، Favicon و پس‌زمینه‌ی ورود؛ برندینگ هر جای نمایش؛ متن‌های تب مرورگر و نصب PWA؛
// و تنظیمات SMTP، پیامک و دروازه‌ی دسترسی.
import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Card, CircularProgress, Divider, Stack, TextField, Typography } from "@mui/material";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import {
  APP_LOGO_SMALL_URL,
  APP_LOGO_URL,
  deleteLoginBackground,
  deleteLogo,
  FAVICON_URL,
  fetchBranding,
  LOGIN_BACKGROUND_URL,
  PWA_ICON_URL,
  updateBranding,
  uploadLoginBackground,
  uploadLogo,
} from "../api/system";
import SmtpSettings from "../components/SmtpSettings";
import SmsSettings from "../components/SmsSettings";
import AccessGateSettings from "../components/AccessGateSettings";
import BrandingSurfaceEditor from "../components/BrandingSurfaceEditor";
import PwaIconSettings from "../components/PwaIconSettings";
import { SURFACE_META } from "../config/brandingSurfaces";

/**
 * کارت آپلود عکس با پیش‌نمایش و دکمه‌های انتخاب/آپلود/حذف (مشترک بین لوگوها، آیکون‌ها و پس‌زمینه‌ی ورود).
 * ورودی: عنوان، راهنما، URL عکس فعلی، نسبت ابعاد، حداکثر عرض، توابع آپلود/حذف و reloadOnChange
 * (بازخوانی کل صفحه پس از تغییر تا BrandingContext عکس جدید را بگیرد).
 */
function ImageUploadCard({ title, helperText, currentImageUrl, aspectRatio = "1 / 1", maxWidth = 200, uploadFn, deleteFn, reloadOnChange }) {
  const fileInputRef = useRef(null);
  const [previewUrl, setPreviewUrl] = useState(null);  // URL موقت پیش‌نمایش فایل انتخاب‌شده
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [imageVersion, setImageVersion] = useState(0);  // پارامتر ?v= برای دور زدن کش مرورگر پس از آپلود
  const [currentImageExists, setCurrentImageExists] = useState(true); // پیش‌فرض true؛ اگر بارگذاری عکس خطا دهد (۴۰۴) false می‌شود

  // فایل انتخاب‌شده را نگه می‌دارد و پیش‌نمایش آن را می‌سازد
  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setError("");
    setSuccess("");
  }

  // فایل انتخاب‌شده را آپلود می‌کند، پیش‌نمایش را پاک و نسخه‌ی عکس را افزایش می‌دهد
  async function handleUpload() {
    if (!selectedFile) return;
    setIsUploading(true);
    setError("");
    setSuccess("");
    try {
      await uploadFn(selectedFile);
      setSuccess("عکس با موفقیت به‌روزرسانی شد.");
      setSelectedFile(null);
      setPreviewUrl(null);
      setCurrentImageExists(true);
      setImageVersion((v) => v + 1);
      if (fileInputRef.current) fileInputRef.current.value = "";
      // BrandingContext فقط یک‌بار هنگام بارگذاری اپ خوانده می‌شود، پس صفحه بازخوانی می‌شود
      // تا بقیه‌ی بخش‌ها (اسپلش، صفحه‌ی ورود، نوار بالا و...) عکس جدید را نشان دهند
      if (reloadOnChange) window.location.reload();
    } catch (err) {
      setError(err.response?.data?.detail || "آپلود عکس با خطا مواجه شد.");
    } finally {
      setIsUploading(false);
    }
  }

  // عکس سفارشی را حذف می‌کند تا مقدار پیش‌فرض استفاده شود
  async function handleDelete() {
    setIsDeleting(true);
    setError("");
    setSuccess("");
    try {
      await deleteFn();
      setCurrentImageExists(false);
      setSuccess("عکس حذف شد — به پیش‌فرض برمی‌گردد.");
      if (reloadOnChange) window.location.reload();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف عکس با خطا مواجه شد.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <Box>
      <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.5 }}>
        {title}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.5 }}>
        {helperText}
      </Typography>

      {/* قاب پیش‌نمایش: فایل انتخاب‌شده، عکس فعلی یا حالت «تنظیم نشده» */}
      <Box
        sx={{
          width: "100%",
          maxWidth,
          aspectRatio,
          borderRadius: 2,
          border: "1px solid",
          borderColor: "divider",
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: "action.hover",
          mb: 1.5,
          backgroundImage: previewUrl
            ? `url(${previewUrl})`
            : currentImageExists
              ? `url(${currentImageUrl}?v=${imageVersion})`
              : "none",
          backgroundSize: "contain",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "center",
        }}
      >
        {!previewUrl && !currentImageExists && (
          <Stack alignItems="center" spacing={0.5} sx={{ color: "text.disabled" }}>
            <ImageOutlinedIcon sx={{ fontSize: 26 }} />
            <Typography variant="caption" sx={{ px: 1, textAlign: "center", fontSize: 10 }}>
              تنظیم نشده
            </Typography>
          </Stack>
        )}
        {/* img پنهان فقط برای تشخیص وجود عکس فعلی از طریق onError */}
        {!previewUrl && currentImageExists && (
          <img
            src={`${currentImageUrl}?v=${imageVersion}`}
            alt=""
            style={{ display: "none" }}
            onError={() => setCurrentImageExists(false)}
          />
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 1.5 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 1.5 }}>
          {success}
        </Alert>
      )}

      {/* دکمه‌های انتخاب، آپلود و حذف */}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Button component="label" size="small" variant="outlined" startIcon={<CloudUploadOutlinedIcon />}>
          انتخاب
          <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp,image/svg+xml" hidden onChange={handleFileChange} />
        </Button>
        <Button
          size="small"
          variant="contained"
          disabled={!selectedFile || isUploading}
          onClick={handleUpload}
          startIcon={isUploading ? <CircularProgress size={14} color="inherit" /> : null}
        >
          {isUploading ? "در حال آپلود..." : "آپلود"}
        </Button>
        {currentImageExists && (
          <Button size="small" variant="text" color="error" disabled={isDeleting} startIcon={<DeleteOutlineOutlinedIcon />} onClick={handleDelete}>
            حذف
          </Button>
        )}
      </Stack>
    </Box>
  );
}

/**
 * گروهی از فیلدهای متنی مرتبط با دکمه‌ی ذخیره‌ی مستقل خودشان.
 * ورودی: عنوان، راهنما، تعریف فیلدها، مقادیر، onChange(key, value)، onSave و وضعیت ذخیره/پیام‌ها.
 */
function TextFieldGroup({ title, helperText, fields, values, onChange, onSave, isSaving, error, success }) {
  return (
    <Box>
      <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.5 }}>
        {title}
      </Typography>
      {helperText && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.5 }}>
          {helperText}
        </Typography>
      )}
      <Stack spacing={1.5}>
        {fields.map((field) => (
          <TextField
            key={field.key}
            label={field.label}
            value={values[field.key]}
            onChange={(e) => onChange(field.key, e.target.value)}
            fullWidth
            size="small"
            multiline={field.multiline}
            minRows={field.multiline ? 2 : undefined}
            inputProps={field.maxLength ? { maxLength: field.maxLength } : undefined}
            helperText={field.helperText}
          />
        ))}
        {error && <Alert severity="error">{error}</Alert>}
        {success && <Alert severity="success">{success}</Alert>}
        <Stack direction="row" spacing={1.5}>
          <Button
            size="small"
            variant="contained"
            disabled={isSaving}
            startIcon={isSaving ? <CircularProgress size={14} color="inherit" /> : <SaveOutlinedIcon />}
            onClick={onSave}
          >
            ذخیره
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

// تعریف گروه‌های فیلد متنی برندینگ؛ هر گروه جداگانه ذخیره می‌شود (key فیلد = نام فیلد در /system/branding)
const FIELD_GROUPS = [
  {
    key: "browser",
    title: "عنوان تب مرورگر",
    fields: [{ key: "browser_title", label: "عنوان", maxLength: 100 }],
  },
  {
    key: "manifest",
    title: "متن‌های نصب PWA",
    helperText: "نام و توضیح اپ نصب‌شده (PWA) در ویندوز و گوشی.",
    fields: [
      {
        key: "manifest_name",
        label: "نام اپ",
        maxLength: 45,
        helperText: "ویندوز: منوی استارت و عنوان پنجره؛ اندروید: دیالوگ نصب. حداکثر ۴۵ حرف",
      },
      { key: "manifest_short_name", label: "نام کوتاه (زیر آیکون)", maxLength: 30, helperText: "حداکثر ۳۰ حرف — هرچه کوتاه‌تر بهتر" },
      { key: "manifest_description", label: "توضیح (در دیالوگ نصب)", maxLength: 200, multiline: true },
    ],
  },
];

/**
 * کامپوننت صفحه‌ی تنظیمات سامانه؛ ورودی ندارد.
 * داده‌های برندینگ را یک‌جا بارگذاری می‌کند و کارت‌های تنظیمات را رندر می‌کند؛ تغییرات بدون Restart سرور اعمال می‌شوند.
 */
export default function SystemSettingsPage() {
  const [values, setValues] = useState(null); // فیلدهای متنی — یک‌جا از /system/branding
  const [brandingData, setBrandingData] = useState(null); // پاسخ کامل (surfaces، pwa_icon، has_custom_*)
  const [savingGroup, setSavingGroup] = useState(null); // کدام گروه در حال ذخیره است
  const [groupMessages, setGroupMessages] = useState({}); // { [groupKey]: {error, success} }

  // بارگذاری برندینگ و استخراج فیلدهای متنی در values
  useEffect(() => {
    fetchBranding().then((data) => {
      setBrandingData(data);
      setValues({
        browser_title: data.browser_title,
        manifest_name: data.manifest_name,
        manifest_short_name: data.manifest_short_name,
        manifest_description: data.manifest_description,
        splash_title: data.splash_title,
        splash_subtitle: data.splash_subtitle,
        login_title: data.login_title,
        login_subtitle: data.login_subtitle,
        sidebar_title: data.sidebar_title,
        profile_title: data.profile_title,
        profile_subtitle: data.profile_subtitle,
        auth_title: data.auth_title,
        auth_subtitle: data.auth_subtitle,
      });
    });
  }, []);

  // مقدار یک فیلد متنی را به‌روز می‌کند
  function handleFieldChange(key, value) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  // فیلدهای یک گروه را (خالی = null) ذخیره و پیام نتیجه را برای همان گروه ثبت می‌کند
  async function handleSaveGroup(group) {
    setSavingGroup(group.key);
    setGroupMessages((prev) => ({ ...prev, [group.key]: {} }));
    try {
      const payload = {};
      for (const field of group.fields) {
        payload[field.key] = values[field.key]?.trim() || null;
      }
      const updated = await updateBranding(payload);
      // مقادیر برگشتی سرور جایگزین می‌شوند (برای فیلد خالی، سرور مقدار پیش‌فرض را برمی‌گرداند)
      setValues((prev) => ({ ...prev, ...Object.fromEntries(group.fields.map((f) => [f.key, updated[f.key]])) }));
      setGroupMessages((prev) => ({ ...prev, [group.key]: { success: "ذخیره شد." } }));
    } catch (err) {
      setGroupMessages((prev) => ({
        ...prev,
        [group.key]: { error: err.response?.data?.detail || "ذخیره با خطا مواجه شد." },
      }));
    } finally {
      setSavingGroup(null);
    }
  }

  // نشانگر بارگذاری تا رسیدن داده‌ها
  if (values === null) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>
        تنظیمات سامانه
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        تنظیمات سراسری کل پرتال — نام‌ها و لوگوها، هرکدام مستقل و مخصوص محل استفاده خودشان.
      </Typography>

      <Alert severity="info" sx={{ mb: 3 }}>
        برای کسانی که پرتال را از قبل روی صفحه اصلی گوشی نصب کرده‌اند، تغییر نام/آیکون
        معمولاً فقط با حذف و نصب دوباره اعمال می‌شود — این یک محدودیت مرورگرها/سیستم‌عامل‌هاست.
      </Alert>

      <Stack spacing={3}>
        {/* کارت لوگوها: لوگوی بزرگ، لوگوی کوچک، آیکون PWA و Favicon */}
        <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
          <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
            لوگوها
          </Typography>
          <Stack spacing={3}>
            <ImageUploadCard
              title="لوگوی درون‌برنامه‌ای (بزرگ)"
              helperText="لوگوی عمومی برای جاهایی که «لوگوی بزرگ» انتخاب شده (پیش‌فرض: اسپلش‌اسکرین، پنل کاربری). هر اندازه‌ای — jpg/png/webp/svg، حداکثر ۴ مگابایت."
              currentImageUrl={APP_LOGO_URL}
              uploadFn={(file) => uploadLogo("app-logo", file)}
              deleteFn={() => deleteLogo("app-logo")}
              reloadOnChange
            />
            <Divider />
            <ImageUploadCard
              title="لوگوی درون‌برنامه‌ای (کوچک)"
              helperText="لوگوی عمومی برای جاهایی که «لوگوی کوچک» انتخاب شده (پیش‌فرض: نوار بالای پنل، صفحه ورود). اگر آپلود نشود، همان لوگوی بزرگ استفاده می‌شود. هر جای نمایش می‌تواند در بخش خودش لوگوی اختصاصی جدا داشته باشد."
              currentImageUrl={APP_LOGO_SMALL_URL}
              uploadFn={(file) => uploadLogo("app-logo-small", file)}
              deleteFn={() => deleteLogo("app-logo-small")}
              reloadOnChange
            />
            <Divider />
            <ImageUploadCard
              title="آیکون نصب (PWA)"
              helperText="یک تصویر؛ نسخه‌های مخصوص اندروید/iOS/ویندوز خودکار از آن ساخته می‌شوند (تنظیم مقیاس در بخش «آیکون نصب در هر پلتفرم»). ترجیحاً PNG مربعی ۵۱۲×۵۱۲ با پس‌زمینه شفاف."
              currentImageUrl={PWA_ICON_URL}
              uploadFn={(file) => uploadLogo("pwa-icon", file)}
              deleteFn={() => deleteLogo("pwa-icon")}
              reloadOnChange
            />
            <Divider />
            <ImageUploadCard
              title="آیکون تب مرورگر (Favicon)"
              helperText="آیکون کوچک کنار عنوان، در تب مرورگر. ترجیحاً ۳۲×۳۲ یا ۱۹۲×۱۹۲ و مربعی."
              currentImageUrl={FAVICON_URL}
              uploadFn={(file) => uploadLogo("favicon", file)}
              deleteFn={() => deleteLogo("favicon")}
            />
          </Stack>
        </Card>

        {/* تنظیم آیکون نصب PWA برای هر پلتفرم */}
        <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
          <PwaIconSettings initial={brandingData?.pwa_icon} hasIcon={Boolean(brandingData?.has_custom_pwa_icon)} />
        </Card>

        {/* ویرایشگر برندینگ هر جای نمایش (لوگو، اندازه، مقیاس، قاب، متن‌ها با فونت و رنگ، پس‌زمینه) با پیش‌نمایش مستقل */}
        {SURFACE_META.map((meta) => (
          <Card key={meta.key} variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
            <BrandingSurfaceEditor
              meta={meta}
              initialConfig={brandingData?.surfaces?.[meta.key]}
              initialTitle={values[meta.titleKey]}
              initialSubtitle={meta.subtitleKey ? values[meta.subtitleKey] : ""}
            />
          </Card>
        ))}

        {/* گروه‌های فیلد متنی (عنوان تب مرورگر، متن‌های نصب PWA) */}
        {FIELD_GROUPS.map((group) => (
          <Card key={group.key} variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
            <TextFieldGroup
              title={group.title}
              helperText={group.helperText}
              fields={group.fields}
              values={values}
              onChange={handleFieldChange}
              onSave={() => handleSaveGroup(group)}
              isSaving={savingGroup === group.key}
              error={groupMessages[group.key]?.error}
              success={groupMessages[group.key]?.success}
            />
          </Card>
        ))}

        {/* عکس پس‌زمینه‌ی صفحه‌ی ورود */}
        <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
          <ImageUploadCard
            title="عکس پس‌زمینه صفحه ورود"
            helperText="پشت فرم ورود (صفحه‌ای که همه — حتی قبل از ورود — می‌بینند). فرمت jpg/png/webp، حداکثر ۸ مگابایت."
            currentImageUrl={LOGIN_BACKGROUND_URL}
            aspectRatio="16 / 9"
            maxWidth={480}
            uploadFn={uploadLoginBackground}
            deleteFn={deleteLoginBackground}
          />
        </Card>

        {/* تنظیمات ایمیل (SMTP)، پیامک و دروازه‌ی دسترسی */}
        <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
          <SmtpSettings />
        </Card>

        <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
          <SmsSettings />
        </Card>

        <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
          <AccessGateSettings />
        </Card>
      </Stack>
    </Box>
  );
}
