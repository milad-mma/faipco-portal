/**
 * ویرایش متن اعلان‌های (Push) / اطلاعیه‌های خودکار یک ماژول (برای یک سایت یا سراسری).
 * ورودی: load() → [{key, label, recipient, when, default, text, customized, vars, max_length}] و save(texts) با همان خروجی.
 * متن خالی یا «متن پیش‌فرض» = برگشت به پیش‌فرض. متغیرها (مثل {amount}) هنگام ارسال با مقدار واقعی جایگزین می‌شوند.
 * والد برای هر سایت key جدا می‌دهد (key={siteId}) تا با عوض شدن سایت، پاسخ دیررس سایت قبلی جای سایت جدید ننشیند.
 */
import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Stack, TextField, Typography } from "@mui/material";
import ResultDialog from "./ResultDialog";

export default function NotificationTemplatesEditor({ load, save }) {
  const [items, setItems] = useState(null);
  const [texts, setTexts] = useState({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const inputs = useRef({}); // کلید → عنصر textarea (برای درج متغیر در محل مکان‌نما)
  const loadRef = useRef(load);
  loadRef.current = load;

  const apply = (rows) => {
    setItems(rows);
    setTexts(Object.fromEntries(rows.map((r) => [r.key, r.text])));
  };

  useEffect(() => {
    let alive = true;
    setItems(null);
    setError("");
    load()
      .then((rows) => alive && apply(rows))
      .catch((e) => alive && setError(e?.response?.data?.detail || "دریافت متن اعلان‌ها ناموفق بود"));
    return () => {
      alive = false;
    };
  }, [load, reloadKey]);

  const onSave = async () => {
    const startedWith = load;
    setSaving(true);
    setError("");
    try {
      const rows = await save(texts);
      if (loadRef.current !== startedWith) return; // سایت در این فاصله عوض شده
      apply(rows);
      setResult({ severity: "success", text: "متن اعلان‌ها ذخیره شد" });
    } catch (e) {
      setError(e?.response?.data?.detail || "ذخیره ناموفق بود");
    } finally {
      setSaving(false);
    }
  };

  // درج {name} در محل مکان‌نما (نه آخر متن)، بدون عبور از سقف طول
  const insertVar = (t, name) => {
    const token = `{${name}}`;
    const el = inputs.current[t.key];
    const current = texts[t.key] ?? "";
    const start = el?.selectionStart ?? current.length;
    const end = el?.selectionEnd ?? current.length;
    const next = current.slice(0, start) + token + current.slice(end);
    if (next.length > (t.max_length || 500)) return;
    setTexts((prev) => ({ ...prev, [t.key]: next }));
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(start + token.length, start + token.length);
    });
  };

  if (error && !items) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={() => setReloadKey((k) => k + 1)}>
            تلاش مجدد
          </Button>
        }
      >
        {error}
      </Alert>
    );
  }
  if (!items) return <CircularProgress />;

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        متن هر اعلان را می‌توانید تغییر دهید. متغیرهای داخل آکولاد (مثل {"{amount}"}) هنگام ارسال با مقدار واقعی جایگزین
        می‌شوند؛ برای درج، مکان‌نما را بگذارید و روی متغیر بزنید. متن خالی یعنی متن پیش‌فرض.
      </Typography>
      {items.map((t) => {
        const value = texts[t.key] ?? "";
        const isDefault = value.trim() === t.default || !value.trim();
        const limit = t.max_length || 500;
        return (
          <Card key={t.key} variant="outlined" sx={{ borderRadius: 3 }}>
            <CardContent>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 0.5 }}>
                <Typography fontWeight={800}>{t.label}</Typography>
                {!isDefault && <Chip size="small" color="info" label="تغییریافته" />}
              </Stack>
              <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1 }}>
                گیرنده: {t.recipient} — زمان ارسال: {t.when}
              </Typography>
              <TextField
                value={value}
                onChange={(e) => setTexts((prev) => ({ ...prev, [t.key]: e.target.value }))}
                multiline
                minRows={limit < 500 ? 1 : 2}
                fullWidth
                inputRef={(el) => {
                  inputs.current[t.key] = el;
                }}
                inputProps={{ maxLength: limit }}
                placeholder={t.default}
                helperText={`${value.length.toLocaleString("fa-IR")} از ${limit.toLocaleString("fa-IR")} نویسه`}
              />
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                {Object.entries(t.vars || {}).map(([name, desc]) => (
                  <Chip key={name} size="small" variant="outlined" label={`{${name}} = ${desc}`} onClick={() => insertVar(t, name)} />
                ))}
                <Box sx={{ flex: 1 }} />
                <Button size="small" disabled={isDefault} onClick={() => setTexts((prev) => ({ ...prev, [t.key]: t.default }))}>
                  متن پیش‌فرض
                </Button>
              </Stack>
            </CardContent>
          </Card>
        );
      })}
      {error && <Alert severity="error">{error}</Alert>}
      <Button variant="contained" onClick={onSave} disabled={saving} sx={{ alignSelf: "flex-start" }}>
        ذخیره
      </Button>
      <ResultDialog result={result} onClose={() => setResult(null)} />
    </Stack>
  );
}
