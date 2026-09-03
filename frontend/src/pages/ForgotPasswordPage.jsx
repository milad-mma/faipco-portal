import { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Link,
  Paper,
  Stack,
  TextField,
  ThemeProvider,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import LockResetOutlinedIcon from "@mui/icons-material/LockResetOutlined";
import { forgotPasswordRequest, resetPasswordRequest } from "../api/auth";
import { modernLightTheme } from "../theme";

/**
 * درخواست بازنشانی رمز عبور - همان شناسه‌ای که برای ورود استفاده می‌شود
 * (نام‌کاربری یا کد پرسنلی) را می‌گیرد، با انتخاب کانال (ایمیل یا پیامک).
 * طبق طراحی امنیتی Backend، همیشه یک پیام موفقیت یکسان نشان می‌دهد (چه
 * شناسه معتبر باشد چه نه) - برای جلوگیری از افشای این‌که کدام شناسه‌ها
 * در سامانه ثبت شده‌اند.
 *
 * ⚠️ کانال پیامک، برخلاف ایمیل (که یک لینک قابل‌کلیک می‌فرستد)، یک کد
 * تأیید ۶ رقمی می‌فرستد که کاربر باید دستی وارد کند - پس بعد از درخواست
 * موفق پیامکی، همین صفحه یک فرم «کد + رمز جدید» نمایش می‌دهد (به‌جای
 * فقط یک پیام «ایمیل خود را بررسی کنید»).
 */
export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [channel, setChannel] = useState("email");
  const [identifier, setIdentifier] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [step, setStep] = useState("request"); // "request" | "sms-verify" | "done"

  const [smsCode, setSmsCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  async function handleRequestSubmit(e) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const result = await forgotPasswordRequest(identifier.trim(), channel);
      setSuccessMessage(result.message);
      setStep(channel === "sms" ? "sms-verify" : "done");
    } catch (err) {
      setError(err.response?.data?.detail || "ارسال درخواست ناموفق بود.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSmsVerifySubmit(e) {
    e.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("رمز عبور و تکرار آن یکسان نیستند.");
      return;
    }
    setIsSubmitting(true);
    try {
      await resetPasswordRequest(smsCode.trim(), newPassword);
      setStep("done");
      setSuccessMessage("رمز عبور با موفقیت تغییر کرد.");
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
                فراموشی رمز عبور
              </Typography>
              {step === "request" && (
                <Typography variant="body2" color="text.secondary" textAlign="center">
                  کد پرسنلی یا نام‌کاربری خود را وارد کنید — اگر ایمیل/موبایلی برایتان ثبت شده باشد،
                  اطلاعات بازنشانی رمز عبور برایتان ارسال می‌شود.
                </Typography>
              )}
            </Stack>

            {step === "request" && (
              <Box component="form" onSubmit={handleRequestSubmit}>
                <Stack spacing={2}>
                  <ToggleButtonGroup
                    value={channel}
                    exclusive
                    onChange={(_, value) => value && setChannel(value)}
                    fullWidth
                    size="small"
                  >
                    <ToggleButton value="email">ایمیل</ToggleButton>
                    <ToggleButton value="sms">پیامک</ToggleButton>
                  </ToggleButtonGroup>
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
                    {isSubmitting ? "در حال ارسال..." : channel === "sms" ? "ارسال کد تأیید" : "ارسال لینک بازنشانی"}
                  </Button>
                </Stack>
              </Box>
            )}

            {step === "sms-verify" && (
              <Box component="form" onSubmit={handleSmsVerifySubmit}>
                <Stack spacing={2}>
                  {successMessage && <Alert severity="success">{successMessage}</Alert>}
                  <TextField
                    label="کد تأیید پیامک‌شده"
                    value={smsCode}
                    onChange={(e) => setSmsCode(e.target.value)}
                    required
                    autoFocus
                    fullWidth
                    inputProps={{ inputMode: "numeric" }}
                  />
                  <TextField
                    label="رمز عبور جدید"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    fullWidth
                    inputProps={{ minLength: 6 }}
                  />
                  <TextField
                    label="تکرار رمز عبور جدید"
                    type="password"
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
                    disabled={isSubmitting || !smsCode.trim() || !newPassword || !confirmPassword}
                    sx={{ borderRadius: 999, height: 48 }}
                  >
                    {isSubmitting ? "در حال ثبت..." : "تغییر رمز عبور"}
                  </Button>
                </Stack>
              </Box>
            )}

            {step === "done" && (
              <Stack spacing={2}>
                <Alert severity="success">{successMessage}</Alert>
                <Button
                  variant="contained"
                  size="large"
                  onClick={() => navigate("/login")}
                  sx={{ borderRadius: 999, height: 48 }}
                >
                  ورود به پرتال
                </Button>
              </Stack>
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
