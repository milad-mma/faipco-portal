/**
 * فرم اطلاعات یک بانک (شماره حساب، شبا، شماره کارت بر اساس حالت هر فیلد در تنظیمات همان بانک).
 * ورودی: bank (تعریف بانک با *_mode و account فعلی)، onSave(payload) که Promise برمی‌گرداند، disabled، saveDisabled
 * (فقط دکمه‌ی ذخیره؛ مثلاً تا تیک تعهد زده نشده).
 * در صفحه‌ی «اطلاعات بانکی» پرسنل و دیالوگ اصلاح منابع انسانی استفاده می‌شود.
 */
import { useState } from "react";
import { Alert, Button, CircularProgress, InputAdornment, Stack, TextField } from "@mui/material";
import { BANK_FIELDS, cleanBankValue, fieldError, shebaDigits } from "../utils/bank";

// شبا در فرم فقط ۲۴ رقم است (IR ثابت کنار فیلد)؛ در دیتابیس IR + ۲۴ رقم ذخیره می‌شود
const clean = (key, value) => (key === "sheba" ? shebaDigits(value) : cleanBankValue(value));

function initialValues(bank) {
  const acc = bank.account || {};
  return Object.fromEntries(BANK_FIELDS.map((f) => [f.key, f.key === "sheba" ? shebaDigits(acc.sheba) : acc[f.key] || ""]));
}

export default function BankAccountForm({ bank, onSave, disabled, saveDisabled }) {
  const [values, setValues] = useState(() => initialValues(bank));
  const [touched, setTouched] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const visible = BANK_FIELDS.filter((f) => bank[`${f.key}_mode`] !== "hidden");
  const errors = Object.fromEntries(
    visible.map((f) => [f.key, fieldError(f.key, values[f.key], bank[`${f.key}_mode`])]),
  );
  const hasErrors = visible.some((f) => errors[f.key]);
  const original = initialValues(bank);
  const dirty = visible.some((f) => clean(f.key, values[f.key]) !== clean(f.key, original[f.key]));

  async function handleSave() {
    setTouched(Object.fromEntries(visible.map((f) => [f.key, true])));
    if (hasErrors) return;
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const payload = Object.fromEntries(
        visible.map((f) => {
          const value = clean(f.key, values[f.key]);
          return [f.key, f.key === "sheba" && value ? `IR${value}` : value];
        }),
      );
      await onSave(payload);
      setSaved(true);
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره با خطا مواجه شد.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack spacing={1.5}>
      {visible.map((f) => {
        const mode = bank[`${f.key}_mode`];
        const showError = touched[f.key] && errors[f.key];
        return (
          <TextField
            key={f.key}
            size="small"
            label={`${f.label}${mode === "required" ? " *" : " (اختیاری)"}`}
            placeholder={f.placeholder}
            value={values[f.key]}
            onChange={(e) => {
              const raw = e.target.value;
              setValues((v) => ({ ...v, [f.key]: f.key === "sheba" ? shebaDigits(raw) : raw }));
              setSaved(false);
            }}
            onBlur={() => setTouched((t) => ({ ...t, [f.key]: true }))}
            error={Boolean(showError)}
            helperText={showError || " "}
            disabled={disabled || saving}
            inputProps={{ dir: "ltr", inputMode: "numeric", maxLength: f.key === "sheba" ? undefined : f.maxLength }}
            InputProps={
              f.key === "sheba"
                ? {
                    // در صفحه‌ی راست‌به‌چپ، endAdornment سمت چپ ارقام می‌نشیند: «IR 1234...»
                    endAdornment: (
                      <InputAdornment position="end" sx={{ "& p": { fontWeight: 700 } }}>
                        IR
                      </InputAdornment>
                    ),
                  }
                : undefined
            }
            fullWidth
          />
        );
      })}
      {error && <Alert severity="error">{error}</Alert>}
      {saved && !dirty && <Alert severity="success">ذخیره شد.</Alert>}
      <Button
        variant="contained"
        onClick={handleSave}
        disabled={disabled || saveDisabled || saving || !dirty}
        startIcon={saving ? <CircularProgress size={16} color="inherit" /> : null}
        sx={{ alignSelf: "flex-start", height: 40 }}
      >
        ذخیره
      </Button>
    </Stack>
  );
}
