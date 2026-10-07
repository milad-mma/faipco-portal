import { useCallback, useEffect, useState } from "react";
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
  FormControlLabel,
  Grid,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import CancelOutlinedIcon from "@mui/icons-material/CancelOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import ReportProblemOutlinedIcon from "@mui/icons-material/ReportProblemOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import BackLink from "../components/BackLink";
import PillTabs from "../components/PillTabs";
import SiteFilterSelect from "../components/SiteFilterSelect";
import { useAuth } from "../context/AuthContext";
import {
  approveFamilyProfile,
  importFamilyInsuranceDays,
  downloadFamilyDocument,
  downloadFamilyExport,
  fetchFamilyProfile,
  fetchFamilyProfiles,
  fetchFamilySettings,
  rejectFamilyProfile,
  returnFamilyProfile,
  updateFamilyHrFields,
  updateFamilySettings,
} from "../api/family";
import FamilySummary from "../components/FamilySummary";
import JalaliCalendarField from "../components/JalaliCalendarField";
import { MEMBER_LABEL, STATUS_COLOR, saveBlob, toEn } from "../utils/family";

/**
 * پنل منابع انسانی «مشخصات خانوادگی» (مسیر /family/admin):
 * - تب «پرسنل»: همه‌ی پرسنل فعال سایت‌های مجاز با وضعیت پرونده و شمول حق تاهل / تعداد فرزند واجد شرایط
 *   (محاسبه بر اساس آخرین نسخه‌ی تأییدشده و قواعد همین پنل)، جزئیات، تأیید/رد/بازگشت، سابقه بیمه و خروجی Excel.
 * - تب «قواعد و تنظیمات» (family.manage): فیلدهای فرم، مدارک و دوره تمدید، شرایط حق تاهل و حق اولاد، هشدارها.
 */

const STATUS_LABEL = { none: "ثبت نشده", draft: "ثبت نشده", pending: "در انتظار بررسی", approved: "تأیید شده", rejected: "رد شده", returned: "بازگشت برای ویرایش" };
const MARITAL_LABEL = { single: "مجرد", married: "متاهل", divorced: "مطلقه", widowed: "همسر فوت‌شده" };
const FLAGS = {
  marriage: "مشمول حق تاهل",
  children: "دارای فرزند واجد شرایط",
  warnings: "دارای هشدار",
  no_insurance_days: "سابقه بیمه نامشخص",
  pending_changes: "تغییرات تأییدنشده",
};
const fa = (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("fa-IR"));
const faDateTime = (iso) => (iso ? new Date(iso).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "—");

function EligibleIcon({ value }) {
  if (value === true) return <CheckCircleOutlineIcon color="success" fontSize="small" />;
  if (value === false) return <CancelOutlinedIcon color="disabled" fontSize="small" />;
  return <Typography variant="caption">—</Typography>;
}

// ---------- کارت نتیجه‌ی شمول ----------

function EvaluationCard({ title, evaluation, color }) {
  if (!evaluation) return null;
  const { marriage, child } = evaluation;
  return (
    <Card variant="outlined" sx={{ p: 1.5, borderRadius: 2, borderColor: `${color}.main` }}>
      <Typography fontWeight={800} sx={{ mb: 1 }}>
        {title}
      </Typography>
      <Stack direction="row" spacing={1} alignItems="center">
        <EligibleIcon value={marriage.eligible} />
        <Typography variant="body2">
          حق تاهل: <b>{marriage.eligible === null ? "غیرفعال" : marriage.eligible ? "مشمول" : "غیرمشمول"}</b>
          {marriage.reason ? ` — ${marriage.reason}` : ""}
        </Typography>
      </Stack>
      <Typography variant="body2" sx={{ mt: 1 }}>
        حق اولاد: <b>{fa(child.eligible_count)}</b> فرزند واجد شرایط از {fa(child.total)}
        {child.blocked_reason ? ` — ${child.blocked_reason}` : ""}
      </Typography>
      {child.children.length > 0 && (
        <Stack spacing={0.25} sx={{ mt: 0.5 }}>
          {child.children.map((c, i) => (
            <Stack key={i} direction="row" spacing={1} alignItems="center">
              <EligibleIcon value={c.eligible} />
              <Typography variant="caption">
                {MEMBER_LABEL[c.member_type]} — {c.name} ({c.age === null ? "سن نامشخص" : `${fa(c.age)} سال`}): {c.reason}
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}
    </Card>
  );
}

// ---------- دیالوگ‌های کوچک ----------

function NoteDialog({ open, title, label, confirmText, color = "primary", withDate, onClose, onConfirm }) {
  const [note, setNote] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setNote("");
      setDate("");
      setError("");
    }
  }, [open]);
  async function submit() {
    setBusy(true);
    setError("");
    try {
      await onConfirm({ note, date });
    } catch (err) {
      setError(err.response?.data?.detail || "عملیات با خطا مواجه شد.");
    } finally {
      setBusy(false);
    }
  }
  const noteRequired = !withDate;
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          {withDate && (
            <JalaliCalendarField label="تاریخ اثر (خالی = امروز)" value={date} onChange={(v) => setDate(v || "")} />
          )}
          <TextField multiline minRows={3} label={label} value={note} onChange={(e) => setNote(e.target.value)} inputProps={{ maxLength: 2000 }} />
          {error && <Alert severity="error">{typeof error === "string" ? error : "خطا"}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          انصراف
        </Button>
        <Button variant="contained" color={color} onClick={submit} disabled={busy || (noteRequired && !note.trim())}>
          {confirmText}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// سابقه بیمه‌ی یک پرسنل: «سابقه‌ی پیش از استخدام» (با روزهای پس از استخدام جمع می‌شود) یا «کل سابقه» (جایگزین محاسبه)
// target: { employee_id, name, hr_prior, hr_total, hr_note?, withNote?, info? }
function HrFieldsDialog({ target, onClose, onSaved }) {
  const [prior, setPrior] = useState("");
  const [total, setTotal] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (target) {
      setPrior(target.hr_prior ?? "");
      setTotal(target.hr_total ?? "");
      setNote(target.hr_note ?? "");
      setError("");
    }
  }, [target]);
  const digits = (v) => toEn(v).replace(/\D/g, "").slice(0, 5);
  async function submit() {
    setBusy(true);
    try {
      const p = String(prior).trim();
      const t = String(total).trim();
      const payload = {
        ...(p === "" ? { clear_hr_prior_insurance_days: true } : { hr_prior_insurance_days: Number(p) }),
        ...(t === "" ? { clear_insurance_days: true } : { insurance_days: Number(t) }),
      };
      if (target.withNote) payload.hr_note = note;
      await updateFamilyHrFields(target.employee_id, payload);
      onSaved();
    } catch (err) {
      setError(typeof err.response?.data?.detail === "string" ? err.response.data.detail : "ذخیره با خطا مواجه شد.");
    } finally {
      setBusy(false);
    }
  }
  const info = target?.info;
  return (
    <Dialog open={Boolean(target)} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>سابقه بیمه {target ? `— ${target.name}` : ""}</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          {info && (
            <Alert severity="info" icon={false}>
              <Typography variant="body2">
                روزهای پس از استخدام: <b>{info.since_hire_days === null ? "تاریخ استخدام ثبت نشده" : fa(info.since_hire_days)}</b>
              </Typography>
              <Typography variant="body2">
                سابقه‌ی قبلی اعلام‌شده توسط پرسنل: <b>{info.employee_prior_days === null || info.employee_prior_days === undefined ? "—" : fa(info.employee_prior_days)}</b>
              </Typography>
            </Alert>
          )}
          <TextField
            size="small"
            label="سابقه‌ی بیمه‌ی پیش از استخدام (روز)"
            value={prior}
            onChange={(e) => setPrior(digits(e.target.value))}
            inputProps={{ dir: "ltr", inputMode: "numeric" }}
            helperText="با روزهای پس از استخدام جمع می‌شود و بر عدد اعلام‌شده توسط پرسنل مقدم است. خالی = ثبت نشده."
          />
          <TextField
            size="small"
            label="کل سابقه‌ی بیمه (روز) — فقط برای موارد استثنا"
            value={total}
            onChange={(e) => setTotal(digits(e.target.value))}
            inputProps={{ dir: "ltr", inputMode: "numeric" }}
            helperText="اگر پر شود، جایگزین محاسبه‌ی خودکار می‌شود و با گذشت زمان زیاد نمی‌شود. خالی = محاسبه‌ی خودکار."
          />
          {target?.withNote && (
            <TextField multiline minRows={2} label="یادداشت داخلی" value={note} onChange={(e) => setNote(e.target.value)} inputProps={{ maxLength: 4000 }} />
          )}
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          انصراف
        </Button>
        <Button variant="contained" onClick={submit} disabled={busy}>
          ذخیره
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ورود گروهی سابقه بیمه از Excel
function InsuranceImportDialog({ open, onClose, onDone }) {
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState("prior");
  const [siteId, setSiteId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setFile(null);
      setResult(null);
      setError("");
    }
  }, [open]);
  async function submit() {
    setBusy(true);
    setError("");
    try {
      const res = await importFamilyInsuranceDays(file, mode, siteId);
      setResult(res);
      onDone();
    } catch (err) {
      setError(typeof err.response?.data?.detail === "string" ? err.response.data.detail : "ورود فایل با خطا مواجه شد.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>ورود سابقه بیمه از Excel</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            فایل xlsx با یک ستون «کد پرسنلی» و یک ستون «سابقه (روز)». ردیف‌های خالی نادیده گرفته می‌شوند.
          </Typography>
          <TextField select size="small" label="مقدار ستون روز" value={mode} onChange={(e) => setMode(e.target.value)}>
            <MenuItem value="prior">سابقه‌ی بیمه‌ی پیش از استخدام (با روزهای پس از استخدام جمع می‌شود)</MenuItem>
            <MenuItem value="total">کل سابقه‌ی بیمه (جایگزین محاسبه‌ی خودکار)</MenuItem>
          </TextField>
          <SiteFilterSelect value={siteId} permission="family.manage" onChange={setSiteId} sx={{ width: "100%" }} />
          <Button component="label" variant="outlined">
            {file ? file.name : "انتخاب فایل Excel"}
            <input hidden type="file" accept=".xlsx" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </Button>
          {error && <Alert severity="error">{error}</Alert>}
          {result && (
            <Alert severity={result.not_found.length || result.invalid.length || result.ambiguous.length ? "warning" : "success"}>
              <div>{fa(result.updated)} نفر به‌روز شد.</div>
              {result.not_found.length > 0 && <div>کد پرسنلی پیدا نشد: {result.not_found.join("، ")}</div>}
              {result.invalid.length > 0 && <div>مقدار نامعتبر: {result.invalid.join("، ")}</div>}
              {result.ambiguous.length > 0 && <div>کد تکراری در چند سایت (سایت را انتخاب کنید): {result.ambiguous.join("، ")}</div>}
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
        <Button variant="contained" onClick={submit} disabled={busy || !file}>
          ورود
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------- جزئیات پرونده ----------

function DetailDialog({ profileId, asOf, canManage, formSettings, onClose, onChanged }) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [action, setAction] = useState(null); // approve / reject / return
  const [hrTarget, setHrTarget] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      setDetail(await fetchFamilyProfile(profileId, asOf));
    } catch (err) {
      setError(err.response?.data?.detail || "بارگذاری جزئیات با خطا مواجه شد.");
    }
  }, [profileId, asOf]);

  useEffect(() => {
    if (profileId) {
      setDetail(null);
      load();
    }
  }, [profileId, load]);

  async function openDoc(doc) {
    try {
      saveBlob(await downloadFamilyDocument(doc.id), doc.file_name);
    } catch {
      setError("دانلود مدرک با خطا مواجه شد.");
    }
  }

  async function doAction({ note, date }) {
    if (action === "approve") await approveFamilyProfile(profileId, { effective_date: date || null, note: note || null });
    else if (action === "reject") await rejectFamilyProfile(profileId, note);
    else await returnFamilyProfile(profileId, note);
    setAction(null);
    await load();
    onChanged();
  }

  const p = detail?.profile;
  const emp = detail?.employee;
  return (
    <Dialog open={Boolean(profileId)} onClose={onClose} maxWidth="md" fullWidth fullScreen={fullScreen}>
      <DialogTitle>
        مشخصات خانوادگی {emp ? `— ${emp.first_name} ${emp.last_name} (${emp.personnel_code})` : ""}
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {!detail && !error && (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
            <CircularProgress />
          </Box>
        )}
        {detail && (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
              <Chip color={STATUS_COLOR[p.status]} label={STATUS_LABEL[p.status]} />
              <Chip variant="outlined" label={`جنسیت: ${emp.gender === 1 ? "مرد" : emp.gender === 2 ? "زن" : "نامشخص"}`} />
              <Chip variant="outlined" label={`سایت: ${emp.site_name || "—"}`} />
              <Chip
                variant="outlined"
                color={detail.insurance?.days === null ? "warning" : "default"}
                label={`سابقه بیمه: ${detail.insurance?.days === null ? "نامشخص" : `${fa(detail.insurance.days)} روز (${detail.insurance.source_label})`}`}
                onClick={
                  canManage
                    ? () =>
                        setHrTarget({
                          employee_id: emp.id,
                          name: `${emp.first_name} ${emp.last_name}`,
                          hr_prior: detail.insurance?.hr_prior_days,
                          hr_total: detail.insurance?.hr_total_days,
                          hr_note: detail.hr_note,
                          withNote: true,
                          info: detail.insurance,
                        })
                    : undefined
                }
                icon={canManage ? <EditOutlinedIcon /> : undefined}
              />
              {p.effective_date && <Chip variant="outlined" label={`تاریخ اثر: ${p.effective_date}`} />}
            </Stack>
            {detail.hr_note && <Alert severity="info">یادداشت داخلی: {detail.hr_note}</Alert>}
            {p.review_note && <Alert severity={p.status === "approved" ? "success" : "warning"}>توضیح بررسی: {p.review_note}</Alert>}
            {detail.missing_documents.length > 0 && <Alert severity="error">مدارک اجباری ناقص: {detail.missing_documents.join("، ")}</Alert>}
            {detail.warnings.length > 0 && (
              <Alert severity="warning">
                {detail.warnings.map((w, i) => (
                  <div key={i}>{w}</div>
                ))}
              </Alert>
            )}

            <Grid container spacing={1.5}>
              {detail.evaluation_approved && (
                <Grid item xs={12} md={p.status === "approved" ? 12 : 6}>
                  <EvaluationCard title="شمول (نسخه‌ی تأییدشده)" evaluation={detail.evaluation_approved} color="success" />
                </Grid>
              )}
              {p.status !== "approved" && (
                <Grid item xs={12} md={detail.evaluation_approved ? 6 : 12}>
                  <EvaluationCard title="شمول در صورت تأیید نسخه‌ی جاری" evaluation={detail.evaluation_current} color="warning" />
                </Grid>
              )}
            </Grid>

            <Divider />
            <Typography fontWeight={800}>اطلاعات ثبت‌شده توسط پرسنل {p.submitted_at ? `(${faDateTime(p.submitted_at)})` : ""}</Typography>
            {p.status === "draft" ? (
              <Alert severity="info">پرسنل هنوز فرم را ثبت نکرده است.</Alert>
            ) : (
              <FamilySummary profile={p} formSettings={formSettings} onOpenDoc={openDoc} />
            )}

            {detail.logs.length > 0 && (
              <>
                <Divider />
                <Typography fontWeight={800}>تاریخچه</Typography>
                <Stack spacing={0.5}>
                  {detail.logs.map((log) => (
                    <Typography key={log.id} variant="caption">
                      {faDateTime(log.created_at)} — {log.action_label}
                      {log.actor_name ? ` — ${log.actor_name}` : ""}
                      {log.effective_date ? ` — تاریخ اثر ${log.effective_date}` : ""}
                      {log.note ? ` — ${log.note}` : ""}
                    </Typography>
                  ))}
                </Stack>
              </>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ flexWrap: "wrap", gap: 1 }}>
        {detail && canManage && p.status !== "draft" && (
          <>
            {["pending", "returned", "rejected"].includes(p.status) && (
              <Button variant="contained" color="success" onClick={() => setAction("approve")}>
                تأیید
              </Button>
            )}
            {p.status === "pending" && (
              <Button variant="outlined" color="error" onClick={() => setAction("reject")}>
                رد
              </Button>
            )}
            {p.status !== "returned" && (
              <Button variant="outlined" onClick={() => setAction("return")}>
                بازگشت برای ویرایش
              </Button>
            )}
          </>
        )}
        <Box sx={{ flex: 1 }} />
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
      <NoteDialog
        open={action === "approve"}
        title="تأیید مشخصات خانوادگی"
        label="توضیح (اختیاری؛ به پرسنل اطلاع داده می‌شود)"
        confirmText="تأیید"
        color="success"
        withDate
        onClose={() => setAction(null)}
        onConfirm={doAction}
      />
      <NoteDialog
        open={action === "reject" || action === "return"}
        title={action === "reject" ? "رد مشخصات خانوادگی" : "بازگشت برای ویرایش"}
        label="دلیل (به پرسنل نمایش داده می‌شود)"
        confirmText={action === "reject" ? "رد" : "بازگشت"}
        color={action === "reject" ? "error" : "primary"}
        onClose={() => setAction(null)}
        onConfirm={doAction}
      />
      <HrFieldsDialog
        target={hrTarget}
        onClose={() => setHrTarget(null)}
        onSaved={async () => {
          setHrTarget(null);
          await load();
          onChanged();
        }}
      />
    </Dialog>
  );
}

// ---------- تب فهرست ----------

function ListTab({ canManage, formSettings }) {
  const [filters, setFilters] = useState({ search: "", siteId: null, status: "", flag: "", asOf: "" });
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [detailId, setDetailId] = useState(null);
  const [hrTarget, setHrTarget] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  const asOfValid = !filters.asOf || /^\d{4}\/\d{2}\/\d{2}$/.test(filters.asOf);
  const params = {
    search: filters.search || undefined,
    site_id: filters.siteId || undefined,
    status_filter: filters.status || undefined,
    flag: filters.flag || undefined,
    as_of: asOfValid && filters.asOf ? filters.asOf : undefined,
  };

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await fetchFamilyProfiles({ ...params, page: page + 1, page_size: rowsPerPage }));
    } catch (err) {
      setError(err.response?.data?.detail || "بارگذاری فهرست با خطا مواجه شد.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.search, filters.siteId, filters.status, filters.flag, filters.asOf, page, rowsPerPage]);

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [load]);

  const setFilter = (patch) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(0);
  };

  async function handleExport() {
    setExporting(true);
    try {
      const blob = await downloadFamilyExport({ site_id: params.site_id, as_of: params.as_of });
      saveBlob(blob, `family_export_${new Date().toISOString().slice(0, 10)}.xlsx`);
    } catch {
      setError("خروجی Excel با خطا مواجه شد.");
    } finally {
      setExporting(false);
    }
  }

  const s = data?.stats;
  return (
    <Box>
      <Card variant="outlined" sx={{ p: 2, borderRadius: 2, mb: 2 }}>
        <Grid container spacing={1.5} alignItems="center">
          <Grid item xs={12} sm={6} md={3}>
            <TextField fullWidth size="small" label="جستجو (کد پرسنلی / نام)" value={filters.search} onChange={(e) => setFilter({ search: e.target.value })} />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <SiteFilterSelect value={filters.siteId} permission={canManage ? "family.manage" : "family.view"} onChange={(v) => setFilter({ siteId: v })} sx={{ width: "100%" }} />
          </Grid>
          <Grid item xs={6} md={2}>
            <TextField select fullWidth size="small" label="وضعیت" value={filters.status} onChange={(e) => setFilter({ status: e.target.value })}>
              <MenuItem value="">همه</MenuItem>
              {Object.entries({ none: "ثبت نشده", pending: "در انتظار بررسی", approved: "تأیید شده", rejected: "رد شده", returned: "بازگشت برای ویرایش" }).map(([k, v]) => (
                <MenuItem key={k} value={k}>
                  {v}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={6} md={2}>
            <TextField select fullWidth size="small" label="فیلتر" value={filters.flag} onChange={(e) => setFilter({ flag: e.target.value })}>
              <MenuItem value="">—</MenuItem>
              {Object.entries(FLAGS).map(([k, v]) => (
                <MenuItem key={k} value={k}>
                  {v}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={6} md={1.5}>
            <JalaliCalendarField label="تاریخ مبنا (خالی = امروز)" value={filters.asOf} onChange={(v) => setFilter({ asOf: v || "" })} />
          </Grid>
          <Grid item xs={6} md={1.5}>
            <Button fullWidth variant="outlined" startIcon={exporting ? <CircularProgress size={16} /> : <FileDownloadOutlinedIcon />} onClick={handleExport} disabled={exporting}>
              Excel
            </Button>
          </Grid>
        </Grid>
        {s && (
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1.5 }}>
            <Chip size="small" label={`پرسنل فعال: ${fa(s.employees)}`} />
            <Chip size="small" label={`ثبت نشده: ${fa(s.not_submitted)}`} />
            <Chip size="small" color="warning" label={`در انتظار بررسی: ${fa(s.pending)}`} onClick={() => setFilter({ status: "pending" })} />
            <Chip size="small" color="success" label={`تأیید شده: ${fa(s.approved)}`} />
            <Chip size="small" variant="outlined" label={`مشمول حق تاهل: ${fa(s.marriage_eligible)}`} />
            <Chip size="small" variant="outlined" label={`فرزندان واجد شرایط: ${fa(s.eligible_children)}`} />
            {s.warnings > 0 && <Chip size="small" color="error" variant="outlined" label={`دارای هشدار: ${fa(s.warnings)}`} onClick={() => setFilter({ flag: "warnings" })} />}
            <Box sx={{ flex: 1 }} />
            {canManage && (
              <Button size="small" startIcon={<UploadFileOutlinedIcon />} onClick={() => setImportOpen(true)}>
                ورود سابقه بیمه از Excel
              </Button>
            )}
          </Stack>
        )}
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
          شمول حق تاهل و تعداد فرزند واجد شرایط بر اساس آخرین نسخه‌ی تأییدشده‌ی هر پرونده و قواعد تب «قواعد و تنظیمات» در تاریخ مبنا محاسبه می‌شود.
        </Typography>
      </Card>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{typeof error === "string" ? error : "خطا"}</Alert>}
      {!data && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {data && (
        <Card variant="outlined" sx={{ borderRadius: 2 }}>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>کد پرسنلی</TableCell>
                  <TableCell>نام و نام خانوادگی</TableCell>
                  <TableCell>سایت</TableCell>
                  <TableCell>وضعیت</TableCell>
                  <TableCell>تاهل</TableCell>
                  <TableCell align="center">پسر / دختر</TableCell>
                  <TableCell align="center">سابقه بیمه</TableCell>
                  <TableCell align="center">حق تاهل</TableCell>
                  <TableCell align="center">فرزند واجد شرایط</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {data.items.map((item) => (
                  <TableRow key={item.employee_id} hover>
                    <TableCell>{item.personnel_code}</TableCell>
                    <TableCell>
                      {item.first_name} {item.last_name}
                    </TableCell>
                    <TableCell>{item.site_name}</TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <Chip size="small" color={STATUS_COLOR[item.status]} label={STATUS_LABEL[item.status]} />
                        {item.has_pending_changes && (
                          <Tooltip title="تغییرات جدید هنوز تأیید نشده؛ محاسبه بر اساس نسخه‌ی تأییدشده‌ی قبلی است">
                            <Chip size="small" variant="outlined" label="تغییر" />
                          </Tooltip>
                        )}
                        {item.warnings.length > 0 && (
                          <Tooltip title={item.warnings.join(" | ")}>
                            <ReportProblemOutlinedIcon color="warning" fontSize="small" />
                          </Tooltip>
                        )}
                      </Stack>
                    </TableCell>
                    <TableCell>{MARITAL_LABEL[item.marital_status] || "—"}</TableCell>
                    <TableCell align="center">
                      {item.status === "none" ? "—" : `${fa(item.sons)} / ${fa(item.daughters)}`}
                    </TableCell>
                    <TableCell align="center">
                      <Tooltip title={item.insurance_source || "تاریخ استخدام ثبت نشده"}>
                        <span>
                          {canManage ? (
                            <Button
                              size="small"
                              color={item.insurance_days === null ? "warning" : "inherit"}
                              onClick={() =>
                                setHrTarget({
                                  employee_id: item.employee_id,
                                  name: `${item.first_name} ${item.last_name}`,
                                  hr_prior: item.insurance_hr_prior,
                                  hr_total: item.insurance_hr_total,
                                })
                              }
                            >
                              {item.insurance_days === null ? "ثبت" : fa(item.insurance_days)}
                            </Button>
                          ) : (
                            fa(item.insurance_days)
                          )}
                        </span>
                      </Tooltip>
                    </TableCell>
                    <TableCell align="center">
                      <EligibleIcon value={item.marriage_eligible} />
                    </TableCell>
                    <TableCell align="center">{item.eligible_children === null ? "—" : fa(item.eligible_children)}</TableCell>
                    <TableCell>
                      {item.profile_id && item.status !== "none" && (
                        <IconButton size="small" onClick={() => setDetailId(item.profile_id)} aria-label="جزئیات">
                          <VisibilityOutlinedIcon fontSize="small" />
                        </IconButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {data.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={10} align="center" sx={{ py: 4, color: "text.secondary" }}>
                      موردی یافت نشد.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div"
            count={data.total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(Number(e.target.value));
              setPage(0);
            }}
            rowsPerPageOptions={[25, 50, 100]}
            labelRowsPerPage="تعداد در صفحه"
            labelDisplayedRows={({ from, to, count }) => `${fa(from)}–${fa(to)} از ${fa(count)}`}
          />
        </Card>
      )}

      <DetailDialog
        profileId={detailId}
        asOf={params.as_of}
        canManage={canManage}
        formSettings={formSettings}
        onClose={() => setDetailId(null)}
        onChanged={load}
      />
      <HrFieldsDialog
        target={hrTarget}
        onClose={() => setHrTarget(null)}
        onSaved={() => {
          setHrTarget(null);
          load();
        }}
      />
      <InsuranceImportDialog open={importOpen} onClose={() => setImportOpen(false)} onDone={load} />
    </Box>
  );
}

// ---------- تب تنظیمات ----------

const SECTION_TITLES = { profile: "کارمند", spouse: "همسر", child: "فرزندان (پسر و دختر)", son: "فقط پسر", daughter: "فقط دختر" };
const MODE_LABELS = { required: "اجباری", optional: "اختیاری", hidden: "مخفی" };

function NumberField({ label, value, onChange, disabled, helperText, allowEmpty = true }) {
  return (
    <TextField
      fullWidth
      size="small"
      label={label}
      value={value ?? ""}
      disabled={disabled}
      helperText={helperText}
      onChange={(e) => {
        const v = toEn(e.target.value).replace(/\D/g, "").slice(0, 5);
        onChange(v === "" ? (allowEmpty ? null : "") : Number(v));
      }}
      inputProps={{ dir: "ltr", inputMode: "numeric" }}
    />
  );
}

function SwitchRow({ label, checked, onChange, disabled }) {
  return <FormControlLabel control={<Switch checked={Boolean(checked)} onChange={(e) => onChange(e.target.checked)} disabled={disabled} />} label={label} />;
}

// تنظیمات شمول حق اولاد یک جنسیت (پسر یا دختر) — برای هر دو با همان ترتیب و همان متن‌ها
function ChildGenderRules({ gender, cr, setRule, disabled }) {
  const who = gender === "son" ? "پسر" : "دختر";
  const k = (name) => `${gender}_${name}`;
  const set = (name) => (v) => setRule("child", k(name), v);
  return (
    <>
      <Grid item xs={12}>
        <Divider textAlign="right">
          <Typography variant="body2" fontWeight={700}>
            {who}
          </Typography>
        </Divider>
      </Grid>
      <Grid item xs={12} md={6}>
        <NumberField
          label={`سن شروع شرط تحصیل ${who} (سال)`}
          value={cr[k("study_age")]}
          onChange={(v) => setRule("child", k("study_age"), v ?? 18)}
          disabled={disabled}
          allowEmpty={false}
          helperText={`از این سن به بعد وضعیت تحصیل، تاریخ اعتبار و گواهی اشتغال به تحصیل ${who} از پرسنل خواسته می‌شود`}
        />
      </Grid>
      <Grid item xs={12} md={6}>
        <NumberField
          label={`سقف سن ${who} (حتی در صورت تحصیل) — خالی = بدون سقف`}
          value={cr[k("max_age")]}
          onChange={set("max_age")}
          disabled={disabled}
          helperText={`${who} از این سن به بعد در هیچ حالتی مشمول نیست (مگر از کار افتاده)`}
        />
      </Grid>
      <Grid item xs={12}>
        <SwitchRow label={`${who} بالای سن شروع شرط تحصیل، فقط اگر در حال تحصیل باشد مشمول است`} checked={cr[k("require_study")]} onChange={set("require_study")} disabled={disabled} />
        <SwitchRow
          label={`برای شمول ${who} محصل، گواهی تحصیل معتبر (منقضی‌نشده) لازم است`}
          checked={cr[k("require_valid_student_certificate")]}
          onChange={set("require_valid_student_certificate")}
          disabled={disabled || !cr[k("require_study")]}
        />
        <SwitchRow label={`${who} از کار افتاده بدون شرط سن و تحصیل مشمول است`} checked={cr[k("extend_if_disabled")]} onChange={set("extend_if_disabled")} disabled={disabled} />
        <SwitchRow label={`${who} با ازدواج از شمول خارج می‌شود`} checked={cr[k("stop_on_marriage")]} onChange={set("stop_on_marriage")} disabled={disabled} />
        <SwitchRow label={`${who} با اشتغال از شمول خارج می‌شود`} checked={cr[k("stop_on_employment")]} onChange={set("stop_on_employment")} disabled={disabled} />
      </Grid>
    </>
  );
}

function SettingsTab({ canManage, editable = true, initial, meta, onSaved }) {
  const [s, setS] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  useEffect(() => setS(initial), [initial]);

  // مدیر یک یا چند سایت (نه همه): تنظیمات مشترک فقط خواندنی
  const ro = !canManage || !editable;
  const setRule = (group, key, value) => setS((cur) => ({ ...cur, rules: { ...cur.rules, [group]: { ...cur.rules[group], [key]: value } } }));
  const mr = s.rules.marriage;
  const cr = s.rules.child;

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      const res = await updateFamilySettings(s);
      onSaved(res);
      setMessage({ severity: "success", text: "تنظیمات ذخیره شد." });
    } catch (err) {
      setMessage({ severity: "error", text: typeof err.response?.data?.detail === "string" ? err.response.data.detail : "ذخیره با خطا مواجه شد." });
    } finally {
      setSaving(false);
    }
  }

  const sections = ["profile", "spouse", "child"];
  const fieldModeSelect = (f) => (
    <TextField
      select
      fullWidth
      size="small"
      label={f.label}
      value={s.fields[f.key]}
      disabled={ro}
      onChange={(e) => setS({ ...s, fields: { ...s.fields, [f.key]: e.target.value } })}
    >
      {Object.entries(MODE_LABELS).map(([k, v]) => (
        <MenuItem key={k} value={k}>
          {v}
        </MenuItem>
      ))}
    </TextField>
  );
  return (
    <Stack spacing={2}>
      {ro && <Alert severity="info">فقط دارنده‌ی مجوز «مدیریت مشخصات خانوادگی» می‌تواند تنظیمات را تغییر دهد.</Alert>}

      <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1 }}>
          کلیات فرم
        </Typography>
        <Stack>
          <SwitchRow label="فرم «مشخصات خانوادگی» برای پرسنل فعال باشد" checked={s.enabled} onChange={(v) => setS({ ...s, enabled: v })} disabled={ro} />
          <SwitchRow
            label="پس از تأیید، پرسنل نتواند فرم را ویرایش کند (فقط با «بازگشت برای ویرایش»)"
            checked={s.lock_after_approval}
            onChange={(v) => setS({ ...s, lock_after_approval: v })}
            disabled={ro}
          />
        </Stack>
        <TextField
          fullWidth
          multiline
          minRows={3}
          sx={{ mt: 1.5 }}
          label="نکات بالای فرم (هر خط یک نکته)"
          value={s.notes.join("\n")}
          onChange={(e) => setS({ ...s, notes: e.target.value.split("\n") })}
          disabled={ro}
        />
      </Card>

      <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800}>سابقه بیمه</Typography>
        <Typography variant="caption" color="text.secondary">
          سابقه = روزهای پس از تاریخ استخدام (کاراوب) + سابقه‌ی پیش از استخدام. منابع انسانی می‌تواند برای هر نفر سابقه‌ی قبلی یا کل سابقه را دستی یا از Excel ثبت کند.
        </Typography>
        <Stack sx={{ mt: 1 }}>
          <SwitchRow
            label="روزهای پس از تاریخ استخدام خودکار جزو سابقه‌ی بیمه حساب شود"
            checked={s.insurance.auto_from_hire_date}
            onChange={(v) => setS({ ...s, insurance: { ...s.insurance, auto_from_hire_date: v } })}
            disabled={ro}
          />
          <SwitchRow
            label="اگر سابقه‌ی همین شرکت کافی نیست، سابقه‌ی بیمه‌ی پیش از استخدام (با پرینت سوابق) از خود پرسنل پرسیده شود"
            checked={s.insurance.ask_employee_prior}
            onChange={(v) => setS({ ...s, insurance: { ...s.insurance, ask_employee_prior: v } })}
            disabled={ro}
          />
        </Stack>
      </Card>

      <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800}>حق تاهل</Typography>
        <Typography variant="caption" color="text.secondary">
          شرایطی که بر اساس آن‌ها شمول حق تاهل هر پرسنل محاسبه می‌شود.
        </Typography>
        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
          <Grid item xs={12}>
            <SwitchRow label="محاسبه‌ی حق تاهل فعال باشد" checked={mr.enabled} onChange={(v) => setRule("marriage", "enabled", v)} disabled={ro} />
            <SwitchRow label="کارمند مرد متاهل مشمول است" checked={mr.male_married} onChange={(v) => setRule("marriage", "male_married", v)} disabled={ro} />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField select fullWidth size="small" label="کارمند زن" value={mr.female_mode} onChange={(e) => setRule("marriage", "female_mode", e.target.value)} disabled={ro}>
              {Object.entries(meta.marriage_female_modes).map(([k, v]) => (
                <MenuItem key={k} value={k}>
                  {v}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} md={6}>
            <NumberField label="حداقل سابقه بیمه (روز) — خالی = بدون شرط" value={mr.min_insurance_days} onChange={(v) => setRule("marriage", "min_insurance_days", v)} disabled={ro} />
          </Grid>
        </Grid>
      </Card>

      <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800}>حق اولاد</Typography>
        <Typography variant="caption" color="text.secondary">
          شرایط کلی کارمند و شرایط هر فرزند برای محاسبه‌ی تعداد فرزند واجد شرایط.
        </Typography>
        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
          <Grid item xs={12}>
            <SwitchRow label="محاسبه‌ی حق اولاد فعال باشد" checked={cr.enabled} onChange={(v) => setRule("child", "enabled", v)} disabled={ro} />
          </Grid>
          <Grid item xs={12} md={4}>
            <NumberField label="حداقل سابقه بیمه (روز) — خالی = بدون شرط" value={cr.min_insurance_days} onChange={(v) => setRule("child", "min_insurance_days", v)} disabled={ro} />
          </Grid>
          <Grid item xs={12} md={4}>
            <NumberField label="سقف تعداد فرزند — خالی = بدون سقف" value={cr.max_children} onChange={(v) => setRule("child", "max_children", v)} disabled={ro} />
          </Grid>
          <Grid item xs={12} md={4}>
            <TextField select fullWidth size="small" label="کارمند زن" value={cr.female_mode} onChange={(e) => setRule("child", "female_mode", e.target.value)} disabled={ro}>
              {Object.entries(meta.child_female_modes).map(([k, v]) => (
                <MenuItem key={k} value={k}>
                  {v}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12}>
            <SwitchRow label="اگر همسر از محل کار خود حق اولاد می‌گیرد، مشمول نباشد" checked={cr.exclude_if_spouse_receives} onChange={(v) => setRule("child", "exclude_if_spouse_receives", v)} disabled={ro} />
            <SwitchRow label="فرزندخوانده مشمول است" checked={cr.include_adopted} onChange={(v) => setRule("child", "include_adopted", v)} disabled={ro} />
            <SwitchRow label="فرزند همسر مشمول است" checked={cr.include_step} onChange={(v) => setRule("child", "include_step", v)} disabled={ro} />
            <SwitchRow label="پس از طلاق فقط فرزندی که حضانتش با کارمند (یا مشترک) است مشمول باشد" checked={cr.require_custody_after_divorce} onChange={(v) => setRule("child", "require_custody_after_divorce", v)} disabled={ro} />
          </Grid>
          {/* پسر و دختر: تنظیمات، ترتیب و متن‌های یکسان */}
          {["son", "daughter"].map((g) => (
            <ChildGenderRules key={g} gender={g} cr={cr} setRule={setRule} disabled={ro} />
          ))}
        </Grid>
      </Card>

      <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1 }}>
          مدارک
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
          هر مدرک فقط وقتی از پرسنل خواسته می‌شود که شرطش برقرار باشد (مثلاً گواهی تحصیل فقط برای پسر یا دختری که به سن شروع شرط تحصیل رسیده و در حال تحصیل است). دوره‌ی تمدید مبنای انقضا و هشدار است؛ انقضای گواهی اشتغال به تحصیل از «تاریخ اعتبار» همان گواهی محاسبه می‌شود.
        </Typography>
        <Stack spacing={1.25}>
          {Object.entries(meta.doc_types).map(([key, spec]) => (
            <Grid container spacing={1} alignItems="center" key={key}>
              <Grid item xs={12} md={5}>
                <Typography variant="body2" fontWeight={700}>
                  {spec.label}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {spec.hint}
                </Typography>
              </Grid>
              <Grid item xs={6} md={3}>
                <TextField
                  select
                  fullWidth
                  size="small"
                  value={s.documents[key].mode}
                  disabled={ro}
                  onChange={(e) => setS({ ...s, documents: { ...s.documents, [key]: { ...s.documents[key], mode: e.target.value } } })}
                >
                  {Object.entries(MODE_LABELS).map(([k, v]) => (
                    <MenuItem key={k} value={k}>
                      {v}
                    </MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid item xs={6} md={4}>
                {spec.expiry_field ? (
                  // گواهی اشتغال به تحصیل: انقضا = «تاریخ اعتبار» که پرسنل همراه گواهی وارد می‌کند (دوره تمدید ندارد)
                  <Typography variant="caption" color="text.secondary">
                    انقضا: «تاریخ اعتبار گواهی» که پرسنل همراه گواهی وارد می‌کند
                  </Typography>
                ) : (
                  <NumberField
                    label="تمدید هر چند ماه — خالی = ندارد"
                    value={s.documents[key].renewal_months}
                    disabled={ro}
                    onChange={(v) => setS({ ...s, documents: { ...s.documents, [key]: { ...s.documents[key], renewal_months: v } } })}
                  />
                )}
              </Grid>
            </Grid>
          ))}
        </Stack>
      </Card>

      <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1 }}>
          فیلدهای فرم
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
          نام و نام خانوادگی اعضا، تاریخ تولد فرزندان، وضعیت تاهل و «دارای فرزند» همیشه اجباری‌اند.
        </Typography>
        {sections.map((section) => (
          <Box key={section} sx={{ mb: 1.5 }}>
            <Typography variant="body2" fontWeight={800} color="primary" sx={{ mb: 0.75 }}>
              {SECTION_TITLES[section]}
            </Typography>
            <Grid container spacing={1}>
              {meta.field_defs
                .filter((f) => f.key.startsWith(`${section}.`))
                .map((f) => (
                  <Grid item xs={12} sm={6} md={4} key={f.key}>
                    {fieldModeSelect(f)}
                  </Grid>
                ))}
            </Grid>
          </Box>
        ))}
        {/* پسر و دختر کنار هم و ردیف‌به‌ردیف هم‌تراز (فیلدها هم‌نام و هم‌ترتیب‌اند) */}
        <Grid container spacing={2}>
          {["son", "daughter"].map((section) => (
            <Grid item xs={12} md={6} key={section}>
              <Typography variant="body2" fontWeight={800} color="primary" sx={{ mb: 0.75 }}>
                {SECTION_TITLES[section]}
              </Typography>
              <Stack spacing={1}>
                {meta.field_defs
                  .filter((f) => f.key.startsWith(`${section}.`))
                  .map((f) => (
                    <Box key={f.key}>{fieldModeSelect(f)}</Box>
                  ))}
              </Stack>
            </Grid>
          ))}
        </Grid>
      </Card>

      <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1 }}>
          هشدارها
        </Typography>
        <Grid container spacing={1.5}>
          <Grid item xs={12} md={6}>
            <NumberField
              label="هشدار رسیدن پسر/دختر به سن شروع شرط تحصیل، چند ماه قبل (۰ = خاموش)"
              value={s.alerts.son_age_warning_months}
              onChange={(v) => setS({ ...s, alerts: { ...s.alerts, son_age_warning_months: v ?? 0 } })}
              disabled={ro}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <NumberField
              label="هشدار انقضای مدرک، چند روز قبل (۰ = خاموش)"
              value={s.alerts.doc_expiry_warning_days}
              onChange={(v) => setS({ ...s, alerts: { ...s.alerts, doc_expiry_warning_days: v ?? 0 } })}
              disabled={ro}
            />
          </Grid>
        </Grid>
      </Card>

      {message && <Alert severity={message.severity}>{message.text}</Alert>}
      {canManage && !editable && (
        <Alert severity="info">
          این قواعد و تنظیمات بین همه‌ی سایت‌ها مشترک است و فقط کسی که مجوز مدیریت مشخصات خانوادگی را برای همه‌ی سایت‌ها
          دارد می‌تواند آن را تغییر دهد. بررسی و تأیید پرونده‌های سایت‌های شما در تب فهرست انجام می‌شود.
        </Alert>
      )}
      {!ro && (
        <Box>
          <Button variant="contained" size="large" startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <SaveOutlinedIcon />} onClick={save} disabled={saving}>
            ذخیره تنظیمات
          </Button>
        </Box>
      )}
    </Stack>
  );
}

// ---------- صفحه ----------

export default function FamilyAdminPage() {
  const { user } = useAuth();
  const canManage = Boolean(user?.can_manage_family);
  const [tab, setTab] = useState("list");
  const [settingsData, setSettingsData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchFamilySettings()
      .then(setSettingsData)
      .catch((err) => setError(err.response?.data?.detail || "بارگذاری تنظیمات با خطا مواجه شد."));
  }, []);

  // تنظیمات فرم به قالبی که FamilySummary انتظار دارد
  const formSettings = settingsData
    ? {
        ...settingsData.meta,
        fields: settingsData.settings.fields,
        documents: settingsData.settings.documents,
      }
    : null;

  const tabs = [
    { key: "list", label: "پرسنل" },
    { key: "settings", label: "قواعد و تنظیمات" },
  ];

  return (
    <Box sx={{ maxWidth: 1300, mx: "auto" }}>
      <BackLink to="/" label="بازگشت" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        مشخصات خانوادگی پرسنل
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        وضعیت تاهل، همسر و فرزندان پرسنل، بررسی و تأیید، و محاسبه‌ی شمول حق تاهل و حق اولاد بر اساس قواعدی که همین‌جا تنظیم می‌کنید.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      {!settingsData && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      )}
      {settingsData && (
        <>
          <PillTabs value={tab} onChange={setTab} tabs={tabs} sx={{ mb: 2 }} />
          {tab === "list" ? (
            <ListTab canManage={canManage} formSettings={formSettings} />
          ) : (
            <SettingsTab canManage={canManage} editable={settingsData.editable !== false} initial={settingsData.settings} meta={settingsData.meta} onSaved={setSettingsData} />
          )}
        </>
      )}
    </Box>
  );
}
