/**
 * صفحه‌ی مدیریت دوره‌های ارزیابی عملکرد.
 * فهرست دوره‌ها را با سایت، بازه، وضعیت و تعداد ارزیابی‌های منتشرشده نشان می‌دهد و امکان ساخت/ویرایش/تمدید،
 * تغییر وضعیت، فعال/غیرفعال‌سازی، حذف (با تأیید عنوان)، مشاهده و حذف ارزیابی‌های منتشرشده و تولید انتساب را فراهم می‌کند.
 */
import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Radio,
  RadioGroup,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import HelpOutlineOutlinedIcon from "@mui/icons-material/HelpOutlineOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { fetchSites } from "../api/sites";
import { fetchEvaluationForms } from "../api/evaluationForms";
import {
  fetchAssignmentScopeOptions,
  generateEvaluationAssignments,
  searchAssignmentScopePeople,
} from "../api/evaluationProcess";
import InlineTitleEdit from "../components/InlineTitleEdit";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";
import {
  createEvaluationPeriod,
  fetchEvaluationPeriods,
  updateEvaluationPeriod,
  updateEvaluationPeriodStatus,
  updateEvaluationPeriodTitle,
  deleteEvaluationPeriod,
  deletePublishedEvaluation,
  fetchPublishedEvaluations,
  setEvaluationPeriodDisabled,
} from "../api/evaluationPeriods";
import ModuleNotificationTemplates from "../components/ModuleNotificationTemplates";

// برچسب فارسی وضعیت دوره
const STATUS_LABELS = {
  draft: "پیش‌نویس",
  scheduled: "زمان‌بندی‌شده",
  active: "فعال",
  closed: "بسته‌شده",
  archived: "بایگانی‌شده",
};

// رنگ Chip هر وضعیت دوره
const STATUS_COLORS = {
  draft: "default",
  scheduled: "info",
  active: "success",
  closed: "warning",
  archived: "default",
};

const EMPTY_FORM = { site_id: "", title: "", description: "", start_date: null, end_date: null };  // مقادیر اولیه‌ی فرم دیالوگ دوره

// مقدار اولیه‌ی فرم: داده‌ی دوره‌ی در حال ویرایش یا مقادیر پیش‌فرض (تاریخ امروز)
function initialPeriodForm(editingPeriod) {
  if (!editingPeriod) return { ...EMPTY_FORM, start_date: new Date(), end_date: new Date() };
  return {
    site_id: editingPeriod.site_id ?? "",
    title: editingPeriod.title,
    description: editingPeriod.description || "",
    start_date: new Date(editingPeriod.start_date),
    end_date: new Date(editingPeriod.end_date),
  };
}

/**
 * دیالوگ ساخت یا ویرایش دوره (سایت، عنوان، توضیحات، تاریخ شروع و پایان).
 * ورودی: open، onClose، onSaved، فهرست سایت‌ها و editingPeriod (null = دوره‌ی جدید).
 * فرم با هر باز شدن (و برای هر دوره) از نو mount می‌شود تا مقدار اولیه همان لحظه‌ی اول درست باشد؛ قبلاً فرم
 * یک رندر با داده‌ی قبلی mount می‌شد و انتخابگر تاریخ همان داده‌ی کهنه را برمی‌گرداند (باگ «بار اول خالی»).
 */
function PeriodDialog({ open, onClose, onSaved, sites, editingPeriod }) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      {open && (
        <PeriodDialogBody
          key={editingPeriod?.id ?? "new"}
          onClose={onClose}
          onSaved={onSaved}
          sites={sites}
          editingPeriod={editingPeriod}
        />
      )}
    </Dialog>
  );
}

function PeriodDialogBody({ onClose, onSaved, sites, editingPeriod }) {
  const [form, setForm] = useState(() => initialPeriodForm(editingPeriod));
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  // به‌روزرسانی یک فیلد با شکل تابعی (بدون وابستگی به form کهنه در closure)
  const setField = (name, value) => setForm((prev) => ({ ...prev, [name]: value }));

  // payload دوره را می‌سازد (site_id خالی → null، تاریخ‌ها به ISO) و دوره را ایجاد یا ویرایش می‌کند
  async function handleSave() {
    setError("");
    setIsSaving(true);
    try {
      const payload = {
        site_id: form.site_id === "" ? null : form.site_id,
        title: form.title,
        description: form.description || null,
        start_date: form.start_date.toISOString(),
        end_date: form.end_date.toISOString(),
      };
      if (editingPeriod) {
        await updateEvaluationPeriod(editingPeriod.id, payload);
      } else {
        await createEvaluationPeriod(payload);
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره دوره ارزیابی با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <>
      <DialogTitle>{editingPeriod ? "ویرایش دوره ارزیابی" : "دوره ارزیابی جدید"}</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <TextField
          select
          label="سایت (اختیاری - خالی یعنی همه سایت‌ها)"
          value={form.site_id}
          onChange={(e) => setField("site_id", e.target.value)}
        >
          <MenuItem value="">همه سایت‌ها</MenuItem>
          {sites.map((site) => (
            <MenuItem key={site.id} value={site.id}>
              {site.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="عنوان دوره"
          value={form.title}
          onChange={(e) => setField("title", e.target.value)}
          placeholder="مثلاً ارزیابی عملکرد نیمه اول ۱۴۰۵"
        />
        <TextField
          label="توضیحات (اختیاری)"
          value={form.description}
          onChange={(e) => setField("description", e.target.value)}
          multiline
          minRows={2}
        />
        {form.start_date && (
          <JalaliDateTimePicker
            label="تاریخ و ساعت شروع"
            value={form.start_date}
            onChange={(d) => setField("start_date", d)}
          />
        )}
        {form.end_date && (
          <JalaliDateTimePicker
            label="تاریخ و ساعت پایان"
            value={form.end_date}
            onChange={(d) => setField("end_date", d)}
          />
        )}
        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSaving}>
          انصراف
        </Button>
        <Button variant="contained" onClick={handleSave} disabled={isSaving || !form.title.trim()}>
          {isSaving ? "در حال ذخیره..." : "ذخیره"}
        </Button>
      </DialogActions>
    </>
  );
}

const EVALUATION_STATUS_LABELS = { not_started: "شروع‌نشده", draft: "در حال انجام", submitted: "ثبت‌شده" };  // برچسب فارسی وضعیت هر ارزیابی منتشرشده
const EVALUATION_STATUS_COLORS = { not_started: "default", draft: "warning", submitted: "success" };  // رنگ Chip وضعیت ارزیابی

/**
 * دیالوگ فهرست ارزیابی‌های منتشرشده‌ی یک دوره با امکان حذف تک‌تک آن‌ها.
 * ورودی: دوره، onClose و onChanged (برای تازه‌سازی شمارنده‌های جدول دوره‌ها).
 */
function PublishedEvaluationsDialog({ period, onClose, onChanged }) {
  const [items, setItems] = useState(null);  // فهرست ارزیابی‌ها؛ null = هنوز دریافت نشده
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);  // assignment_id ارزیابی در حال حذف

  // فهرست ارزیابی‌های منتشرشده‌ی دوره را از سرور می‌گیرد
  function load() {
    setError("");
    fetchPublishedEvaluations(period.id)
      .then(setItems)
      .catch((err) => setError(err.response?.data?.detail || "دریافت ارزیابی‌ها با خطا مواجه شد."));
  }

  // بارگذاری فهرست با تغییر دوره
  useEffect(load, [period.id]);

  // پس از تأیید کاربر، ارزیابی (با پاسخ‌ها و نتیجه) را حذف و فهرست و جدول دوره‌ها را تازه می‌کند
  async function handleDelete(item) {
    if (
      !window.confirm(
        `ارزیابی «${item.target_name}» توسط «${item.evaluator_name}» همراه پاسخ‌ها و نتیجه‌اش برای همیشه حذف شود؟`
      )
    )
      return;
    setDeletingId(item.assignment_id);
    try {
      await deletePublishedEvaluation(period.id, item.assignment_id);
      load();
      onChanged();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف ارزیابی با خطا مواجه شد.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>ارزیابی‌های منتشرشده «{period.title}»</DialogTitle>
      <DialogContent>
        {period.is_disabled && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            این دوره غیرفعال است - ارزیابی‌هایش برای ارزیاب‌ها و پرسنل نمایش داده نمی‌شود.
          </Alert>
        )}
        {period.incomplete_closed && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            ارزیابی‌های انجام‌نشده‌ی این دوره بسته شده است؛ نتایج ثبت‌شده برای پرسنل نمایش داده می‌شود.
          </Alert>
        )}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        {/* حالت‌های فهرست: در حال بارگذاری، خالی، یا جدول ارزیابی‌ها */}
        {items === null ? null : items.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            هنوز هیچ ارزیابی‌ای برای این دوره منتشر نشده (تولید انتساب انجام نشده).
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ارزیاب</TableCell>
                  <TableCell>ارزیابی‌شونده</TableCell>
                  <TableCell>فرم</TableCell>
                  <TableCell>وضعیت</TableCell>
                  <TableCell>امتیاز</TableCell>
                  <TableCell>حذف</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.assignment_id}>
                    <TableCell>{item.evaluator_name}</TableCell>
                    <TableCell>{item.target_name}</TableCell>
                    <TableCell>{item.form_title || "—"}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        color={EVALUATION_STATUS_COLORS[item.status]}
                        label={EVALUATION_STATUS_LABELS[item.status] || item.status}
                      />
                    </TableCell>
                    <TableCell>{item.total_score != null ? Number(item.total_score).toFixed(1) : "—"}</TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        color="error"
                        disabled={deletingId === item.assignment_id}
                        onClick={() => handleDelete(item)}
                        aria-label="حذف"
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

/**
 * دیالوگ حذف قطعی دوره‌ای که ارزیابی منتشرشده دارد یا پیش‌نویس نیست.
 * ورودی: دوره، onClose و onDeleted؛ دکمه‌ی حذف فقط با تایپ دقیق عنوان دوره فعال می‌شود.
 */
/**
 * دیالوگ غیرفعال کردن دوره با دو حالت: غیرفعال کامل، یا فقط بستن ارزیابی‌های انجام‌نشده (نتایج ثبت‌شده می‌ماند).
 */
function DisablePeriodDialog({ period, onClose, onDone }) {
  const [mode, setMode] = useState("full");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setBusy(true);
    setError("");
    try {
      await setEvaluationPeriodDisabled(period.id, true, mode);
      onDone(mode);
    } catch (err) {
      setError(err.response?.data?.detail || "تغییر وضعیت دسترسی با خطا مواجه شد.");
    } finally {
      setBusy(false);
    }
  }

  const option = (value, title, text) => (
    <Box
      onClick={() => setMode(value)}
      sx={{
        p: 1.5,
        borderRadius: 2,
        cursor: "pointer",
        border: 1.5,
        borderColor: mode === value ? "primary.main" : "divider",
        bgcolor: mode === value ? "action.selected" : "transparent",
      }}
    >
      <FormControlLabel
        value={value}
        control={<Radio size="small" />}
        label={<Typography fontWeight={700}>{title}</Typography>}
      />
      <Typography variant="body2" color="text.secondary" sx={{ pr: 4 }}>
        {text}
      </Typography>
    </Box>
  );

  return (
    <Dialog open onClose={busy ? undefined : onClose} fullWidth maxWidth="sm">
      <DialogTitle>غیرفعال کردن دوره‌ی «{period.title}»</DialogTitle>
      <DialogContent>
        <RadioGroup value={mode} onChange={(e) => setMode(e.target.value)} sx={{ gap: 1.5 }}>
          {option(
            "full",
            "غیرفعال کردن کامل",
            "همه‌ی ارزیابی‌های این دوره از دسترس خارج می‌شود: ارزیاب‌ها نه فهرست ارزیابی‌ها را می‌بینند و نه می‌توانند ارزیابی کنند، و پرسنل هم نتیجه‌ای نمی‌بینند. هر زمان بخواهید می‌توانید دوره را دوباره فعال کنید."
          )}
          {option(
            "incomplete",
            "بستن ارزیابی‌های انجام‌نشده",
            "فقط ارزیابی‌هایی که مدیر یا سرپرست هنوز ثبت نهایی نکرده از دسترس ارزیاب‌ها خارج می‌شود. پرسنلی که ارزیابی شده‌اند نتیجه‌ی خود را مثل قبل می‌بینند و پرسنلی که ارزیابی نشده‌اند به جای نتیجه پیامی می‌بینند که ارزیابی آن‌ها انجام نشده است. این کار هم قابل برگشت است."
          )}
        </RadioGroup>
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>انصراف</Button>
        <Button variant="contained" color="warning" onClick={submit} disabled={busy}>
          {busy ? "در حال اعمال..." : "تأیید و غیرفعال کردن"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function DeletePeriodDialog({ period, onClose, onDeleted }) {
  const [confirmTitle, setConfirmTitle] = useState("");
  const [error, setError] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  // دوره را با ارسال عنوان تأییدشده (confirm_title) حذف می‌کند
  async function handleDelete() {
    setError("");
    setIsDeleting(true);
    try {
      await deleteEvaluationPeriod(period.id, confirmTitle);
      onDeleted();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف دوره ارزیابی با خطا مواجه شد.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <Dialog open onClose={isDeleting ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>حذف قطعی دوره ارزیابی</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <Alert severity="error">
          دوره «{period.title}» و همه {period.assignments_total} ارزیابی منتشرشده‌اش (همراه پاسخ‌ها و نتایج)
          برای همیشه حذف می‌شوند و قابل‌برگشت نیستند. اگر فقط می‌خواهید در دسترس پرسنل نباشد، «غیرفعال» کنید.
        </Alert>
        <TextField
          label="برای تأیید، عنوان دوره را دقیقاً وارد کنید"
          value={confirmTitle}
          onChange={(e) => setConfirmTitle(e.target.value)}
          placeholder={period.title}
        />
        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isDeleting}>
          انصراف
        </Button>
        <Button
          color="error"
          variant="contained"
          onClick={handleDelete}
          disabled={isDeleting || confirmTitle.trim() !== period.title.trim()}
        >
          {isDeleting ? "در حال حذف..." : "حذف قطعی"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/**
 * دیالوگ تولید انتساب‌های ارزیابی برای یک دوره بر اساس ساختار ارزیابی و یک فرم فعال.
 * ورودی: open، onClose و دوره؛ خروجی سرور (تعداد ساخته‌شده و مجموع) در پیام موفقیت نمایش داده می‌شود.
 */
function GenerateAssignmentsDialog({ open, onClose, period }) {
  const [forms, setForms] = useState([]);
  const [formId, setFormId] = useState("");
  const [scope, setScope] = useState("site");
  const [departments, setDepartments] = useState([]);
  const [selectedDepts, setSelectedDepts] = useState([]);
  const [people, setPeople] = useState([]);
  const [peopleQuery, setPeopleQuery] = useState("");
  const [selectedPeople, setSelectedPeople] = useState([]);
  const [result, setResult] = useState(null);  // { created_count, removed_count, total_assignments, targets_count }
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // با باز شدن دیالوگ، وضعیت قبلی پاک و فرم‌ها و واحدهای سایت دوره دریافت می‌شوند
  useEffect(() => {
    if (!open) return;
    setResult(null);
    setError("");
    setFormId("");
    setScope("site");
    setSelectedDepts([]);
    setSelectedPeople([]);
    fetchEvaluationForms(period?.site_id).then(setForms);
    fetchAssignmentScopeOptions(period.id)
      .then((d) => setDepartments(d.departments || []))
      .catch(() => setDepartments([]));
  }, [open, period]);

  // جستجوی افراد (دامنه‌ی «افراد خاص»)
  useEffect(() => {
    if (!open || scope !== "employees") return;
    let alive = true;
    const t = setTimeout(() => {
      searchAssignmentScopePeople(period.id, peopleQuery)
        .then((d) => alive && setPeople(d))
        .catch(() => alive && setPeople([]));
    }, 300);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [open, scope, peopleQuery, period]);

  const needsDepts = scope === "departments";
  const needsPeople = scope === "employees";
  const ready =
    formId && (!needsDepts || selectedDepts.length > 0) && (!needsPeople || selectedPeople.length > 0);

  async function handleGenerate() {
    setError("");
    setIsSaving(true);
    try {
      const data = await generateEvaluationAssignments(
        period.id,
        formId,
        scope,
        scope === "departments" || scope === "supervisors" ? selectedDepts.map((d) => d.id) : [],
        scope === "employees" ? selectedPeople.map((p) => p.id) : []
      );
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || "تولید انتساب با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  const deptOptions = scope === "supervisors" ? departments.filter((d) => d.has_supervisor) : departments;

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>تولید انتساب ارزیابی برای «{period?.title}»</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <Typography variant="body2" color="text.secondary">
          انتخاب کنید <b>چه کسانی ارزیابی شوند</b>. ارزیاب هر نفر از ساختار ارزیابی تعیین می‌شود (سرپرست واحد، مدیر یا
          سرشیفت)؛ مثلاً سرپرست هر واحد را مدیری ارزیابی می‌کند که در ساختار برای او تعیین شده است.
        </Typography>
        <TextField select label="ارزیابی‌شونده‌ها" value={scope} onChange={(e) => { setScope(e.target.value); setResult(null); }}>
          <MenuItem value="site">همه‌ی پرسنل سایت</MenuItem>
          <MenuItem value="departments">پرسنل واحدهای انتخابی</MenuItem>
          <MenuItem value="supervisors">سرپرستان واحدها</MenuItem>
          <MenuItem value="employees">افراد خاص</MenuItem>
        </TextField>
        {(scope === "departments" || scope === "supervisors") && (
          <Autocomplete
            multiple
            options={deptOptions}
            value={selectedDepts}
            onChange={(_, v) => setSelectedDepts(v)}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            getOptionLabel={(o) => o.name}
            noOptionsText="واحدی پیدا نشد"
            renderInput={(params) => (
              <TextField
                {...params}
                label={scope === "supervisors" ? "واحدها (خالی = سرپرستان همه‌ی واحدها)" : "واحدها"}
              />
            )}
          />
        )}
        {needsPeople && (
          <Autocomplete
            multiple
            options={people}
            value={selectedPeople}
            filterOptions={(x) => x}
            onChange={(_, v) => setSelectedPeople(v)}
            onInputChange={(_, v, reason) => reason === "input" && setPeopleQuery(v)}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            getOptionLabel={(o) => o.name}
            noOptionsText="کسی پیدا نشد"
            renderOption={(props, o) => (
              <li {...props} key={o.id}>
                <Box>
                  <Typography variant="body2">{o.name}</Typography>
                  <Typography variant="caption" color="text.secondary">{o.department || "—"}</Typography>
                </Box>
              </li>
            )}
            renderInput={(params) => <TextField {...params} label="افراد (جستجو با نام یا واحد)" />}
          />
        )}
        <TextField select label="فرم ارزیابی" value={formId} onChange={(e) => setFormId(e.target.value)}>
          {forms
            .filter((f) => f.status === "active")
            .map((form) => (
              <MenuItem key={form.id} value={form.id}>
                {form.title} (نسخه {form.version})
              </MenuItem>
            ))}
        </TextField>
        <Alert severity="info">
          اجرای دوباره چیزی را تکراری نمی‌سازد و فقط به همین گروه دست می‌زند. اگر کسی از این گروه قبلاً با فرم دیگری
          انتساب گرفته و ارزیابی‌اش هنوز شروع نشده، انتسابش به این فرم تغییر می‌کند. ارزیابی شروع‌شده یا ثبت‌شده هرگز
          حذف نمی‌شود. برای چند فرم: اول «همه‌ی پرسنل سایت» را با فرم عمومی بسازید، بعد گروه‌های خاص را با فرم خودشان.
        </Alert>
        {result && (
          <Alert severity="success">
            {result.targets_count} نفر در این گروه انتساب دارند — {result.created_count} انتساب جدید ساخته شد
            {result.removed_count ? ` و ${result.removed_count} انتساب قبلی حذف/جابه‌جا شد` : ""}. مجموع انتساب‌های این
            فرم در دوره: {result.total_assignments}
          </Alert>
        )}
        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
        <Button variant="contained" onClick={handleGenerate} disabled={isSaving || !ready}>
          {isSaving ? "در حال تولید..." : "تولید انتساب"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/**
 * صفحه‌ی اصلی دوره‌های ارزیابی.
 */
export default function EvaluationPeriodsPage() {
  const [sites, setSites] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPeriod, setEditingPeriod] = useState(null);  // دوره‌ی در حال ویرایش؛ null = دوره‌ی جدید
  const [generateDialogPeriod, setGenerateDialogPeriod] = useState(null);  // دوره‌ی دیالوگ تولید انتساب؛ null = بسته
  const [publishedPeriod, setPublishedPeriod] = useState(null);  // دوره‌ی دیالوگ ارزیابی‌های منتشرشده؛ null = بسته
  const [deletingPeriod, setDeletingPeriod] = useState(null);  // دوره‌ی دیالوگ حذف قطعی؛ null = بسته
  const [disablingPeriod, setDisablingPeriod] = useState(null);  // دوره‌ی دیالوگ غیرفعال کردن؛ null = بسته
  const [toast, setToast] = useState("");  // پیام Snackbar موفقیت

  // دریافت فهرست سایت‌ها برای نمایش نام سایت و انتخاب در دیالوگ
  useEffect(() => {
    fetchSites().then(setSites);
  }, []);

  // فهرست دوره‌های ارزیابی را از سرور می‌گیرد
  function loadPeriods() {
    setError("");
    fetchEvaluationPeriods()
      .then(setPeriods)
      .catch((err) => setError(err.response?.data?.detail || "دریافت دوره‌های ارزیابی با خطا مواجه شد."));
  }

  // بارگذاری اولیه‌ی دوره‌ها
  useEffect(loadPeriods, []);

  // نام سایت را از روی شناسه برمی‌گرداند؛ null یعنی «همه سایت‌ها»
  function siteName(siteId) {
    if (siteId === null) return "همه سایت‌ها";
    return sites.find((s) => s.id === siteId)?.name || "—";
  }

  // وضعیت دوره را تغییر می‌دهد و فهرست را تازه می‌کند
  async function handleStatusChange(period, status) {
    try {
      await updateEvaluationPeriodStatus(period.id, status);
      loadPeriods();
    } catch (err) {
      setError(err.response?.data?.detail || "تغییر وضعیت با خطا مواجه شد.");
    }
  }

  // حذف دوره: دوره‌ی پیش‌نویس بدون ارزیابی با confirm ساده، بقیه با دیالوگ تأیید عنوان
  async function handleDelete(period) {
    // دوره‌ای که ارزیابی منتشرشده دارد یا دیگر پیش‌نویس نیست: تأیید با تایپ عنوان
    if (period.assignments_total > 0 || period.status !== "draft") {
      setDeletingPeriod(period);
      return;
    }
    if (!window.confirm(`دوره «${period.title}» حذف شود؟`)) return;
    try {
      await deleteEvaluationPeriod(period.id);
      setToast("دوره حذف شد.");
      loadPeriods();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف دوره ارزیابی با خطا مواجه شد.");
    }
  }

  // دسترسی ارزیاب‌ها و پرسنل به ارزیابی‌های دوره را قطع/وصل می‌کند (غیرفعال‌سازی با تأیید)
  async function handleToggleDisabled(period) {
    const inactive = period.is_disabled || period.incomplete_closed;
    if (!inactive) {
      setDisablingPeriod(period); // انتخاب حالت در دیالوگ
      return;
    }
    try {
      await setEvaluationPeriodDisabled(period.id, false);
      setToast("دوره دوباره فعال شد.");
      loadPeriods();
    } catch (err) {
      setError(err.response?.data?.detail || "تغییر وضعیت دسترسی با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      {/* سربرگ: عنوان صفحه و دکمه‌ی دوره‌ی جدید */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>
          دوره‌های ارزیابی
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddOutlinedIcon />}
          onClick={() => {
            setEditingPeriod(null);
            setDialogOpen(true);
          }}
        >
          دوره جدید
        </Button>
      </Stack>

      {/* راهنمای مراحل کار با دوره‌ها */}
      <Accordion variant="outlined" sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
          <Stack direction="row" spacing={1} alignItems="center">
            <HelpOutlineOutlinedIcon fontSize="small" color="primary" />
            <Typography fontWeight={700}>راهنما - این صفحه برای چیه و چطور ازش استفاده کنم؟</Typography>
          </Stack>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" sx={{ mb: 1.5 }}>
            <b>دوره ارزیابی</b> یعنی یک بازه زمانی مشخص (مثلاً «سه ماه اول ۱۴۰۵») که می‌خواهید توی همون
            بازه، پرسنل ارزیابی بشن. خودِ دوره فقط یه اسم و یه تاریخ شروع/پایان داره - سوال‌ها و
            امتیازها جای دیگه‌ای (فرم‌های ارزیابی) تعریف می‌شن.
          </Typography>
          <Typography variant="body2" fontWeight={700} sx={{ mb: 1 }}>
            مراحل کامل کار (به ترتیب):
          </Typography>
          <Stack component="ol" sx={{ pl: 2.5, m: 0 }} spacing={0.75}>
            <Typography component="li" variant="body2">
              یه دوره جدید بسازید (همین صفحه - دکمه «دوره جدید»).
            </Typography>
            <Typography component="li" variant="body2">
              برید صفحه «فرم‌های ارزیابی» و یه فرم بسازید (سوال‌هایی که می‌خواید پرسیده بشه رو اونجا
              تعریف می‌کنید - راهنمای کامل توی همون صفحه هست).
            </Typography>
            <Typography component="li" variant="body2">
              برگردید همینجا، کنار همین دوره‌ای که ساختید دکمه «تولید انتساب» رو بزنید و فرمی که ساختید
              رو انتخاب کنید. سیستم خودش، بر اساس ساختار سازمانی («ساختار ارزیابی» - سرپرست/مدیر
              سایت/سرشیفت)، مشخص می‌کنه کی باید کی رو ارزیابی کنه.
            </Typography>
            <Typography component="li" variant="body2">
              همین. از این به بعد، سرپرست‌ها و مدیرها از داشبورد خودشون (کارت «ارزیابی عملکرد») وارد
              می‌شن و ارزیابی پرسنل‌شون رو انجام می‌دن.
            </Typography>
          </Stack>
          <Typography variant="body2" sx={{ mt: 1.5 }}>
            <b>وضعیت‌های دوره:</b> زمان‌بندی‌شده/فعال/بسته‌شده خودکار با تاریخ‌ها عوض می‌شن. برای تمدید مهلت
            یک دوره بسته‌شده، «تمدید/ویرایش» رو بزنید و تاریخ پایان رو جلو ببرید - دوره خودش دوباره فعال
            می‌شه. «غیرفعال» ارزیابی‌های دوره رو از دسترس ارزیاب‌ها و پرسنل خارج می‌کنه (قابل برگشت)؛ «حذف»
            دوره رو با همه ارزیابی‌ها و نتایجش برای همیشه پاک می‌کنه. با زدن روی ستون «ارزیابی‌های منتشرشده»
            فهرست‌شون رو می‌بینید و می‌تونید تک‌تک حذف‌شون کنید.
          </Typography>
        </AccordionDetails>
      </Accordion>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* جدول دوره‌ها: عنوان قابل‌ویرایش، سایت، بازه، وضعیت، شمارنده‌ی ارزیابی‌ها و عملیات */}
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>عنوان</TableCell>
              <TableCell>سایت</TableCell>
              <TableCell>بازه</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>ارزیابی‌های منتشرشده</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {periods.map((period) => (
              <TableRow key={period.id} sx={period.is_disabled ? { opacity: 0.6 } : undefined}>
                <TableCell>
                  <InlineTitleEdit
                    title={period.title}
                    onSave={async (newTitle) => {
                      await updateEvaluationPeriodTitle(period.id, newTitle);
                      loadPeriods();
                    }}
                  />
                </TableCell>
                <TableCell>{siteName(period.site_id)}</TableCell>
                <TableCell>
                  {new Date(period.start_date).toLocaleDateString("fa-IR")} تا{" "}
                  {new Date(period.end_date).toLocaleDateString("fa-IR")}
                </TableCell>
                <TableCell>
                  <TextField
                    select
                    size="small"
                    value={period.status}
                    onChange={(e) => handleStatusChange(period, e.target.value)}
                    sx={{ minWidth: 150 }}
                  >
                    {Object.entries(STATUS_LABELS).map(([value, label]) => (
                      <MenuItem key={value} value={value}>
                        <Chip size="small" color={STATUS_COLORS[value]} label={label} />
                      </MenuItem>
                    ))}
                  </TextField>
                  {period.is_disabled && (
                    <Chip size="small" color="error" variant="outlined" label="غیرفعال" sx={{ mt: 0.5 }} />
                  )}
                  {period.incomplete_closed && (
                    <Chip
                      size="small"
                      color="warning"
                      variant="outlined"
                      label="ارزیابی‌های انجام‌نشده بسته شد"
                      sx={{ mt: 0.5 }}
                    />
                  )}
                </TableCell>
                <TableCell>
                  <Button size="small" onClick={() => setPublishedPeriod(period)}>
                    {period.assignments_completed} از {period.assignments_total} انجام‌شده
                  </Button>
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {period.status !== "archived" && (
                      <Button
                        size="small"
                        onClick={() => {
                          setEditingPeriod(period);
                          setDialogOpen(true);
                        }}
                      >
                        {period.status === "closed" ? "تمدید/ویرایش" : "ویرایش"}
                      </Button>
                    )}
                    {period.status !== "draft" && (
                      <Button
                        size="small"
                        color={period.is_disabled || period.incomplete_closed ? "success" : "warning"}
                        onClick={() => handleToggleDisabled(period)}
                      >
                        {period.is_disabled || period.incomplete_closed ? "فعال‌سازی" : "غیرفعال"}
                      </Button>
                    )}
                    <Button size="small" color="error" onClick={() => handleDelete(period)}>
                      حذف
                    </Button>
                    <Button size="small" variant="outlined" onClick={() => setGenerateDialogPeriod(period)}>
                      تولید انتساب
                    </Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* دیالوگ‌های صفحه: ساخت/ویرایش، تولید انتساب، ارزیابی‌های منتشرشده و حذف قطعی */}
      <PeriodDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSaved={loadPeriods}
        sites={sites}
        editingPeriod={editingPeriod}
      />

      <GenerateAssignmentsDialog
        open={generateDialogPeriod !== null}
        onClose={() => {
          setGenerateDialogPeriod(null);
          loadPeriods();
        }}
        period={generateDialogPeriod}
      />

      {publishedPeriod && (
        <PublishedEvaluationsDialog
          period={publishedPeriod}
          onClose={() => setPublishedPeriod(null)}
          onChanged={loadPeriods}
        />
      )}

      {disablingPeriod && (
        <DisablePeriodDialog
          period={disablingPeriod}
          onClose={() => setDisablingPeriod(null)}
          onDone={(mode) => {
            setDisablingPeriod(null);
            setToast(
              mode === "full"
                ? "دوره غیرفعال شد و دیگر در دسترس پرسنل نیست."
                : "ارزیابی‌های انجام‌نشده بسته شد؛ نتایج ثبت‌شده برای پرسنل در دسترس است."
            );
            loadPeriods();
          }}
        />
      )}

      {deletingPeriod && (
        <DeletePeriodDialog
          period={deletingPeriod}
          onClose={() => setDeletingPeriod(null)}
          onDeleted={() => {
            setDeletingPeriod(null);
            setToast("دوره و ارزیابی‌هایش حذف شدند.");
            loadPeriods();
          }}
        />
      )}

      {/* پیام موفقیت عملیات */}
      <Snackbar
        open={Boolean(toast)}
        autoHideDuration={4000}
        onClose={() => setToast("")}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity="success" variant="filled" onClose={() => setToast("")} sx={{ width: "100%" }}>
          {toast}
        </Alert>
      </Snackbar>
      <ModuleNotificationTemplates module="evaluation" title="متن اعلان‌های ارزیابی عملکرد" />
    </Box>
  );
}
