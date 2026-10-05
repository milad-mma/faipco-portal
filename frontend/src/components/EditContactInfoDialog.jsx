import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { updateMyContactInfo } from "../api/auth";
import { useAuth } from "../context/AuthContext";

const GENDER_LABELS = { 1: "مرد", 2: "زن" };

// مشخصات فقط‌خواندنی: [کلید در /auth/me، برچسب، قالب‌بندی اختیاری]
const READONLY_FIELDS = [
  ["full_name", "نام و نام خانوادگی"],
  ["hire_date_jalali", "تاریخ استخدام"],
  ["position_title", "سمت"],
  ["department_name", "واحد"],
  ["education_title", "مدرک تحصیلی"],
  ["birth_date_jalali", "تاریخ تولد"],
  ["national_code", "کد ملی"],
  ["gender", "جنسیت", (v) => GENDER_LABELS[v] || "—"],
  ["address", "آدرس"],
];

/**
 * دیالوگ «مشخصات کاربری»: ویرایش ایمیل و موبایل، به‌علاوه‌ی مشخصات فقط‌خواندنی از سیستم منبع (کاراوب):
 * نام و نام خانوادگی، تاریخ استخدام، سمت، واحد، مدرک تحصیلی، تاریخ تولد، کد ملی، جنسیت و آدرس. تغییر این موارد فقط از کاراوب ممکن است.
 * ورودی: open و onClose. خروجی: Dialog با دو فیلد (موبایل اجباری) و پیام نتیجه.
 * اگر در نگاشت ستون‌های سایت کاربر، ستون ایمیل/موبایل مشخص شده باشد، Backend مقدار جدید را
 * در دیتابیس اصلی همان سایت هم به‌روزرسانی می‌کند (Write-back)، نه فقط در دیتابیس پرتال.
 * امنیت: ایمیل/موبایل مقصد بازیابی رمز است؛ وقتی کاربر یکی از آن‌ها را واقعاً تغییر می‌دهد، فیلد
 * «رمز عبور فعلی» ظاهر می‌شود و سرور بدون آن تغییر را نمی‌پذیرد (400) (نشست دزدیده‌شده به‌تنهایی کافی نباشد).
 * بدون تغییر، رمز خواسته نمی‌شود.
 */
export default function EditContactInfoDialog({ open, onClose }) {
  const { user, refetchUser } = useAuth();
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const usesNationalCode = user && !user.has_custom_password; // بدون رمز اختصاصی: «رمز فعلی» همان کد ملی است
  // مقایسه با مقدار ذخیره‌شده (موبایل فقط ارقام، ایمیل بدون حساسیت به حروف بزرگ/کوچک)
  const mobileChanged = mobile.replace(/\D/g, "") !== (user?.mobile || "").replace(/\D/g, "");
  const emailChanged = email.trim().toLowerCase() !== (user?.email || "").trim().toLowerCase();
  const needsPassword = mobileChanged || emailChanged;

  // با باز شدن دیالوگ، فیلدها از اطلاعات فعلی کاربر پر و پیام‌ها پاک می‌شوند
  useEffect(() => {
    if (open) {
      setEmail(user?.email || "");
      setMobile(user?.mobile || "");
      setCurrentPassword("");
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
      await updateMyContactInfo({
        email: email.trim(),
        mobile: mobile.trim(),
        currentPassword: needsPassword ? currentPassword : undefined,
      });
      setCurrentPassword("");
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
          <Alert severity="info">فقط ایمیل و شماره موبایل قابل تغییر هستند.</Alert>
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
          {needsPassword && (
            // فقط وقتی موبایل/ایمیل واقعاً تغییر کرده نشان داده می‌شود؛ سرور بدون آن 400 می‌دهد
            <TextField
              label={usesNationalCode ? "کد ملی (برای تأیید تغییر)" : "رمز عبور فعلی (برای تأیید تغییر)"}
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              helperText="چون موبایل/ایمیل مقصد بازیابی رمز است، برای تغییر آن تأیید هویت لازم است."
              required
              fullWidth
              disabled={isSubmitting}
            />
          )}
          {error && <Alert severity="error">{error}</Alert>}
          {successMessage && <Alert severity="success">{successMessage}</Alert>}

          {user?.employee_id && (
            <>
              <Divider />
              {READONLY_FIELDS.map(([key, label, format]) => (
                <TextField
                  key={key}
                  label={label}
                  value={
                    key === "full_name"
                      ? [user?.first_name, user?.last_name].filter(Boolean).join(" ") || "—"
                      : format
                        ? format(user?.[key])
                        : user?.[key] || "—"
                  }
                  fullWidth
                  multiline={key === "address"}
                  InputProps={{ readOnly: true }}
                  inputProps={
                    key === "national_code" || key.endsWith("_jalali")
                      ? { dir: "ltr", style: { textAlign: "right" } }
                      : undefined
                  }
                  variant="filled"
                  size="small"
                />
              ))}
              <Typography variant="caption" color="text.secondary">
                سایر مشخصات از سیستم پرسنلی خوانده می‌شوند؛ برای اصلاح آن‌ها به واحد منابع انسانی مراجعه کنید.
              </Typography>
            </>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={isSubmitting}>
          بستن
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={isSubmitting || !mobile.trim() || (needsPassword && !currentPassword)}
        >
          {isSubmitting ? "در حال ذخیره..." : "ذخیره"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
