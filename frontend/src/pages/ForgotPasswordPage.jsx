/**
 * صفحه فراموشی رمز عبور.
 * کاربر شناسه ورود و کانال (پیامک یا ایمیل) را انتخاب می‌کند. در کانال ایمیل لینک بازنشانی
 * ارسال می‌شود؛ در کانال پیامک ابتدا کد تأیید بررسی و سپس فرم رمز جدید نمایش داده می‌شود.
 * مدت اعتبار کد/لینک با شمارش معکوس نشان داده می‌شود.
 */
import { useEffect, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { Alert, Box, Button, Link, TextField, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { forgotPasswordRequest, resetPasswordRequest, verifyResetCodeRequest } from "../api/auth";
import AuthPageShell from "../components/AuthPageShell";

// ثانیه باقی‌مانده را می‌گیرد و رشته «MM:SS» برای شمارش معکوس برمی‌گرداند
function formatCountdown(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/**
 * نسخه ناقص مخاطب (masked_contact) با جهت صریح LTR نمایش داده می‌شود -
 * چون این رشته (ترکیب اعداد لاتین و ستاره) اگر بدون این ایزوله‌سازی
 * وسط یک جمله فارسی راست‌به‌چپ قرار بگیرد، الگوریتم دوجهته یونیکد
 * می‌تواند ترتیب نمایشی آن را جابه‌جا کند.
 * ورودی: value (رشته ماسک‌شده)؛ خروجی: عنصر <bdi dir="ltr">.
 */
function MaskedContact({ value }) {
  // از خصیصه HTML یعنی dir استفاده شده، نه CSS direction: پروژه از stylis-plugin-rtl
  // استفاده می‌کند که فقط استایل‌های CSS-in-JS را برمی‌گرداند و روی خصیصه‌های HTML
  // اثری ندارد؛ پس dir="ltr" مستقیماً به الگوریتم دوجهته مرورگر می‌رسد و ترتیب رشته حفظ می‌شود.
  return (
    <Box component="bdi" dir="ltr" sx={{ unicodeBidi: "isolate" }}>
      {value}
    </Box>
  );
}

/**
 * درخواست بازنشانی رمز عبور - همان شناسه‌ای که برای ورود استفاده می‌شود
 * (نام‌کاربری یا کد پرسنلی) را می‌گیرد، با انتخاب کانال (پیامک به‌عنوان
 * روش پیش‌فرض و اصلی، سپس ایمیل).
 *
 * جریان پیامک، برخلاف ایمیل، دو مرحله جداگانه دارد: ابتدا کد تأیید
 * دریافت و بررسی می‌شود، سپس (و فقط پس از تأیید صحت کد) فرم رمز عبور
 * جدید نمایش داده می‌شود.
 */
export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [channel, setChannel] = useState("sms");
  const [identifier, setIdentifier] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [maskedContact, setMaskedContact] = useState("");  // شماره/ایمیل ماسک‌شده مقصد که سرور برمی‌گرداند
  const [step, setStep] = useState("request"); // "request" | "sms-verify-code" | "sms-new-password" | "done"
  const [remainingSeconds, setRemainingSeconds] = useState(null);  // ثانیه‌های باقی‌مانده اعتبار کد/لینک؛ null = نامشخص، 0 = منقضی

  const [smsCode, setSmsCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // شمارش معکوس: وقتی remainingSeconds مقدار گرفت، هر ثانیه یکی کم می‌کند تا به صفر برسد؛
  // وابستگی فقط «null بودن یا نبودن» است تا تایمر با هر تیک از نو ساخته نشود
  useEffect(() => {
    if (remainingSeconds === null || remainingSeconds <= 0) return undefined;
    const timer = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remainingSeconds !== null]);

  // مرحله اول: درخواست بازنشانی با شناسه و کانال را ارسال می‌کند، مخاطب ماسک‌شده و مدت اعتبار را ذخیره
  // و به مرحله بررسی کد (پیامک) یا مرحله پایانی (ایمیل) می‌رود
  async function handleRequestSubmit(e) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const result = await forgotPasswordRequest(identifier.trim(), channel);
      setMaskedContact(result.masked_contact || "");
      setRemainingSeconds(result.expires_in_seconds ?? null);
      setStep(channel === "sms" ? "sms-verify-code" : "done");
    } catch (err) {
      setError(err.response?.data?.detail || "ارسال درخواست با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  // مرحله پیامک: کد تأیید را بررسی می‌کند و در صورت صحت به فرم رمز جدید می‌رود
  async function handleVerifyCodeSubmit(e) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      await verifyResetCodeRequest(smsCode.trim());
      setStep("sms-new-password");
    } catch (err) {
      setError(err.response?.data?.detail || "بررسی کد تأیید با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  // مرحله پیامک: یکسان بودن رمز و تکرار را بررسی و رمز جدید را با همان کد پیامکی ثبت می‌کند
  async function handleNewPasswordSubmit(e) {
    e.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("رمز عبور و تکرار آن با یکدیگر مطابقت ندارند.");
      return;
    }
    setIsSubmitting(true);
    try {
      await resetPasswordRequest(smsCode.trim(), newPassword);
      setStep("done");
      setRemainingSeconds(null);
    } catch (err) {
      setError(err.response?.data?.detail || "بازنشانی رمز عبور با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  // بعد از انقضای کد، فرم را به مرحله درخواست اولیه برمی‌گرداند
  function handleRequestAgain() {
    setStep("request");
    setRemainingSeconds(null);
    setSmsCode("");
    setError("");
  }

  const expired = remainingSeconds === 0;  // اعتبار کد/لینک تمام شده است

  return (
    <AuthPageShell
      title="فراموشی رمز عبور"
      subtitle={
        step === "request" ? "برای بازنشانی رمز عبور، شناسه ورود و روش دریافت را انتخاب نمایید." : undefined
      }
    >
      {/* مرحله ۱: انتخاب کانال و وارد کردن شناسه ورود */}
      {step === "request" && (
        <Box
          component="form"
          onSubmit={handleRequestSubmit}
          sx={{ display: "flex", flexDirection: "column", gap: 2 }}
        >
          <ToggleButtonGroup
            value={channel}
            exclusive
            onChange={(_, value) => value && setChannel(value)}
            fullWidth
            size="small"
          >
            <ToggleButton value="sms">پیامک</ToggleButton>
            <ToggleButton value="email">ایمیل</ToggleButton>
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
            sx={{ mt: 1, borderRadius: 999, height: 48 }}
          >
            {isSubmitting ? "در حال ارسال..." : channel === "sms" ? "ارسال کد تأیید" : "ارسال لینک بازنشانی"}
          </Button>
        </Box>
      )}

      {/* مرحله ۲ (پیامک): وارد کردن کد تأیید با نمایش شمارش معکوس؛ پس از انقضا دکمه درخواست مجدد */}
      {step === "sms-verify-code" && (
        <Box
          component="form"
          onSubmit={handleVerifyCodeSubmit}
          sx={{ display: "flex", flexDirection: "column", gap: 2 }}
        >
          <Typography variant="body2" color="text.secondary">
            کد تأیید به شماره <MaskedContact value={maskedContact} /> پیامک شد.
          </Typography>
          {remainingSeconds !== null && (
            <Typography variant="body2" color={expired ? "error" : "text.secondary"}>
              {expired
                ? "اعتبار کد به پایان رسیده است. برای دریافت کد جدید، درخواست را تکرار نمایید."
                : `این کد تا ${formatCountdown(remainingSeconds)} دیگر معتبر است.`}
            </Typography>
          )}
          <TextField
            label="کد تأیید"
            value={smsCode}
            onChange={(e) => setSmsCode(e.target.value)}
            required
            autoFocus
            fullWidth
            disabled={expired}
            inputProps={{ inputMode: "numeric" }}
          />
          {error && <Alert severity="error">{error}</Alert>}
          {expired ? (
            <Button
              variant="contained"
              size="large"
              onClick={handleRequestAgain}
              sx={{ mt: 1, borderRadius: 999, height: 48 }}
            >
              درخواست کد جدید
            </Button>
          ) : (
            <Button
              type="submit"
              variant="contained"
              size="large"
              disabled={isSubmitting || !smsCode.trim()}
              sx={{ mt: 1, borderRadius: 999, height: 48 }}
            >
              {isSubmitting ? "در حال بررسی..." : "تأیید کد"}
            </Button>
          )}
        </Box>
      )}

      {/* مرحله ۳ (پیامک): فرم رمز عبور جدید و تکرار آن */}
      {step === "sms-new-password" && (
        <Box
          component="form"
          onSubmit={handleNewPasswordSubmit}
          sx={{ display: "flex", flexDirection: "column", gap: 2 }}
        >
          <Typography variant="body2" color="text.secondary">
            کد تأیید با موفقیت پذیرفته شد. رمز عبور جدید خود را وارد نمایید.
          </Typography>
          <TextField
            label="رمز عبور جدید"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            autoFocus
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
            disabled={isSubmitting || !newPassword || !confirmPassword}
            sx={{ mt: 1, borderRadius: 999, height: 48 }}
          >
            {isSubmitting ? "در حال ثبت..." : "تغییر رمز عبور"}
          </Button>
        </Box>
      )}

      {/* مرحله پایانی: پیام ارسال لینک (ایمیل) یا موفقیت تغییر رمز (پیامک) */}
      {step === "done" && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {channel === "email" ? (
            <>
              <Typography variant="body2" color="text.secondary">
                لینک بازنشانی رمز عبور به آدرس <MaskedContact value={maskedContact} /> ارسال شد. لطفاً صندوق
                ایمیل خود را بررسی نمایید.
              </Typography>
              {remainingSeconds !== null && remainingSeconds > 0 && (
                <Typography variant="body2" color="text.secondary">
                  این لینک تا {formatCountdown(remainingSeconds)} دیگر معتبر است.
                </Typography>
              )}
            </>
          ) : (
            <Alert severity="success">رمز عبور با موفقیت تغییر یافت.</Alert>
          )}
          <Button
            variant="contained"
            size="large"
            onClick={() => navigate("/login")}
            sx={{ mt: 1, borderRadius: 999, height: 48 }}
          >
            ورود به پرتال
          </Button>
        </Box>
      )}

      {/* لینک بازگشت به صفحه ورود */}
      <Typography variant="body2" textAlign="center" sx={{ mt: 3 }}>
        <Link component={RouterLink} to="/login">
          بازگشت به صفحه ورود
        </Link>
      </Typography>
    </AuthPageShell>
  );
}
