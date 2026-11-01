/**
 * «تنظیمات اتوماسیون اداری» (مجوز automation.settings، سایت‌محور) — فاز ۱:
 * - تب پیوست‌ها: تعداد، حجم و فرمت مجاز پیوست برای هر سایت (سقف حجم هر فایل = سقف آپلود سرور).
 * - تب اسکنر و آزمایش: وضعیت ClamAV و بانک شناسایی، فضای دیسک، و آزمایش آپلود با تنظیمات یک سایت.
 * جزئیات: docs/office-automation.md
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import PillTabs from "../components/PillTabs";
import {
  deleteFile,
  downloadFile,
  fetchAttachmentSettings,
  fetchAutomationStatus,
  fetchMyFiles,
  runClamavAction,
  saveAttachmentSettings,
  setScanEnabled,
  testUpload,
} from "../api/automation";
import { useAuth } from "../context/AuthContext";
import { saveBlob } from "../utils/family";
import { toPersianDigits } from "../utils/searchText";

const LIMIT_GROUPS = [
  {
    title: "پیوست نامه (در هر نسخه)",
    fields: [
      { key: "letter_max_files", label: "حداکثر تعداد فایل", unit: "فایل" },
      { key: "letter_max_file_mb", label: "حجم هر فایل", unit: "مگابایت", perFile: true },
      { key: "letter_max_total_mb", label: "حجم مجموع", unit: "مگابایت" },
    ],
  },
  {
    title: "پیوست هر ارجاع یا اقدام",
    fields: [
      { key: "action_max_files", label: "حداکثر تعداد فایل", unit: "فایل" },
      { key: "action_max_file_mb", label: "حجم هر فایل", unit: "مگابایت", perFile: true },
      { key: "action_max_total_mb", label: "حجم مجموع", unit: "مگابایت" },
    ],
  },
  {
    title: "کل نامه",
    fields: [{ key: "letter_all_max_total_mb", label: "حجم کل پیوست‌های نامه", unit: "مگابایت" }],
  },
];

const STATUS_COLORS = {
  clean: "success",
  infected: "error",
  rejected: "error",
  scan_pending: "warning",
  scanning: "info",
  uploading: "default",
};

const STATUS_LABELS = {
  clean: "سالم",
  infected: "آلوده (قرنطینه)",
  rejected: "رد شد",
  scan_pending: "در انتظار اسکن",
  scanning: "در حال اسکن",
  uploading: "در حال بارگذاری",
};

function fmtBytes(n) {
  if (n == null) return "—";
  const units = ["بایت", "کیلوبایت", "مگابایت", "گیگابایت", "ترابایت"];
  let v = Number(n);
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${toPersianDigits(v.toFixed(i ? 1 : 0))} ${units[i]}`;
}

function fmtDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return String(value);
  }
}

function errorText(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "مقدارهای واردشده معتبر نیستند.";
  return fallback;
}

// ---------- تب پیوست‌ها ----------

function AttachmentSettingsTab() {
  const [data, setData] = useState(null);
  const [siteId, setSiteId] = useState("");
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setError("");
    fetchAttachmentSettings()
      .then((d) => {
        setData(d);
        setSiteId((prev) => prev || d.sites[0]?.site_id || "");
      })
      .catch((err) => setError(errorText(err, "دریافت تنظیمات با خطا مواجه شد.")));
  }, []);

  useEffect(load, [load]);

  const site = useMemo(() => data?.sites.find((s) => s.site_id === Number(siteId)), [data, siteId]);
  // فرم با داده‌ی تازه‌ی سایت پر می‌شود؛ پیام‌ها فقط با عوض شدن سایت پاک می‌شوند (نه با بارگذاری دوباره بعد از ذخیره)
  useEffect(() => {
    if (site) setForm({ ...site.values, allowed_formats: [...site.values.allowed_formats] });
  }, [site]);
  useEffect(() => {
    setSaved("");
    setError("");
  }, [siteId]);

  if (error && !data) return <Alert severity="error">{error}</Alert>;
  if (!data || !form) return <CircularProgress size={28} />;
  const { catalog } = data;
  const serverMax = catalog.server_max_file_mb;

  const setNum = (key, raw) => setForm((f) => ({ ...f, [key]: raw.replace(/[^\d۰-۹]/g, "") }));
  const toggleFormat = (code) =>
    setForm((f) => ({
      ...f,
      allowed_formats: f.allowed_formats.includes(code)
        ? f.allowed_formats.filter((c) => c !== code)
        : [...f.allowed_formats, code],
    }));

  async function handleSave() {
    setError("");
    setSaved("");
    const payload = { ...form };
    for (const g of LIMIT_GROUPS) {
      for (const f of g.fields) {
        const v = String(form[f.key]).replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d));
        payload[f.key] = Number(v);
      }
    }
    setSaving(true);
    try {
      await saveAttachmentSettings(site.site_id, payload);
      setSaved(`تنظیمات پیوست «${site.site_name}» ذخیره شد. فقط برای آپلودهای بعدی اعمال می‌شود.`);
      load();
    } catch (err) {
      setError(errorText(err, "ذخیره‌ی تنظیمات با خطا مواجه شد."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
        <TextField
          select
          size="small"
          label="سایت"
          value={siteId}
          onChange={(e) => setSiteId(e.target.value)}
          sx={{ minWidth: 220, "& .MuiInputBase-root": { height: 40 } }}
        >
          {data.sites.map((s) => (
            <MenuItem key={s.site_id} value={s.site_id}>
              {s.site_name}
            </MenuItem>
          ))}
        </TextField>
        {site?.is_default ? (
          <Chip size="small" label="هنوز تنظیم نشده — مقدار اولیه" variant="outlined" />
        ) : (
          <Typography variant="caption" color="text.secondary">
            آخرین تغییر: {fmtDate(site?.updated_at)}
          </Typography>
        )}
      </Stack>

      <Alert severity="info" sx={{ py: 0.5 }}>
        سقف آپلود سرور: هر فایل حداکثر {toPersianDigits(serverMax)} مگابایت. حجم بیشتر از این قابل تنظیم نیست؛ برای بالاتر
        بردن آن، ادمین کل «سقف آپلود سرور» را در «تنظیمات سامانه» تغییر می‌دهد.
      </Alert>

      <Grid container spacing={2}>
        {LIMIT_GROUPS.map((g) => (
          <Grid item xs={12} md={4} key={g.title}>
            <Card variant="outlined" sx={{ p: 2, height: "100%" }}>
              <Typography fontWeight={700} sx={{ mb: 1.5 }}>
                {g.title}
              </Typography>
              <Stack spacing={1.5}>
                {g.fields.map((f) => (
                  <TextField
                    key={f.key}
                    size="small"
                    label={`${f.label} (${f.unit})`}
                    value={form[f.key]}
                    onChange={(e) => setNum(f.key, e.target.value)}
                    inputProps={{ inputMode: "numeric" }}
                    helperText={f.perFile ? `حداکثر ${toPersianDigits(serverMax)}` : undefined}
                    sx={{ "& .MuiInputBase-root": { height: 40 } }}
                  />
                ))}
              </Stack>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Card variant="outlined" sx={{ p: 2 }}>
        <Typography fontWeight={700}>فرمت‌های مجاز</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          برای هر فرمت، نوع واقعی و ساختار فایل بررسی می‌شود (نه فقط پسوند) و همه‌ی فایل‌ها با آنتی‌ویروس اسکن می‌شوند.
        </Typography>
        <Grid container>
          {catalog.formats.map((f) => (
            <Grid item xs={12} sm={6} md={4} key={f.code}>
              <FormControlLabel
                control={
                  <Checkbox
                    size="small"
                    checked={form.allowed_formats.includes(f.code)}
                    onChange={() => toggleFormat(f.code)}
                  />
                }
                label={
                  <Box>
                    <Typography variant="body2" component="span">
                      {f.label}
                    </Typography>
                    {f.note && (
                      <Typography variant="caption" color="text.secondary" component="span" sx={{ mr: 0.5 }}>
                        ({f.note})
                      </Typography>
                    )}
                  </Box>
                }
              />
            </Grid>
          ))}
        </Grid>
        <Divider sx={{ my: 1.5 }} />
        <Typography variant="body2" color="error.main">
          همیشه ممنوع و غیرقابل فعال‌سازی: {catalog.forbidden_label}
        </Typography>
      </Card>

      {error && <Alert severity="error">{error}</Alert>}
      {saved && <Alert severity="success">{saved}</Alert>}
      <Stack direction="row" spacing={1}>
        <Button
          variant="contained"
          startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />}
          onClick={handleSave}
          disabled={saving}
          sx={{ height: 40 }}
        >
          ذخیره‌ی تنظیمات {site?.site_name}
        </Button>
        <Button
          variant="outlined"
          startIcon={<RestartAltIcon />}
          onClick={() => setForm({ ...catalog.defaults, allowed_formats: [...catalog.defaults.allowed_formats] })}
          sx={{ height: 40 }}
        >
          مقدار اولیه
        </Button>
      </Stack>
    </Stack>
  );
}

// ---------- کارت اسکن ویروس (اختیاری) و مدیریت ClamAV ----------

const CLAMAV_ACTIONS = [
  { key: "install", label: "نصب و راه‌اندازی", needs: (c) => !c.installed },
  { key: "update-db", label: "دریافت/به‌روزرسانی بانک", needs: (c) => c.installed },
  { key: "start", label: "روشن کردن", needs: (c) => c.installed && c.has_db && c.daemon !== "active" },
  { key: "stop", label: "خاموش کردن", needs: (c) => c.installed && (c.daemon === "active" || c.freshclam === "active") },
];

const SERVICE_LABELS = { active: "روشن", inactive: "خاموش", failed: "خطا", activating: "در حال روشن شدن" };

function ClamavCard({ status, onChange }) {
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_superuser);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [showLog, setShowLog] = useState(false);
  const job = status.clamav_job || {};
  const c = status.clamav || {};

  // تا وقتی عملیات سرور در حال اجراست، هر ۵ ثانیه وضعیت تازه شود
  useEffect(() => {
    if (!job.running) return undefined;
    const t = window.setInterval(onChange, 5000);
    return () => window.clearInterval(t);
  }, [job.running, onChange]);

  async function act(action) {
    setError("");
    setBusy(action);
    try {
      await runClamavAction(action);
      setTimeout(onChange, 1500);
    } catch (err) {
      setError(errorText(err, "اجرای دستور با خطا مواجه شد."));
    } finally {
      setBusy("");
    }
  }

  async function toggleScan(enabled) {
    setError("");
    setBusy("toggle");
    try {
      await setScanEnabled(enabled);
      onChange();
    } catch (err) {
      setError(errorText(err, "تغییر تنظیم با خطا مواجه شد."));
    } finally {
      setBusy("");
    }
  }

  return (
    <Card variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
        <Typography fontWeight={700}>اسکن ویروس با ClamAV (اختیاری)</Typography>
        <FormControlLabel
          control={
            <Switch
              checked={Boolean(status.scan_enabled)}
              onChange={(e) => toggleScan(e.target.checked)}
              disabled={!isAdmin || busy !== ""}
            />
          }
          label={status.scan_enabled ? "روشن" : "خاموش"}
        />
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {status.scan_enabled
          ? "همه‌ی فایل‌های جدید با آنتی‌ویروس اسکن می‌شوند."
          : "اسکن ویروس خاموش است: فایل‌ها بعد از بررسی نوع و ساختار (پسوند خطرناک، ماکرو، رمز، PDF فعال، ZIP خطرناک) «سالم (بدون اسکن ویروس)» می‌شوند. بدون اسکن، بدافزار شناخته‌شده‌ی پنهان در فایل ظاهراً سالم تشخیص داده نمی‌شود."}
        {status.unscanned_clean > 0 &&
          ` ${toPersianDigits(status.unscanned_clean)} فایل بدون اسکن ثبت شده${
            status.scan_enabled ? " که در پس‌زمینه اسکن می‌شوند." : "؛ با روشن کردن اسکن، آن‌ها هم اسکن می‌شوند."
          }`}
      </Typography>

      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
        <Chip size="small" variant="outlined" label={c.installed ? "ClamAV نصب است" : "ClamAV نصب نیست"}
          color={c.installed ? "success" : "default"} />
        {c.installed && (
          <>
            <Chip size="small" variant="outlined" color={c.has_db ? "success" : "warning"}
              label={c.has_db ? "بانک شناسایی موجود است" : "بانک شناسایی دریافت نشده"} />
            <Chip size="small" variant="outlined" color={c.daemon === "active" ? "success" : "default"}
              label={`سرویس اسکن: ${SERVICE_LABELS[c.daemon] || c.daemon}`} />
            <Chip size="small" variant="outlined"
              label={`به‌روزرسانی خودکار بانک: ${SERVICE_LABELS[c.freshclam] || c.freshclam}`} />
          </>
        )}
      </Stack>

      {isAdmin ? (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {CLAMAV_ACTIONS.filter((a) => a.needs(c)).map((a) => (
            <Button key={a.key} variant={a.key === "stop" ? "outlined" : "contained"}
              color={a.key === "stop" ? "inherit" : "primary"} onClick={() => act(a.key)}
              disabled={busy !== "" || job.running} sx={{ height: 40 }}
              startIcon={busy === a.key ? <CircularProgress size={16} color="inherit" /> : null}>
              {a.label}
            </Button>
          ))}
          {job.log && (
            <Button variant="text" onClick={() => setShowLog(true)} sx={{ height: 40 }}>
              گزارش آخرین عملیات
            </Button>
          )}
        </Stack>
      ) : (
        <Typography variant="caption" color="text.secondary">نصب و روشن/خاموش کردن اسکنر فقط با ادمین کل است.</Typography>
      )}

      {job.running && (
        <Alert severity="info" icon={<CircularProgress size={18} />} sx={{ mt: 1.5 }}>
          «{job.action_label}» روی سرور در حال اجراست (دریافت بانک ممکن است چند دقیقه طول بکشد)…
        </Alert>
      )}
      {!job.running && job.result && (
        <Alert severity={job.result === "ok" ? "success" : "error"} sx={{ mt: 1.5 }}
          action={<Button size="small" color="inherit" onClick={() => setShowLog(true)}>گزارش</Button>}>
          {job.result === "ok" ? `«${job.action_label}» با موفقیت انجام شد.` : `«${job.action_label}» ناموفق بود.`}
        </Alert>
      )}
      {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}

      <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1.5 }}>
        دریافت بانک شناسایی از سرور ClamAV از ایران مسدود است؛ فقط وقتی سرور با VPN به اینترنت وصل است «نصب» یا «دریافت
        بانک» را بزنید. ClamAV روشن حدود ۱ تا ۱.۵ گیگابایت RAM مصرف می‌کند؛ خاموش، هیچ.
      </Typography>

      <Dialog open={showLog} onClose={() => setShowLog(false)} maxWidth="md" fullWidth>
        <DialogTitle>گزارش آخرین عملیات ClamAV</DialogTitle>
        <DialogContent>
          <Box component="pre" dir="ltr" sx={{ whiteSpace: "pre-wrap", fontSize: 12, m: 0, maxHeight: 480, overflow: "auto" }}>
            {job.log || "—"}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowLog(false)}>بستن</Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}

// ---------- تب اسکنر و آزمایش ----------

function ScannerTab() {
  const [status, setStatus] = useState(null);
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("");
  const [files, setFiles] = useState([]);
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const loadStatus = useCallback(() => {
    fetchAutomationStatus()
      .then(setStatus)
      .catch((err) => setError(errorText(err, "دریافت وضعیت با خطا مواجه شد.")));
  }, []);
  const loadFiles = useCallback(() => {
    fetchMyFiles()
      .then(setFiles)
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadStatus();
    loadFiles();
    fetchAttachmentSettings()
      .then((d) => {
        setSites(d.sites);
        setSiteId((prev) => prev || d.sites[0]?.site_id || "");
      })
      .catch(() => {});
  }, [loadStatus, loadFiles]);

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !siteId) return;
    setError("");
    setResult(null);
    setProgress(0);
    try {
      const row = await testUpload(siteId, file, setProgress);
      setResult({ ok: true, row });
    } catch (err) {
      setResult({ ok: false, message: errorText(err, "آپلود با خطا مواجه شد.") });
    } finally {
      setProgress(null);
      loadFiles();
      loadStatus();
    }
  }

  async function handleDownload(row) {
    try {
      const response = await downloadFile(row.id);
      saveBlob(response.data, row.name);
    } catch (err) {
      setError(errorText(err, "دانلود با خطا مواجه شد."));
    }
  }

  async function handleDelete(row) {
    try {
      await deleteFile(row.id);
      loadFiles();
    } catch (err) {
      setError(errorText(err, "حذف با خطا مواجه شد."));
    }
  }

  const scanner = status?.scanner;
  return (
    <Stack spacing={2}>
      {status && <ClamavCard status={status} onChange={loadStatus} />}
      <Card variant="outlined" sx={{ p: 2 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Typography fontWeight={700}>آنتی‌ویروس (ClamAV) و فضای فایل‌ها</Typography>
          <IconButton size="small" onClick={loadStatus} aria-label="به‌روزرسانی">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Stack>
        {!status ? (
          <CircularProgress size={22} />
        ) : (
          <Stack spacing={1}>
            {scanner.available ? (
              <Alert severity={scanner.db_stale ? "warning" : "success"} sx={{ py: 0.5 }}>
                اسکنر فعال است — نسخه {scanner.engine || "—"}، بانک شناسایی {scanner.db || "—"} (تاریخ{" "}
                {fmtDate(scanner.db_date)}).
                {scanner.db_stale &&
                  ` بانک شناسایی بیش از ${toPersianDigits(status.db_stale_days)} روز به‌روز نشده است؛ اسکن ادامه دارد ولی بانک قدیمی است (معمولاً به‌خاطر قطع اینترنت سرور).`}
              </Alert>
            ) : !status.scan_enabled ? (
              <Alert severity="info" sx={{ py: 0.5 }}>
                اسکن ویروس خاموش است.
              </Alert>
            ) : (
              <Alert severity="error" sx={{ py: 0.5 }}>
                اسکنر در دسترس نیست؛ فایل‌های جدید «در انتظار اسکن» می‌مانند و تا برگشت اسکنر قابل دانلود نیستند. (
                {scanner.error})
              </Alert>
            )}
            <Typography variant="body2">
              فضای آزاد دیسک فایل‌ها: {fmtBytes(status.disk?.free)} از {fmtBytes(status.disk?.total)}
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {Object.entries(status.counts || {}).map(([k, v]) => (
                <Chip key={k} size="small" color={STATUS_COLORS[k] || "default"} variant="outlined"
                  label={`${STATUS_LABELS[k] || k}: ${toPersianDigits(v)}`} />
              ))}
            </Stack>
          </Stack>
        )}
      </Card>

      <Card variant="outlined" sx={{ p: 2 }}>
        <Typography fontWeight={700}>آزمایش آپلود</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          یک فایل را با تنظیمات پیوست سایت انتخابی بارگذاری کنید تا نتیجه‌ی بررسی نوع، ساختار و اسکن را ببینید (برای
          چک‌لیست سرور تست: پسوند جعلی، فایل ماکرودار، فایل آزمایشی EICAR، ZIP خیلی بزرگ). فایل‌های آزمایشی موقت‌اند و
          خودکار پاک می‌شوند.
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
          <TextField
            select
            size="small"
            label="تنظیمات سایت"
            value={siteId}
            onChange={(e) => setSiteId(e.target.value)}
            sx={{ minWidth: 220, "& .MuiInputBase-root": { height: 40 } }}
          >
            {sites.map((s) => (
              <MenuItem key={s.site_id} value={s.site_id}>
                {s.site_name}
              </MenuItem>
            ))}
          </TextField>
          <Button
            component="label"
            variant="contained"
            startIcon={<UploadFileOutlinedIcon />}
            disabled={progress != null || !siteId}
            sx={{ height: 40 }}
          >
            انتخاب فایل
            <input hidden type="file" onChange={handleUpload} />
          </Button>
        </Stack>
        {progress != null && (
          <Box sx={{ mt: 1.5 }}>
            <LinearProgress variant={progress < 100 ? "determinate" : "indeterminate"} value={progress} />
            <Typography variant="caption" color="text.secondary">
              {progress < 100 ? `در حال ارسال: ${toPersianDigits(progress)}٪` : "در حال بررسی و اسکن…"}
            </Typography>
          </Box>
        )}
        {result && (
          <Alert
            severity={!result.ok ? "error" : result.row.status === "clean" ? "success" : "warning"}
            sx={{ mt: 1.5 }}
          >
            {result.ok
              ? `«${result.row.name}»: ${result.row.status_label}${
                  result.row.scan_result ? ` — ${result.row.scan_result}` : ""
                }`
              : `رد شد: ${result.message}`}
          </Alert>
        )}
        {error && (
          <Alert severity="error" sx={{ mt: 1.5 }}>
            {error}
          </Alert>
        )}
      </Card>

      {files.length > 0 && (
        <TableContainer component={Card} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>فایل</TableCell>
                <TableCell>حجم</TableCell>
                <TableCell>وضعیت</TableCell>
                <TableCell>زمان</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {files.map((f) => (
                <TableRow key={f.id}>
                  <TableCell sx={{ maxWidth: 260, wordBreak: "break-all" }}>{f.name}</TableCell>
                  <TableCell>{fmtBytes(f.size)}</TableCell>
                  <TableCell>
                    <Tooltip title={f.reject_reason || f.scan_result || ""}>
                      <Chip size="small" color={STATUS_COLORS[f.status] || "default"} label={f.status_label} />
                    </Tooltip>
                  </TableCell>
                  <TableCell>{fmtDate(f.created_at)}</TableCell>
                  <TableCell align="left" sx={{ whiteSpace: "nowrap" }}>
                    {f.can_download && (
                      <IconButton size="small" onClick={() => handleDownload(f)} aria-label="دانلود">
                        <DownloadOutlinedIcon fontSize="small" />
                      </IconButton>
                    )}
                    {f.state === "temp" && (
                      <IconButton size="small" onClick={() => handleDelete(f)} aria-label="حذف">
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  );
}

export default function AutomationSettingsPage() {
  const [tab, setTab] = useState("attachments");
  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        تنظیمات اتوماسیون اداری
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        تنظیمات هر سایت جداست و فقط برای سایت‌هایی که مجوز تنظیمات اتوماسیون آن‌ها را دارید نمایش داده می‌شود.
      </Typography>
      <PillTabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "attachments", label: "پیوست‌ها" },
          { key: "scanner", label: "اسکنر و آزمایش آپلود" },
        ]}
        sx={{ mb: 2 }}
      />
      {tab === "attachments" ? <AttachmentSettingsTab /> : <ScannerTab />}
    </Box>
  );
}
