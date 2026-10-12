import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  FormControlLabel,
  Radio,
  RadioGroup,
  Typography,
} from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import { changePasswordRequest, fetchPasswordOtpOptions, sendPasswordOtp } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import OtpCodeField from "./OtpCodeField";
import PasswordField from "./PasswordField";

const CHANNEL_LABELS = { sms: "پیامک", email: "ایمیل" };

const MIN_LENGTH = 10; // حداقل طول رمز عبور جدید

// فهرست شرایط قدرت رمز عبور؛ هر مورد: {label, ok} برای نمایش چک‌لیست زیر فرم
function getStrengthChecks(password) {
  return [
    { label: `حداقل ${MIN_LENGTH} کاراکتر`, ok: password.length >= MIN_LENGTH },
    { label: "حداقل یک حرف کوچک انگلیسی (a-z)", ok: /[a-z]/.test(password) },
    { label: "حداقل یک حرف بزرگ انگلیسی (A-Z)", ok: /[A-Z]/.test(password) },
    { label: "حداقل یک عدد (0-9)", ok: /[0-9]/.test(password) },
  ];
}

/**
 * دیالوگ تغییر رمز عبور کاربر جاری با چک‌لیست زنده‌ی قدرت رمز.
 * ورودی: open، onClose و mandatory.
 * mandatory=true برای وقتی است که کاربر با رمز ضعیف/پیش‌فرض وارد شده و باید قبل از هر کاری
 * رمزش را عوض کند: انصراف ندارد و با کلیک بیرون یا Esc بسته نمی‌شود؛ فقط «خروج از سامانه» دارد.
 * شرایط رمز (با تیک زنده) پیش از فیلدها نمایش داده می‌شود.
 * تأیید هویت در حالت اجباری (اولین ورود): فقط «رمز عبور فعلی» (رمز پیش‌فرض)، بدون کد تأیید.
 * در تغییر رمز عادی از پروفایل: اگر کاربر موبایل/ایمیل قابل‌استفاده دارد، «کد تأیید» پیامکی/ایمیلی جای «رمز عبور فعلی» را می‌گیرد
 * (اگر هر دو باشد، کاربر کانال را انتخاب می‌کند)؛ وگرنه همان «رمز عبور فعلی» پرسیده می‌شود.
 * خروجی: Dialog شامل کد تأیید یا رمز فعلی، رمز جدید/تکرار و پیام‌های راهنما، موفقیت و خطا.
 */
export default function ChangePasswordDialog({ open, onClose, mandatory = false }) {
  const { refetchUser, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [otpOptions, setOtpOptions] = useState(null); // پاسخ otp-options؛ null = در حال بارگذاری
  const [optionsError, setOptionsError] = useState("");
  const [channel, setChannel] = useState("sms");
  const [otpCode, setOtpCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showNew, setShowNew] = useState(false); // نمایش رمز جدید و تکرارش با یک دکمه
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // با باز شدن دیالوگ، روش تأیید هویت (کد یا رمز فعلی) از سرور خوانده می‌شود
  // در حالت اجباری (اولین ورود) کد تأیید لازم نیست: فقط رمز پیش‌فرض فعلی پرسیده می‌شود
  async function loadOptions() {
    setOptionsError("");
    if (mandatory) {
      setOtpOptions({ otp_required: false, channels: {} });
      return;
    }
    setOtpOptions(null);
    try {
      const data = await fetchPasswordOtpOptions();
      setOtpOptions(data);
      const channels = Object.keys(data.channels || {});
      if (channels.length) setChannel(channels.includes("sms") ? "sms" : channels[0]);
    } catch (err) {
      setOptionsError(err.response?.data?.detail || "دریافت روش تأیید هویت با خطا مواجه شد.");
    }
  }

  useEffect(() => {
    if (open) loadOptions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const otpMode = !!otpOptions?.otp_required;
  const channelEntries = Object.entries(otpOptions?.channels || {});
  const strengthChecks = getStrengthChecks(newPassword);
  const isStrongEnough = strengthChecks.every((c) => c.ok);

  // پاک کردن همه‌ی فیلدها و پیام‌ها
  function reset() {
    setCurrentPassword("");
    setOtpCode("");
    setNewPassword("");
    setConfirmPassword("");
    setError("");
    setSuccess(false);
  }

  // بستن دیالوگ (در حالت اجباری غیرفعال است)
  function handleClose() {
    if (mandatory) return; // اصلاً قابل بستن نیست تا رمز عوض شود
    reset();
    onClose();
  }

  // اعتبارسنجی تطابق و قدرت رمز، ارسال به سرور و در حالت اجباری به‌روزرسانی اطلاعات کاربر
  async function handleSubmit() {
    setError("");
    if (newPassword !== confirmPassword) {
      setError("رمز عبور جدید و تکرار آن با یکدیگر مطابقت ندارند.");
      return;
    }
    if (!isStrongEnough) {
      setError("رمز عبور جدید باید تمامی موارد فهرست‌شده زیر را رعایت کند.");
      return;
    }
    if (otpMode && otpCode.length !== 6) {
      setError("کد تأیید ۶ رقمی را وارد کنید.");
      return;
    }
    setIsSubmitting(true);
    try {
      await changePasswordRequest(
        otpMode ? { otpCode, newPassword } : { currentPassword, newPassword },
      );
      setSuccess(true);
      setCurrentPassword("");
      setOtpCode("");
      setNewPassword("");
      setConfirmPassword("");
      if (mandatory) {
        await refetchUser(); // must_change_password را false می‌کند و Dialog خودکار جمع می‌شود
      }
    } catch (err) {
      setError(err.response?.data?.detail || "تغییر رمز عبور با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      fullWidth
      maxWidth="xs"
      disableEscapeKeyDown={mandatory}
    >
      <DialogTitle>تغییر رمز عبور</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {/* توضیح حالت اجباری */}
        {mandatory && !success && (
          <Typography variant="body2">برای ادامه استفاده از سامانه، ابتدا باید یک رمز عبور قوی‌ انتخاب کنید.</Typography>
        )}
        {success && (
          <Alert severity="success">
            رمز عبور با موفقیت تغییر یافت. از این پس فقط با همین رمز عبور جدید وارد شوید — روش قبلی
            دیگر معتبر نیست.
          </Alert>
        )}
        {/* فرم تغییر رمز و چک‌لیست قدرت رمز (پس از موفقیت پنهان می‌شود) */}
        {!success && (
          <>
            {/* شرایط رمز عبور (با تیک زنده) پیش از فیلدها */}
            <List dense disablePadding>
              {strengthChecks.map((check) => (
                <ListItem key={check.label} disableGutters sx={{ py: 0.25 }}>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    {check.ok ? (
                      <CheckCircleOutlineIcon fontSize="small" color="success" />
                    ) : (
                      <RadioButtonUncheckedIcon fontSize="small" color="disabled" />
                    )}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography variant="caption" color={check.ok ? "text.primary" : "text.secondary"}>
                        {check.label}
                      </Typography>
                    }
                  />
                </ListItem>
              ))}
            </List>
            {/* تأیید هویت: کد پیامک/ایمیل، یا اگر کانالی نیست رمز فعلی */}
            {!otpOptions && !optionsError && (
              <Box sx={{ display: "flex", justifyContent: "center", py: 1 }}>
                <CircularProgress size={24} />
              </Box>
            )}
            {optionsError && (
              <Alert
                severity="error"
                action={
                  <Button color="inherit" size="small" onClick={loadOptions}>
                    تلاش دوباره
                  </Button>
                }
              >
                {optionsError}
              </Alert>
            )}
            {otpOptions && otpMode && (
              <>
                {channelEntries.length > 1 && (
                  <RadioGroup row value={channel} onChange={(e) => setChannel(e.target.value)}>
                    {channelEntries.map(([key, masked]) => (
                      <FormControlLabel
                        key={key}
                        value={key}
                        control={<Radio size="small" />}
                        label={
                          <Typography variant="body2">
                            {CHANNEL_LABELS[key]} (<bdi dir="ltr">{masked}</bdi>)
                          </Typography>
                        }
                      />
                    ))}
                  </RadioGroup>
                )}
                <OtpCodeField
                  value={otpCode}
                  onChange={setOtpCode}
                  onSend={() => sendPasswordOtp(channel)}
                  resetKey={channel}
                  disabled={isSubmitting}
                  sendLabel={
                    channelEntries.length > 1 ? "ارسال کد" : `ارسال کد با ${CHANNEL_LABELS[channel] || "پیامک"}`
                  }
                />
              </>
            )}
            {otpOptions && !otpMode && (
              <PasswordField
                label="رمز عبور فعلی"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                fullWidth
                autoFocus
              />
            )}
            <PasswordField
              label="رمز عبور جدید"
              show={showNew}
              onToggle={() => setShowNew((v) => !v)}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              fullWidth
            />
            <PasswordField
              label="تکرار رمز عبور جدید"
              show={showNew}
              hideToggle
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              fullWidth
            />
          </>
        )}
        {/* پیام خطا درست بالای دکمه‌های عملیات (نه بالای فرم) نمایش داده می‌شود */}
        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      {/* دکمه‌ی انصراف/بستن فقط در حالت غیراجباری */}
      <DialogActions sx={{ p: 2.5 }}>
        {!mandatory && <Button onClick={handleClose}>{success ? "بستن" : "انصراف"}</Button>}
        {/* حالت اجباری: کسی که نمی‌خواهد رمز را عوض کند، از سامانه خارج می‌شود */}
        {mandatory && !success && (
          <Button color="inherit" onClick={logout} disabled={isSubmitting} sx={{ marginInlineEnd: "auto" }}>
            خروج از سامانه
          </Button>
        )}
        {!success && (
          <Button variant="contained" onClick={handleSubmit} disabled={isSubmitting || !otpOptions}>
            {isSubmitting ? "در حال ثبت..." : "تغییر رمز"}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
