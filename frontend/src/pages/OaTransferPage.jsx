// «انتقال کارهای باز» (مجوز automation.reassign): کارهای باز فرد ترک‌کار/جابه‌جا به جایگزین منتقل می‌شود.
// فقط کارهای غیرمحرمانه فهرست می‌شوند؛ درباره‌ی محرمانه فقط یک عبارت ثابت (بدون تعداد، موضوع یا طرفین).
import { useEffect, useState } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import SwapHorizOutlinedIcon from "@mui/icons-material/SwapHorizOutlined";
import { doTaskTransfer, fetchTransferCandidates, fetchTransferHistory, fetchTransferPreview } from "../api/automationLetters";
import { toPersianDigits } from "../utils/searchText";

const KIND = { action: "اقدام", info: "اطلاع", paraph: "پاراف", approve: "تأیید", sign: "امضا" };
const fmt = (d) => (d ? new Date(d).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "");

function PersonSearch({ side, label, value, onChange, disabled }) {
  const [q, setQ] = useState("");
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    const t = setTimeout(() => {
      fetchTransferCandidates(side, q)
        .then((d) => alive && setOptions(d))
        .catch(() => alive && setOptions([]))
        .finally(() => alive && setLoading(false));
    }, 300);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [side, q]);
  return (
    <Autocomplete
      options={options}
      value={value}
      disabled={disabled}
      loading={loading}
      filterOptions={(x) => x}
      isOptionEqualToValue={(a, b) => a.employee_id === b.employee_id}
      getOptionLabel={(o) => o.name || ""}
      onChange={(_, v) => onChange(v)}
      onInputChange={(_, v) => setQ(v)}
      noOptionsText={side === "from" ? "کسی با کار باز پیدا نشد" : "کسی پیدا نشد"}
      renderOption={(props, o) => (
        <li {...props} key={o.employee_id}>
          <Stack sx={{ width: "100%" }}>
            <Stack direction="row" alignItems="center" gap={1}>
              <Typography variant="body2" fontWeight={600}>{o.name}</Typography>
              {side === "from" && !o.active && <Chip size="small" color="warning" label="غیرفعال" sx={{ height: 18, fontSize: 10 }} />}
              {side === "from" && o.normal_open > 0 && (
                <Chip size="small" variant="outlined" label={`${toPersianDigits(o.normal_open)} کار باز`} sx={{ height: 18, fontSize: 10 }} />
              )}
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {[o.title, o.department].filter(Boolean).join(" — ")}
            </Typography>
          </Stack>
        </li>
      )}
      renderInput={(params) => <TextField {...params} size="small" label={label} />}
    />
  );
}

export default function OaTransferPage() {
  const [from, setFrom] = useState(null);
  const [to, setTo] = useState(null);
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState(null);

  const loadHistory = () => fetchTransferHistory().then(setHistory).catch(() => setHistory([]));
  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    setPreview(null);
    if (!from) return;
    fetchTransferPreview(from.employee_id)
      .then(setPreview)
      .catch((err) => setError(err.response?.data?.detail || "دریافت کارهای باز ناموفق بود."));
  }, [from]);

  async function submit() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await doTaskTransfer(from.employee_id, to.employee_id, reason));
      setFrom(null);
      setTo(null);
      setReason("");
      loadHistory();
    } catch (err) {
      setError(err.response?.data?.detail || "انتقال انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <Typography variant="h5" fontWeight={800} sx={{ mb: 0.5 }}>
        انتقال کارهای باز
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        برای کسی که ترک کار کرده یا جابه‌جا شده: همه‌ی کارهای باز او (اقدام، اطلاع و نوبت‌های تأیید/پاراف/امضا) به جایگزین منتقل
        می‌شود. نامه‌ها و سابقه‌ی او حذف نمی‌شوند و در هر نامه ثبت می‌شود که چه کسی، کی و چرا منتقل کرده است. این کار به شما اجازه‌ی
        خواندن نامه‌های محرمانه نمی‌دهد.
      </Typography>

      <Card variant="outlined" sx={{ p: 2, borderRadius: 2, mb: 2 }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
            <Box sx={{ flex: 1 }}>
              <PersonSearch side="from" label="فرد قبلی" value={from} onChange={setFrom} disabled={busy} />
            </Box>
            <SwapHorizOutlinedIcon color="action" sx={{ alignSelf: "center" }} />
            <Box sx={{ flex: 1 }}>
              <PersonSearch side="to" label="جایگزین" value={to} onChange={setTo} disabled={busy} />
            </Box>
          </Stack>
          {from && !preview && <CircularProgress size={22} />}
          {preview && (
            <Box>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                کارهای باز غیرمحرمانه‌ی {preview.person.name}
                {!preview.person.active ? " (غیرفعال)" : ""}
              </Typography>
              {preview.items.length === 0 ? (
                <Typography variant="body2" color="text.secondary">کار باز غیرمحرمانه‌ای ندارد.</Typography>
              ) : (
                <Stack spacing={0.5}>
                  {preview.items.map((it, i) => (
                    <Stack key={i} direction="row" gap={1} alignItems="center" sx={{ p: 0.75, bgcolor: "action.hover", borderRadius: 1 }}>
                      <Chip size="small" variant="outlined" label={KIND[it.kind] || it.kind} />
                      <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }} noWrap>{it.subject || "(بدون موضوع)"}</Typography>
                      {it.number && <Typography variant="caption" color="text.secondary"><bdi dir="ltr">{toPersianDigits(it.number)}</bdi></Typography>}
                      {it.due_at && <Typography variant="caption" color="text.secondary">مهلت {fmt(it.due_at)}</Typography>}
                    </Stack>
                  ))}
                </Stack>
              )}
              <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>{preview.note}</Typography>
            </Box>
          )}
          <TextField size="small" label="دلیل انتقال" value={reason} onChange={(e) => setReason(e.target.value)} disabled={busy} multiline maxRows={4} inputProps={{ maxLength: 2000 }} />
          <Box>
            <Button variant="contained" onClick={submit} disabled={busy || !from || !to || !reason.trim()} sx={{ height: 40 }}>
              {busy ? "در حال انتقال..." : "انتقال کارهای باز"}
            </Button>
          </Box>
          {error && <Alert severity="error">{error}</Alert>}
          {result && (
            <Alert severity="success">
              {toPersianDigits(result.moved.length)} کار غیرمحرمانه منتقل شد. {result.note}
            </Alert>
          )}
        </Stack>
      </Card>

      <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>سابقه‌ی انتقال‌ها</Typography>
      {history === null ? (
        <CircularProgress size={22} />
      ) : history.length === 0 ? (
        <Typography variant="body2" color="text.secondary">انتقالی ثبت نشده است.</Typography>
      ) : (
        <Stack spacing={1}>
          {history.map((h) => (
            <Card key={h.id} variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
              <Typography variant="body2" fontWeight={600}>
                {h.from} ← {h.to}
              </Typography>
              <Typography variant="caption" color="text.secondary" component="div">
                {fmt(h.at)} — توسط {h.by || "—"} — {toPersianDigits(h.visible.length)} کار غیرمحرمانه — دلیل: {h.reason}
              </Typography>
            </Card>
          ))}
        </Stack>
      )}
    </Box>
  );
}
