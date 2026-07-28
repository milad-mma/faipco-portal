import { useEffect, useState } from "react";
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
  Divider,
  Grid,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import SettingsEthernetOutlinedIcon from "@mui/icons-material/SettingsEthernetOutlined";
import ViewColumnOutlinedIcon from "@mui/icons-material/ViewColumnOutlined";
import { createSite, fetchSites, upsertSiteConnection, upsertSiteMapping } from "../api/sites";

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
};

export default function SitesPage() {
  const [sites, setSites] = useState([]);
  const [siteDialogOpen, setSiteDialogOpen] = useState(false);
  const [connectionDialogSite, setConnectionDialogSite] = useState(null);
  const [mappingDialogSite, setMappingDialogSite] = useState(null);

  const [newSite, setNewSite] = useState({ name: "", code: "", description: "" });
  const [connectionForm, setConnectionForm] = useState(EMPTY_CONNECTION);
  const [mappingForm, setMappingForm] = useState(EMPTY_MAPPING);
  const [error, setError] = useState("");

  function loadSites() {
    fetchSites().then(setSites);
  }

  useEffect(() => {
    loadSites();
  }, []);

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

  async function handleSaveConnection() {
    setError("");
    try {
      await upsertSiteConnection(connectionDialogSite.id, connectionForm);
      setConnectionDialogSite(null);
      setConnectionForm(EMPTY_CONNECTION);
      loadSites();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره اتصال ناموفق بود");
    }
  }

  async function handleSaveMapping() {
    setError("");
    try {
      await upsertSiteMapping(mappingDialogSite.id, mappingForm);
      setMappingDialogSite(null);
      setMappingForm(EMPTY_MAPPING);
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره Mapping ناموفق بود");
    }
  }

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3 }}>
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
                <Chip
                  size="small"
                  label={site.is_active ? "فعال" : "غیرفعال"}
                  color={site.is_active ? "success" : "default"}
                  variant="outlined"
                />
              </Stack>

              {site.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                  {site.description}
                </Typography>
              )}

              <Divider sx={{ my: 2 }} />

              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<SettingsEthernetOutlinedIcon />}
                  onClick={() => {
                    setConnectionDialogSite(site);
                    setConnectionForm(EMPTY_CONNECTION);
                  }}
                >
                  اتصال دیتابیس
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<ViewColumnOutlinedIcon />}
                  onClick={() => {
                    setMappingDialogSite(site);
                    setMappingForm(EMPTY_MAPPING);
                  }}
                >
                  Mapping ستون‌ها
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

      {/* Dialog: تعریف اتصال دیتابیس */}
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
            helperText="در دیتابیس Portal به‌صورت رمزنگاری‌شده ذخیره می‌شود"
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setConnectionDialogSite(null)}>انصراف</Button>
          <Button variant="contained" onClick={handleSaveConnection}>
            ذخیره
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: تعریف Mapping ستون‌ها */}
      <Dialog open={Boolean(mappingDialogSite)} onClose={() => setMappingDialogSite(null)} fullWidth maxWidth="xs">
        <DialogTitle>Mapping ستون‌ها — {mappingDialogSite?.name}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
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
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setMappingDialogSite(null)}>انصراف</Button>
          <Button variant="contained" onClick={handleSaveMapping}>
            ذخیره
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
