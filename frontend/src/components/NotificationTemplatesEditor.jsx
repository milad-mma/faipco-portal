/**
 * ویرایش متن اعلان‌های (Push) یک ماژول برای یک سایت (مرخصی/ماموریت، وام، …).
 * ورودی: load() → [{key, label, recipient, when, default, text, customized, vars}] و save(texts) با همان خروجی.
 * متن خالی یا «متن پیش‌فرض» = برگشت به پیش‌فرض. متغیرها (مثل {amount}) هنگام ارسال با مقدار واقعی جایگزین می‌شوند.
 */
import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Stack, TextField, Typography } from "@mui/material";
import ResultDialog from "./ResultDialog";

export default function NotificationTemplatesEditor({ load, save }) {
  const [items, setItems] = useState(null);
  const [texts, setTexts] = useState({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);

  const apply = (rows) => {
    setItems(rows);
    setTexts(Object.fromEntries(rows.map((r) => [r.key, r.text])));
  };

  useEffect(() => {
    setItems(null);
    setError("");
    load()
      .then(apply)
      .catch((e) => setError(e?.response?.data?.detail || "دریافت متن اعلان‌ها ناموفق بود"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  const onSave = async () => {
    setSaving(true);
    setError("");
    try {
      apply(await save(texts));
      setResult({ severity: "success", text: "متن اعلان‌ها ذخیره شد" });
    } catch (e) {
      setError(e?.response?.data?.detail || "ذخیره ناموفق بود");
    } finally {
      setSaving(false);
    }
  };

  if (error && !items) return <Alert severity="error">{error}</Alert>;
  if (!items) return <CircularProgress />;

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        متن هر اعلان را می‌توانید تغییر دهید. متغیرهای داخل آکولاد (مثل {"{amount}"}) هنگام ارسال با مقدار واقعی جایگزین
        می‌شوند. متن خالی یعنی متن پیش‌فرض.
      </Typography>
      {items.map((t) => {
        const value = texts[t.key] ?? "";
        const isDefault = value.trim() === t.default || !value.trim();
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
                minRows={2}
                fullWidth
                inputProps={{ maxLength: 500 }}
                placeholder={t.default}
              />
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                {Object.entries(t.vars || {}).map(([name, desc]) => (
                  <Chip
                    key={name}
                    size="small"
                    variant="outlined"
                    label={`{${name}} = ${desc}`}
                    onClick={() => setTexts((prev) => ({ ...prev, [t.key]: `${prev[t.key] || ""}{${name}}` }))}
                  />
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
