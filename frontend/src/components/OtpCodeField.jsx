import { useEffect, useState } from "react";
import { Alert, Box, Button, TextField } from "@mui/material";

/**
 * فیلد «کد تأیید» به‌همراه دکمه‌ی «ارسال کد» و شمارش معکوس ارسال دوباره (برای تغییر رمز و تغییر موبایل).
 * ورودی:
 * - onSend: تابع async که کد را می‌فرستد و { masked_contact, resend_cooldown_seconds } برمی‌گرداند
 * - value / onChange(value): مقدار کد (فقط رقم، حداکثر ۶)
 * - disabled، sendDisabled (مثلاً وقتی شماره‌ی جدید هنوز معتبر نیست)، sendLabel
 * - resetKey: با تغییرش (مثلاً عوض شدن شماره یا کانال) وضعیت «ارسال شد» پاک می‌شود
 * خطای ارسال (از جمله 429 «زود است» با هدر Retry-After) زیر دکمه نمایش داده می‌شود.
 */
export default function OtpCodeField({
  onSend,
  value,
  onChange,
  disabled = false,
  sendDisabled = false,
  sendLabel = "ارسال کد",
  resetKey,
}) {
  const [sentTo, setSentTo] = useState(""); // مقصد ماسک‌شده‌ی آخرین ارسال
  const [cooldown, setCooldown] = useState(0); // ثانیه تا امکان ارسال دوباره
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  // با عوض شدن مقصد (شماره/کانال)، ارسال قبلی دیگر معتبر نیست
  useEffect(() => {
    setSentTo("");
    setCooldown(0);
    setError("");
  }, [resetKey]);

  // شمارش معکوس ثانیه‌ای
  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  async function handleSend() {
    setError("");
    setSending(true);
    try {
      const data = await onSend();
      setSentTo(data?.masked_contact || "");
      setCooldown(data?.resend_cooldown_seconds || 60);
    } catch (err) {
      const retry = Number(err.response?.headers?.["retry-after"]);
      if (retry > 0) setCooldown(retry);
      setError(err.response?.data?.detail || "ارسال کد با خطا مواجه شد.");
    } finally {
      setSending(false);
    }
  }

  const buttonText = sending
    ? "در حال ارسال..."
    : cooldown > 0
      ? `ارسال دوباره (${cooldown})`
      : sentTo
        ? "ارسال دوباره"
        : sendLabel;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
        <TextField
          label="کد تأیید"
          value={value}
          onChange={(e) => onChange(e.target.value.replace(/[^0-9۰-۹٠-٩]/g, "").slice(0, 6))}
          inputProps={{ inputMode: "numeric", dir: "ltr", style: { textAlign: "center", letterSpacing: 4 } }}
          autoComplete="one-time-code"
          disabled={disabled}
          sx={{ flex: 1 }}
        />
        <Button
          variant="outlined"
          onClick={handleSend}
          disabled={disabled || sendDisabled || sending || cooldown > 0}
          sx={{ whiteSpace: "nowrap", minWidth: 128, height: 56 }}
        >
          {buttonText}
        </Button>
      </Box>
      {sentTo && !error && (
        <Alert severity="info" sx={{ py: 0 }}>
          کد تأیید به <bdi dir="ltr">{sentTo}</bdi> ارسال شد (۵ دقیقه اعتبار دارد).
        </Alert>
      )}
      {error && (
        <Alert severity="warning" sx={{ py: 0 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
}
