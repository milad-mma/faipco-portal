import { useEffect, useState } from "react";
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
  Typography,
} from "@mui/material";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import BackLink from "../components/BackLink";
import PillTabs from "../components/PillTabs";
import SiteFilterSelect from "../components/SiteFilterSelect";
import InsuranceRateInfo from "../components/InsuranceRateInfo";
import { useAuth } from "../context/AuthContext";
import {
  deleteInsuranceRegistration,
  downloadInsuranceDocument,
  downloadInsuranceExport,
  fetchInsuranceRegistration,
  fetchInsuranceRegistrations,
  fetchInsuranceSettings,
  rejectInsuranceDocument,
  updateInsuranceSettings,
} from "../api/insurance";

/**
 * صفحه‌ی مدیریت بیمه تکمیلی (مسیر /insurance/admin).
 * دو تب دارد: «ثبت‌نام‌ها» (فهرست، جستجو، جزئیات، حذف، خروجی Excel) برای
 * دارندگان insurance.view و «تنظیمات» (فعال/غیرفعال، جدول نرخ، نکات) برای
 * دارندگان insurance.manage.
 */

// برچسب کدهای عددی جنسیت/تأهل و عنوان فارسی انواع عضو
const GENDER_LABEL = { 1: "مرد", 2: "زن" };
const MARITAL_LABEL = { 2: "مجرد", 3: "متاهل" };
// عبارتی که در عنوان/متن اطلاعیه‌ی رد مدرک با نام و نام خانوادگی عضو جایگزین می‌شود (هم‌نام با بک‌اند)
const MEMBER_PLACEHOLDER = "{نام عضو}";
const RELATION_LABEL = { spouse: "همسر", son: "فرزند پسر", daughter: "فرزند دختر", father: "پدر", mother: "مادر" };
// تاریخ ISO را به تاریخ شمسی کوتاه تبدیل می‌کند؛ خالی → «—»
const faDate = (iso) => (iso ? new Date(iso).toLocaleDateString("fa-IR") : "—");

// یک Blob را با نام داده‌شده در مرورگر دانلود می‌کند (لینک موقت ساخته و کلیک می‌شود)
function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/**
 * پنجره‌ی جزئیات یک ثبت‌نام: مشخصات شخص اصلی، جدول اعضا با دکمه‌ی دانلود مدرک
 * و (برای دارنده‌ی insurance.manage) دکمه‌ی حذف کل ثبت‌نام.
 * ورودی: شناسه‌ی ثبت‌نام، تابع بستن، مجوز مدیریت و تابع اطلاع از حذف.
 */
function RegistrationDialog({ id, onClose, canManage, onDeleted, onChanged }) {
  const [reg, setReg] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [rejectTarget, setRejectTarget] = useState(null); // عضوی که پنجره‌ی تأیید رد مدرکش باز است
  const [notice, setNotice] = useState(""); // پیام موفقیت رد مدرک
  const [rejectText, setRejectText] = useState({ title: "", body: "" }); // متن قابل ویرایش اطلاعیه‌ی رد

  // باز کردن پنجره‌ی رد: متن پیش‌فرض از تنظیمات خوانده و «{نام عضو}» با نام عضو جایگزین می‌شود
  async function openReject(member) {
    const name = `${member.first_name} ${member.last_name}`.trim();
    let title = "مدرک بیمه تکمیلی تأیید نشد";
    let body = `مدرک ارائه‌شده برای ${MEMBER_PLACEHOLDER} مورد تأیید نیست. لطفاً جهت پیگیری علت رد مدارک به واحد منابع انسانی مراجعه نمائید.`;
    try {
      const s = await fetchInsuranceSettings();
      title = s.reject_notice_title || title;
      body = s.reject_notice_body || body;
    } catch {
      // تنظیمات در دسترس نبود؛ متن پیش‌فرض
    }
    setRejectText({ title: title.split(MEMBER_PLACEHOLDER).join(name), body: body.split(MEMBER_PLACEHOLDER).join(name) });
    setRejectTarget(member);
  }

  // بارگذاری جزئیات (هنگام باز شدن یا تغییر شناسه و بعد از رد مدرک)
  function loadDetail() {
    fetchInsuranceRegistration(id)
      .then(setReg)
      .catch((e) => setError(e.response?.data?.detail || "دریافت جزئیات با خطا مواجه شد."));
  }
  useEffect(loadDetail, [id]);

  // رد مدرک عضو انتخاب‌شده: فایل حذف و اطلاعیه برای ثبت‌نام‌کننده فرستاده می‌شود
  async function handleReject() {
    const member = rejectTarget;
    setBusy(true);
    setError("");
    try {
      const res = await rejectInsuranceDocument(reg.id, member.id, {
        title: rejectText.title.trim(),
        body: rejectText.body.trim(),
      });
      setNotice(`مدرک ${res.member_name} رد شد و اطلاعیه برای ${reg.first_name} ${reg.last_name} ارسال شد.`);
      setRejectTarget(null);
      loadDetail();
      onChanged?.();
    } catch (e) {
      setError(e.response?.data?.detail || "رد مدرک با خطا مواجه شد.");
    } finally {
      setBusy(false);
    }
  }

  // مدرک را از سرور می‌گیرد و با نام اصلی‌اش دانلود می‌کند
  async function openDoc(doc) {
    try {
      const blob = await downloadInsuranceDocument(doc.id);
      saveBlob(blob, doc.file_name);
    } catch {
      setError("دانلود مدرک با خطا مواجه شد.");
    }
  }

  // حذف ثبت‌نام پس از تأیید کاربر؛ در موفقیت به والد اطلاع می‌دهد تا فهرست تازه شود
  async function handleDelete() {
    if (!window.confirm(`ثبت‌نام «${reg.first_name} ${reg.last_name}» و همه اعضا و مدارکش حذف شود؟`)) return;
    setBusy(true);
    try {
      await deleteInsuranceRegistration(reg.id);
      onDeleted();
    } catch (e) {
      setError(e.response?.data?.detail || "حذف با خطا مواجه شد.");
      setBusy(false);
    }
  }

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>جزئیات ثبت‌نام</DialogTitle>
      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        {notice && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice("")}>
            {notice}
          </Alert>
        )}
        {!reg ? (
          <CircularProgress size={24} />
        ) : (
          <>
            {/* مشخصات شخص اصلی به‌صورت جفت برچسب/مقدار */}
            <Grid container spacing={1.5} sx={{ mb: 2 }}>
              {[
                ["کد پرسنلی", reg.personnel_code],
                ["نام و نام خانوادگی", `${reg.first_name} ${reg.last_name}`],
                ["نام پدر", reg.father_name],
                ["تاریخ تولد", reg.birth_date],
                ["جنسیت", GENDER_LABEL[reg.gender]],
                ["وضعیت تاهل", MARITAL_LABEL[reg.marital_status]],
                ["کد ملی", reg.national_id],
                ["شماره شناسنامه", reg.birth_certificate_no],
                ["شماره تماس", reg.mobile_number],
                ["تاریخ استخدام", reg.employment_date],
                ["شماره بیمه", reg.insurance_no],
                ["کد بانک", reg.bank_code],
                ["شماره حساب", reg.account_number],
                ["شبا", reg.sheba],
                ["نوع حساب", reg.account_type],
                ["صاحب حساب", `${reg.account_owner} (${reg.account_owner_national_id})`],
                ["تاریخ ثبت", faDate(reg.created_at)],
                ["آخرین ویرایش", faDate(reg.updated_at)],
              ].map(([l, v]) => (
                <Grid item xs={6} md={4} key={l}>
                  <Typography variant="caption" color="text.secondary">
                    {l}
                  </Typography>
                  <Typography variant="body2" fontWeight={700} sx={{ direction: "ltr", textAlign: "right" }}>
                    {v ?? "—"}
                  </Typography>
                </Grid>
              ))}
            </Grid>
            <Typography fontWeight={700} sx={{ mb: 1 }}>
              اعضای خانواده ({reg.members.length.toLocaleString("fa-IR")})
            </Typography>
            {reg.members.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                عضوی ثبت نشده است.
              </Typography>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>نسبت</TableCell>
                      <TableCell>نام</TableCell>
                      <TableCell>نام پدر</TableCell>
                      <TableCell>تاریخ تولد</TableCell>
                      <TableCell>کد ملی</TableCell>
                      <TableCell>تاهل</TableCell>
                      <TableCell>کفالت</TableCell>
                      <TableCell>مدرک</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {reg.members.map((m) => (
                      <TableRow key={m.id}>
                        <TableCell>{RELATION_LABEL[m.member_type] || m.member_type}</TableCell>
                        <TableCell>
                          {m.first_name} {m.last_name}
                        </TableCell>
                        <TableCell>{m.father_name}</TableCell>
                        <TableCell sx={{ direction: "ltr" }}>{m.birth_date}</TableCell>
                        <TableCell sx={{ direction: "ltr" }}>{m.national_id}</TableCell>
                        <TableCell>{MARITAL_LABEL[m.marital_status]}</TableCell>
                        <TableCell>{m.kafala_status === "yes" ? "بله" : m.kafala_status === "no" ? "خیر" : "—"}</TableCell>
                        {/* مدرک: دانلود و (با insurance.manage) رد؛ مدرک ردشده‌ای که هنوز جایگزین نشده با تراشه */}
                        <TableCell>
                          {m.document ? (
                            <Stack direction="row" spacing={0.5}>
                              <Button size="small" startIcon={<DownloadOutlinedIcon />} onClick={() => openDoc(m.document)}>
                                دانلود
                              </Button>
                              {canManage && (
                                <Button size="small" color="error" onClick={() => openReject(m)} disabled={busy}>
                                  رد مدرک
                                </Button>
                              )}
                            </Stack>
                          ) : m.document_rejected_at ? (
                            <Chip size="small" color="error" variant="outlined" label="مدرک رد شده" />
                          ) : (
                            "—"
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ justifyContent: "space-between" }}>
        {canManage && reg ? (
          <Button color="error" startIcon={<DeleteOutlineOutlinedIcon />} onClick={handleDelete} disabled={busy}>
            حذف ثبت‌نام
          </Button>
        ) : (
          <span />
        )}
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>

      {/* تأیید رد مدرک با متن اطلاعیه‌ای که برای ثبت‌نام‌کننده فرستاده می‌شود */}
      <Dialog open={Boolean(rejectTarget)} onClose={() => !busy && setRejectTarget(null)} maxWidth="sm" fullWidth>
        <DialogTitle>رد مدرک</DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" sx={{ mb: 2 }}>
            مدرک <b>{rejectTarget?.first_name} {rejectTarget?.last_name}</b> حذف می‌شود و این اطلاعیه برای{" "}
            {reg?.first_name} {reg?.last_name} ارسال می‌شود. می‌توانید عنوان و متن را برای همین مورد ویرایش کنید:
          </Typography>
          <Stack spacing={2}>
            <TextField
              label="عنوان اطلاعیه"
              value={rejectText.title}
              onChange={(e) => setRejectText({ ...rejectText, title: e.target.value })}
              inputProps={{ maxLength: 255 }}
              fullWidth
              disabled={busy}
            />
            <TextField
              label="متن اطلاعیه"
              value={rejectText.body}
              onChange={(e) => setRejectText({ ...rejectText, body: e.target.value })}
              inputProps={{ maxLength: 2000 }}
              multiline
              minRows={3}
              fullWidth
              disabled={busy}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectTarget(null)} disabled={busy}>
            انصراف
          </Button>
          <Button color="error" variant="contained" onClick={handleReject} disabled={busy || !rejectText.title.trim() || !rejectText.body.trim()}>
            رد مدرک و ارسال اطلاعیه
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  );
}

// گزینه‌های فیلتر فهرست بر اساس وضعیت اعضا (مقدار = پارامتر member_filter در API)
const MEMBER_FILTERS = [
  { value: "", label: "همه‌ی ثبت‌نام‌ها" },
  { value: "non_dependent", label: "دارای عضو غیر تحت کفالت" },
  { value: "with_documents", label: "دارای مدرک کفالت" },
  { value: "rejected", label: "دارای مدرک ردشده" },
];

/**
 * تب «ثبت‌نام‌ها»: نوار جستجو و فیلتر سایت، آمار (ثبت‌نام‌شده/فعال/نکرده)،
 * جدول صفحه‌بندی‌شده و دکمه‌ی خروجی Excel. کلیک روی هر سطر پنجره‌ی جزئیات را باز می‌کند.
 */
function RegistrationsTab({ canManage }) {
  const [siteId, setSiteId] = useState(null);
  const [memberFilter, setMemberFilter] = useState(""); // فیلتر وضعیت اعضا (MEMBER_FILTERS)
  const [search, setSearch] = useState(""); // متن داخل فیلد جستجو
  const [query, setQuery] = useState(""); // عبارتی که واقعاً به سرور فرستاده شده (با Enter یا دکمه)
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);
  const [exporting, setExporting] = useState(false);

  // دریافت فهرست با فیلترهای فعلی؛ شماره صفحه در UI صفرمبنا و در API یک‌مبنا است
  function load() {
    fetchInsuranceRegistrations({
      search: query || undefined,
      site_id: siteId || undefined,
      member_filter: memberFilter || undefined,
      page: page + 1,
      page_size: pageSize,
    })
      .then(setData)
      .catch((e) => setError(e.response?.data?.detail || "دریافت فهرست با خطا مواجه شد."));
  }
  useEffect(load, [query, siteId, memberFilter, page, pageSize]);

  // دانلود Excel ثبت‌نام‌های سایت انتخاب‌شده (یا همه‌ی سایت‌های مجاز)
  async function handleExport() {
    setExporting(true);
    try {
      const blob = await downloadInsuranceExport(siteId);
      saveBlob(blob, `insurance_export_${new Date().toISOString().slice(0, 10)}.xlsx`);
    } catch {
      setError("خروجی Excel با خطا مواجه شد.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <Box>
      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap alignItems="center" sx={{ mb: 2 }}>
        <TextField
          size="small"
          label="جستجو (کد پرسنلی، نام، کد ملی)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (setPage(0), setQuery(search.trim()))}
          sx={{ minWidth: 260 }}
        />
        <Button variant="outlined" size="small" onClick={() => (setPage(0), setQuery(search.trim()))}>
          جستجو
        </Button>
        {query && (
          <Button size="small" onClick={() => (setSearch(""), setQuery(""), setPage(0))}>
            پاک
          </Button>
        )}
        <SiteFilterSelect value={siteId} permission="insurance.view" onChange={(v) => (setSiteId(v), setPage(0))} />
        <TextField
          select
          size="small"
          label="وضعیت اعضا"
          value={memberFilter}
          onChange={(e) => (setMemberFilter(e.target.value), setPage(0))}
          sx={{ minWidth: 200 }}
        >
          {MEMBER_FILTERS.map((f) => (
            <MenuItem key={f.value} value={f.value}>
              {f.label}
            </MenuItem>
          ))}
        </TextField>
        <Box sx={{ flex: 1 }} />
        <Button variant="contained" color="success" startIcon={exporting ? <CircularProgress size={16} color="inherit" /> : <DownloadOutlinedIcon />} onClick={handleExport} disabled={exporting}>
          خروجی Excel
        </Button>
      </Stack>
      {/* آمار کلی (مستقل از جستجو) */}
      {data && (
        <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
          <Chip label={`ثبت‌نام‌شده: ${data.registered.toLocaleString("fa-IR")}`} color="success" size="small" />
          <Chip label={`پرسنل فعال: ${data.eligible.toLocaleString("fa-IR")}`} size="small" />
          <Chip label={`ثبت‌نام‌نکرده: ${Math.max(data.eligible - data.registered, 0).toLocaleString("fa-IR")}`} color="warning" size="small" />
        </Stack>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {!data ? (
        <CircularProgress size={24} />
      ) : (
        <TableContainer component={Card} variant="outlined" sx={{ borderRadius: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>کد پرسنلی</TableCell>
                <TableCell>نام</TableCell>
                <TableCell>نام خانوادگی</TableCell>
                <TableCell>کد ملی</TableCell>
                <TableCell>موبایل</TableCell>
                <TableCell>سایت / واحد</TableCell>
                <TableCell align="center">اعضا</TableCell>
                <TableCell align="center">مدارک</TableCell>
                <TableCell>وضعیت</TableCell>
                <TableCell>تاریخ ثبت</TableCell>
                <TableCell align="center">عملیات</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={11} align="center" sx={{ color: "text.secondary", py: 4 }}>
                    ثبت‌نامی یافت نشد.
                  </TableCell>
                </TableRow>
              )}
              {data.items.map((r) => (
                <TableRow key={r.id} hover>
                  <TableCell sx={{ direction: "ltr" }}>{r.personnel_code}</TableCell>
                  <TableCell>{r.first_name}</TableCell>
                  <TableCell>{r.last_name}</TableCell>
                  <TableCell sx={{ direction: "ltr" }}>{r.national_id}</TableCell>
                  <TableCell sx={{ direction: "ltr" }}>{r.mobile_number}</TableCell>
                  <TableCell>
                    {r.site_name}
                    {r.department_name ? ` / ${r.department_name}` : ""}
                  </TableCell>
                  <TableCell align="center">{r.members_count.toLocaleString("fa-IR")}</TableCell>
                  <TableCell align="center">{r.documents_count.toLocaleString("fa-IR")}</TableCell>
                  {/* تعداد اعضای غیر تحت کفالت و مدارک ردشده */}
                  <TableCell>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      {r.non_dependent_count > 0 && (
                        <Chip size="small" variant="outlined" label={`غیر تحت کفالت: ${r.non_dependent_count.toLocaleString("fa-IR")}`} />
                      )}
                      {r.rejected_documents_count > 0 && (
                        <Chip size="small" color="error" variant="outlined" label={`مدرک ردشده: ${r.rejected_documents_count.toLocaleString("fa-IR")}`} />
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell>{faDate(r.created_at)}</TableCell>
                  <TableCell align="center">
                    <IconButton size="small" onClick={() => setOpenId(r.id)} aria-label="جزئیات">
                      <VisibilityOutlinedIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={data.total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={pageSize}
            onRowsPerPageChange={(e) => (setPageSize(Number(e.target.value)), setPage(0))}
            rowsPerPageOptions={[25, 50, 100]}
            labelRowsPerPage="تعداد در صفحه"
            labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
          />
        </TableContainer>
      )}
      {openId && (
        <RegistrationDialog
          id={openId}
          canManage={canManage}
          onClose={() => setOpenId(null)}
          onChanged={load}
          onDeleted={() => {
            setOpenId(null);
            load();
          }}
        />
      )}
    </Box>
  );
}

/**
 * تب «تنظیمات»: کلید فعال/غیرفعال (ذخیره‌ی فوری)، ویرایشگر جدول نرخ
 * (عناوین ستون‌ها و سطرها با جابه‌جایی/حذف/افزودن)، ویرایشگر نکات و پیش‌نمایش
 * زنده؛ جدول و نکات با دکمه‌ی ذخیره ارسال می‌شوند.
 */
function SettingsTab() {
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchInsuranceSettings()
      .then(setSettings)
      .catch(() => setMessage({ severity: "error", text: "دریافت تنظیمات با خطا مواجه شد." }));
  }, []);

  // بخشی از تنظیمات را به سرور می‌فرستد و state را با پاسخ کامل سرور جایگزین می‌کند
  async function save(patch, successText) {
    setSaving(true);
    setMessage(null);
    try {
      setSettings(await updateInsuranceSettings(patch));
      setMessage({ severity: "success", text: successText });
    } catch (e) {
      setMessage({ severity: "error", text: e.response?.data?.detail || "ذخیره با خطا مواجه شد." });
    } finally {
      setSaving(false);
    }
  }

  if (!settings) return <CircularProgress size={24} />;
  // توابع کمکی ویرایش جدول نرخ و نکات در state محلی (بدون ارسال به سرور)
  const table = settings.rate_table;
  const setTable = (next) => setSettings({ ...settings, rate_table: next });
  const setRow = (i, key, value) => setTable({ ...table, rows: table.rows.map((r, j) => (j === i ? { ...r, [key]: value } : r)) });
  // جابه‌جایی سطر i با سطر قبلی (dir=-1) یا بعدی (dir=+1)
  const moveRow = (i, dir) => {
    const rows = [...table.rows];
    const j = i + dir;
    if (j < 0 || j >= rows.length) return;
    [rows[i], rows[j]] = [rows[j], rows[i]];
    setTable({ ...table, rows });
  };
  const notes = settings.notes;
  const setNotes = (next) => setSettings({ ...settings, notes: next });
  const moveNote = (i, dir) => {
    const arr = [...notes];
    const j = i + dir;
    if (j < 0 || j >= arr.length) return;
    [arr[i], arr[j]] = [arr[j], arr[i]];
    setNotes(arr);
  };

  return (
    <Stack spacing={3}>
      {message && <Alert severity={message.severity}>{message.text}</Alert>}

      {/* کلید فعال/غیرفعال ماژول؛ هر تغییر بلافاصله ذخیره می‌شود */}
      <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
        <FormControlLabel
          control={<Switch checked={settings.enabled} disabled={saving} onChange={(e) => save({ enabled: e.target.checked }, e.target.checked ? "ماژول فعال شد." : "ماژول غیرفعال شد.")} />}
          label={<Typography fontWeight={700}>ثبت‌نام بیمه تکمیلی {settings.enabled ? "فعال است" : "غیرفعال است"}</Typography>}
        />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          با غیرفعال‌کردن، کاشی «بیمه تکمیلی» در داشبورد پرسنل برچسب «غیرفعال» می‌گیرد و صفحه ثبت‌نام بسته می‌شود؛ ثبت‌نام‌های
          موجود و این فهرست دست‌نخورده می‌مانند.
        </Typography>
      </Card>

      {/* ویرایشگر جدول نرخ: عناوین ستون‌ها + یک ردیف ورودی به ازای هر بازه‌ی سنی */}
      <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
        <Typography fontWeight={700} sx={{ mb: 0.5 }}>
          جدول نرخ حق بیمه تکمیلی پرسنل
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          همان‌طور که در بخش ۴ فرم ثبت‌نام به پرسنل نمایش داده می‌شود. مبالغ عدد بدون جداکننده.
        </Typography>
        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          <Grid item xs={6} md={3}>
            <TextField size="small" fullWidth label="عنوان ستون سن" value={table.age_header} onChange={(e) => setTable({ ...table, age_header: e.target.value })} />
          </Grid>
          <Grid item xs={6} md={3}>
            <TextField size="small" fullWidth label="واحد" value={table.unit} onChange={(e) => setTable({ ...table, unit: e.target.value })} />
          </Grid>
          <Grid item xs={6} md={3}>
            <TextField size="small" fullWidth label="عنوان ستون غیر تحت تکفل" value={table.non_dependent_header} onChange={(e) => setTable({ ...table, non_dependent_header: e.target.value })} />
          </Grid>
          <Grid item xs={6} md={3}>
            <TextField size="small" fullWidth label="عنوان ستون تحت تکفل" value={table.dependent_header} onChange={(e) => setTable({ ...table, dependent_header: e.target.value })} />
          </Grid>
        </Grid>
        <Stack spacing={1.5}>
          {table.rows.map((row, i) => (
            <Stack key={i} direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <TextField size="small" label="بازه سنی" value={row.age_label} onChange={(e) => setRow(i, "age_label", e.target.value)} sx={{ minWidth: 180 }} />
              <TextField size="small" label="غیر تحت تکفل" type="number" value={row.non_dependent} onChange={(e) => setRow(i, "non_dependent", e.target.value)} inputProps={{ dir: "ltr", min: 0 }} sx={{ width: 170 }} />
              <TextField size="small" label="تحت تکفل" type="number" value={row.dependent} onChange={(e) => setRow(i, "dependent", e.target.value)} inputProps={{ dir: "ltr", min: 0 }} sx={{ width: 170 }} />
              <Button size="small" onClick={() => moveRow(i, -1)} disabled={i === 0}>
                ▲
              </Button>
              <Button size="small" onClick={() => moveRow(i, 1)} disabled={i === table.rows.length - 1}>
                ▼
              </Button>
              <IconButton size="small" color="error" onClick={() => setTable({ ...table, rows: table.rows.filter((_, j) => j !== i) })} disabled={table.rows.length <= 1}>
                <DeleteOutlineOutlinedIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}
        </Stack>
        <Button size="small" startIcon={<AddOutlinedIcon />} sx={{ mt: 1.5 }} onClick={() => setTable({ ...table, rows: [...table.rows, { age_label: "", non_dependent: 0, dependent: 0 }] })}>
          افزودن ردیف
        </Button>
      </Card>

      {/* ویرایشگر نکات: هر نکته یک فیلد چندخطی با جابه‌جایی و حذف */}
      <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
        <Typography fontWeight={700} sx={{ mb: 0.5 }}>
          توضیحات زیر جدول (باکس آبی)
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          هر نکته یک ردیف. برای پررنگ کردن بخشی از متن آن را بین دو ستاره بگذارید: **متن**؛ برای زیرخط: __متن__.
        </Typography>
        <Stack spacing={1.5}>
          {notes.map((n, i) => (
            <Stack key={i} direction="row" spacing={1} alignItems="flex-start">
              <TextField size="small" fullWidth multiline value={n} onChange={(e) => setNotes(notes.map((x, j) => (j === i ? e.target.value : x)))} inputProps={{ maxLength: 500 }} />
              <Button size="small" onClick={() => moveNote(i, -1)} disabled={i === 0}>
                ▲
              </Button>
              <Button size="small" onClick={() => moveNote(i, 1)} disabled={i === notes.length - 1}>
                ▼
              </Button>
              <IconButton size="small" color="error" onClick={() => setNotes(notes.filter((_, j) => j !== i))}>
                <DeleteOutlineOutlinedIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}
        </Stack>
        <Button size="small" startIcon={<AddOutlinedIcon />} sx={{ mt: 1.5 }} onClick={() => setNotes([...notes, ""])}>
          افزودن نکته
        </Button>
      </Card>

      {/* پیش‌نمایش زنده با همان کامپوننتی که در فرم پرسنل استفاده می‌شود */}
      <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
        <Typography fontWeight={700} sx={{ mb: 1.5 }}>
          پیش‌نمایش (همان‌طور که پرسنل می‌بینند)
        </Typography>
        <InsuranceRateInfo rateTable={table} notes={notes} />
      </Card>

      <Box>
        <Button variant="contained" startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />} disabled={saving} onClick={() => save({ rate_table: table, notes }, "جدول نرخ و توضیحات ذخیره شد.")}>
          ذخیره جدول و توضیحات
        </Button>
      </Box>

      {/* متن پیش‌فرض اطلاعیه‌ی رد مدرک؛ در پنجره‌ی رد هر مورد هم قابل ویرایش است */}
      <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
        <Typography fontWeight={700} sx={{ mb: 0.5 }}>
          اطلاعیه‌ی رد مدرک
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          وقتی مدرک یک عضو رد می‌شود، این اطلاعیه (همراه نوتیف) برای ثبت‌نام‌کننده فرستاده می‌شود. عبارت{" "}
          <b>{MEMBER_PLACEHOLDER}</b> با نام و نام خانوادگی آن عضو جایگزین می‌شود. متن خالی یعنی متن پیش‌فرض.
        </Typography>
        <Stack spacing={2}>
          <TextField
            label="عنوان اطلاعیه"
            value={settings.reject_notice_title || ""}
            onChange={(e) => setSettings({ ...settings, reject_notice_title: e.target.value })}
            inputProps={{ maxLength: 255 }}
            fullWidth
          />
          <TextField
            label="متن اطلاعیه"
            value={settings.reject_notice_body || ""}
            onChange={(e) => setSettings({ ...settings, reject_notice_body: e.target.value })}
            inputProps={{ maxLength: 2000 }}
            multiline
            minRows={3}
            fullWidth
          />
        </Stack>
        <Button
          variant="contained"
          sx={{ mt: 2 }}
          startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />}
          disabled={saving}
          onClick={() =>
            save(
              { reject_notice_title: settings.reject_notice_title || "", reject_notice_body: settings.reject_notice_body || "" },
              "متن اطلاعیه‌ی رد مدرک ذخیره شد."
            )
          }
        >
          ذخیره متن اطلاعیه
        </Button>
      </Card>
    </Stack>
  );
}

// صفحه‌ی اصلی: انتخاب تب؛ تب تنظیمات فقط برای دارنده‌ی insurance.manage نمایش داده می‌شود
export default function InsuranceAdminPage() {
  const { user } = useAuth();
  const canManage = Boolean(user?.can_manage_insurance);
  const [tab, setTab] = useState("list");
  const tabs = [{ key: "list", label: "ثبت‌نام‌ها" }];
  if (canManage) tabs.push({ key: "settings", label: "تنظیمات" });

  return (
    <Box sx={{ maxWidth: 1200, mx: "auto" }}>
      <BackLink to="/" label="بازگشت" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        بیمه تکمیلی
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        ثبت‌نام‌های بیمه تکمیلی پرسنل و اعضای خانواده، خروجی Excel برای بیمه‌گر و تنظیمات فرم.
      </Typography>
      <PillTabs value={tab} onChange={setTab} tabs={tabs} sx={{ mb: 2 }} />
      {tab === "list" ? <RegistrationsTab canManage={canManage} /> : <SettingsTab />}
    </Box>
  );
}
