import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Card, CircularProgress, Stack, TextField, Typography } from "@mui/material";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import RestartAltOutlinedIcon from "@mui/icons-material/RestartAltOutlined";
import {
  APP_LOGO_URL,
  deleteAppLogo,
  deleteLoginBackground,
  fetchBranding,
  LOGIN_BACKGROUND_URL,
  updateBranding,
  uploadAppLogo,
  uploadLoginBackground,
} from "../api/system";

/**
 * یک کارت آپلود عکس با پیش‌نمایش + دکمه‌های انتخاب/آپلود/حذف — الگوی
 * مشترک بین «لوگوی اپ» و «عکس پس‌زمینه صفحه ورود»، برای جلوگیری از تکرار.
 */
function ImageUploadCard({
  title,
  helperText,
  currentImageUrl,
  aspectRatio = "1 / 1",
  maxWidth = 220,
  uploadFn,
  deleteFn,
  onChanged,
}) {
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
      onChanged?.();
    } catch (err) {
      setError(err.response?.data?.detail || "آپلود عکس ناموفق بود.");
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
      onChanged?.();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف عکس ناموفق بود.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
      <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
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
          mb: 2,
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
          <Stack alignItems="center" spacing={1} sx={{ color: "text.disabled" }}>
            <ImageOutlinedIcon sx={{ fontSize: 32 }} />
            <Typography variant="caption" sx={{ px: 1, textAlign: "center" }}>
              هنوز عکسی تنظیم نشده
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
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
        <Button component="label" variant="outlined" startIcon={<CloudUploadOutlinedIcon />}>
          انتخاب عکس
          <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp,image/svg+xml" hidden onChange={handleFileChange} />
        </Button>
        <Button
          variant="contained"
          disabled={!selectedFile || isUploading}
          onClick={handleUpload}
          startIcon={isUploading ? <CircularProgress size={16} color="inherit" /> : null}
        >
          {isUploading ? "در حال آپلود..." : "آپلود و اعمال"}
        </Button>
        {currentImageExists && (
          <Button
            variant="text"
            color="error"
            disabled={isDeleting}
            startIcon={<DeleteOutlineOutlinedIcon />}
            onClick={handleDelete}
          >
            {isDeleting ? "در حال حذف..." : "حذف عکس"}
          </Button>
        )}
      </Stack>
    </Card>
  );
}

/**
 * تنظیمات سامانه — تنظیمات سراسری کل پرتال، قابل‌تغییر بدون نیاز به
 * کد‌نویسی یا Restart سرور. فعلاً دو بخش: برندینگ (نام/لوگوی اپ در همه‌جای
 * پروژه — از‌جمله PWA روی اندروید/آیفون/ویندوز) و عکس پس‌زمینه صفحه ورود.
 */
export default function SystemSettingsPage() {
  return (
    <Box sx={{ maxWidth: 560, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>
        تنظیمات سامانه
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        تنظیمات سراسری کل پرتال.
      </Typography>

      <Stack spacing={3}>
        <BrandingSection />

        <ImageUploadCard
          title="عکس پس‌زمینه صفحه ورود"
          helperText="این عکس پشت فرم ورود (صفحه‌ای که همه — حتی قبل از ورود — می‌بینند) نمایش داده می‌شود. فرمت jpg/png/webp، حداکثر ۸ مگابایت."
          currentImageUrl={LOGIN_BACKGROUND_URL}
          aspectRatio="16 / 9"
          maxWidth={480}
          uploadFn={uploadLoginBackground}
          deleteFn={deleteLoginBackground}
        />
      </Stack>
    </Box>
  );
}

/**
 * نام/اسم‌کوتاه/توضیح + لوگوی اپ — همان چیزهایی که تا امروز همه‌جای پروژه
 * (اسپلش‌اسکرین، صفحه ورود، نوار بالای پنل، Manifest نصب PWA) به‌صورت
 * ثابت («فایپکو»، «شرکت تولیدی صنعتی فوادالیاف») نوشته شده بود.
 */
function BrandingSection() {
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [description, setDescription] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    fetchBranding().then((data) => {
      setName(data.name);
      setShortName(data.short_name);
      setDescription(data.description);
    });
  }, []);

  async function handleSave() {
    setIsSaving(true);
    setError("");
    setSuccess("");
    try {
      await updateBranding({
        name: name.trim() || null,
        short_name: shortName.trim() || null,
        description: description.trim() || null,
      });
      setSuccess("ذخیره شد — صفحه را رفرش کنید تا همه‌جا اعمال شود.");
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReset() {
    setIsSaving(true);
    setError("");
    setSuccess("");
    try {
      const data = await updateBranding({ name: null, short_name: null, description: null });
      setName(data.name);
      setShortName(data.short_name);
      setDescription(data.description);
      setSuccess("به مقادیر پیش‌فرض بازگشت.");
    } catch (err) {
      setError(err.response?.data?.detail || "بازگرداندن ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
      <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
        نام و لوگوی سامانه
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        در اسپلش‌اسکرین، صفحه ورود، نوار بالای پنل، و نام/آیکون اپ روی اندروید/آیفون/ویندوز (بعد از نصب) استفاده می‌شود.
      </Typography>

      <ImageUploadCard
        title="لوگو"
        helperText="ترجیحاً یک تصویر مربعی حداقل ۵۱۲×۵۱۲ (jpg/png/webp/svg، حداکثر ۴ مگابایت) — همین یک لوگو برای همه‌جای پروژه و همه اندازه‌های آیکون PWA استفاده می‌شود."
        currentImageUrl={APP_LOGO_URL}
        uploadFn={uploadAppLogo}
        deleteFn={deleteAppLogo}
        onChanged={() => window.location.reload()}
      />

      <Stack spacing={2} sx={{ mt: 3 }}>
        <TextField
          label="نام کامل سامانه"
          value={name}
          onChange={(e) => setName(e.target.value)}
          fullWidth
          helperText="در اسپلش‌اسکرین، صفحه ورود و عنوان تب مرورگر"
        />
        <TextField
          label="نام کوتاه"
          value={shortName}
          onChange={(e) => setShortName(e.target.value)}
          fullWidth
          inputProps={{ maxLength: 30 }}
          helperText="زیر آیکون، روی صفحه اصلی گوشی بعد از نصب (حداکثر ۳۰ حرف)"
        />
        <TextField
          label="توضیح کوتاه"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          fullWidth
          multiline
          minRows={2}
          helperText="زیر نام کامل، در صفحه ورود و اسپلش‌اسکرین"
        />
        {error && <Alert severity="error">{error}</Alert>}
        {success && <Alert severity="success">{success}</Alert>}
        <Stack direction="row" spacing={1.5}>
          <Button
            variant="contained"
            disabled={isSaving}
            startIcon={isSaving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />}
            onClick={handleSave}
          >
            {isSaving ? "در حال ذخیره..." : "ذخیره"}
          </Button>
          <Button variant="text" disabled={isSaving} startIcon={<RestartAltOutlinedIcon />} onClick={handleReset}>
            بازگشت به پیش‌فرض
          </Button>
        </Stack>
      </Stack>

      {/* ⚠️ توضیح محدودیت واقعی — نه یک نقص این پیاده‌سازی: مرورگرها/سیستم‌عامل‌ها
          معمولاً Manifest را فقط هنگام نصب اولیه PWA می‌خوانند. برای کسانی
          که از قبل پرتال را نصب کرده‌اند، این تغییرات معمولاً فقط با
          حذف‌ونصب دوباره اعمال می‌شود، نه خودکار. */}
      <Alert severity="info" sx={{ mt: 2 }}>
        برای کسانی که پرتال را از قبل روی صفحه اصلی گوشی نصب کرده‌اند، تغییر نام/آیکون
        معمولاً فقط با حذف و نصب دوباره اعمال می‌شود — این یک محدودیت مرورگرها/سیستم‌عامل‌هاست.
      </Alert>
    </Card>
  );
}
