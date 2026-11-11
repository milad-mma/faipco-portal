// «مسیر تأیید» در نوشتن نامه: افراد به ترتیب، هر کدام پاراف / تأیید / امضا. با مسیر، دکمه‌ی ارسال «ارسال برای تأیید» می‌شود.
// نامه‌ی «از طرف» مدیر: مرحله‌ی آخر خودکار «امضا»ی خود مدیر است (حذف‌شدنی نیست).
import { useState } from "react";
import { Alert, Box, Button, Chip, IconButton, MenuItem, Stack, TextField, Tooltip, Typography } from "@mui/material";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import CloseIcon from "@mui/icons-material/Close";
import AddIcon from "@mui/icons-material/Add";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import PersonPicker from "./PersonPicker";
import { setApprovalSteps } from "../../api/automationLetters";
import { toPersianDigits } from "../../utils/searchText";

const KINDS = { paraph: "پاراف", approve: "تأیید", sign: "امضا" };

export default function ApprovalPathEditor({ letterId, plan, onChange, disabled, onBusyChange, onErrorChange }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const steps = plan?.steps || [];
  const auto = plan?.auto_final;

  async function save(next) {
    setBusy(true);
    onBusyChange?.(true);
    setError("");
    onErrorChange?.(false);
    try {
      onChange(await setApprovalSteps(letterId, next.map((s) => ({ employee_id: s.employee_id, kind: s.kind }))));
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره‌ی مسیر تأیید ناموفق بود.");
      onErrorChange?.(true);
    } finally {
      setBusy(false);
      onBusyChange?.(false);
    }
  }

  const move = (i, d) => {
    const next = [...steps];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    save(next);
  };

  const lastReturned = (plan?.history || []).filter((h) => h.status === "returned").slice(-1)[0];

  return (
    <Box sx={{ px: 2, py: 1.5, borderTop: 1, borderColor: "divider" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: steps.length || auto ? 1 : 0 }}>
        <Typography variant="body2" fontWeight={700}>
          مسیر تأیید {steps.length || auto ? "" : <Typography component="span" variant="caption" color="text.secondary">(اختیاری — بدون مسیر، نامه مستقیم ارسال می‌شود)</Typography>}
        </Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={() => setPickerOpen(true)} disabled={disabled || busy}>
          افزودن مرحله
        </Button>
      </Stack>
      {lastReturned && (
        <Alert severity="warning" sx={{ mb: 1 }}>
          برگشت برای اصلاح توسط {lastReturned.name}: {lastReturned.note}
        </Alert>
      )}
      <Stack spacing={0.75}>
        {steps.map((s, i) => (
          <Stack key={s.id || s.employee_id} direction="row" alignItems="center" gap={{ xs: 0.25, sm: 1 }} sx={{ p: 0.75, borderRadius: 1, bgcolor: "action.hover", minWidth: 0 }}>
            <Chip size="small" label={toPersianDigits(i + 1)} />
            <Typography variant="body2" sx={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={`${s.name}${s.title ? ` — ${s.title}` : ""}`}>
              {s.name}
              {s.title ? ` — ${s.title}` : ""}
            </Typography>
            <TextField
              select
              size="small"
              variant="standard"
              value={s.kind}
              disabled={disabled || busy}
              onChange={(e) => save(steps.map((x, j) => (j === i ? { ...x, kind: e.target.value } : x)))}
              sx={{ width: 86, flexShrink: 0 }}
            >
              {Object.entries(KINDS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
            <IconButton size="small" disabled={disabled || busy || i === 0} onClick={() => move(i, -1)} aria-label="بالا"><ArrowUpwardIcon fontSize="small" /></IconButton>
            <IconButton size="small" disabled={disabled || busy || i === steps.length - 1} onClick={() => move(i, 1)} aria-label="پایین"><ArrowDownwardIcon fontSize="small" /></IconButton>
            <IconButton size="small" disabled={disabled || busy} onClick={() => save(steps.filter((_, j) => j !== i))} aria-label="حذف"><CloseIcon fontSize="small" /></IconButton>
          </Stack>
        ))}
        {auto && (
          <Tooltip title="نامه‌ای که از طرف مدیر نوشته می‌شود، آخر کار با امضای خود او ارسال می‌شود">
            <Stack direction="row" alignItems="center" gap={1} sx={{ p: 0.75, borderRadius: 1, bgcolor: "action.selected" }}>
              <Chip size="small" label={toPersianDigits(steps.length + 1)} />
              <Typography variant="body2" sx={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={`${auto.name}${auto.title ? ` — ${auto.title}` : ""}`}>
                {auto.name}
                {auto.title ? ` — ${auto.title}` : ""}
              </Typography>
              <Chip size="small" color="primary" variant="outlined" icon={<LockOutlinedIcon />} label="امضا (خودکار)" />
            </Stack>
          </Tooltip>
        )}
      </Stack>
      {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
      <PersonPicker
        open={pickerOpen}
        title="افزودن به مسیر تأیید (به ترتیب انتخاب)"
        exclude={[...steps.map((s) => s.employee_id), ...(auto ? [auto.employee_id] : [])]}
        onClose={() => setPickerOpen(false)}
        onConfirm={(list) => {
          setPickerOpen(false);
          save([...steps, ...list.map((p) => ({ employee_id: p.employee_id, kind: "approve", name: p.name, title: p.title }))]);
        }}
      />
    </Box>
  );
}
