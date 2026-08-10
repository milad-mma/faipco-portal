import { useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from "@mui/material";
import { changePasswordRequest } from "../api/auth";
import { useAuth } from "../context/AuthContext";

export default function ChangePasswordDialog({ open, onClose }) {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const usesNationalCode = user && !user.has_custom_password;

  function reset() {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setError("");
    setSuccess(false);
  }

  function handleClose() {
    reset();
    onClose();
  }

  async function handleSubmit() {
    setError("");
    if (newPassword !== confirmPassword) {
      setError("رمز عبور جدید و تکرار آن یکسان نیستند");
      return;
    }
    if (newPassword.length < 6) {
      setError("رمز عبور جدید باید حداقل ۶ کاراکتر باشد");
      return;
    }
    setIsSubmitting(true);
    try {
      await changePasswordRequest(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err.response?.data?.detail || "تغییر رمز عبور ناموفق بود");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="xs">
      <DialogTitle>تغییر رمز عبور</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
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
                شما هنوز رمز عبور اختصاصی تعیین نکرده‌اید. در فیلد «رمز عبور فعلی»، همان کد ملی
                خودتان را وارد کنید.
              </Alert>
            )}
            <TextField
              label={usesNationalCode ? "رمز عبور فعلی (کد ملی)" : "رمز عبور فعلی"}
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
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={handleClose}>{success ? "بستن" : "انصراف"}</Button>
        {!success && (
          <Button variant="contained" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "در حال ثبت..." : "تغییر رمز"}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
