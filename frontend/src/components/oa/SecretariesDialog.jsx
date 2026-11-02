// «منشی‌های من»: منشی برای من پیش‌نویس تهیه می‌کند و به نام من ارسال می‌کند. کارتابل من را نمی‌بیند.
// پایین پنجره: کسانی که من منشی آن‌ها هستم (در نوشتن نامه گزینه‌ی «از طرف» را دارم).
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import PersonAddAltOutlinedIcon from "@mui/icons-material/PersonAddAltOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import PersonPicker from "./PersonPicker";
import { addMySecretary, fetchMySecretaries, removeMySecretary } from "../../api/automationLetters";
import { toPersianDigits } from "../../utils/searchText";

const personText = (p) => `${p.name}${p.title ? ` — ${p.title}` : ""}${p.department ? ` (${p.department})` : ""}`;

export default function SecretariesDialog({ open, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError("");
    fetchMySecretaries()
      .then(setData)
      .catch((err) => setError(err.response?.data?.detail || "دریافت ناموفق بود."));
  }, [open]);

  async function run(fn) {
    setBusy(true);
    setError("");
    try {
      setData(await fn());
    } catch (err) {
      setError(err.response?.data?.detail || "انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  async function addPeople(list) {
    setPickerOpen(false);
    await run(async () => {
      let last = data;
      for (const p of list) last = await addMySecretary(p.employee_id);
      return last;
    });
  }

  const full = data && data.secretaries.length >= data.max;

  return (
    <>
      <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="sm">
        <DialogTitle>منشی‌های من</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            منشی می‌تواند برای شما نامه بنویسد و آن را به نام شما ارسال کند. در گردش نامه ثبت می‌شود که منشی ارسال کرده است.
            منشی کارتابل و نامه‌های دریافتی شما را نمی‌بیند.
          </Typography>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {!data && !error && <CircularProgress size={24} />}
          {data && (
            <Stack spacing={1}>
              {data.secretaries.length === 0 && <Alert severity="info">منشی ندارید.</Alert>}
              {data.secretaries.map((s) => (
                <Stack key={s.id} direction="row" alignItems="center" spacing={1} sx={{ p: 1, borderRadius: 1, bgcolor: "action.hover" }}>
                  <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }} noWrap>{personText(s)}</Typography>
                  <IconButton size="small" color="error" disabled={busy} onClick={() => run(() => removeMySecretary(s.id))} aria-label="حذف">
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Stack>
              ))}
              <Box>
                <Button variant="outlined" startIcon={<PersonAddAltOutlinedIcon />} disabled={busy || full} onClick={() => setPickerOpen(true)} sx={{ height: 40 }}>
                  افزودن منشی
                </Button>
                {full && (
                  <Typography variant="caption" color="text.secondary" sx={{ mx: 1 }}>
                    حداکثر {toPersianDigits(data.max)} منشی
                  </Typography>
                )}
              </Box>
              {data.principals.length > 0 && (
                <Box sx={{ pt: 2 }}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.5 }}>شما منشی این افراد هستید</Typography>
                  <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1 }}>
                    هنگام نوشتن نامه از گزینه‌ی «از طرف» استفاده کنید.
                  </Typography>
                  {data.principals.map((p) => (
                    <Typography key={p.employee_id} variant="body2">• {personText(p)}</Typography>
                  ))}
                </Box>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={busy}>بستن</Button>
        </DialogActions>
      </Dialog>
      <PersonPicker
        open={pickerOpen}
        title="انتخاب منشی"
        exclude={(data?.secretaries || []).map((s) => s.employee_id)}
        onClose={() => setPickerOpen(false)}
        onConfirm={addPeople}
      />
    </>
  );
}
