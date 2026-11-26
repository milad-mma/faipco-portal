/**
 * صفحه‌ی فهرست فرم‌های ارزیابی عملکرد.
 * فرم‌ها را با سایت، نسخه و وضعیت نمایش می‌دهد و امکان ساخت فرم جدید، ساخت نسخه‌ی جدید (کپی)،
 * حذف فرم پیش‌نویس و رفتن به فرم‌ساز را فراهم می‌کند.
 */
import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
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
import ContentCopyOutlinedIcon from "@mui/icons-material/ContentCopyOutlined";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import HelpOutlineOutlinedIcon from "@mui/icons-material/HelpOutlineOutlined";
import { useNavigate } from "react-router-dom";
import { fetchSites } from "../api/sites";
import {
  createEvaluationForm,
  importEvaluationForm,
  deleteEvaluationForm,
  duplicateEvaluationForm,
  fetchEvaluationForms,
} from "../api/evaluationForms";

const templates = [
  ["single_choice", "انتخاب یک گزینه"], ["multiple_choice", "انتخاب چند گزینه"],
  ["rating", "امتیازی"], ["yes_no", "بله یا خیر"], ["text", "پاسخ متنی"],
  ["number", "پاسخ عددی"], ["date", "پاسخ تاریخی"],
];

const STATUS_LABELS = { draft: "پیش‌نویس", active: "فعال", inactive: "غیرفعال", archived: "بایگانی‌شده" };  // برچسب فارسی وضعیت فرم
const STATUS_COLORS = { draft: "default", active: "success", inactive: "warning", archived: "default" };  // رنگ Chip هر وضعیت فرم

/**
 * دیالوگ ساخت فرم ارزیابی جدید (سایت اختیاری، عنوان، توضیحات).
 * ورودی: open، onClose، onCreated و فهرست سایت‌ها؛ پس از ساخت به فرم‌ساز فرم جدید می‌رود.
 */
function NewFormDialog({ open, onClose, onCreated, sites, excel }) {
  const [siteId, setSiteId] = useState("");  // رشته‌ی خالی = فرم برای همه‌ی سایت‌ها
  const [files, setFiles] = useState([]);
  const [template, setTemplate] = useState(templates[0][0]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const navigate = useNavigate();

  // فرم را می‌سازد (site_id خالی → null)، فهرست را تازه می‌کند و به صفحه‌ی فرم‌ساز می‌رود
  async function handleCreate() {
    setError("");
    setIsSaving(true);
    try {
      const payload = {
        site_id: siteId === "" ? null : siteId,
        title,
        description: description || null,
      };
      const form = excel ? await importEvaluationForm(payload, files) : await createEvaluationForm(payload);
      onCreated();
      onClose();
      navigate(`/performance/forms/${form.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "ساخت فرم با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onClose={isSaving ? undefined : onClose} fullWidth maxWidth="sm">
      <DialogTitle>{excel ? "ساخت فرم از اکسل" : "فرم ارزیابی جدید"}</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <TextField
          select
          label="سایت (اختیاری - خالی یعنی همه سایت‌ها)"
          value={siteId}
          onChange={(e) => setSiteId(e.target.value)}
        >
          <MenuItem value="">همه سایت‌ها</MenuItem>
          {sites.map((site) => (
            <MenuItem key={site.id} value={site.id}>
              {site.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="عنوان فرم"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="مثلاً فرم ارزیابی عملکرد پرسنل"
        />
        <TextField
          label="توضیحات (اختیاری)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          multiline
          minRows={2}
        />
        {excel && (
          <>
            <TextField select label="۱. چه نوع سؤالی دارید؟" value={template} onChange={(e) => setTemplate(e.target.value)}>
              {templates.map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}
            </TextField>
            <Button component="a" variant="outlined" href={import.meta.env.BASE_URL + "templates/evaluation-" + template + ".xlsx?v=category-first"}
              download={"نمونه " + templates.find(([key]) => key === template)[1] + ".xlsx"}>
              دانلود نمونه {templates.find(([key]) => key === template)[1]}
            </Button>
            <Typography variant="body2">۲. ردیف‌های نمونه را با سؤال‌های خود جایگزین کنید و نمونه‌های اضافی را حذف کنید. در هر ردیف ابتدا نام دسته، سپس امتیاز دسته و بعد سؤال را بنویسید. مجموع امتیاز دسته‌های فرم برای فعال‌سازی باید ۱۰۰ باشد.</Typography>
            <Button component="label" variant="outlined" disabled={isSaving}>
              {files.length ? "افزودن فایل دیگر به همین فرم" : "۳. انتخاب فایل تکمیل‌شده"}
              <input hidden multiple type="file" accept=".xlsx" onChange={(e) => {
                const selected = Array.from(e.target.files || []);
                e.target.value = "";
                setFiles((current) => [...current.filter(f => !selected.some(s => s.name === f.name)), ...selected]);
                setError("");
              }} />
            </Button>
            {files.map(f => <Chip key={f.name} label={f.name} disabled={isSaving}
              onDelete={() => setFiles(current => current.filter(item => item !== f))} />)}
            {files.length > 7 && <Alert severity="error">برای هر فرم حداکثر هفت فایل انتخاب کنید.</Alert>}
          </>
        )}
        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSaving}>
          انصراف
        </Button>
        <Button variant="contained" onClick={handleCreate} disabled={isSaving || !title.trim() || (excel && (!files.length || files.length > 7))}>
          {isSaving ? "در حال ساخت..." : "ساخت و ادامه به فرم‌ساز"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/**
 * صفحه‌ی اصلی فهرست فرم‌های ارزیابی.
 */
export default function EvaluationFormsPage() {
  const [sites, setSites] = useState([]);
  const [forms, setForms] = useState([]);
  const [error, setError] = useState("");
  const [dialogMode, setDialogMode] = useState(null);  // باز بودن دیالوگ فرم جدید
  const navigate = useNavigate();

  // دریافت فهرست سایت‌ها برای نمایش نام سایت و انتخاب در دیالوگ
  useEffect(() => {
    fetchSites().then(setSites);
  }, []);

  // فهرست فرم‌های ارزیابی را از سرور می‌گیرد
  function loadForms() {
    setError("");
    fetchEvaluationForms()
      .then(setForms)
      .catch((err) => setError(err.response?.data?.detail || "دریافت فرم‌های ارزیابی با خطا مواجه شد."));
  }

  // بارگذاری اولیه‌ی فرم‌ها
  useEffect(loadForms, []);

  // نام سایت را از روی شناسه برمی‌گرداند؛ null یعنی «همه سایت‌ها»
  function siteName(siteId) {
    if (siteId === null) return "همه سایت‌ها";
    return sites.find((s) => s.id === siteId)?.name || "—";
  }

  // یک نسخه‌ی قابل‌ویرایش از فرم می‌سازد و به فرم‌ساز آن می‌رود
  async function handleDuplicate(form) {
    try {
      const newForm = await duplicateEvaluationForm(form.id);
      loadForms();
      navigate(`/performance/forms/${newForm.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "ساخت نسخه جدید با خطا مواجه شد.");
    }
  }

  // فرم (فقط پیش‌نویس) را حذف و فهرست را تازه می‌کند
  async function handleDelete(form) {
    try {
      await deleteEvaluationForm(form.id);
      loadForms();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف فرم با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      {/* سربرگ: عنوان صفحه و دکمه‌ی فرم جدید */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>
          فرم‌های ارزیابی
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" onClick={() => setDialogMode("excel")}>ساخت از اکسل</Button>
          <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={() => setDialogMode("manual")}>
            فرم جدید
          </Button>
        </Stack>
      </Stack>

      {/* راهنمای کار با فرم‌های ارزیابی */}
      <Accordion variant="outlined" sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
          <Stack direction="row" spacing={1} alignItems="center">
            <HelpOutlineOutlinedIcon fontSize="small" color="primary" />
            <Typography fontWeight={700}>راهنما - فرم ارزیابی چیه؟</Typography>
          </Stack>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" sx={{ mb: 1.5 }}>
            <b>فرم ارزیابی</b> یعنی مجموعه سوال‌هایی که می‌خواید از هر ارزیاب بپرسید - مثلاً «فرم
            ارزیابی سالانه پرسنل». با «فرم جدید» سؤال‌ها را در فرم‌ساز اضافه کنید یا با «ساخت از اکسل» دسته‌بندی‌ها، سؤال‌ها و گزینه‌ها را از فایل نمونه وارد کنید.
          </Typography>
          <Stack component="ol" sx={{ pl: 2.5, m: 0 }} spacing={0.75}>
            <Typography component="li" variant="body2">
              دکمه «فرم جدید» رو بزنید، فقط یه اسم کافیه (مثلاً «فرم ارزیابی عملکرد پرسنل»).
            </Typography>
            <Typography component="li" variant="body2">
              خودکار می‌رید به فرم‌ساز - اونجا دسته‌بندی و سوال اضافه می‌کنید (راهنمای کامل همون‌جا
              هست).
            </Typography>
            <Typography component="li" variant="body2">
              تا وقتی فرم رو «فعال» نکردید، آزادانه می‌تونید تغییرش بدید یا حذفش کنید.
            </Typography>
            <Typography component="li" variant="body2">
              بعد از فعال‌شدن، دیگه قابل‌ویرایش نیست (تا جواب‌های ثبت‌شده خراب نشه). اگه بعداً نیاز به
              تغییر داشتید، دکمه «نسخه جدید» یه کپی قابل‌ویرایش از همون فرم می‌سازه.
            </Typography>
            <Typography component="li" variant="body2">
              بعد از ساخت فرم، برید صفحه «دوره‌های ارزیابی» و همین فرم رو برای «تولید انتساب» انتخاب
              کنید.
            </Typography>
          </Stack>
        </AccordionDetails>
      </Accordion>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* جدول فرم‌ها با عملیات ویرایش، نسخه‌ی جدید و حذف */}
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>عنوان</TableCell>
              <TableCell>سایت</TableCell>
              <TableCell>نسخه</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {forms.map((form) => (
              <TableRow key={form.id} hover sx={{ cursor: "pointer" }}>
                <TableCell onClick={() => navigate(`/performance/forms/${form.id}`)}>{form.title}</TableCell>
                <TableCell>{siteName(form.site_id)}</TableCell>
                <TableCell>نسخه {form.version}</TableCell>
                <TableCell>
                  <Chip size="small" color={STATUS_COLORS[form.status]} label={STATUS_LABELS[form.status]} />
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1}>
                    <Button size="small" onClick={() => navigate(`/performance/forms/${form.id}`)}>
                      ویرایش
                    </Button>
                    <Button
                      size="small"
                      startIcon={<ContentCopyOutlinedIcon fontSize="small" />}
                      onClick={() => handleDuplicate(form)}
                    >
                      نسخه جدید
                    </Button>
                    {form.status === "draft" && (
                      <Button size="small" color="error" onClick={() => handleDelete(form)}>
                        حذف
                      </Button>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* دیالوگ ساخت فرم جدید */}
      {dialogMode && <NewFormDialog open excel={dialogMode === "excel"} onClose={() => setDialogMode(null)} onCreated={loadForms} sites={sites} />}
    </Box>
  );
}
