/**
 * پنل «اپ اندروید» (docs/android-app.md):
 * - گوشی‌ها: خلاصه، فهرست گوشی‌های متصل با مشکلات، ابطال (mobile.devices، سایت‌محور)
 * - ورود/خروج خودکار: رویدادهای Geofencing با نتیجه‌ی پردازش
 * - معافیت‌ها: پرسنل معاف از پیش‌نیاز اپ
 * - تنظیمات و نسخه‌ها: پارامترهای Geofencing و بارگذاری APK (system.mobile_app)
 */
import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Divider,
  FormControlLabel,
  Grid,
  LinearProgress,
  MenuItem,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { useAuth } from "../context/AuthContext";
import SiteFilterSelect from "../components/SiteFilterSelect";
import EmployeePicker from "../components/EmployeePicker";
import {
  addExemption,
  deleteExemption,
  deleteRelease,
  fetchExemptions,
  fetchGeofenceEvents,
  fetchMobileDevices,
  fetchMobileLabels,
  fetchMobileSettings,
  fetchMobileSummary,
  fetchReleases,
  revokeMobileDevice,
  saveMobileSettings,
  uploadRelease,
} from "../api/mobile";
import { normalizeSearchText } from "../utils/searchText";
import { monoFontSx } from "../theme";

const faDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "—";
const fa = (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("fa-IR"));

function errorText(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => String(d.msg || "").replace(/^Value error, /, "")).join("، ");
  return fallback;
}

function useDebounced(value, delay = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}

export default function MobileDevicesPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState(0);
  const [labels, setLabels] = useState({ issues: {}, blocking: [], event_status: {} });
  useEffect(() => {
    fetchMobileLabels().then(setLabels).catch(() => {});
  }, []);
  const canDevices = user?.can_manage_mobile_devices;
  const canApp = user?.can_manage_mobile_app;
  const tabs = [
    canDevices && { key: "devices", label: "گوشی‌ها" },
    canDevices && { key: "events", label: "ورود/خروج خودکار" },
    canDevices && { key: "exemptions", label: "معافیت‌ها" },
    canApp && { key: "settings", label: "تنظیمات و نسخه‌ها" },
  ].filter(Boolean);
  const current = tabs[Math.min(tab, tabs.length - 1)]?.key;

  return (
    <Box sx={{ maxWidth: 1150, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        اپ اندروید
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        گوشی‌های متصل، وضعیت دسترسی موقعیت، ورود و خروج خودکار (Geofencing) و انتشار نسخه‌ی اپ.
      </Typography>
      <Tabs value={Math.min(tab, tabs.length - 1)} onChange={(_, v) => setTab(v)} variant="scrollable" sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}>
        {tabs.map((t) => (
          <Tab key={t.key} label={t.label} />
        ))}
      </Tabs>
      {current === "devices" && <DevicesTab labels={labels} />}
      {current === "events" && <EventsTab labels={labels} />}
      {current === "exemptions" && <ExemptionsTab />}
      {current === "settings" && <SettingsTab />}
    </Box>
  );
}

// ---------------------------------------------------------------- گوشی‌ها

function StatTile({ label, value, tone }) {
  return (
    <Card variant="outlined" sx={{ p: 2, borderRadius: 2, height: "100%" }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h5" fontWeight={800} color={tone ? `${tone}.main` : "text.primary"}>
        {fa(value)}
      </Typography>
    </Card>
  );
}

function DevicesTab({ labels }) {
  const [siteId, setSiteId] = useState(null);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [health, setHealth] = useState("");
  const [includeRevoked, setIncludeRevoked] = useState(false);
  const [summary, setSummary] = useState(null);
  const [devices, setDevices] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);

  const load = useCallback(async () => {
    setError("");
    try {
      const [s, d] = await Promise.all([
        fetchMobileSummary(siteId),
        fetchMobileDevices({ siteId, search, health, includeRevoked }),
      ]);
      setSummary(s);
      setDevices(d);
      setPage(0);
    } catch (err) {
      setError(errorText(err, "دریافت فهرست گوشی‌ها ناموفق بود."));
    }
  }, [siteId, search, health, includeRevoked]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRevoke(d) {
    if (!window.confirm(`گوشی ${d.employee_name || ""} باطل شود؟ کاربر باید دوباره از داخل اپ «فعال‌سازی» کند.`)) return;
    try {
      await revokeMobileDevice(d.id);
      load();
    } catch (err) {
      setError(errorText(err, "ابطال ناموفق بود."));
    }
  }

  const blocking = new Set(labels.blocking || []);
  const rowsPerPage = 50;

  return (
    <Stack spacing={2}>
      <Grid container spacing={1.5}>
        <Grid item xs={6} md={3}>
          <StatTile label="پرسنل فعال" value={summary?.active_employees} />
        </Grid>
        <Grid item xs={6} md={3}>
          <StatTile label="گوشی فعال و سالم" value={summary?.healthy} tone="success" />
        </Grid>
        <Grid item xs={6} md={3}>
          <StatTile label="گوشی نیازمند بررسی" value={summary?.unhealthy} tone="warning" />
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined" sx={{ p: 2, borderRadius: 2, height: "100%" }}>
            <Typography variant="caption" color="text.secondary">
              آخرین نسخه‌ی اپ
            </Typography>
            <Typography variant="h6" fontWeight={800}>
              {summary?.latest_release ? summary.latest_release.version_name : "منتشر نشده"}
            </Typography>
          </Card>
        </Grid>
      </Grid>

      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
        <SiteFilterSelect value={siteId} onChange={setSiteId} permission="mobile.devices" />
        <TextField size="small" label="جست‌وجوی نام، کد پرسنلی یا مدل" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} />
        <TextField select size="small" label="وضعیت" value={health} onChange={(e) => setHealth(e.target.value)} sx={{ minWidth: 160 }}>
          <MenuItem value="">همه</MenuItem>
          <MenuItem value="healthy">سالم</MenuItem>
          <MenuItem value="unhealthy">نیازمند بررسی</MenuItem>
        </TextField>
        <FormControlLabel control={<Switch checked={includeRevoked} onChange={(e) => setIncludeRevoked(e.target.checked)} />} label="باطل‌شده‌ها هم" />
        <Button startIcon={<RefreshIcon />} onClick={load}>
          به‌روزرسانی
        </Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}

      <Card variant="outlined" sx={{ borderRadius: 2 }}>
        {devices === null ? (
          <Box sx={{ p: 2 }}>
            <CircularProgress size={20} />
          </Box>
        ) : (
          <>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>پرسنل</TableCell>
                    <TableCell>سایت</TableCell>
                    <TableCell>گوشی</TableCell>
                    <TableCell>وضعیت</TableCell>
                    <TableCell>موتور</TableCell>
                    <TableCell>آخرین گزارش</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {devices.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7}>
                        <Typography variant="body2" color="text.secondary">
                          گوشی‌ای پیدا نشد.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                  {devices.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage).map((d) => (
                    <TableRow key={d.id} sx={d.revoked_at ? { opacity: 0.55 } : undefined}>
                      <TableCell>
                        <Typography variant="body2">{d.employee_name || "—"}</Typography>
                        <Typography variant="caption" color="text.secondary" sx={monoFontSx}>
                          {d.personnel_code}
                        </Typography>
                      </TableCell>
                      <TableCell>{d.site_name || "—"}</TableCell>
                      <TableCell>
                        <Typography variant="body2">{[d.manufacturer, d.model].filter(Boolean).join(" ") || "—"}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          اندروید {d.os_version || "?"} · اپ {d.app_version_name || "?"}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ maxWidth: 320 }}>
                        {d.revoked_at ? (
                          <Chip size="small" label="باطل‌شده" />
                        ) : d.issues.length === 0 ? (
                          <Chip size="small" color="success" label="سالم" />
                        ) : (
                          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                            {d.issues.map((i) => (
                              <Chip
                                key={i}
                                size="small"
                                variant="outlined"
                                color={blocking.has(i) ? "error" : "warning"}
                                label={labels.issues?.[i] || i}
                              />
                            ))}
                          </Stack>
                        )}
                      </TableCell>
                      <TableCell>
                        <Tooltip title={d.has_gms === false ? "بدون سرویس‌های گوگل (موتور داخلی اندروید)" : "سرویس‌های گوگل"}>
                          <span>{d.geofence_engine === "platform" ? "داخلی" : d.geofence_engine === "gms" ? "گوگل" : "—"}</span>
                        </Tooltip>
                      </TableCell>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{faDateTime(d.status_reported_at)}</TableCell>
                      <TableCell>
                        {!d.revoked_at && (
                          <Button size="small" color="error" onClick={() => handleRevoke(d)}>
                            ابطال
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={devices.length}
              page={page}
              onPageChange={(_, p) => setPage(p)}
              rowsPerPage={rowsPerPage}
              rowsPerPageOptions={[rowsPerPage]}
              labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
            />
          </>
        )}
      </Card>
    </Stack>
  );
}

// ---------------------------------------------------------------- رویدادها

const TRANSITION_LABELS = { enter: "ورود", dwell: "ورود", exit: "خروج" };

function EventsTab({ labels }) {
  const [siteId, setSiteId] = useState(null);
  const [status, setStatus] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const rowsPerPage = 50;

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await fetchGeofenceEvents({ siteId, status, search, limit: rowsPerPage, offset: page * rowsPerPage }));
    } catch (err) {
      setError(errorText(err, "دریافت رویدادها ناموفق بود."));
    }
  }, [siteId, status, search, page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
        <SiteFilterSelect value={siteId} onChange={(v) => (setSiteId(v), setPage(0))} permission="mobile.devices" />
        <TextField select size="small" label="نتیجه" value={status} onChange={(e) => (setStatus(e.target.value), setPage(0))} sx={{ minWidth: 180 }}>
          <MenuItem value="">همه</MenuItem>
          {Object.entries(labels.event_status || {}).map(([k, v]) => (
            <MenuItem key={k} value={k}>
              {v}
            </MenuItem>
          ))}
        </TextField>
        <TextField size="small" label="جست‌وجوی پرسنل" value={searchInput} onChange={(e) => (setSearchInput(e.target.value), setPage(0))} />
        <Button startIcon={<RefreshIcon />} onClick={load}>
          به‌روزرسانی
        </Button>
      </Stack>
      <Typography variant="caption" color="text.secondary">
        هفت روز اخیر. رکوردهای «ثبت شد» در گزارش ورود و خروج با برچسب «خودکار» دیده می‌شوند و به کاراوب نوشته نمی‌شوند.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <Card variant="outlined" sx={{ borderRadius: 2 }}>
        {data === null ? (
          <Box sx={{ p: 2 }}>
            <CircularProgress size={20} />
          </Box>
        ) : (
          <>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>زمان</TableCell>
                    <TableCell>پرسنل</TableCell>
                    <TableCell>سایت</TableCell>
                    <TableCell>نوع</TableCell>
                    <TableCell>نتیجه</TableCell>
                    <TableCell>دقت / فاصله</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6}>
                        <Typography variant="body2" color="text.secondary">
                          رویدادی ثبت نشده است.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                  {data.items.map((e) => (
                    <TableRow key={e.id}>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{faDateTime(e.occurred_at)}</TableCell>
                      <TableCell>
                        {e.employee_name || "—"}{" "}
                        <Typography component="span" variant="caption" color="text.secondary" sx={monoFontSx}>
                          {e.personnel_code}
                        </Typography>
                      </TableCell>
                      <TableCell>{e.site_name || "—"}</TableCell>
                      <TableCell>{TRANSITION_LABELS[e.transition] || e.transition}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          variant="outlined"
                          color={e.status === "logged" ? "success" : e.status === "mock" ? "error" : "default"}
                          label={labels.event_status?.[e.status] || e.status}
                        />
                      </TableCell>
                      <TableCell>
                        {e.accuracy_meters != null ? `${fa(Math.round(e.accuracy_meters))} م` : "—"}
                        {e.distance_meters != null ? ` / ${fa(Math.round(e.distance_meters))} م` : ""}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={data.total}
              page={page}
              onPageChange={(_, p) => setPage(p)}
              rowsPerPage={rowsPerPage}
              rowsPerPageOptions={[rowsPerPage]}
              labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
            />
          </>
        )}
      </Card>
    </Stack>
  );
}

// ---------------------------------------------------------------- معافیت‌ها

function ExemptionsTab() {
  const [items, setItems] = useState(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    fetchExemptions()
      .then(setItems)
      .catch((err) => setError(errorText(err, "دریافت معافیت‌ها ناموفق بود.")));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd(emp) {
    setError("");
    try {
      await addExemption(emp.id, reason.trim());
      setReason("");
      load();
    } catch (err) {
      setError(errorText(err, "افزودن معافیت ناموفق بود."));
    }
  }

  async function handleDelete(id) {
    try {
      await deleteExemption(id);
      load();
    } catch (err) {
      setError(errorText(err, "حذف معافیت ناموفق بود."));
    }
  }

  return (
    <Stack spacing={2} sx={{ maxWidth: 820 }}>
      <Alert severity="info">
        آیفون و کامپیوتر خودکار معاف‌اند. اینجا فقط پرسنلی را اضافه کنید که با گوشی اندروید کار می‌کنند ولی به دلیل خاص نباید
        ملزم به نصب اپ باشند.
      </Alert>
      <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <TextField size="small" label="دلیل (اختیاری)" value={reason} onChange={(e) => setReason(e.target.value)} sx={{ flex: 1 }} />
          <Box sx={{ flex: 1 }}>
            <EmployeePicker label="افزودن پرسنل معاف" onSelect={handleAdd} excludeIds={(items || []).map((x) => x.employee_id)} />
          </Box>
        </Stack>
      </Card>
      {error && <Alert severity="error">{error}</Alert>}
      <Card variant="outlined" sx={{ borderRadius: 2 }}>
        {items === null ? (
          <Box sx={{ p: 2 }}>
            <CircularProgress size={20} />
          </Box>
        ) : items.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
            کسی معاف نشده است.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>پرسنل</TableCell>
                <TableCell>سایت</TableCell>
                <TableCell>دلیل</TableCell>
                <TableCell>تاریخ</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((x) => (
                <TableRow key={x.id}>
                  <TableCell>
                    {x.employee_name}{" "}
                    <Typography component="span" variant="caption" color="text.secondary" sx={monoFontSx}>
                      {x.personnel_code}
                    </Typography>
                  </TableCell>
                  <TableCell>{x.site_name || "—"}</TableCell>
                  <TableCell>{x.reason || "—"}</TableCell>
                  <TableCell>{faDateTime(x.created_at)}</TableCell>
                  <TableCell>
                    <Button size="small" color="error" startIcon={<DeleteOutlineIcon />} onClick={() => handleDelete(x.id)}>
                      حذف
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </Stack>
  );
}

// ---------------------------------------------------------------- تنظیمات و نسخه‌ها

const NUM_FIELDS = [
  ["loitering_seconds", "مکث داخل محدوده پیش از ثبت ورود (ثانیه)", "فقط گوشی‌های دارای سرویس گوگل؛ جلوی ثبت هنگام عبور از کنار کارخانه را می‌گیرد."],
  ["responsiveness_seconds", "تأخیر مجاز اعلان رویداد (ثانیه)", "عدد بیشتر = مصرف باتری کمتر و ثبت دیرتر."],
  ["repeat_guard_hours", "نادیده گرفتن ورود پشت ورود (ساعت)", "ورودِ دوباره بدون خروج در این بازه ثبت نمی‌شود (همین‌طور خروج پشت خروج)."],
  ["status_stale_days", "بی‌خبری مجاز گوشی (روز)", "گوشی‌ای که بیش از این گزارش نداده «نیازمند بررسی» می‌شود."],
  ["min_version_code", "حداقل نسخه‌ی مجاز اپ (versionCode)", "۰ = بدون محدودیت. نسخه‌های قدیمی‌تر «نیازمند به‌روزرسانی» می‌شوند."],
];

function SettingsTab() {
  const [form, setForm] = useState(null);
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [releases, setReleases] = useState(null);
  const [upload, setUpload] = useState({ file: null, versionCode: "", versionName: "", notes: "" });
  const [progress, setProgress] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);

  const loadReleases = () => fetchReleases().then(setReleases).catch(() => setReleases([]));

  useEffect(() => {
    fetchMobileSettings()
      .then((s) => setForm(Object.fromEntries(Object.entries(s).map(([k, v]) => [k, typeof v === "number" ? String(v) : v]))))
      .catch((err) => setResult({ success: false, message: errorText(err, "دریافت تنظیمات ناموفق بود.") }));
    loadReleases();
  }, []);

  async function handleSave() {
    setSaving(true);
    setResult(null);
    try {
      const payload = { ...form };
      NUM_FIELDS.forEach(([k]) => (payload[k] = Number(form[k] || 0)));
      const saved = await saveMobileSettings(payload);
      setForm(Object.fromEntries(Object.entries(saved).map(([k, v]) => [k, typeof v === "number" ? String(v) : v])));
      setResult({ success: true, message: "ذخیره شد. گوشی‌ها تغییر را در باز شدن بعدی اپ یا گزارش روزانه می‌گیرند." });
    } catch (err) {
      setResult({ success: false, message: errorText(err, "ذخیره ناموفق بود.") });
    } finally {
      setSaving(false);
    }
  }

  async function handleUpload() {
    setUploadResult(null);
    setProgress(0);
    try {
      await uploadRelease(
        {
          file: upload.file,
          versionCode: Number(normalizeSearchText(upload.versionCode)),
          versionName: normalizeSearchText(upload.versionName).trim(),
          notes: upload.notes,
        },
        setProgress
      );
      setUpload({ file: null, versionCode: "", versionName: "", notes: "" });
      setUploadResult({ success: true, message: "نسخه منتشر شد؛ لینک دانلود پرتال همین نسخه را می‌دهد." });
      loadReleases();
    } catch (err) {
      setUploadResult({ success: false, message: errorText(err, "بارگذاری ناموفق بود.") });
    } finally {
      setProgress(null);
    }
  }

  async function handleDeleteRelease(id) {
    if (!window.confirm("این نسخه حذف شود؟")) return;
    await deleteRelease(id).catch(() => {});
    loadReleases();
  }

  return (
    <Stack spacing={2} sx={{ maxWidth: 820 }}>
      <Card variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
        <Typography variant="subtitle2" fontWeight={700}>
          ورود و خروج خودکار
        </Typography>
        <Divider sx={{ my: 1.5 }} />
        {!form ? (
          result ? <Alert severity="error">{result.message}</Alert> : <CircularProgress size={20} />
        ) : (
          <>
            <FormControlLabel
              control={<Switch checked={Boolean(form.auto_clock_enabled)} onChange={(e) => setForm((f) => ({ ...f, auto_clock_enabled: e.target.checked }))} />}
              label="ثبت خودکار ورود و خروج با Geofencing"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.online_tracking_enabled !== false}
                  onChange={(e) => setForm((f) => ({ ...f, online_tracking_enabled: e.target.checked }))}
                />
              }
              label="آنلاین در محیط کار: ثبت وصل بودن گوشی به اینترنت داخل محدوده‌ی سایت (حتی با اپ بسته)"
            />
            <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
              {NUM_FIELDS.map(([key, label, help]) => (
                <Grid item xs={12} sm={6} key={key}>
                  <TextField
                    size="small"
                    fullWidth
                    label={label}
                    value={form[key]}
                    helperText={help}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: normalizeSearchText(e.target.value).replace(/[^0-9]/g, "") }))}
                    inputProps={{ inputMode: "numeric", dir: "ltr" }}
                  />
                </Grid>
              ))}
            </Grid>
            <TextField
              size="small"
              fullWidth
              sx={{ mt: 2 }}
              label="اثر انگشت SHA-256 کلید امضای اپ"
              value={form.signing_sha256 || ""}
              onChange={(e) => setForm((f) => ({ ...f, signing_sha256: e.target.value }))}
              helperText="از خروجی «ساخت کلید امضا» در GitHub کپی کنید. در assetlinks.json سایت نوشته می‌شود تا اپ بدون نوار آدرس باز شود."
              inputProps={{ dir: "ltr", style: { fontFamily: "monospace", fontSize: 12 } }}
            />
            {result && (
              <Alert severity={result.success ? "success" : "error"} sx={{ mt: 2 }}>
                {result.message}
              </Alert>
            )}
            <Button variant="contained" sx={{ mt: 2 }} startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />} onClick={handleSave} disabled={saving}>
              ذخیره
            </Button>
          </>
        )}
      </Card>

      <Card variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
        <Typography variant="subtitle2" fontWeight={700}>
          انتشار نسخه‌ی جدید اپ
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
          فایل APK ساخته‌شده در GitHub (بخش Actions ← آخرین اجرا ← Artifacts) را اینجا بارگذاری کنید. versionCode و versionName در
          همان صفحه‌ی ساخت نوشته شده‌اند.
        </Typography>
        <Divider sx={{ my: 1.5 }} />
        <Stack spacing={1.5}>
          <Button variant="outlined" component="label" startIcon={<UploadFileOutlinedIcon />} sx={{ alignSelf: "flex-start" }}>
            {upload.file ? upload.file.name : "انتخاب فایل APK"}
            <input hidden type="file" accept=".apk,application/vnd.android.package-archive" onChange={(e) => setUpload((u) => ({ ...u, file: e.target.files?.[0] || null }))} />
          </Button>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <TextField size="small" label="versionCode (عدد)" value={upload.versionCode} onChange={(e) => setUpload((u) => ({ ...u, versionCode: e.target.value }))} inputProps={{ inputMode: "numeric", dir: "ltr" }} />
            <TextField size="small" label="versionName (مثلاً 1.0.3)" value={upload.versionName} onChange={(e) => setUpload((u) => ({ ...u, versionName: e.target.value }))} inputProps={{ dir: "ltr" }} />
          </Stack>
          <TextField size="small" label="تغییرات این نسخه (اختیاری)" value={upload.notes} onChange={(e) => setUpload((u) => ({ ...u, notes: e.target.value }))} multiline minRows={2} />
          {progress !== null && <LinearProgress variant="determinate" value={progress} />}
          {uploadResult && <Alert severity={uploadResult.success ? "success" : "error"}>{uploadResult.message}</Alert>}
          <Button
            variant="contained"
            sx={{ alignSelf: "flex-start" }}
            disabled={!upload.file || !upload.versionCode || !upload.versionName || progress !== null}
            onClick={handleUpload}
          >
            انتشار
          </Button>
        </Stack>
        <Divider sx={{ my: 2 }} />
        {releases === null ? (
          <CircularProgress size={20} />
        ) : releases.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            هنوز نسخه‌ای منتشر نشده است.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>نسخه</TableCell>
                <TableCell>versionCode</TableCell>
                <TableCell>حجم</TableCell>
                <TableCell>تاریخ</TableCell>
                <TableCell>تغییرات</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {releases.map((r, i) => (
                <TableRow key={r.id}>
                  <TableCell>
                    {r.version_name} {i === 0 && <Chip size="small" color="primary" label="فعلی" sx={{ ms: 0.5 }} />}
                  </TableCell>
                  <TableCell sx={monoFontSx}>{r.version_code}</TableCell>
                  <TableCell>{fa(Math.round((r.file_size / 1048576) * 10) / 10)} MB</TableCell>
                  <TableCell>{faDateTime(r.uploaded_at)}</TableCell>
                  <TableCell sx={{ maxWidth: 240 }}>{r.notes || "—"}</TableCell>
                  <TableCell>
                    <Button size="small" color="error" onClick={() => handleDeleteRelease(r.id)}>
                      حذف
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </Stack>
  );
}
