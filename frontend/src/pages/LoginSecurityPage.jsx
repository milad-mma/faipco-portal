/**
 * صفحه‌ی «امنیت ورود» (مجوز system.login_security):
 * - تب گزارش: خلاصه‌ی بازه، قفل‌های فعال با دکمه‌ی رفع قفل، پرتکرارترین IPها و شناسه‌ها، فهرست رویدادها.
 * - تب تنظیمات: قفل پلکانی، محدودیت IP و IPهای معاف، کپچای داخلی، هشدار و مدت نگهداری گزارش.
 * جزئیات: docs/login-security.md
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
  Typography,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import LockOpenOutlinedIcon from "@mui/icons-material/LockOpenOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import {
  fetchActiveLocks,
  fetchLoginSecuritySettings,
  fetchSecurityEvents,
  fetchSecuritySummary,
  saveLoginSecuritySettings,
  unlockKey,
} from "../api/loginSecurity";
import { normalizeSearchText } from "../utils/searchText";
import { monoFontSx } from "../theme";

const RANGES = [
  { value: 24, label: "۲۴ ساعت اخیر" },
  { value: 24 * 7, label: "۷ روز اخیر" },
  { value: 24 * 30, label: "۳۰ روز اخیر" },
];
const LOCK_KIND_LABELS = { identifier: "شناسه", ip: "IP", reset: "بازیابی رمز (IP)" };
const KIND_COLORS = {
  login_failed: "warning",
  captcha_failed: "warning",
  reset_code_failed: "warning",
  login_locked: "error",
  ip_blocked: "error",
  forgot_password: "default",
};

const faDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "—";

// پیام خطای قابل نمایش (رشته یا فهرست خطاهای اعتبارسنجی FastAPI)
function errorText(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => String(d.msg || "").replace(/^Value error, /, "")).join("، ");
  return fallback;
}

export default function LoginSecurityPage() {
  const [tab, setTab] = useState(0);
  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        امنیت ورود
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        قفل موقت بعد از تلاش ناموفق، محدودیت IP، کپچای داخلی و گزارش تلاش‌های ناموفق ورود و بازیابی رمز.
      </Typography>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}>
        <Tab label="گزارش" />
        <Tab label="تنظیمات" />
      </Tabs>
      {tab === 0 ? <ReportTab /> : <SettingsTab />}
    </Box>
  );
}

// ---------------------------------------------------------------- گزارش

function StatTile({ label, value, tone }) {
  return (
    <Card variant="outlined" sx={{ p: 2, borderRadius: 2, height: "100%" }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h5" fontWeight={800} color={tone ? `${tone}.main` : "text.primary"}>
        {value === null || value === undefined ? "—" : Number(value).toLocaleString("fa-IR")}
      </Typography>
    </Card>
  );
}

function ReportTab() {
  const [hours, setHours] = useState(24);
  const [summary, setSummary] = useState(null);
  const [locks, setLocks] = useState(null);
  const [error, setError] = useState("");
  const [unlocking, setUnlocking] = useState("");

  const [kind, setKind] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [events, setEvents] = useState(null);

  const loadOverview = useCallback(async () => {
    setError("");
    try {
      const [s, l] = await Promise.all([fetchSecuritySummary(hours), fetchActiveLocks()]);
      setSummary(s);
      setLocks(l);
    } catch (err) {
      setError(errorText(err, "دریافت گزارش ناموفق بود."));
    }
  }, [hours]);

  const loadEvents = useCallback(async () => {
    try {
      setEvents(
        await fetchSecurityEvents({ kind, search, hours, limit: rowsPerPage, offset: page * rowsPerPage })
      );
    } catch (err) {
      setError(errorText(err, "دریافت رویدادها ناموفق بود."));
    }
  }, [kind, search, hours, page, rowsPerPage]);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  // جست‌وجو با تأخیر ۳۰۰ میلی‌ثانیه
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  async function handleUnlock(key) {
    setUnlocking(key);
    try {
      await unlockKey(key);
      await Promise.all([loadOverview(), loadEvents()]);
    } catch (err) {
      setError(errorText(err, "رفع قفل ناموفق بود."));
    } finally {
      setUnlocking("");
    }
  }

  const labels = summary?.labels || events?.labels || {};

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} alignItems="center">
        <TextField select size="small" label="بازه" value={hours} onChange={(e) => (setHours(e.target.value), setPage(0))} sx={{ minWidth: 160 }}>
          {RANGES.map((r) => (
            <MenuItem key={r.value} value={r.value}>
              {r.label}
            </MenuItem>
          ))}
        </TextField>
        <Button startIcon={<RefreshIcon />} onClick={() => (loadOverview(), loadEvents())}>
          به‌روزرسانی
        </Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}

      <Grid container spacing={1.5}>
        <Grid item xs={6} md={3}>
          <StatTile label="تلاش ناموفق" value={summary?.failures} tone="warning" />
        </Grid>
        <Grid item xs={6} md={3}>
          <StatTile label="شناسه‌ی قفل (الان)" value={summary?.active_locks?.identifier} tone="error" />
        </Grid>
        <Grid item xs={6} md={3}>
          <StatTile label="IP مسدود (الان)" value={summary?.active_locks?.ip} tone="error" />
        </Grid>
        <Grid item xs={6} md={3}>
          <StatTile label="درخواست بازیابی رمز" value={summary?.by_kind?.forgot_password ?? 0} />
        </Grid>
      </Grid>

      <Card variant="outlined" sx={{ borderRadius: 2 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ p: 2, pb: 1 }}>
          قفل‌های فعال
        </Typography>
        {locks === null ? (
          <Box sx={{ p: 2 }}>
            <CircularProgress size={20} />
          </Box>
        ) : locks.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ px: 2, pb: 2 }}>
            در حال حاضر هیچ شناسه یا IPی قفل نیست.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>نوع</TableCell>
                  <TableCell>شناسه / IP</TableCell>
                  <TableCell>تلاش ناموفق</TableCell>
                  <TableCell>قفل تا</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {locks.map((l) => (
                  <TableRow key={l.key}>
                    <TableCell>{LOCK_KIND_LABELS[l.kind] || l.kind}</TableCell>
                    <TableCell sx={monoFontSx}>{l.value}</TableCell>
                    <TableCell>{l.kind === "ip" ? "—" : Number(l.fail_count).toLocaleString("fa-IR")}</TableCell>
                    <TableCell>{faDateTime(l.locked_until)}</TableCell>
                    <TableCell align="left">
                      <Button
                        size="small"
                        startIcon={unlocking === l.key ? <CircularProgress size={14} /> : <LockOpenOutlinedIcon />}
                        disabled={Boolean(unlocking)}
                        onClick={() => handleUnlock(l.key)}
                      >
                        رفع قفل
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Card>

      <Grid container spacing={1.5}>
        <Grid item xs={12} md={6}>
          <TopTable
            title="پرتکرارترین IPها (تلاش ناموفق)"
            head={["IP", "تعداد", "شناسه‌ی متفاوت"]}
            rows={(summary?.top_ips || []).map((r) => [r.ip, r.count, r.identifiers])}
            onPick={(row) => setSearchInput(row[0])}
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <TopTable
            title="پرتکرارترین شناسه‌ها (تلاش ناموفق)"
            head={["شناسه", "تعداد"]}
            rows={(summary?.top_identifiers || []).map((r) => [r.identifier, r.count])}
            onPick={(row) => setSearchInput(row[0])}
          />
        </Grid>
      </Grid>

      <Card variant="outlined" sx={{ borderRadius: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ p: 2 }} alignItems={{ sm: "center" }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ flex: 1 }}>
            رویدادها
          </Typography>
          <TextField select size="small" label="نوع" value={kind} onChange={(e) => (setKind(e.target.value), setPage(0))} sx={{ minWidth: 190 }}>
            <MenuItem value="">همه</MenuItem>
            {Object.entries(labels).map(([k, v]) => (
              <MenuItem key={k} value={k}>
                {v}
              </MenuItem>
            ))}
          </TextField>
          <TextField size="small" label="جست‌وجوی IP یا شناسه" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} />
        </Stack>
        {events === null ? (
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
                    <TableCell>رویداد</TableCell>
                    <TableCell>شناسه</TableCell>
                    <TableCell>IP</TableCell>
                    <TableCell>دستگاه</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {events.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5}>
                        <Typography variant="body2" color="text.secondary">
                          رویدادی در این بازه ثبت نشده است.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                  {events.items.map((e) => (
                    <TableRow key={e.id}>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{faDateTime(e.created_at)}</TableCell>
                      <TableCell>
                        <Chip size="small" variant="outlined" color={KIND_COLORS[e.kind] || "default"} label={labels[e.kind] || e.kind} />
                      </TableCell>
                      <TableCell sx={monoFontSx}>{e.identifier || "—"}</TableCell>
                      <TableCell sx={monoFontSx}>{e.ip}</TableCell>
                      <TableCell sx={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={e.user_agent || ""}>
                        <Typography variant="caption" color="text.secondary">
                          {e.user_agent || "—"}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={events.total}
              page={page}
              onPageChange={(_, p) => setPage(p)}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={(e) => (setRowsPerPage(Number(e.target.value)), setPage(0))}
              rowsPerPageOptions={[25, 50, 100]}
              labelRowsPerPage="تعداد در صفحه"
              labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
            />
          </>
        )}
      </Card>
    </Stack>
  );
}

// جدول کوچک پرتکرارها؛ کلیک روی ردیف فیلتر رویدادها را پر می‌کند
function TopTable({ title, head, rows, onPick }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 2, height: "100%" }}>
      <Typography variant="subtitle2" fontWeight={700} sx={{ p: 2, pb: 1 }}>
        {title}
      </Typography>
      {rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ px: 2, pb: 2 }}>
          موردی نیست.
        </Typography>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              {head.map((h) => (
                <TableCell key={h}>{h}</TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row[0]} hover sx={{ cursor: "pointer" }} onClick={() => onPick(row)}>
                {row.map((cell, i) => (
                  <TableCell key={i} sx={i === 0 ? monoFontSx : undefined}>
                    {typeof cell === "number" ? cell.toLocaleString("fa-IR") : cell}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- تنظیمات

// فیلد عددی که ارقام فارسی را هم می‌پذیرد؛ مقدار به‌صورت رشته در فرم نگه داشته می‌شود
function NumberField({ label, value, onChange, helperText, disabled }) {
  return (
    <TextField
      size="small"
      label={label}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(normalizeSearchText(e.target.value).replace(/[^0-9]/g, ""))}
      helperText={helperText}
      inputProps={{ inputMode: "numeric", dir: "ltr" }}
      fullWidth
    />
  );
}

function toForm(s) {
  return {
    ...s,
    attempts_per_tier: String(s.attempts_per_tier),
    lock_minutes: s.lock_minutes.join("، "),
    ip_max_failures: String(s.ip_max_failures),
    ip_window_minutes: String(s.ip_window_minutes),
    ip_block_minutes: String(s.ip_block_minutes),
    exempt_ips: s.exempt_ips.join("\n"),
    captcha_after_failures: String(s.captcha_after_failures),
    alert_threshold: String(s.alert_threshold),
    alert_window_minutes: String(s.alert_window_minutes),
    retention_days: String(s.retention_days),
  };
}

function fromForm(f) {
  const n = (v) => Number(v || 0);
  return {
    attempts_per_tier: n(f.attempts_per_tier),
    lock_minutes: normalizeSearchText(f.lock_minutes)
      .split(/[,،\s]+/)
      .filter(Boolean)
      .map(Number),
    ip_limit_enabled: f.ip_limit_enabled,
    ip_max_failures: n(f.ip_max_failures),
    ip_window_minutes: n(f.ip_window_minutes),
    ip_block_minutes: n(f.ip_block_minutes),
    exempt_ips: normalizeSearchText(f.exempt_ips)
      .split(/[\n,،\s]+/)
      .map((x) => x.trim())
      .filter(Boolean),
    captcha_enabled: f.captcha_enabled,
    captcha_after_failures: n(f.captcha_after_failures),
    captcha_on_forgot_password: f.captcha_on_forgot_password,
    alert_enabled: f.alert_enabled,
    alert_threshold: n(f.alert_threshold),
    alert_window_minutes: n(f.alert_window_minutes),
    retention_days: n(f.retention_days),
  };
}

function Section({ title, subtitle, children }) {
  return (
    <Card variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
      <Typography variant="subtitle2" fontWeight={700}>
        {title}
      </Typography>
      {subtitle && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
          {subtitle}
        </Typography>
      )}
      <Divider sx={{ my: 1.5 }} />
      {children}
    </Card>
  );
}

function SettingsTab() {
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchLoginSecuritySettings()
      .then((s) => setForm(toForm(s)))
      .catch((err) => setResult({ success: false, message: errorText(err, "دریافت تنظیمات ناموفق بود.") }));
  }, []);

  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));
  const toggle = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.checked }));

  async function handleSave() {
    setSaving(true);
    setResult(null);
    try {
      const saved = await saveLoginSecuritySettings(fromForm(form));
      setForm(toForm(saved));
      setResult({ success: true, message: "تنظیمات ذخیره شد و از ورود بعدی اعمال می‌شود." });
    } catch (err) {
      setResult({ success: false, message: errorText(err, "ذخیره‌ی تنظیمات ناموفق بود.") });
    } finally {
      setSaving(false);
    }
  }

  if (!form) {
    return result ? <Alert severity="error">{result.message}</Alert> : <CircularProgress />;
  }

  const tiersPreview = (() => {
    const per = Number(form.attempts_per_tier || 0);
    const mins = normalizeSearchText(form.lock_minutes).split(/[,،\s]+/).filter(Boolean).map(Number);
    if (!per || mins.length === 0 || mins.some((m) => !m)) return "";
    return mins
      .map((m, i) => `${(per * (i + 1)).toLocaleString("fa-IR")} تلاش → ${m.toLocaleString("fa-IR")} دقیقه`)
      .join("، ") + " (بعد از آن همان پله‌ی آخر)";
  })();

  return (
    <Stack spacing={2} sx={{ maxWidth: 760 }}>
      <Section title="قفل موقت هر شناسه" subtitle="بعد از تلاش ناموفق روی یک کد پرسنلی یا نام کاربری، همان شناسه به‌صورت پلکانی قفل می‌شود.">
        <Grid container spacing={1.5}>
          <Grid item xs={12} sm={5}>
            <NumberField label="هر چند تلاش ناموفق یک پله" value={form.attempts_per_tier} onChange={set("attempts_per_tier")} />
          </Grid>
          <Grid item xs={12} sm={7}>
            <TextField
              size="small"
              fullWidth
              label="مدت قفل پله‌ها (دقیقه، با ویرگول)"
              value={form.lock_minutes}
              onChange={(e) => set("lock_minutes")(e.target.value)}
              inputProps={{ dir: "ltr" }}
            />
          </Grid>
        </Grid>
        {tiersPreview && (
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
            {tiersPreview}
          </Typography>
        )}
      </Section>

      <Section
        title="محدودیت IP"
        subtitle="جلوی کسی را می‌گیرد که از یک IP روی کد پرسنلی‌های مختلف امتحان می‌کند و با قفل هر شناسه متوقف نمی‌شود."
      >
        <FormControlLabel control={<Switch checked={form.ip_limit_enabled} onChange={toggle("ip_limit_enabled")} />} label="فعال" />
        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
          <Grid item xs={12} sm={4}>
            <NumberField label="حداکثر تلاش ناموفق" value={form.ip_max_failures} onChange={set("ip_max_failures")} disabled={!form.ip_limit_enabled} />
          </Grid>
          <Grid item xs={12} sm={4}>
            <NumberField label="در بازه‌ی (دقیقه)" value={form.ip_window_minutes} onChange={set("ip_window_minutes")} disabled={!form.ip_limit_enabled} />
          </Grid>
          <Grid item xs={12} sm={4}>
            <NumberField label="مدت مسدودیت (دقیقه)" value={form.ip_block_minutes} onChange={set("ip_block_minutes")} disabled={!form.ip_limit_enabled} />
          </Grid>
        </Grid>
        <TextField
          label="IPهای معاف (هر خط یک IP یا رنج CIDR)"
          value={form.exempt_ips}
          onChange={(e) => set("exempt_ips")(e.target.value)}
          multiline
          minRows={3}
          fullWidth
          size="small"
          sx={{ mt: 2 }}
          inputProps={{ dir: "ltr", style: { fontFamily: "monospace" } }}
          helperText="مثلاً IP مشترک اینترنت کارخانه. این IPها محدودیت IP و کپچای مبتنی بر IP ندارند تا خطای یک نفر بقیه را قفل نکند؛ قفل هر شناسه برایشان برقرار است."
        />
      </Section>

      <Section title="کپچای داخلی" subtitle="تصویر ارقام روی همین سرور ساخته می‌شود و به سرویس خارجی وابسته نیست؛ پاسخ با کیبورد فارسی یا انگلیسی پذیرفته می‌شود.">
        <FormControlLabel control={<Switch checked={form.captcha_enabled} onChange={toggle("captcha_enabled")} />} label="فعال" />
        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
          <Grid item xs={12} sm={6}>
            <NumberField
              label="نمایش در ورود بعد از چند تلاش ناموفق"
              value={form.captcha_after_failures}
              onChange={set("captcha_after_failures")}
              disabled={!form.captcha_enabled}
              helperText="روی همان شناسه یا همان IP؛ ۰ = همیشه"
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormControlLabel
              control={
                <Switch checked={form.captcha_on_forgot_password} onChange={toggle("captcha_on_forgot_password")} disabled={!form.captcha_enabled} />
              }
              label="همیشه در فراموشی رمز (پیش از ارسال پیامک/ایمیل)"
            />
          </Grid>
        </Grid>
      </Section>

      <Section title="هشدار حجم غیرعادی" subtitle="اعلان به مدیران سیستم و دارندگان مجوز «امنیت ورود»؛ حداکثر یک‌بار در هر بازه.">
        <FormControlLabel control={<Switch checked={form.alert_enabled} onChange={toggle("alert_enabled")} />} label="فعال" />
        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
          <Grid item xs={12} sm={6}>
            <NumberField label="تعداد تلاش ناموفق" value={form.alert_threshold} onChange={set("alert_threshold")} disabled={!form.alert_enabled} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <NumberField label="در بازه‌ی (دقیقه)" value={form.alert_window_minutes} onChange={set("alert_window_minutes")} disabled={!form.alert_enabled} />
          </Grid>
        </Grid>
      </Section>

      <Section title="نگهداری گزارش">
        <Box sx={{ maxWidth: 260 }}>
          <NumberField label="مدت نگهداری رویدادها (روز)" value={form.retention_days} onChange={set("retention_days")} />
        </Box>
      </Section>

      {result && <Alert severity={result.success ? "success" : "error"}>{result.message}</Alert>}
      <Box>
        <Button variant="contained" startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />} onClick={handleSave} disabled={saving}>
          ذخیره‌ی تنظیمات
        </Button>
      </Box>
    </Stack>
  );
}
