import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { Alert, Box, Button, Link, Paper, Stack, TextField, ThemeProvider, Typography } from "@mui/material";
import LockResetOutlinedIcon from "@mui/icons-material/LockResetOutlined";
import { forgotPasswordRequest } from "../api/auth";
import { modernLightTheme } from "../theme";

/**
 * درخواست بازنشانی رمز عبور - همان شناسه‌ای که برای ورود استفاده می‌شود
 * (نام‌کاربری یا کد پرسنلی) را می‌گیرد. طبق طراحی امنیتی Backend، همیشه
 * یک پیام موفقیت یکسان نشان می‌دهد (چه شناسه معتبر باشد چه نه) - برای
 * جلوگیری از افشای این‌که کدام شناسه‌ها در سامانه ثبت شده‌اند.
 */
export default function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const result = await forgotPasswordRequest(identifier.trim());
      setSuccessMessage(result.message);
    } catch (err) {
      setError(err.response?.data?.detail || "ارسال درخواست ناموفق بود.");
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
                فراموشی رمز عبور
              </Typography>
              <Typography variant="body2" color="text.secondary" textAlign="center">
                کد پرسنلی یا نام‌کاربری خود را وارد کنید — اگر ایمیلی برایتان ثبت شده باشد، لینک بازنشانی
                رمز عبور برایتان ارسال می‌شود.
              </Typography>
            </Stack>

            {successMessage ? (
              <Alert severity="success">{successMessage}</Alert>
            ) : (
              <Box component="form" onSubmit={handleSubmit}>
                <Stack spacing={2}>
                  <TextField
                    label="کد پرسنلی / نام کاربری"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    required
                    autoFocus
                    fullWidth
                  />
                  {error && <Alert severity="error">{error}</Alert>}
                  <Button
                    type="submit"
                    variant="contained"
                    size="large"
                    disabled={isSubmitting || !identifier.trim()}
                    sx={{ borderRadius: 999, height: 48 }}
                  >
                    {isSubmitting ? "در حال ارسال..." : "ارسال لینک بازنشانی"}
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
