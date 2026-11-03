// تب «دبیرخانه‌ها» در تنظیمات اتوماسیون: پیشوند شماره‌ی هر سایت (فقط از پرتال، بدون پیش‌فرض، یکتا).
// الگوی شماره: {پیشوند}/{سال شمسی}/{ترتیب شش‌رقمی}. بعد از صدور اولین شماره پیشوند قفل می‌شود.
import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, Chip, CircularProgress, Stack, TextField, Typography } from "@mui/material";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import { fetchSecretariats, saveSecretariat } from "../../api/automationLetters";
import { toPersianDigits } from "../../utils/searchText";

function Row({ row, onSaved }) {
  const [prefix, setPrefix] = useState(row.number_prefix || "");
  const [name, setName] = useState(row.name || "دبیرخانه");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const dirty = prefix !== (row.number_prefix || "") || name !== (row.name || "دبیرخانه");

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      onSaved(await saveSecretariat(row.site_id, { number_prefix: prefix.trim(), name: name.trim() }));
      setMsg({ ok: true, text: "ذخیره شد." });
    } catch (err) {
      setMsg({ ok: false, text: err.response?.data?.detail || "ذخیره نشد." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" gap={1} sx={{ mb: 1.5 }} flexWrap="wrap">
        <Typography fontWeight={700} sx={{ flex: 1 }}>{row.site_name}</Typography>
        {!row.number_prefix && <Chip size="small" color="warning" label="پیشوند تعیین نشده — ارسال نامه ممکن نیست" />}
        {row.locked && <Chip size="small" icon={<LockOutlinedIcon />} label={`${toPersianDigits(row.issued_count)} شماره صادر شده`} />}
      </Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "flex-start" }}>
        <TextField
          size="small"
          label="پیشوند شماره"
          value={prefix}
          onChange={(e) => setPrefix(e.target.value.replace(/\s/g, ""))}
          disabled={row.locked || busy}
          inputProps={{ maxLength: 10, dir: "ltr" }}
          helperText={row.locked ? "بعد از صدور اولین شماره قابل تغییر نیست" : "۱ تا ۱۰ نویسه، فقط رقم یا حروف لاتین"}
          sx={{ width: { sm: 200 } }}
        />
        <TextField size="small" label="نام دبیرخانه" value={name} onChange={(e) => setName(e.target.value)} disabled={busy} inputProps={{ maxLength: 200 }} sx={{ flex: 1 }} />
        <Button variant="contained" onClick={save} disabled={busy || !dirty || !prefix.trim()} sx={{ height: 40 }}>ذخیره</Button>
      </Stack>
      {row.sample && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          شماره‌ی بعدی: <bdi dir="ltr" style={{ fontWeight: 700 }}>{row.sample}</bdi>
        </Typography>
      )}
      {msg && <Alert severity={msg.ok ? "success" : "error"} sx={{ mt: 1 }}>{msg.text}</Alert>}
    </Card>
  );
}

export default function SecretariatsTab() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetchSecretariats()
      .then(setRows)
      .catch((err) => setError(err.response?.data?.detail || "دریافت ناموفق بود."));
  }, []);
  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        هر نامه هنگام ارسال یک شماره‌ی رسمی از دبیرخانه‌ی سایت خودش می‌گیرد، با الگوی
        <bdi dir="ltr"> پیشوند/سال/ترتیب </bdi>
        (مثل <bdi dir="ltr">01/1405/000125</bdi>). شمارش هر سال شمسی از ۱ شروع می‌شود و شماره‌ی تکراری صادر نمی‌شود.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      {!rows && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {rows?.map((r) => <Row key={`${r.site_id}-${r.number_prefix}-${r.issued_count}`} row={r} onSaved={setRows} />)}
    </Stack>
  );
}
