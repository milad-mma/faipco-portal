// پنل «گردش تأیید» در صفحه‌ی نامه: مراحل دور فعلی با وضعیت، دکمه‌های نوبت خود کاربر
// (پاراف / تأیید / تأیید و امضا، برگشت برای اصلاح با توضیح اجباری) و «پس گرفتن» برای نویسنده.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { approveStep, returnStep, withdrawLetter } from "../../api/automationLetters";
import { toPersianDigits } from "../../utils/searchText";

const STATUS = {
  approved: { label: "انجام شد", color: "success" },
  active: { label: "در نوبت", color: "warning" },
  pending: { label: "در انتظار", color: "default" },
  returned: { label: "برگشت برای اصلاح", color: "error" },
  cancelled: { label: "لغو شد", color: "default" },
};
const ACTION = { paraph: "پاراف", approve: "تأیید", sign: "تأیید و امضا" };
const fmt = (d) => (d ? new Date(d).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "");

export default function ApprovalPanel({ letter, onDone, onMessage }) {
  const navigate = useNavigate();
  const a = letter.approval;
  const [note, setNote] = useState("");
  const [returnOpen, setReturnOpen] = useState(false);
  const [returnNote, setReturnNote] = useState("");
  const [busy, setBusy] = useState(false);
  if (!a) return null;
  const my = a.my_step;
  const blockedSign = my?.kind === "sign" && !a.my_has_signature;

  async function run(fn, ok) {
    setBusy(true);
    try {
      const res = await fn();
      onMessage?.({ ok: true, text: typeof ok === "function" ? ok(res) : ok });
      await onDone?.();
      return true;
    } catch (err) {
      onMessage?.({ ok: false, text: err.response?.data?.detail || "انجام نشد." });
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card variant="outlined" sx={{ p: 2, borderRadius: 2, gridArea: "approval", borderColor: letter.status === "in_approval" ? "warning.main" : "divider" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1} flexWrap="wrap" sx={{ mb: 1 }}>
        <Typography variant="subtitle2" fontWeight={700}>
          گردش تأیید{a.round > 1 ? ` (دور ${toPersianDigits(a.round)})` : ""}
        </Typography>
        {letter.status === "in_approval" && <Chip size="small" color="warning" label="در انتظار تأیید — هنوز ارسال نشده" />}
      </Stack>
      <Stack spacing={0.75}>
        {a.steps.map((s) => (
          <Box key={s.id} sx={{ p: 1, borderRadius: 1, bgcolor: s.status === "active" ? "action.selected" : "action.hover", border: s.status === "active" ? 1 : 0, borderColor: "warning.light" }}>
            <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
              <Chip size="small" label={toPersianDigits(s.step_no)} />
              <Typography variant="body2" fontWeight={600} sx={{ flex: 1, minWidth: 0 }}>
                {s.name}
                {s.title ? ` — ${s.title}` : ""}
              </Typography>
              <Chip size="small" variant="outlined" label={s.kind_label} />
              <Chip size="small" color={STATUS[s.status]?.color || "default"} label={STATUS[s.status]?.label || s.status} />
            </Stack>
            {(s.acted_at || s.note) && (
              <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
                {fmt(s.acted_at)}
                {s.note ? ` — ${s.note}` : ""}
              </Typography>
            )}
          </Box>
        ))}
      </Stack>

      {my && (
        <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: "divider" }}>
          <Typography variant="body2" fontWeight={700} sx={{ mb: 1 }}>
            نوبت {ACTION[my.kind]} شماست
          </Typography>
          {blockedSign && (
            <Alert
              severity="warning"
              sx={{ mb: 1 }}
              action={<Button color="inherit" size="small" onClick={() => navigate("/automation/signature")}>امضای من</Button>}
            >
              برای «تأیید و امضا» اول در «اتوماسیون اداری ← امضای من» امضا ثبت کنید.
            </Alert>
          )}
          <TextField size="small" fullWidth multiline maxRows={4} placeholder="توضیح (اختیاری)" value={note} onChange={(e) => setNote(e.target.value)} inputProps={{ maxLength: 2000 }} sx={{ mb: 1, "& .MuiInputBase-root": { bgcolor: "background.paper" } }} />
          <Stack direction="row" spacing={1}>
            <Button
              variant="contained"
              color="success"
              disabled={busy || blockedSign}
              onClick={() => run(() => approveStep(my.id, note), (r) => (r?.dispatched ? "تأیید شد؛ نامه شماره گرفت و ارسال شد." : "ثبت شد؛ نوبت مرحله‌ی بعد است.")).then((ok) => ok && setNote(""))}
              sx={{ height: 40 }}
            >
              {ACTION[my.kind]}
            </Button>
            <Button variant="outlined" color="error" disabled={busy} onClick={() => setReturnOpen(true)} sx={{ height: 40 }}>
              برگشت برای اصلاح
            </Button>
          </Stack>
        </Box>
      )}

      {a.can_withdraw && (
        <Box sx={{ mt: 2 }}>
          <Button size="small" color="inherit" disabled={busy} onClick={() => run(() => withdrawLetter(letter.id), "نامه پس گرفته شد و دوباره پیش‌نویس است.").then((ok) => ok && navigate(`/automation/drafts/${letter.id}`))}>
            پس گرفتن و ویرایش
          </Button>
        </Box>
      )}

      {a.history?.length > 0 && (
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1.5 }}>
          دورهای قبل:{" "}
          {a.history
            .filter((h) => h.status === "returned")
            .map((h) => `${h.name} (${fmt(h.acted_at)}): ${h.note}`)
            .join(" | ") || "—"}
        </Typography>
      )}

      <Dialog open={returnOpen} onClose={() => !busy && setReturnOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>برگشت برای اصلاح</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            نامه به نویسنده برمی‌گردد تا اصلاح و دوباره برای تأیید ارسال کند.
          </Typography>
          <TextField autoFocus fullWidth multiline minRows={3} label="چه چیزی باید اصلاح شود؟" value={returnNote} onChange={(e) => setReturnNote(e.target.value)} inputProps={{ maxLength: 2000 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReturnOpen(false)} disabled={busy}>انصراف</Button>
          <Button
            variant="contained"
            color="error"
            disabled={busy || !returnNote.trim()}
            onClick={() => run(() => returnStep(my.id, returnNote), "نامه برای اصلاح برگشت داده شد.").then((ok) => {
              if (ok) {
                setReturnOpen(false);
                setReturnNote("");
              }
            })}
          >
            برگشت
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}
