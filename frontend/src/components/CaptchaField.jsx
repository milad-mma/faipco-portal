/**
 * کادر کپچای تصویری داخلی (ورود و فراموشی رمز).
 * ورودی:
 *   purpose: "login" | "forgot"
 *   value: { captcha_id, captcha_answer } | null، onChange(nextValue)
 *   reloadKey: هر بار تغییر کند چالش تازه گرفته می‌شود (کپچا یک‌بارمصرف است؛ بعد از هر تلاش ناموفق)
 *   onNotRequired: وقتی سرور بگوید کپچا لازم نیست (فقط purpose=forgot)
 * پاسخ با ارقام فارسی یا انگلیسی پذیرفته می‌شود (یکسان‌سازی در سرور).
 */
import { useCallback, useEffect, useState } from "react";
import { Box, CircularProgress, IconButton, Stack, TextField, Tooltip } from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import { fetchCaptcha } from "../api/auth";

// CSP سرور (img-src 'self' blob:) تصویر data: را مسدود می‌کند؛ تصویر به Blob و آدرس blob: تبدیل می‌شود
function dataUrlToObjectUrl(dataUrl) {
  const [header, base64] = String(dataUrl).split(",");
  const mime = /data:([^;]+)/.exec(header)?.[1] || "image/png";
  const bytes = Uint8Array.from(atob(base64 || ""), (c) => c.charCodeAt(0));
  return URL.createObjectURL(new Blob([bytes], { type: mime }));
}

export default function CaptchaField({ purpose = "login", value, onChange, reloadKey = 0, onNotRequired, disabled }) {
  const [image, setImage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchCaptcha(purpose);
      if (!data.required) {
        setImage(null);
        onChange(null);
        onNotRequired?.();
        return;
      }
      setImage(dataUrlToObjectUrl(data.image));
      onChange({ captcha_id: data.captcha_id, captcha_answer: "" });
    } catch {
      setError("دریافت کد امنیتی ناموفق بود؛ دکمه‌ی تازه‌سازی را بزنید.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [purpose]);

  useEffect(() => {
    load();
  }, [load, reloadKey]);

  // آزادسازی آدرس blob: تصویر قبلی
  useEffect(() => {
    if (!image) return undefined;
    return () => URL.revokeObjectURL(image);
  }, [image]);

  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Box
        sx={{
          width: 180,
          height: 59,
          flexShrink: 0,
          borderRadius: 1,
          border: 1,
          borderColor: "divider",
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: "#f6f8fb",
        }}
      >
        {loading ? (
          <CircularProgress size={20} />
        ) : image ? (
          <img src={image} alt="کد امنیتی" width={180} height={59} style={{ display: "block" }} />
        ) : null}
      </Box>
      <Tooltip title="کد جدید">
        <span>
          <IconButton size="small" onClick={load} disabled={loading || disabled} aria-label="کد امنیتی جدید">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <TextField
        label="کد امنیتی"
        value={value?.captcha_answer || ""}
        onChange={(e) => onChange({ captcha_id: value?.captcha_id || "", captcha_answer: e.target.value })}
        required
        disabled={disabled}
        error={Boolean(error)}
        helperText={error || undefined}
        inputProps={{ inputMode: "numeric", maxLength: 8, autoComplete: "off", dir: "ltr", style: { textAlign: "center", letterSpacing: 4 } }}
        sx={{ flex: 1, minWidth: 0 }}
      />
    </Stack>
  );
}
