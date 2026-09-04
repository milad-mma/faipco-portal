import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { updateMyContactInfo } from "../api/auth";
import { useAuth } from "../context/AuthContext";

/**
 * ویرایش ایمیل/موبایل شخصی از پنل کاربری. اگر برای سایت خودِ کاربر،
 * ستون ایمیل/موبایل در نگاشت ستون‌ها (تنظیمات سایت) مشخص شده باشد، مقدار
 * جدید در دیتابیس اصلی همان سایت هم به‌روزرسانی می‌شود (Write-back)، نه
 * فقط دیتابیس داخلی پرتال - پیام موفقیت این را به کاربر اطلاع می‌دهد.
 */
export default function EditContactInfoDialog({ open, onClose }) {
  const { user, refetchUser } = useAuth();
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setEmail(user?.email || "");
      setMobile(user?.mobile || "");
      setError("");
      setSuccessMessage("");
    }
    // ⚠️ عمداً فقط به open وابسته است، نه به user - چون در انتهای ذخیره
    // موفق، refetchUser() مقدار user را در Context تازه می‌کند؛ اگر user
    // هم اینجا Dependency بود، همین افکت دوباره اجرا و پیام موفقیت را
    // بلافاصله بعد از نمایش پاک می‌کرد (باگ اصلی «واکنشی نشان نمی‌دهد»).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function handleClose() {
    if (isSubmitting) return;
    onClose();
  }

  async function handleSubmit() {
    if (isSubmitting) return; // محافظت اضافی در برابر چند کلیک سریع، جدا از غیرفعال‌شدن دکمه
    setError("");
    setSuccessMessage("");
    setIsSubmitting(true);
    try {
      await updateMyContactInfo({ email: email.trim(), mobile: mobile.trim() });
      setSuccessMessage("اطلاعات با موفقیت ذخیره شد.");
      await refetchUser();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره اطلاعات با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="xs">
      <DialogTitle>مشخصات کاربری</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            این اطلاعات برای «فراموشی رمز عبور» استفاده می‌شود.
          </Typography>
          <TextField
            label="ایمیل"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            fullWidth
            disabled={isSubmitting}
          />
          <TextField
            label="موبایل"
            value={mobile}
            onChange={(e) => setMobile(e.target.value)}
            placeholder="09123456789"
            fullWidth
            disabled={isSubmitting}
          />
          {error && <Alert severity="error">{error}</Alert>}
          {successMessage && <Alert severity="success">{successMessage}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={isSubmitting}>
          بستن
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={isSubmitting || (!email.trim() && !mobile.trim())}
        >
          {isSubmitting ? "در حال ذخیره..." : "ذخیره"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
