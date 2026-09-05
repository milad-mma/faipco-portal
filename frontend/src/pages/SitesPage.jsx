import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  Snackbar,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import SettingsEthernetOutlinedIcon from "@mui/icons-material/SettingsEthernetOutlined";
import ViewColumnOutlinedIcon from "@mui/icons-material/ViewColumnOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { createSite, deleteSite, fetchSites, setSiteActive } from "../api/sites";

export default function SitesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const canManage = Boolean(user?.can_manage_sites);
  const [sites, setSites] = useState(null);
  const [siteDialogOpen, setSiteDialogOpen] = useState(false);

  const [newSite, setNewSite] = useState({ name: "", code: "", description: "" });
  const [error, setError] = useState("");
  const [snackbar, setSnackbar] = useState("");
  const [togglingId, setTogglingId] = useState(null);
  const [deleteDialogSite, setDeleteDialogSite] = useState(null);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [deactivateDialogSite, setDeactivateDialogSite] = useState(null);

  function loadSites() {
    fetchSites().then(setSites);
  }

  useEffect(() => {
    loadSites();
  }, []);

  async function applyToggleActive(site, nextActive) {
    setTogglingId(site.id);
    try {
      const updated = await setSiteActive(site.id, nextActive);
      setSites((prev) => prev.map((s) => (s.id === site.id ? updated : s)));
      setSnackbar(
        nextActive
          ? `سایت «${site.name}» فعال شد.`
          : `سایت «${site.name}» و همگام‌سازی خودکار آن غیرفعال شد.`
      );
    } catch (err) {
      setSnackbar(err.response?.data?.detail || "تغییر وضعیت سایت با خطا مواجه شد.");
    } finally {
      setTogglingId(null);
    }
  }

  function handleToggleActive(site) {
    if (site.is_active) {
      // غیرفعال‌کردن سایت اثر جانبی مهم دارد (خاموش‌شدن خودکار Sync)، پس با
      // یک Dialog صریح و دکمه‌های تأیید/انصراف از Admin تأییدیه گرفته می‌شود.
      setDeactivateDialogSite(site);
    } else {
      applyToggleActive(site, true);
    }
  }

  function handleConfirmDeactivate() {
    if (!deactivateDialogSite) return;
    const site = deactivateDialogSite;
    setDeactivateDialogSite(null);
    applyToggleActive(site, false);
  }

  function openDeleteDialog(site) {
    setDeleteDialogSite(site);
    setDeleteConfirmText("");
  }

  async function handleDeleteSite() {
    if (deleteConfirmText.trim() !== "DELETE" || !deleteDialogSite) return;
    setIsDeleting(true);
    try {
      await deleteSite(deleteDialogSite.id);
      setSnackbar(`سایت «${deleteDialogSite.name}» و همه واحدها/پرسنل آن برای همیشه حذف شد.`);
      setDeleteDialogSite(null);
      loadSites();
    } catch (err) {
      setSnackbar(err.response?.data?.detail || "حذف سایت با خطا مواجه شد.");
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleCreateSite() {
    setError("");
    try {
      await createSite(newSite);
      setSiteDialogOpen(false);
      setNewSite({ name: "", code: "", description: "" });
      loadSites();
    } catch (err) {
      setError(err.response?.data?.detail || "ساخت سایت با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3, flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            سایت‌ها
          </Typography>
          <Typography variant="body2" color="text.secondary">
            هر سایت متعلق به یک کارخانه/شعبه است و یک اتصال دیتابیس + یک Mapping ستون دارد
          </Typography>
        </Box>
        {canManage && (
          <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={() => setSiteDialogOpen(true)}>
            سایت جدید
          </Button>
        )}
      </Box>

      <Grid container spacing={2.5}>
        {sites === null ? (
          <Grid item xs={12}>
            <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
              <CircularProgress />
            </Box>
          </Grid>
        ) : (
          sites.map((site) => (
          <Grid item xs={12} md={6} lg={4} key={site.id}>
            <Card variant="outlined" sx={{ p: 3, borderRadius: 3, height: "100%" }}>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="subtitle1" fontWeight={700}>
                    {site.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    کد: {site.code}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <Chip
                    size="small"
                    label={site.is_active ? "فعال" : "غیرفعال"}
                    color={site.is_active ? "success" : "default"}
                    variant="outlined"
                  />
                  {canManage && (
                    <Switch
                      size="small"
                      checked={site.is_active}
                      disabled={togglingId === site.id}
                      onChange={() => handleToggleActive(site)}
                    />
                  )}
                </Stack>
              </Stack>

              {site.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                  {site.description}
                </Typography>
              )}

              <Divider sx={{ my: 2 }} />

              {canManage && (
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<SettingsEthernetOutlinedIcon />}
                    onClick={() => navigate(`/sites/${site.id}/settings?tab=connection`)}
                  >
                    اتصال دیتابیس
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<ViewColumnOutlinedIcon />}
                    onClick={() => navigate(`/sites/${site.id}/settings?tab=mapping`)}
                  >
                    Mapping ستون‌ها
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    startIcon={<DeleteOutlineIcon />}
                    onClick={() => openDeleteDialog(site)}
                  >
                    حذف سایت
                  </Button>
                </Stack>
              )}
            </Card>
          </Grid>
          ))
        )}
      </Grid>

      {/* Dialog: ساخت سایت جدید */}
      <Dialog open={siteDialogOpen} onClose={() => setSiteDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>سایت جدید</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <TextField
            label="نام سایت"
            fullWidth
            value={newSite.name}
            onChange={(e) => setNewSite({ ...newSite, name: e.target.value })}
          />
          <TextField
            label="کد سایت (یکتا)"
            fullWidth
            value={newSite.code}
            onChange={(e) => setNewSite({ ...newSite, code: e.target.value })}
          />
          <TextField
            label="توضیحات (اختیاری)"
            fullWidth
            multiline
            rows={2}
            value={newSite.description}
            onChange={(e) => setNewSite({ ...newSite, description: e.target.value })}
          />
          {error && <Alert severity="error">{error}</Alert>}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setSiteDialogOpen(false)}>انصراف</Button>
          <Button variant="contained" onClick={handleCreateSite}>
            ذخیره
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: تأیید غیرفعال‌کردن سایت — چون این کار خودکار Sync آن را هم
          خاموش می‌کند، Admin باید صریحاً این اثر جانبی را تأیید کند. */}
      <Dialog
        open={Boolean(deactivateDialogSite)}
        onClose={() => setDeactivateDialogSite(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>غیرفعال‌کردن سایت «{deactivateDialogSite?.name}»</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            با غیرفعال‌کردن این سایت، همگام‌سازی خودکار آن نیز به‌صورت خودکار خاموش می‌شود
            (بدون حذف اطلاعات اتصال دیتابیس) — می‌توانید بعداً از صفحه «همگام‌سازی دیتابیس»
            دوباره روشنش کنید.
          </Alert>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setDeactivateDialogSite(null)}>عدم تأیید</Button>
          <Button variant="contained" color="warning" onClick={handleConfirmDeactivate}>
            تأیید و غیرفعال‌سازی
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: حذف قطعی سایت — با تأییدیه قوی (تایپ‌کردن DELETE) چون این عملیات
          کل واحدهای سازمانی، پرسنل، اتصال دیتابیس و Mapping این سایت را هم حذف می‌کند */}
      <Dialog open={Boolean(deleteDialogSite)} onClose={() => !isDeleting && setDeleteDialogSite(null)} fullWidth maxWidth="xs">
        <DialogTitle color="error.main">حذف قطعی سایت «{deleteDialogSite?.name}»</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <Alert severity="error">
            این عملیات برگشت‌ناپذیر است. با حذف این سایت، همه واحدهای سازمانی، همه پرسنل
            سینک‌شده، اتصال دیتابیس و Mapping ستون‌های آن نیز برای همیشه حذف می‌شوند.
          </Alert>
          <Typography variant="body2">
            برای تأیید، عبارت <strong>DELETE</strong> را دقیقاً در کادر زیر تایپ کنید:
          </Typography>
          <TextField
            autoFocus
            fullWidth
            value={deleteConfirmText}
            onChange={(e) => setDeleteConfirmText(e.target.value)}
            placeholder="DELETE"
            disabled={isDeleting}
            sx={{ direction: "ltr" }}
            inputProps={{ style: { textAlign: "center", fontFamily: "monospace", letterSpacing: 2 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setDeleteDialogSite(null)} disabled={isDeleting}>
            انصراف
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDeleteSite}
            disabled={deleteConfirmText.trim() !== "DELETE" || isDeleting}
          >
            {isDeleting ? "در حال حذف..." : "حذف قطعی سایت"}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={Boolean(snackbar)}
        autoHideDuration={4000}
        onClose={() => setSnackbar("")}
        message={snackbar}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      />
    </Box>
  );
}
