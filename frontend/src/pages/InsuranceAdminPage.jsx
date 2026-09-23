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
  updateInsuranceSettings,
} from "../api/insurance";

const GENDER_LABEL = { 1: "مرد", 2: "زن" };
const MARITAL_LABEL = { 2: "مجرد", 3: "متاهل" };
const RELATION_LABEL = { spouse: "همسر", son: "فرزند پسر", daughter: "فرزند دختر", father: "پدر", mother: "مادر" };
const faDate = (iso) => (iso ? new Date(iso).toLocaleDateString("fa-IR") : "—");

function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** جزئیات یک ثبت‌نام + اعضا + مدارک (بازسازی نمای جزئیات admin/index.php) */
function RegistrationDialog({ id, onClose, canManage, onDeleted }) {
  const [reg, setReg] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchInsuranceRegistration(id)
      .then(setReg)
      .catch((e) => setError(e.response?.data?.detail || "دریافت جزئیات با خطا مواجه شد."));
  }, [id]);

  async function openDoc(doc) {
    try {
      const blob = await downloadInsuranceDocument(doc.id);
      saveBlob(blob, doc.file_name);
    } catch {
      setError("دانلود مدرک با خطا مواجه شد.");
    }
  }

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
        {!reg ? (
          <CircularProgress size={24} />
        ) : (
          <>
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
                        <TableCell>
                          {m.document ? (
                            <Button size="small" startIcon={<DownloadOutlinedIcon />} onClick={() => openDoc(m.document)}>
                              دانلود
                            </Button>
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
    </Dialog>
  );
}

function RegistrationsTab({ canManage }) {
  const [siteId, setSiteId] = useState(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);
  const [exporting, setExporting] = useState(false);

  function load() {
    fetchInsuranceRegistrations({ search: query || undefined, site_id: siteId || undefined, page: page + 1, page_size: pageSize })
      .then(setData)
      .catch((e) => setError(e.response?.data?.detail || "دریافت فهرست با خطا مواجه شد."));
  }
  useEffect(load, [query, siteId, page, pageSize]);

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
        <Box sx={{ flex: 1 }} />
        <Button variant="contained" color="success" startIcon={exporting ? <CircularProgress size={16} color="inherit" /> : <DownloadOutlinedIcon />} onClick={handleExport} disabled={exporting}>
          خروجی Excel
        </Button>
      </Stack>
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
                <TableCell>تاریخ ثبت</TableCell>
                <TableCell align="center">عملیات</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={10} align="center" sx={{ color: "text.secondary", py: 4 }}>
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
          onDeleted={() => {
            setOpenId(null);
            load();
          }}
        />
      )}
    </Box>
  );
}

function SettingsTab() {
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchInsuranceSettings()
      .then(setSettings)
      .catch(() => setMessage({ severity: "error", text: "دریافت تنظیمات با خطا مواجه شد." }));
  }, []);

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
  const table = settings.rate_table;
  const setTable = (next) => setSettings({ ...settings, rate_table: next });
  const setRow = (i, key, value) => setTable({ ...table, rows: table.rows.map((r, j) => (j === i ? { ...r, [key]: value } : r)) });
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
    </Stack>
  );
}

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
