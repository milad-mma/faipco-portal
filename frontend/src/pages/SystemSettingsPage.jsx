import { useRef, useState } from "react";
import { Alert, Box, Button, Card, CircularProgress, Stack, Typography } from "@mui/material";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import { deleteLoginBackground, LOGIN_BACKGROUND_URL, uploadLoginBackground } from "../api/system";

/**
 * تنظیمات سامانه — فعلاً فقط عکس پس‌زمینه صفحه ورود. اگر در آینده
 * تنظیمات سراسری دیگری اضافه شد، همین صفحه محل طبیعی‌اش است.
 */
export default function SystemSettingsPage() {
  const fileInputRef = useRef(null);
  const [previewUrl, setPreviewUrl] = useState(null); // پیش‌نمایش فایل تازه‌انتخاب‌شده (قبل از آپلود)
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  // با تغییر این عدد، آدرس عکس فعلی دوباره (بدون Cache قدیمی مرورگر) گرفته می‌شود
  const [currentImageVersion, setCurrentImageVersion] = useState(0);
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
      await uploadLoginBackground(selectedFile);
      setSuccess("عکس پس‌زمینه با موفقیت به‌روزرسانی شد.");
      setSelectedFile(null);
      setPreviewUrl(null);
      setCurrentImageExists(true);
      setCurrentImageVersion((v) => v + 1);
      if (fileInputRef.current) fileInputRef.current.value = "";
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
      await deleteLoginBackground();
      setCurrentImageExists(false);
      setSuccess("عکس پس‌زمینه حذف شد — صفحه ورود به پس‌زمینه پیش‌فرض برمی‌گردد.");
    } catch (err) {
      setError(err.response?.data?.detail || "حذف عکس ناموفق بود.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 560, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>
        تنظیمات سامانه
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        تنظیمات سراسری کل پرتال.
      </Typography>

      <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
          عکس پس‌زمینه صفحه ورود
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          این عکس پشت فرم ورود (صفحه‌ای که همه — حتی قبل از ورود — می‌بینند) نمایش داده می‌شود.
          فرمت jpg/png/webp، حداکثر ۸ مگابایت.
        </Typography>

        <Box
          sx={{
            width: "100%",
            height: 220,
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
                ? `url(${LOGIN_BACKGROUND_URL}?v=${currentImageVersion})`
                : "none",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        >
          {!previewUrl && !currentImageExists && (
            <Stack alignItems="center" spacing={1} sx={{ color: "text.disabled" }}>
              <ImageOutlinedIcon sx={{ fontSize: 40 }} />
              <Typography variant="caption">هنوز عکسی تنظیم نشده — پس‌زمینه پیش‌فرض نمایش داده می‌شود</Typography>
            </Stack>
          )}
          {/* اگر عکس فعلی واقعاً وجود نداشته باشد (۴۰۴)، این img مخفی نامرئی همین را به ما اطلاع می‌دهد */}
          {!previewUrl && currentImageExists && (
            <img
              src={`${LOGIN_BACKGROUND_URL}?v=${currentImageVersion}`}
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
            <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={handleFileChange} />
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
              {isDeleting ? "در حال حذف..." : "حذف عکس پس‌زمینه"}
            </Button>
          )}
        </Stack>
      </Card>
    </Box>
  );
}
