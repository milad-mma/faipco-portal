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
} from "@mui/material";
import { updateMyContactInfo } from "../api/auth";
import { useAuth } from "../context/AuthContext";

/**
 * دیالوگ ویرایش ایمیل و موبایل شخصی کاربر جاری از پنل کاربری.
 * ورودی: open و onClose. خروجی: Dialog با دو فیلد (موبایل اجباری) و پیام نتیجه.
 * اگر در نگاشت ستون‌های سایت کاربر، ستون ایمیل/موبایل مشخص شده باشد، Backend مقدار جدید را
 * در دیتابیس اصلی همان سایت هم به‌روزرسانی می‌کند (Write-back)، نه فقط در دیتابیس پرتال.
 */
export default function EditContactInfoDialog({ open, onClose }) {
  const { user, refetchUser } = useAuth();
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // با باز شدن دیالوگ، فیلدها از اطلاعات فعلی کاربر پر و پیام‌ها پاک می‌شوند
  useEffect(() => {
    if (open) {
      setEmail(user?.email || "");
      setMobile(user?.mobile || "");
      setError("");
      setSuccessMessage("");
    }
    // فقط به open وابسته است، نه به user: پس از ذخیره، refetchUser() مقدار user را تازه می‌کند
    // و وابستگی به user باعث اجرای دوباره‌ی افکت و پاک شدن پیام موفقیت می‌شد.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // بستن دیالوگ؛ در حین ذخیره غیرفعال است
  function handleClose() {
    if (isSubmitting) return;
    onClose();
  }

  // ذخیره‌ی ایمیل و موبایل (trim‌شده) و تازه کردن اطلاعات کاربر در Context
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
            required
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
        <Button variant="contained" onClick={handleSubmit} disabled={isSubmitting || !mobile.trim()}>
          {isSubmitting ? "در حال ذخیره..." : "ذخیره"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
