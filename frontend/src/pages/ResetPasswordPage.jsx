import { useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { Alert, Box, Button, IconButton, InputAdornment, Link, TextField, Typography } from "@mui/material";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import VisibilityOffOutlinedIcon from "@mui/icons-material/VisibilityOffOutlined";
import { resetPasswordRequest } from "../api/auth";
import AuthPageShell from "../components/AuthPageShell";

/**
 * بازنشانی رمز عبور از طریق لینک ایمیل - توکن از querystring خوانده
 * می‌شود (?token=...، همان قالبی که Backend در password_reset_service.py
 * می‌سازد).
 */
export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (newPassword !== confirmPassword) {
      setError("رمز عبور و تکرار آن با یکدیگر مطابقت ندارند.");
      return;
    }

    setIsSubmitting(true);
    try {
      await resetPasswordRequest(token, newPassword);
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || "بازنشانی رمز عبور با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthPageShell title="بازنشانی رمز عبور">
      {!token ? (
        <Alert severity="error">
          لینک نامعتبر است. لطفاً از طریق لینک ارسال‌شده به ایمیل خود وارد این صفحه شوید.
        </Alert>
      ) : success ? (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Alert severity="success">رمز عبور با موفقیت تغییر یافت.</Alert>
          <Button
            variant="contained"
            size="large"
            onClick={() => navigate("/login")}
            sx={{ mt: 1, borderRadius: 999, height: 48 }}
          >
            ورود به پرتال
          </Button>
        </Box>
      ) : (
        <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <TextField
            label="رمز عبور جدید"
            type={showPassword ? "text" : "password"}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            autoFocus
            fullWidth
            inputProps={{ minLength: 6 }}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    edge="end"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label="نمایش رمز عبور"
                    tabIndex={-1}
                  >
                    {showPassword ? (
                      <VisibilityOffOutlinedIcon fontSize="small" />
                    ) : (
                      <VisibilityOutlinedIcon fontSize="small" />
                    )}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
          <TextField
            label="تکرار رمز عبور جدید"
            type={showPassword ? "text" : "password"}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            fullWidth
            inputProps={{ minLength: 6 }}
          />
          {error && <Alert severity="error">{error}</Alert>}
          <Button
            type="submit"
            variant="contained"
            size="large"
            disabled={isSubmitting || !newPassword || !confirmPassword}
            sx={{ mt: 1, borderRadius: 999, height: 48 }}
          >
            {isSubmitting ? "در حال ثبت..." : "تغییر رمز عبور"}
          </Button>
        </Box>
      )}

      <Typography variant="body2" textAlign="center" sx={{ mt: 3 }}>
        <Link component={RouterLink} to="/login">
          بازگشت به صفحه ورود
        </Link>
      </Typography>
    </AuthPageShell>
  );
}
