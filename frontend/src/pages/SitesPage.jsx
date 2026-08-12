import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Grid,
  MenuItem,
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
import {
  createSite,
  deleteSite,
  deleteSiteConnection,
  deleteSiteMapping,
  fetchSiteConnection,
  fetchSiteMapping,
  fetchSites,
  setSiteActive,
  upsertSiteConnection,
  upsertSiteMapping,
} from "../api/sites";

const DB_TYPES = [
  { value: "postgresql", label: "PostgreSQL" },
  { value: "mysql", label: "MySQL" },
  { value: "mssql", label: "SQL Server" },
];

const EMPTY_CONNECTION = {
  db_type: "postgresql",
  host: "",
  port: 5432,
  database_name: "",
  username: "",
  password: "",
};
const EMPTY_MAPPING = {
  table_name: "",
  personnel_code_column: "",
  national_code_column: "",
  first_name_column: "",
  last_name_column: "",
  mobile_column: "",
  birth_date_column: "",
  is_active_column: "",
  is_active_inverted: false,
  department_column: "",
  department_lookup_table: "",
  department_lookup_id_column: "",
  department_lookup_name_column: "",
};

export default function SitesPage() {
  const [sites, setSites] = useState([]);
  const [siteDialogOpen, setSiteDialogOpen] = useState(false);
  const [connectionDialogSite, setConnectionDialogSite] = useState(null);
  const [mappingDialogSite, setMappingDialogSite] = useState(null);
  const [hasExistingConnection, setHasExistingConnection] = useState(false);
  const [hasExistingMapping, setHasExistingMapping] = useState(false);

  const [newSite, setNewSite] = useState({ name: "", code: "", description: "" });
  const [connectionForm, setConnectionForm] = useState(EMPTY_CONNECTION);
  const [mappingForm, setMappingForm] = useState(EMPTY_MAPPING);
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
      setSnackbar(err.response?.data?.detail || "تغییر وضعیت سایت ناموفق بود.");
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
      setSnackbar(err.response?.data?.detail || "حذف سایت ناموفق بود.");
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
      setError(err.response?.data?.detail || "ساخت سایت ناموفق بود");
    }
  }

  async function openConnectionDialog(site) {
    setError("");
    setConnectionDialogSite(site);
    setConnectionForm(EMPTY_CONNECTION);
    setHasExistingConnection(false);
    const existing = await fetchSiteConnection(site.id).catch(() => null);
    if (existing) {
      setConnectionForm({
        db_type: existing.db_type,
        host: existing.host,
        port: existing.port,
        database_name: existing.database_name,
        username: existing.username,
        password: "", // پسورد هرگز از سرور برنمی‌گردد؛ خالی یعنی بدون تغییر
      });
      setHasExistingConnection(true);
    }
  }

  async function openMappingDialog(site) {
    setError("");
    setMappingDialogSite(site);
    setMappingForm(EMPTY_MAPPING);
    setHasExistingMapping(false);
    const existing = await fetchSiteMapping(site.id).catch(() => null);
    if (existing) {
      setMappingForm({
        table_name: existing.table_name,
        personnel_code_column: existing.personnel_code_column,
        national_code_column: existing.national_code_column || "",
        first_name_column: existing.first_name_column,
        last_name_column: existing.last_name_column,
        mobile_column: existing.mobile_column || "",
        birth_date_column: existing.birth_date_column || "",
        is_active_column: existing.is_active_column || "",
        is_active_inverted: existing.is_active_inverted || false,
        department_column: existing.department_column || "",
        department_lookup_table: existing.department_lookup_table || "",
        department_lookup_id_column: existing.department_lookup_id_column || "",
        department_lookup_name_column: existing.department_lookup_name_column || "",
      });
      setHasExistingMapping(true);
    }
  }

  async function handleSaveConnection() {
    setError("");
    try {
      await upsertSiteConnection(connectionDialogSite.id, connectionForm);
      setConnectionDialogSite(null);
      loadSites();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره اتصال ناموفق بود");
    }
  }

  async function handleDeleteConnection() {
    if (!window.confirm("اتصال دیتابیس این سایت حذف شود؟")) return;
    await deleteSiteConnection(connectionDialogSite.id);
    setConnectionDialogSite(null);
    loadSites();
  }

  async function handleSaveMapping() {
    setError("");
    try {
      await upsertSiteMapping(mappingDialogSite.id, mappingForm);
      setMappingDialogSite(null);
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره Mapping ناموفق بود");
    }
  }

  async function handleDeleteMapping() {
    if (!window.confirm("Mapping ستون‌های این سایت حذف شود؟")) return;
    await deleteSiteMapping(mappingDialogSite.id);
    setMappingDialogSite(null);
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
        <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={() => setSiteDialogOpen(true)}>
          سایت جدید
        </Button>
      </Box>

      <Grid container spacing={2.5}>
        {sites.map((site) => (
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
                  <Switch
                    size="small"
                    checked={site.is_active}
                    disabled={togglingId === site.id}
                    onChange={() => handleToggleActive(site)}
                  />
                </Stack>
              </Stack>

              {site.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                  {site.description}
                </Typography>
              )}

              <Divider sx={{ my: 2 }} />

              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<SettingsEthernetOutlinedIcon />}
                  onClick={() => openConnectionDialog(site)}
                >
                  اتصال دیتابیس
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<ViewColumnOutlinedIcon />}
                  onClick={() => openMappingDialog(site)}
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
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Dialog: ساخت سایت جدید */}
      <Dialog open={siteDialogOpen} onClose={() => setSiteDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>سایت جدید</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
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
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setSiteDialogOpen(false)}>انصراف</Button>
          <Button variant="contained" onClick={handleCreateSite}>
            ذخیره
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: تعریف/ویرایش اتصال دیتابیس */}
      <Dialog open={Boolean(connectionDialogSite)} onClose={() => setConnectionDialogSite(null)} fullWidth maxWidth="xs">
        <DialogTitle>اتصال دیتابیس — {connectionDialogSite?.name}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            select
            label="نوع دیتابیس"
            value={connectionForm.db_type}
            onChange={(e) => setConnectionForm({ ...connectionForm, db_type: e.target.value })}
          >
            {DB_TYPES.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Host"
            value={connectionForm.host}
            onChange={(e) => setConnectionForm({ ...connectionForm, host: e.target.value })}
          />
          <TextField
            label="Port"
            type="number"
            value={connectionForm.port}
            onChange={(e) => setConnectionForm({ ...connectionForm, port: Number(e.target.value) })}
          />
          <TextField
            label="نام دیتابیس"
            value={connectionForm.database_name}
            onChange={(e) => setConnectionForm({ ...connectionForm, database_name: e.target.value })}
          />
          <TextField
            label="نام کاربری"
            value={connectionForm.username}
            onChange={(e) => setConnectionForm({ ...connectionForm, username: e.target.value })}
          />
          <TextField
            label="رمز عبور"
            type="password"
            value={connectionForm.password}
            onChange={(e) => setConnectionForm({ ...connectionForm, password: e.target.value })}
            helperText={
              hasExistingConnection
                ? "برای حفظ رمز فعلی، این فیلد را خالی بگذارید"
                : "در دیتابیس Portal به‌صورت رمزنگاری‌شده ذخیره می‌شود"
            }
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5, justifyContent: "space-between" }}>
          {hasExistingConnection ? (
            <Button color="error" startIcon={<DeleteOutlineIcon />} onClick={handleDeleteConnection}>
              حذف اتصال
            </Button>
          ) : (
            <span />
          )}
          <Stack direction="row" spacing={1}>
            <Button onClick={() => setConnectionDialogSite(null)}>انصراف</Button>
            <Button variant="contained" onClick={handleSaveConnection}>
              ذخیره
            </Button>
          </Stack>
        </DialogActions>
      </Dialog>

      {/* Dialog: تعریف/ویرایش Mapping ستون‌ها */}
      <Dialog open={Boolean(mappingDialogSite)} onClose={() => setMappingDialogSite(null)} fullWidth maxWidth="sm">
        <DialogTitle>Mapping ستون‌ها — {mappingDialogSite?.name}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}

          <Typography variant="subtitle2" fontWeight={700}>
            جدول اصلی پرسنل
          </Typography>
          <TextField
            label="نام جدول"
            value={mappingForm.table_name}
            onChange={(e) => setMappingForm({ ...mappingForm, table_name: e.target.value })}
          />
          <TextField
            label="ستون کد پرسنلی"
            value={mappingForm.personnel_code_column}
            onChange={(e) => setMappingForm({ ...mappingForm, personnel_code_column: e.target.value })}
          />
          <TextField
            label="ستون کد ملی (اختیاری)"
            value={mappingForm.national_code_column}
            onChange={(e) => setMappingForm({ ...mappingForm, national_code_column: e.target.value })}
          />
          <TextField
            label="ستون نام"
            value={mappingForm.first_name_column}
            onChange={(e) => setMappingForm({ ...mappingForm, first_name_column: e.target.value })}
          />
          <TextField
            label="ستون نام خانوادگی"
            value={mappingForm.last_name_column}
            onChange={(e) => setMappingForm({ ...mappingForm, last_name_column: e.target.value })}
          />
          <TextField
            label="ستون موبایل (اختیاری)"
            value={mappingForm.mobile_column}
            onChange={(e) => setMappingForm({ ...mappingForm, mobile_column: e.target.value })}
          />
          <TextField
            label="ستون تاریخ تولد شمسی (اختیاری — برای کارت «متولدین روز جاری» در داشبورد)"
            value={mappingForm.birth_date_column}
            onChange={(e) => setMappingForm({ ...mappingForm, birth_date_column: e.target.value })}
            helperText='فرمت مورد انتظار مثل «1370/05/21» یا «13700521»'
          />
          <TextField
            label="ستون وضعیت فعال/غیرفعال (اختیاری)"
            value={mappingForm.is_active_column}
            onChange={(e) => setMappingForm({ ...mappingForm, is_active_column: e.target.value })}
            helperText="اگر منبع ستونی مثل IsActive یا IsCut دارد که با ۰/۱ نشان می‌دهد"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={mappingForm.is_active_inverted}
                onChange={(e) => setMappingForm({ ...mappingForm, is_active_inverted: e.target.checked })}
              />
            }
            label="منطق این ستون برعکس است (مثل IsCut: ۱=غیرفعال، ۰=فعال)"
          />

          <Divider sx={{ my: 1 }} />

          <Typography variant="subtitle2" fontWeight={700}>
            واحد سازمانی (اختیاری)
          </Typography>
          <TextField
            label="ستون کد واحد در جدول پرسنل"
            value={mappingForm.department_column}
            onChange={(e) => setMappingForm({ ...mappingForm, department_column: e.target.value })}
            helperText="مثال: Sec_No"
          />
          <Typography variant="caption" color="text.secondary">
            اگر جدول جداگانه‌ای این کد را به نام واقعی واحد ترجمه می‌کند (مثل dbo.Sections)،
            سه فیلد زیر را هم پر کنید تا نام واحدها خودکار همگام شود:
          </Typography>
          <TextField
            label="نام جدول Lookup"
            value={mappingForm.department_lookup_table}
            onChange={(e) => setMappingForm({ ...mappingForm, department_lookup_table: e.target.value })}
            helperText="مثال: dbo.Sections"
          />
          <TextField
            label="ستون کد در جدول Lookup"
            value={mappingForm.department_lookup_id_column}
            onChange={(e) => setMappingForm({ ...mappingForm, department_lookup_id_column: e.target.value })}
            helperText="مثال: Sec_No"
          />
          <TextField
            label="ستون نام واحد در جدول Lookup"
            value={mappingForm.department_lookup_name_column}
            onChange={(e) => setMappingForm({ ...mappingForm, department_lookup_name_column: e.target.value })}
            helperText="مثال: Title"
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5, justifyContent: "space-between" }}>
          {hasExistingMapping ? (
            <Button color="error" startIcon={<DeleteOutlineIcon />} onClick={handleDeleteMapping}>
              حذف Mapping
            </Button>
          ) : (
            <span />
          )}
          <Stack direction="row" spacing={1}>
            <Button onClick={() => setMappingDialogSite(null)}>انصراف</Button>
            <Button variant="contained" onClick={handleSaveMapping}>
              ذخیره
            </Button>
          </Stack>
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
