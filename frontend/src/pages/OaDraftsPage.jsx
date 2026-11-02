// «پیش‌نویس‌های من» — فهرست پیش‌نویس‌های شخصی (فقط خود کاربر می‌بیند) و «نامه‌ی جدید» که مستقیم ویرایشگر را باز می‌کند
// (مثل ایمیل؛ قالب و کاغذ داخل ویرایشگر قابل تغییرند). نامه متعلق به سایت خود پرسنل است.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Box, Button, Card, CardActionArea, Chip, CircularProgress, Stack, Typography } from "@mui/material";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import { createDraft, fetchMyDrafts } from "../api/automationLetters";

const URGENCY = { urgent: "فوری", immediate: "آنی" };

export default function OaDraftsPage() {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchMyDrafts()
      .then(setDrafts)
      .catch((err) => setError(err.response?.data?.detail || "دریافت پیش‌نویس‌ها ناموفق بود."));
  }, []);

  async function handleNew() {
    setCreating(true);
    setError("");
    try {
      const d = await createDraft({});
      navigate(`/automation/drafts/${d.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "ساخت نامه ناموفق بود.");
      setCreating(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }} flexWrap="wrap" gap={1}>
        <Box>
          <Typography variant="h5" fontWeight={700}>پیش‌نویس‌های من</Typography>
          <Typography variant="body2" color="text.secondary">پیش‌نویس‌ها فقط برای خود شما دیده می‌شوند.</Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={creating ? <CircularProgress size={16} color="inherit" /> : <EditOutlinedIcon />}
          onClick={handleNew}
          disabled={creating}
          sx={{ height: 40, borderRadius: 5, px: 3 }}
        >
          نامه‌ی جدید
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {!drafts && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      )}
      {drafts && drafts.length === 0 && <Alert severity="info">هنوز پیش‌نویسی ندارید.</Alert>}
      {drafts && drafts.length > 0 && (
        <Stack spacing={1}>
          {drafts.map((d) => (
            <Card key={d.id} variant="outlined" sx={{ borderRadius: 2 }}>
              <CardActionArea onClick={() => navigate(`/automation/drafts/${d.id}`)} sx={{ p: 1.5 }}>
                <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
                  <Typography fontWeight={600} sx={{ flex: 1, minWidth: 0 }} noWrap>{d.subject || "(بدون موضوع)"}</Typography>
                  {URGENCY[d.urgency] && <Chip size="small" color="warning" label={URGENCY[d.urgency]} />}
                  {d.confidentiality === "confidential" && <Chip size="small" color="error" label="محرمانه" />}
                  <Typography variant="caption" color="text.secondary">{new Date(d.updated_at).toLocaleString("fa-IR")}</Typography>
                </Stack>
                <Typography variant="body2" color="text.secondary" noWrap>{d.excerpt || "—"}</Typography>
              </CardActionArea>
            </Card>
          ))}
        </Stack>
      )}
    </Box>
  );
}
