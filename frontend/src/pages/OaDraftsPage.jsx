// «پیش‌نویس‌های من» — اتوماسیون اداری فاز ۲. فهرست پیش‌نویس‌های شخصی کاربر (فقط خودش می‌بیند) و ساخت نامه‌ی تازه
// (سایت، قالب و اندازه‌ی کاغذ). مجوز automation.compose.
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { createDraft, fetchComposeOptions, fetchMyDrafts } from "../api/automationLetters";

export default function OaDraftsPage() {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState(null);
  const [options, setOptions] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ site_id: "", template_id: "", paper_size: "A4" });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    Promise.all([fetchMyDrafts(), fetchComposeOptions()])
      .then(([d, o]) => {
        setDrafts(d);
        setOptions(o);
        if (o.sites.length === 1) setForm((f) => ({ ...f, site_id: o.sites[0].id }));
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت پیش‌نویس‌ها ناموفق بود."));
  }, []);

  const siteTemplates = useMemo(
    () => (options?.templates || []).filter((t) => t.site_id === Number(form.site_id)),
    [options, form.site_id],
  );

  // با انتخاب سایت، اولین قالب و اندازه‌ی پیش‌فرض آن انتخاب می‌شود
  function pickSite(siteId) {
    const first = (options?.templates || []).find((t) => t.site_id === Number(siteId));
    setForm({ site_id: siteId, template_id: first?.id || "", paper_size: first?.default_paper_size || "A4" });
  }

  async function handleCreate() {
    setCreating(true);
    setCreateError("");
    try {
      const d = await createDraft({
        site_id: Number(form.site_id),
        template_id: form.template_id ? Number(form.template_id) : null,
        paper_size: form.paper_size,
      });
      navigate(`/automation/drafts/${d.id}`);
    } catch (err) {
      setCreateError(err.response?.data?.detail || "ساخت پیش‌نویس ناموفق بود.");
      setCreating(false);
    }
  }

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!drafts || !options) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }} flexWrap="wrap" gap={1}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            پیش‌نویس‌های من
          </Typography>
          <Typography variant="body2" color="text.secondary">
            پیش‌نویس‌ها فقط برای خود شما دیده می‌شوند. ارسال نامه در مرحله‌ی بعدی اتوماسیون اضافه می‌شود.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)} sx={{ height: 40 }}>
          نامه‌ی جدید
        </Button>
      </Stack>

      {drafts.length === 0 ? (
        <Alert severity="info">هنوز پیش‌نویسی ندارید.</Alert>
      ) : (
        <Stack spacing={1.5}>
          {drafts.map((d) => (
            <Card key={d.id} variant="outlined" sx={{ borderRadius: 2 }}>
              <CardActionArea onClick={() => navigate(`/automation/drafts/${d.id}`)} sx={{ p: 2 }}>
                <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap" sx={{ mb: 0.5 }}>
                  <Typography fontWeight={700}>{d.subject || "(بدون موضوع)"}</Typography>
                  <Chip size="small" label={d.paper_size} />
                  {d.urgency !== "normal" && <Chip size="small" color="warning" label={options.urgencies[d.urgency]} />}
                  {d.confidentiality !== "normal" && <Chip size="small" color="error" label={options.confidentiality[d.confidentiality]} />}
                  {options.sites.length > 1 && <Chip size="small" variant="outlined" label={d.site_name} />}
                </Stack>
                <Typography variant="body2" color="text.secondary" noWrap>
                  {d.excerpt || "—"}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  آخرین تغییر: {new Date(d.updated_at).toLocaleString("fa-IR")}
                </Typography>
              </CardActionArea>
            </Card>
          ))}
        </Stack>
      )}

      <Dialog open={open} onClose={() => !creating && setOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>نامه‌ی جدید</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {options.sites.length > 1 && (
              <TextField select size="small" label="سایت" value={form.site_id} onChange={(e) => pickSite(e.target.value)}>
                {options.sites.map((s) => (
                  <MenuItem key={s.id} value={s.id}>
                    {s.name}
                  </MenuItem>
                ))}
              </TextField>
            )}
            <TextField
              select
              size="small"
              label="قالب (سربرگ)"
              value={form.template_id}
              onChange={(e) => {
                const t = siteTemplates.find((x) => x.id === Number(e.target.value));
                setForm((f) => ({ ...f, template_id: e.target.value, paper_size: t?.default_paper_size || f.paper_size }));
              }}
              disabled={!form.site_id}
              helperText={form.site_id && siteTemplates.length === 0 ? "برای این سایت هنوز قالبی ساخته نشده؛ نامه بدون سربرگ ساخته می‌شود." : ""}
            >
              <MenuItem value="">بدون قالب</MenuItem>
              {siteTemplates.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField select size="small" label="اندازه‌ی کاغذ" value={form.paper_size} onChange={(e) => setForm((f) => ({ ...f, paper_size: e.target.value }))}>
              <MenuItem value="A4">A4</MenuItem>
              <MenuItem value="A5">A5</MenuItem>
            </TextField>
            {createError && <Alert severity="error">{createError}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)} disabled={creating}>
            انصراف
          </Button>
          <Button variant="contained" onClick={handleCreate} disabled={creating || !form.site_id}>
            {creating ? "در حال ساخت..." : "ساخت پیش‌نویس"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
