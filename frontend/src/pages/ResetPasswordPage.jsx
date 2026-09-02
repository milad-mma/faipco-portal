import { useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  IconButton,
  InputAdornment,
  Link,
  Paper,
  Stack,
  TextField,
  ThemeProvider,
  Typography,
} from "@mui/material";
import LockResetOutlinedIcon from "@mui/icons-material/LockResetOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import VisibilityOffOutlinedIcon from "@mui/icons-material/VisibilityOffOutlined";
import { resetPasswordRequest } from "../api/auth";
import { modernLightTheme } from "../theme";

/**
 * بازنشانی رمز عبور - توکن از querystring لینک ایمیل خوانده می‌شود
 * (?token=...، همان قالبی که Backend در password_reset_service.py می‌سازد).
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
      setError("رمز عبور و تکرار آن یکسان نیستند.");
      return;
    }

    setIsSubmitting(true);
    try {
      await resetPasswordRequest(token, newPassword);
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || "بازنشانی رمز عبور ناموفق بود.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ThemeProvider theme={modernLightTheme}>
      <Box
        sx={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: "#F3F7FA",
          p: 2,
        }}
      >
        <Paper
          elevation={0}
          sx={{ width: "100%", maxWidth: 420, p: 4, borderRadius: 3, boxShadow: "0 24px 55px rgba(33,67,91,.10)" }}
        >
          <Stack spacing={2.5}>
            <Stack alignItems="center" spacing={1}>
              <LockResetOutlinedIcon color="primary" sx={{ fontSize: 40 }} />
              <Typography variant="h5" fontWeight={800}>
                بازنشانی رمز عبور
              </Typography>
            </Stack>

            {!token ? (
              <Alert severity="error">
                لینک نامعتبر است — لطفاً از طریق لینک ارسال‌شده به ایمیل خود وارد این صفحه شوید.
              </Alert>
            ) : success ? (
              <Stack spacing={2}>
                <Alert severity="success">رمز عبور با موفقیت تغییر کرد.</Alert>
                <Button
                  variant="contained"
                  size="large"
                  onClick={() => navigate("/login")}
                  sx={{ borderRadius: 999, height: 48 }}
                >
                  ورود به پرتال
                </Button>
              </Stack>
            ) : (
              <Box component="form" onSubmit={handleSubmit}>
                <Stack spacing={2}>
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
                          <IconButton size="small" onClick={() => setShowPassword((v) => !v)} tabIndex={-1}>
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
                    sx={{ borderRadius: 999, height: 48 }}
                  >
                    {isSubmitting ? "در حال ثبت..." : "تغییر رمز عبور"}
                  </Button>
                </Stack>
              </Box>
            )}

            <Typography variant="body2" textAlign="center">
              <Link component={RouterLink} to="/login">
                بازگشت به صفحه ورود
              </Link>
            </Typography>
          </Stack>
        </Paper>
      </Box>
    </ThemeProvider>
  );
}
