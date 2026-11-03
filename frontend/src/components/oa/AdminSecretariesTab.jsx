// تب «منشی‌ها» در تنظیمات اتوماسیون (automation.settings): تعیین منشی برای مدیران سایت‌های مجاز.
// خود مدیر هم از کارتابل (دکمه‌ی «منشی‌ها») می‌تواند منشی تعیین کند.
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import PersonPicker from "./PersonPicker";
import { adminAddSecretary, adminRemoveSecretary, fetchAllSecretaries, fetchSecretaryPeople } from "../../api/automationLetters";

const personText = (p) => `${p.name}${p.title ? ` — ${p.title}` : ""}`;

export default function AdminSecretariesTab() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [principal, setPrincipal] = useState(null);
  const [picker, setPicker] = useState(null); // "principal" | "secretary"

  useEffect(() => {
    fetchAllSecretaries()
      .then(setRows)
      .catch((err) => setError(err.response?.data?.detail || "دریافت ناموفق بود."));
  }, []);

  async function run(fn) {
    setBusy(true);
    setError("");
    try {
      setRows(await fn());
      return true;
    } catch (err) {
      setError(err.response?.data?.detail || "انجام نشد.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function onPick(list) {
    const kind = picker;
    setPicker(null);
    if (!list.length) return;
    if (kind === "principal") {
      setPrincipal(list[0]);
      return;
    }
    let ok = true;
    for (const s of list) {
      ok = await run(() => adminAddSecretary(principal.employee_id, s.employee_id));
      if (!ok) break;
    }
    if (ok) setPrincipal(null);
  }

  return (
    <Stack spacing={2}>
      <Card variant="outlined" sx={{ p: 2 }}>
        <Typography fontWeight={700} sx={{ mb: 0.5 }}>تعیین منشی</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          منشی برای مدیر نامه می‌نویسد و به نام مدیر ارسال می‌کند (در گردش نامه نام منشی ثبت می‌شود). منشی کارتابل مدیر را
          نمی‌بیند. مدیر و منشی هر دو باید دسترسی اتوماسیون داشته باشند.
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
          <Button variant="outlined" onClick={() => setPicker("principal")} disabled={busy} sx={{ height: 40 }}>
            {principal ? `مدیر: ${principal.name}` : "۱. انتخاب مدیر"}
          </Button>
          <Button variant="contained" onClick={() => setPicker("secretary")} disabled={busy || !principal} sx={{ height: 40 }}>
            ۲. انتخاب منشی
          </Button>
          {principal && (
            <Button variant="text" color="inherit" onClick={() => setPrincipal(null)} disabled={busy} sx={{ height: 40 }}>
              انصراف
            </Button>
          )}
        </Stack>
      </Card>

      {error && <Alert severity="error">{error}</Alert>}
      {!rows && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {rows && rows.length === 0 && <Alert severity="info">هنوز منشی‌ای تعیین نشده است.</Alert>}
      {rows && rows.length > 0 && (
        <Card variant="outlined">
          {rows.map((r, i) => (
            <Stack
              key={r.id}
              direction={{ xs: "column", sm: "row" }}
              alignItems={{ sm: "center" }}
              spacing={1}
              sx={{ px: 2, py: 1.25, borderTop: i ? 1 : 0, borderColor: "divider" }}
            >
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2">
                  <b>مدیر:</b> {personText(r.principal)}
                  {!r.principal_active && <Chip size="small" color="warning" label="غیرفعال" sx={{ mx: 1 }} />}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  <b>منشی:</b> {personText(r.secretary)}
                  {!r.secretary_active && <Chip size="small" color="warning" label="غیرفعال" sx={{ mx: 1 }} />}
                </Typography>
              </Box>
              <Chip size="small" variant="outlined" label={r.site} />
              <IconButton color="error" disabled={busy} onClick={() => run(() => adminRemoveSecretary(r.id))} aria-label="حذف">
                <DeleteOutlineIcon />
              </IconButton>
            </Stack>
          ))}
        </Card>
      )}

      <PersonPicker
        open={Boolean(picker)}
        title={picker === "principal" ? "انتخاب مدیر (یک نفر)" : `انتخاب منشی برای ${principal?.name || ""}`}
        exclude={principal && picker === "secretary" ? [principal.employee_id] : []}
        onClose={() => setPicker(null)}
        onConfirm={onPick}
        fetcher={fetchSecretaryPeople}
        emptyText="کسی پیدا نشد. فقط پرسنل فعال سایت‌هایی که تنظیمات اتوماسیونشان با شماست و خودشان مجوز «استفاده از اتوماسیون اداری» دارند نمایش داده می‌شوند."
      />
    </Stack>
  );
}
