import { useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  TextField,
  Typography,
} from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import { changePasswordRequest } from "../api/auth";
import { useAuth } from "../context/AuthContext";

const MIN_LENGTH = 10;

function getStrengthChecks(password) {
  return [
    { label: `حداقل ${MIN_LENGTH} کاراکتر`, ok: password.length >= MIN_LENGTH },
    { label: "حداقل یک حرف کوچک انگلیسی (a-z)", ok: /[a-z]/.test(password) },
    { label: "حداقل یک حرف بزرگ انگلیسی (A-Z)", ok: /[A-Z]/.test(password) },
    { label: "حداقل یک عدد (0-9)", ok: /[0-9]/.test(password) },
  ];
}

/**
 * mandatory=true: برای وقتی که کاربر با یک رمز ضعیف/پیش‌فرض وارد شده و
 * سیستم مجبورش می‌کند قبل از هر کار دیگری رمزش را عوض کند — بدون دکمه
 * انصراف، بدون امکان بستن با کلیک بیرون از Dialog یا کلید Esc.
 */
export default function ChangePasswordDialog({ open, onClose, mandatory = false }) {
  const { user, refetchUser } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const usesNationalCode = user && !user.has_custom_password;
  const strengthChecks = getStrengthChecks(newPassword);
  const isStrongEnough = strengthChecks.every((c) => c.ok);

  function reset() {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setError("");
    setSuccess(false);
  }

  function handleClose() {
    if (mandatory) return; // اصلاً قابل بستن نیست تا رمز عوض شود
    reset();
    onClose();
  }

  async function handleSubmit() {
    setError("");
    if (newPassword !== confirmPassword) {
      setError("رمز عبور جدید و تکرار آن یکسان نیستند");
      return;
    }
    if (!isStrongEnough) {
      setError("رمز عبور جدید باید همه موارد فهرست‌شده زیر را رعایت کند");
      return;
    }
    setIsSubmitting(true);
    try {
      await changePasswordRequest(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      if (mandatory) {
        await refetchUser(); // must_change_password را false می‌کند و Dialog خودکار جمع می‌شود
      }
    } catch (err) {
      setError(err.response?.data?.detail || "تغییر رمز عبور ناموفق بود");
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
      <DialogTitle>{mandatory ? "لازم است رمز عبور خود را تغییر دهید" : "تغییر رمز عبور"}</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {mandatory && !success && (
          <Alert severity="warning">
            رمز عبور فعلی حساب شما ضعیف یا پیش‌فرض است. برای ادامه استفاده از پرتال، ابتدا باید یک
            رمز عبور قوی‌تر تعیین کنید.
          </Alert>
        )}
        {error && <Alert severity="error">{error}</Alert>}
        {success && (
          <Alert severity="success">
            رمز عبور با موفقیت تغییر کرد. از این پس فقط با همین رمز عبور جدید وارد شوید — روش قبلی
            دیگر کار نمی‌کند.
          </Alert>
        )}
        {!success && (
          <>
            {usesNationalCode && (
              <Alert severity="info">
                شما هنوز رمز عبور اختصاصی تعیین نکرده‌اید. در فیلد «رمز عبور فعلی»، همان اطلاعاتی
                که برای ورود استفاده می‌کنید را وارد کنید.
              </Alert>
            )}
            <TextField
              label="رمز عبور فعلی"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              fullWidth
              autoFocus
            />
            <TextField
              label="رمز عبور جدید"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              fullWidth
            />
            <TextField
              label="تکرار رمز عبور جدید"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              fullWidth
            />
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
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ p: 2.5 }}>
        {!mandatory && <Button onClick={handleClose}>{success ? "بستن" : "انصراف"}</Button>}
        {!success && (
          <Button variant="contained" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "در حال ثبت..." : "تغییر رمز"}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
