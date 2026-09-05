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

/**
 * یک کارت آپلود عکس با پیش‌نمایش + دکمه‌های انتخاب/آپلود/حذف — الگوی
 * مشترک بین هر سه لوگو و عکس پس‌زمینه ورود، برای جلوگیری از تکرار.
 */
function ImageUploadCard({ title, helperText, currentImageUrl, aspectRatio = "1 / 1", maxWidth = 200, uploadFn, deleteFn, reloadOnChange }) {
  const fileInputRef = useRef(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [imageVersion, setImageVersion] = useState(0);
  const [currentImageExists, setCurrentImageExists] = useState(true); // خوش‌بینانه — اگر ۴۰۴ بخورد، false می‌شود

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setError("");
    setSuccess("");
  }

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
      // ⚠️ BrandingContext فقط یک‌بار در بارگذاری اپ فچ می‌شود — بدون این
      // Reload، بقیه صفحات (اسپلش، صفحه ورود، نوار بالا، ...) تا Refresh
      // بعدی همچنان عکس قبلی را نشان می‌دادند.
      if (reloadOnChange) window.location.reload();
    } catch (err) {
      setError(err.response?.data?.detail || "آپلود عکس با خطا مواجه شد.");
    } finally {
      setIsUploading(false);
    }
  }

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
 * یک گروه از فیلدهای متنی مرتبط + دکمه ذخیره مستقل خودشان — هر گروه
 * (Manifest، اسپلش‌اسکرین، صفحه ورود) کاملاً مستقل ذخیره می‌شود.
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

const FIELD_GROUPS = [
  {
    key: "browser",
    title: "عنوان تب مرورگر",
    fields: [{ key: "browser_title", label: "عنوان", maxLength: 100 }],
  },
  {
    key: "manifest",
    title: "متن‌های نصب PWA",
    helperText: "زیر آیکون، روی صفحه اصلی گوشی بعد از نصب.",
    fields: [
      { key: "manifest_short_name", label: "نام کوتاه (زیر آیکون)", maxLength: 30, helperText: "حداکثر ۳۰ حرف — هرچه کوتاه‌تر بهتر" },
      { key: "manifest_description", label: "توضیح (در دیالوگ نصب)", maxLength: 200, multiline: true },
    ],
  },
  {
    key: "splash",
    title: "اسپلش‌اسکرین",
    helperText: "صفحه معرفی کوتاهی که هنگام باز‌شدن اپ دیده می‌شود.",
    fields: [
      { key: "splash_title", label: "عنوان", maxLength: 100 },
      { key: "splash_subtitle", label: "زیرعنوان", maxLength: 100 },
    ],
  },
  {
    key: "login",
    title: "صفحه ورود",
    fields: [
      { key: "login_title", label: "عنوان", maxLength: 100 },
      { key: "login_subtitle", label: "زیرعنوان", maxLength: 100 },
    ],
  },
  {
    key: "sidebar",
    title: "نوار بالای پنل",
    helperText: "متن کنار لوگو، در نوار بالای همه صفحات داخل پنل.",
    fields: [{ key: "sidebar_title", label: "عنوان", maxLength: 50 }],
  },
  {
    key: "profile",
    title: "پنل کاربری",
    helperText: "زیر لوگو، در صفحه پروفایل هر کاربر.",
    fields: [
      { key: "profile_title", label: "عنوان", maxLength: 100 },
      { key: "profile_subtitle", label: "زیرعنوان", maxLength: 100 },
    ],
  },
];

/**
 * تنظیمات سامانه — تنظیمات سراسری کل پرتال، قابل‌تغییر بدون نیاز به
 * کد‌نویسی یا Restart سرور.
 */
export default function SystemSettingsPage() {
  const [values, setValues] = useState(null); // فیلدهای متنی — یک‌جا از /system/branding
  const [savingGroup, setSavingGroup] = useState(null); // کدام گروه در حال ذخیره است
  const [groupMessages, setGroupMessages] = useState({}); // { [groupKey]: {error, success} }

  useEffect(() => {
    fetchBranding().then((data) => {
      setValues({
        browser_title: data.browser_title,
        manifest_short_name: data.manifest_short_name,
        manifest_description: data.manifest_description,
        splash_title: data.splash_title,
        splash_subtitle: data.splash_subtitle,
        login_title: data.login_title,
        login_subtitle: data.login_subtitle,
        sidebar_title: data.sidebar_title,
        profile_title: data.profile_title,
        profile_subtitle: data.profile_subtitle,
      });
    });
  }, []);

  function handleFieldChange(key, value) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSaveGroup(group) {
    setSavingGroup(group.key);
    setGroupMessages((prev) => ({ ...prev, [group.key]: {} }));
    try {
      const payload = {};
      for (const field of group.fields) {
        payload[field.key] = values[field.key]?.trim() || null;
      }
      const updated = await updateBranding(payload);
      // مقادیر واقعی برگشتی از سرور را جایگزین می‌کنیم (اگر خالی فرستاده
      // بودیم، سرور مقدار پیش‌فرض را برگردانده — این‌جا هم باید دیده شود)
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
        <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
          <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
            لوگوها
          </Typography>
          <Stack spacing={3}>
            <ImageUploadCard
              title="لوگوی درون‌برنامه‌ای (بزرگ)"
              helperText="اسپلش‌اسکرین، پنل کاربری. هر اندازه‌ای — jpg/png/webp/svg، حداکثر ۴ مگابایت."
              currentImageUrl={APP_LOGO_URL}
              uploadFn={(file) => uploadLogo("app-logo", file)}
              deleteFn={() => deleteLogo("app-logo")}
              reloadOnChange
            />
            <Divider />
            <ImageUploadCard
              title="لوگوی درون‌برنامه‌ای (کوچک)"
              helperText="نوار بالای پنل، صفحه ورود. اگر آپلود نشود، همان لوگوی بزرگ (با اندازه کوچک‌تر) استفاده می‌شود — برای بهترین نتیجه در اندازه‌های خیلی کوچک، یک نسخه ساده‌شده/نمادین جداگانه آپلود کنید."
              currentImageUrl={APP_LOGO_SMALL_URL}
              uploadFn={(file) => uploadLogo("app-logo-small", file)}
              deleteFn={() => deleteLogo("app-logo-small")}
              reloadOnChange
            />
            <Divider />
            <ImageUploadCard
              title="آیکون نصب (PWA)"
              helperText="آیکون روی صفحه اصلی گوشی بعد از نصب. ترجیحاً ۵۱۲×۵۱۲ و مربعی."
              currentImageUrl={PWA_ICON_URL}
              uploadFn={(file) => uploadLogo("pwa-icon", file)}
              deleteFn={() => deleteLogo("pwa-icon")}
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

        <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
          <SmtpSettings />
        </Card>

        <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
          <SmsSettings />
        </Card>
      </Stack>
    </Box>
  );
}
