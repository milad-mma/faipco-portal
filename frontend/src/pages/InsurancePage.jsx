import { useEffect, useMemo, useRef, useState } from "react";
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
  LinearProgress,
  MenuItem,
  Radio,
  RadioGroup,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import BackLink from "../components/BackLink";
import InsuranceRateInfo from "../components/InsuranceRateInfo";
import { useAuth } from "../context/AuthContext";
import {
  deleteMyInsuranceDocument,
  fetchMyInsurance,
  saveMyInsurance,
  uploadInsuranceDocument,
} from "../api/insurance";

/**
 * صفحه‌ی فرم ثبت‌نام بیمه تکمیلی پرسنل (مسیر /insurance).
 * چهار بخش دارد: اطلاعات شخص اصلی، اطلاعات بانکی، اعضای خانواده، جدول نرخ.
 * اطلاعات هویتی پرسنل از سرور می‌آید و فقط نمایش داده می‌شود؛ بقیه‌ی فیلدها
 * قابل ویرایش‌اند. قبل از ارسال، اعتبارسنجی اولیه در همین صفحه انجام می‌شود و
 * اعتبارسنجی نهایی سمت سرور است. ثبت مجدد یعنی ویرایش ثبت‌نام قبلی.
 * اگر ثبت‌نام کاملی وجود داشته باشد صفحه در حالت «نمایش» (فقط‌خواندنی) باز می‌شود
 * و فرم فقط با دکمه‌ی «ویرایش ثبت نام» نمایش داده می‌شود. پیام نتیجه‌ی ثبت و
 * خطاهای فرم در پنجره‌ی دیالوگ نشان داده می‌شوند.
 */

// ترتیب نمایش دکمه‌های افزودن عضو و رنگ هر نوع عضو
const MEMBER_ORDER = ["spouse", "son", "daughter", "father", "mother"];
const MEMBER_BUTTON_COLOR = { spouse: "primary", son: "success", daughter: "info", father: "warning", mother: "error" };
// برچسب کدهای عددی جنسیت و تأهل (کدها همان مقادیر ذخیره‌شده در سرور هستند)
const GENDER_LABEL = { 1: "مرد", 2: "زن" };
const MARITAL_LABEL = { 2: "مجرد", 3: "متاهل" };
// تبدیل ارقام فارسی/عربی به انگلیسی
const toEn = (v) => String(v ?? "").replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d));
// فقط ارقام را نگه می‌دارد و به max کاراکتر محدود می‌کند
const digitsOnly = (v, max) => toEn(v).replace(/\D/g, "").slice(0, max);

// صحت کد ملی ایرانی را با الگوریتم رقم کنترل بررسی می‌کند (کد ۹ رقمی با صفر ابتدایی تکمیل می‌شود)
function validateNationalId(raw) {
  let id = toEn(raw).trim();
  if (id.length === 9) id = "0" + id;
  if (!/^\d{10}$/.test(id) || /^(\d)\1{9}$/.test(id)) return false; // غیر ۱۰ رقمی یا همه‌ی ارقام یکسان
  let sum = 0;
  for (let i = 0; i < 9; i++) sum += parseInt(id[i], 10) * (10 - i);
  const rem = sum % 11;
  const check = parseInt(id[9], 10);
  return rem < 2 ? check === rem : check === 11 - rem;
}
/**
 * پیام خطای قابل‌فهم برای آپلود مدرک: پیام سرور اگر متنی باشد، وگرنه بر اساس نوع خطا
 * (پایان زمان، قطع ارتباط، حجم زیاد در سرور، خطای سرور) و در نهایت پیام عمومی همراه کد وضعیت.
 */
function uploadErrorMessage(err) {
  const detail = err.response?.data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) return "فایل به‌درستی ارسال نشد؛ لطفاً دوباره انتخاب کنید.";
  if (err.code === "ECONNABORTED" || err.code === "ETIMEDOUT")
    return "ارسال فایل بیش از حد طول کشید؛ اتصال اینترنت را بررسی و دوباره تلاش کنید یا فایل کم‌حجم‌تری انتخاب کنید.";
  if (!err.response) return "ارتباط با سرور برقرار نشد؛ اتصال اینترنت را بررسی و دوباره تلاش کنید.";
  if (err.response.status === 413) return "حجم فایل برای سرور بیش از حد مجاز است.";
  if (err.response.status >= 500) return `خطای سرور هنگام ذخیره فایل (کد ${err.response.status})؛ لطفاً به واحد فناوری اطلاع دهید.`;
  return `آپلود فایل با خطا مواجه شد (کد ${err.response.status}).`;
}

// مدرک کفالت این عضو توسط مدیر رد شده و هنوز مدرک جدیدی جایگزین نشده است
const isDocRejected = (m) => Boolean(m.document_rejected_at) && !m.document;
const REJECTED_DOC_TEXT = "مدرک این عضو تأیید نشد؛ لطفاً ثبت‌نام را ویرایش و مدرک جدید آپلود کنید.";

// فقط قالب تاریخ شمسی «YYYY/MM/DD» را بررسی می‌کند (درستی روز/ماه سمت سرور)
const validateJalali = (d) => /^\d{4}\/\d{2}\/\d{2}$/.test(toEn(d).trim());

// نمایش یک مقدار فقط‌خواندنی با برچسب کوچک بالای آن؛ مقدار خالی به‌صورت «—»
function ReadOnlyField({ label, value }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography fontWeight={700} sx={{ minHeight: 24 }}>
        {value || "—"}
      </Typography>
    </Box>
  );
}

// کارت هر بخش فرم: سربرگ با شماره‌ی دایره‌ای و عنوان، محتوای بخش در بدنه
function SectionCard({ num, title, subtitle, children }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 2, mb: 2.5, overflow: "hidden" }}>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ px: 2.5, py: 1.5, bgcolor: "action.hover" }}>
        <Box
          sx={{ width: 30, height: 30, borderRadius: "50%", bgcolor: "primary.main", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800 }}
        >
          {num}
        </Box>
        <Typography fontWeight={800}>{title}</Typography>
        {subtitle && (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </Stack>
      <Box sx={{ p: 2.5 }}>{children}</Box>
    </Card>
  );
}

/**
 * کارت ویرایش یک عضو خانواده.
 * ورودی: داده‌ی عضو، شماره‌ی ترتیبی (برای «فرزند پسر ۲»)، تعریف انواع عضو،
 * اطلاعات پرسنل، موبایل شخص اصلی، خطاهای اعتبارسنجی و توابع تغییر/حذف.
 * بسته به نوع عضو و جنسیت پرسنل، برخی فیلدها مقدار ثابت دارند و نمایش داده
 * نمی‌شوند؛ برای برخی اعضا بخش کفالت و آپلود مدرک نشان داده می‌شود.
 */
function MemberCard({ member, index, typeInfo, employee, mainMobile, onChange, onRemove, errors, disabled }) {
  const cfg = typeInfo[member.member_type];
  const type = member.member_type;
  const empMale = employee.gender === 1;
  // فیلدهای ثابت: جنسیت عضو از نوع عضو (همسر = مخالف پرسنل)، همسر همیشه متأهل،
  // فرزندان پرسنل مرد نام پدر = نام پرسنل، فرزندان و پدرِ پرسنل مرد نام خانوادگی = پرسنل
  const genderFixed = type === "spouse" ? (empMale ? 2 : 1) : type === "son" || type === "father" ? 1 : 2;
  const maritalFixed = type === "spouse" ? 3 : null;
  const fatherFixed = empMale && (type === "son" || type === "daughter") ? employee.first_name : null;
  const familyFixed = empMale && (type === "son" || type === "daughter" || type === "father") ? employee.last_name : null;
  // وضعیت کفالت برای پدر/مادر و برای همه‌ی اعضای پرسنل زن پرسیده می‌شود
  const needsKafala = employee.gender === 2 || type === "father" || type === "mother";
  const [uploadPct, setUploadPct] = useState(null); // درصد آپلود؛ null = آپلودی در جریان نیست
  const [uploadErr, setUploadErr] = useState("");
  const fileRef = useRef(null);
  const set = (key) => (e) => onChange({ ...member, [key]: e.target.value });
  const err = errors || {};

  // فایل انتخاب‌شده را (پس از بررسی حجم) آپلود می‌کند و شناسه‌ی مدرک را روی عضو می‌گذارد
  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      setUploadErr("حجم فایل نباید بیشتر از ۱۰ مگابایت باشد.");
      return;
    }
    setUploadErr("");
    setUploadPct(0);
    try {
      const doc = await uploadInsuranceDocument(file, setUploadPct);
      onChange({ ...member, document: doc, document_id: doc.id });
    } catch (e2) {
      setUploadErr(uploadErrorMessage(e2));
    } finally {
      setUploadPct(null);
      if (fileRef.current) fileRef.current.value = ""; // تا انتخاب دوباره‌ی همان فایل هم رویداد بدهد
    }
  }

  // مدرک را از سرور حذف و از عضو جدا می‌کند
  async function handleRemoveDoc() {
    if (member.document?.id) {
      try {
        await deleteMyInsuranceDocument(member.document.id);
      } catch {
        // حذف سمت سرور ناموفق (مثلاً مدرک به عضو ثبت‌شده‌ی قبلی وصل است)؛ فقط از فرم جدا می‌شود
      }
    }
    onChange({ ...member, document: null, document_id: null });
  }

  // عنوان کارت: برای انواعی که چند عضو مجازند شماره هم اضافه می‌شود
  const title = cfg.max_count > 1 ? `${cfg.title} ${index}` : cfg.title;
  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: 2, borderColor: Object.keys(err).length ? "error.main" : "divider" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Chip label={title} color={MEMBER_BUTTON_COLOR[type]} size="small" />
        <IconButton size="small" color="error" onClick={onRemove} disabled={disabled} aria-label="حذف عضو">
          <DeleteOutlineOutlinedIcon fontSize="small" />
        </IconButton>
      </Stack>
      <Grid container spacing={1.5}>
        <Grid item xs={12} sm={6} md={3}>
          <TextField size="small" fullWidth required label="نام" value={member.first_name} onChange={set("first_name")} error={Boolean(err.first_name)} inputProps={{ maxLength: 100 }} disabled={disabled} />
        </Grid>
        {familyFixed === null && (
          <Grid item xs={12} sm={6} md={3}>
            <TextField size="small" fullWidth required label="نام خانوادگی" value={member.last_name} onChange={set("last_name")} error={Boolean(err.last_name)} inputProps={{ maxLength: 100 }} disabled={disabled} />
          </Grid>
        )}
        {fatherFixed === null && (
          <Grid item xs={12} sm={6} md={3}>
            <TextField size="small" fullWidth required label="نام پدر" value={member.father_name} onChange={set("father_name")} error={Boolean(err.father_name)} inputProps={{ maxLength: 100 }} disabled={disabled} />
          </Grid>
        )}
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            size="small"
            fullWidth
            required
            label="تاریخ تولد"
            placeholder="1370/01/01"
            value={member.birth_date}
            onChange={(e) => onChange({ ...member, birth_date: toEn(e.target.value).replace(/[^\d/]/g, "").slice(0, 10) })}
            error={Boolean(err.birth_date)}
            helperText={err.birth_date || ""}
            inputProps={{ dir: "ltr", style: { textAlign: "left" } }}
            disabled={disabled}
          />
        </Grid>
        {maritalFixed === null && (
          <Grid item xs={12} sm={6} md={3}>
            <TextField select size="small" fullWidth required label="وضعیت تاهل" value={member.marital_status || ""} onChange={set("marital_status")} error={Boolean(err.marital_status)} disabled={disabled}>
              <MenuItem value="">انتخاب</MenuItem>
              <MenuItem value={2}>مجرد</MenuItem>
              <MenuItem value={3}>متاهل</MenuItem>
            </TextField>
          </Grid>
        )}
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            size="small"
            fullWidth
            required
            label="کد ملی"
            value={member.national_id}
            onChange={(e) => onChange({ ...member, national_id: digitsOnly(e.target.value, 10) })}
            error={Boolean(err.national_id)}
            helperText={err.national_id || ""}
            inputProps={{ dir: "ltr", style: { textAlign: "left" }, inputMode: "numeric" }}
            disabled={disabled}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            size="small"
            fullWidth
            required
            label="شماره شناسنامه"
            value={member.birth_certificate_no}
            onChange={(e) => onChange({ ...member, birth_certificate_no: digitsOnly(e.target.value, 20) })}
            error={Boolean(err.birth_certificate_no)}
            inputProps={{ dir: "ltr", style: { textAlign: "left" }, inputMode: "numeric" }}
            disabled={disabled}
          />
        </Grid>
      </Grid>
      {/* خلاصه‌ی مقادیر ثابتی که کاربر نمی‌تواند تغییر دهد */}
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
        جنسیت: {GENDER_LABEL[genderFixed]}
        {maritalFixed ? " — وضعیت تاهل: متاهل" : ""}
        {familyFixed ? ` — نام خانوادگی: ${familyFixed}` : ""}
        {fatherFixed ? ` — نام پدر: ${fatherFixed}` : ""}
        {` — شماره تماس: ${mainMobile || "—"}`}
      </Typography>

      {/* بخش کفالت: انتخاب بله/خیر؛ با «بله» آپلود مدرک اجباری می‌شود، با «خیر» مدرک قبلی پاک می‌شود */}
      {needsKafala && (
        <Box sx={{ mt: 2, p: 2, borderRadius: 2, border: "1px solid", borderColor: err.kafala ? "error.main" : "#f1dfa8", bgcolor: "#fffbf0" }}>
          <Typography fontWeight={700} sx={{ mb: 1 }}>
            وضعیت تکفل شخص مورد نظر:
          </Typography>
          <RadioGroup value={member.kafala_status || ""} onChange={(e) => onChange({ ...member, kafala_status: e.target.value, ...(e.target.value === "no" ? { document: null, document_id: null } : {}) })}>
            <FormControlLabel value="yes" control={<Radio size="small" />} label={<Typography fontWeight={700} color="#1a7a3a">✔ شخص مورد نظر تحت کفالت اینجانب می‌باشد.</Typography>} disabled={disabled} />
            <FormControlLabel value="no" control={<Radio size="small" />} label={<Typography fontWeight={700} color="#c62828">✖ شخص مورد نظر تحت کفالت اینجانب نمی‌باشد.</Typography>} disabled={disabled} />
          </RadioGroup>
          {err.kafala && (
            <Typography variant="caption" color="error">
              {err.kafala}
            </Typography>
          )}
          {member.kafala_status === "yes" && isDocRejected(member) && (
            <Alert severity="warning" sx={{ mt: 1.5 }}>
              {REJECTED_DOC_TEXT}
            </Alert>
          )}
          {member.kafala_status === "yes" && (
            <Box sx={{ mt: 1.5 }}>
              <Typography fontWeight={700} variant="body2" sx={{ mb: 1 }}>
                📎 آپلود تصویر مدرک کفالت یا حضانت <span style={{ color: "#c62828" }}>*</span>{" "}
                <Typography component="span" variant="caption" color="text.secondary">
                  (تصویر یا PDF — حداکثر ۱۰ مگابایت)
                </Typography>
              </Typography>
              {member.document ? (
                <Stack direction="row" spacing={1} alignItems="center" sx={{ p: 1.5, border: "1px solid", borderColor: "success.main", borderRadius: 1, bgcolor: "#fff" }}>
                  <CheckCircleOutlineIcon color="success" fontSize="small" />
                  <Typography variant="body2" sx={{ flex: 1 }} noWrap>
                    {member.document.file_name}
                  </Typography>
                  <Button size="small" color="error" onClick={handleRemoveDoc} disabled={disabled}>
                    حذف
                  </Button>
                </Stack>
              ) : (
                <Box>
                  <Button component="label" variant="outlined" startIcon={<CloudUploadOutlinedIcon />} disabled={uploadPct !== null || disabled} sx={{ borderStyle: "dashed", borderColor: err.document ? "error.main" : undefined }}>
                    برای انتخاب فایل کلیک کنید
                    <input ref={fileRef} type="file" hidden accept="image/*,application/pdf" onChange={handleFile} />
                  </Button>
                  {uploadPct !== null && <LinearProgress variant="determinate" value={uploadPct} sx={{ mt: 1 }} />}
                  {(uploadErr || err.document) && (
                    <Typography variant="caption" color="error" display="block" sx={{ mt: 0.5 }}>
                      {uploadErr || err.document}
                    </Typography>
                  )}
                </Box>
              )}
            </Box>
          )}
        </Box>
      )}
    </Card>
  );
}

// شمارنده‌ی کلید یکتای اعضا در فرم (کلید React، مستقل از id دیتابیس)
let memberSeq = 0;

export default function InsurancePage() {
  const { user } = useAuth();
  const [data, setData] = useState(null); // پاسخ کامل /insurance/me
  const [loadError, setLoadError] = useState("");
  const [form, setForm] = useState(null); // فیلدهای قابل ویرایش شخص اصلی + بانک
  const [members, setMembers] = useState([]); // اعضای خانواده در فرم
  const [errors, setErrors] = useState({}); // خطاهای فیلدهای شخص اصلی
  const [memberErrors, setMemberErrors] = useState({}); // خطاهای هر عضو، با کلید member.key
  const [reviewOpen, setReviewOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null); // پیام نتیجه در دیالوگ: { severity, text }
  const [mode, setMode] = useState("edit"); // "view" = نمایش فقط‌خواندنی ثبت‌نام، "edit" = فرم
  const topRef = useRef(null); // برای اسکرول به بالای صفحه هنگام تغییر حالت

  // فرم و اعضا را از روی ثبت‌نام سرور (یا مقادیر خالی) پر می‌کند.
  // ثبت‌نام کامل (insurance_no پر) مقداردهی می‌شود، وگرنه فیلدهای خالی با پیش‌فرض
  // موبایل و نام پرسنل به‌عنوان صاحب حساب.
  function fillForm(reg, emp) {
    const complete = reg && reg.insurance_no;
    setForm({
      father_name: complete ? reg.father_name : "",
      birth_certificate_no: complete ? reg.birth_certificate_no : "",
      mobile_number: complete ? reg.mobile_number : emp?.mobile || "",
      marital_status: complete ? reg.marital_status : "",
      insurance_no: complete ? reg.insurance_no : "",
      bank_code: complete ? reg.bank_code : "",
      account_number: complete ? reg.account_number : "",
      sheba: complete ? reg.sheba : "",
      account_type: complete ? reg.account_type : "",
      account_owner_national_id: complete ? reg.account_owner_national_id : "",
      account_owner: complete ? reg.account_owner : emp ? `${emp.first_name} ${emp.last_name}` : "",
    });
    // اعضای ثبت‌نام قبلی به ساختار فرم تبدیل می‌شوند (عضو موقت نگهدارنده‌ی مدرک حذف می‌شود)
    setMembers(
      (complete ? reg.members : [])
        .filter((m) => m.member_type !== "pending")
        .map((m) => ({
          key: ++memberSeq,
          id: m.id,
          member_type: m.member_type,
          first_name: m.first_name,
          last_name: m.last_name,
          father_name: m.father_name,
          birth_date: m.birth_date,
          marital_status: m.marital_status,
          national_id: m.national_id,
          birth_certificate_no: m.birth_certificate_no,
          kafala_status: m.kafala_status,
          document: m.document,
          document_id: m.document?.id || null,
          document_rejected_at: m.document_rejected_at || null,
        }))
    );
    setErrors({});
    setMemberErrors({});
    setMode(complete ? "view" : "edit");
  }

  // بارگذاری اولیه: داده‌ی سرور را می‌گیرد و فرم را پر می‌کند
  useEffect(() => {
    fetchMyInsurance()
      .then((d) => {
        setData(d);
        fillForm(d.registration, d.employee);
      })
      .catch((e) => setLoadError(e.response?.data?.detail || "دریافت اطلاعات با خطا مواجه شد."));
  }, []);

  const employee = data?.employee;
  const typeInfo = data?.member_types || {};
  const isEdit = Boolean(data?.registration?.insurance_no); // ثبت‌نام کامل قبلی وجود دارد
  // غیرفعال: یا برای این کاربر خاص، یا کل ماژول از پنل
  const disabled = Boolean(user?.insurance_disabled) || data?.enabled === false;

  // تعداد اعضای هر نوع، برای غیرفعال کردن دکمه‌ی افزودن وقتی به سقف رسید
  const memberCounts = useMemo(() => {
    const c = {};
    for (const m of members) c[m.member_type] = (c[m.member_type] || 0) + 1;
    return c;
  }, [members]);

  // یک عضو خالی از نوع داده‌شده اضافه می‌کند (اگر به سقف آن نوع نرسیده باشد)
  function addMember(type) {
    const cfg = typeInfo[type];
    if (!cfg || (memberCounts[type] || 0) >= cfg.max_count) return;
    setMembers([
      ...members,
      { key: ++memberSeq, member_type: type, first_name: "", last_name: "", father_name: "", birth_date: "", marital_status: type === "spouse" ? 3 : "", national_id: "", birth_certificate_no: "", kafala_status: null, document: null, document_id: null },
    ]);
  }

  // تغییر وضعیت تأهل شخص اصلی؛ انتخاب «مجرد» عضو همسر را از فرم حذف می‌کند
  function setMarital(value) {
    setForm({ ...form, marital_status: value });
    if (String(value) === "2") setMembers(members.filter((m) => m.member_type !== "spouse"));
  }

  // اعتبارسنجی سمت کلاینت کل فرم؛ خطاها را در state می‌گذارد و true/false برمی‌گرداند
  function validate() {
    const e = {};
    const norm = (v) => (toEn(v).length === 9 ? "0" + toEn(v) : toEn(v)); // کد ملی ۹ رقمی → صفر ابتدایی
    // فیلدهای اجباری شخص اصلی
    const req = ["father_name", "birth_certificate_no", "mobile_number", "marital_status", "insurance_no", "bank_code", "account_number", "sheba", "account_type", "account_owner", "account_owner_national_id"];
    for (const k of req) if (String(form[k] ?? "").trim() === "") e[k] = "این فیلد الزامی است.";
    // قواعد قالب: کد ملی صاحب حساب = کد ملی پرسنل، شبا ۲۴ رقم، شماره بیمه ۱۰ رقم، موبایل معتبر
    if (norm(form.account_owner_national_id) !== norm(employee.national_id || "")) e.account_owner_national_id = "کد ملی صاحب حساب باید با کد ملی شخص اصلی یکسان باشد.";
    if (!/^\d{24}$/.test(toEn(form.sheba).replace(/^IR/i, ""))) e.sheba = "شماره شبا باید دقیقاً ۲۴ رقم باشد (بدون IR).";
    if (!/^\d{10}$/.test(toEn(form.insurance_no))) e.insurance_no = "شماره بیمه تامین اجتماعی باید دقیقاً ۱۰ رقم باشد.";
    if (!/^0?9\d{9}$/.test(toEn(form.mobile_number).trim())) e.mobile_number = "شماره موبایل معتبر نیست.";
    // اعتبارسنجی هر عضو؛ فیلدهایی که مقدار ثابت دارند بررسی نمی‌شوند
    const me = {};
    members.forEach((m) => {
      const err = {};
      const empMale = employee.gender === 1;
      if (!m.first_name.trim()) err.first_name = true;
      if (!(empMale && ["son", "daughter", "father"].includes(m.member_type)) && !m.last_name.trim()) err.last_name = true;
      if (!(empMale && ["son", "daughter"].includes(m.member_type)) && !m.father_name.trim()) err.father_name = true;
      if (!validateJalali(m.birth_date)) err.birth_date = "فرمت تاریخ: ۱۳۷۰/۰۱/۰۱";
      if (!validateNationalId(m.national_id)) err.national_id = "کد ملی معتبر نیست.";
      if (!m.birth_certificate_no.trim()) err.birth_certificate_no = true;
      if (m.member_type !== "spouse" && !m.marital_status) err.marital_status = true;
      const needsKafala = employee.gender === 2 || m.member_type === "father" || m.member_type === "mother";
      if (needsKafala) {
        if (!m.kafala_status) err.kafala = "انتخاب یکی از گزینه‌های بالا الزامی است.";
        else if (m.kafala_status === "yes" && !m.document_id) err.document = "آپلود مدرک کفالت یا حضانت اجباری است.";
      }
      if (Object.keys(err).length) me[m.key] = err;
    });
    setErrors(e);
    setMemberErrors(me);
    return Object.keys(e).length === 0 && Object.keys(me).length === 0;
  }

  // کلیک «بررسی و ثبت»: اگر فرم معتبر بود پنجره‌ی بررسی نهایی باز می‌شود
  function handleReview() {
    if (!validate()) {
      setResult({ severity: "error", text: "لطفاً خطاهای فرم را برطرف کنید. فیلدها و اعضای دارای خطا با رنگ قرمز مشخص شده‌اند." });
      return;
    }
    setReviewOpen(true);
  }

  // تأیید نهایی: فرم را به ساختار API تبدیل و ارسال می‌کند، سپس پیام موفقیت/خطا نشان می‌دهد
  async function handleSubmit() {
    setSaving(true);
    try {
      // کدهای انتخابی به عدد تبدیل می‌شوند؛ تاریخ تولد اعضا با ارقام انگلیسی
      const payload = {
        ...form,
        marital_status: Number(form.marital_status),
        bank_code: Number(form.bank_code),
        account_type: Number(form.account_type),
        members: members.map((m) => ({
          id: m.id || null,
          member_type: m.member_type,
          first_name: m.first_name,
          last_name: m.last_name,
          father_name: m.father_name,
          birth_date: toEn(m.birth_date),
          marital_status: m.marital_status ? Number(m.marital_status) : null,
          national_id: m.national_id,
          birth_certificate_no: m.birth_certificate_no,
          kafala_status: m.kafala_status,
          document_id: m.document_id,
        })),
      };
      const saved = await saveMyInsurance(payload);
      setData({ ...data, registration: saved });
      fillForm(saved, employee); // خروج از فرم و نمایش اطلاعات ثبت‌شده
      setReviewOpen(false);
      setResult({ severity: "success", text: isEdit ? "ویرایش ثبت‌نام با موفقیت انجام شد." : "ثبت‌نام شما با موفقیت انجام شد." });
      topRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      setReviewOpen(false);
      const detail = e.response?.data?.detail;
      setResult({ severity: "error", text: typeof detail === "string" && detail ? detail : "ثبت اطلاعات با خطا مواجه شد." });
    } finally {
      setSaving(false);
    }
  }

  // نام بانک و نوع حساب از روی کد (برای پنجره‌ی بررسی)
  const bankName = (code) => data?.bank_codes?.[code] || "—";
  const accountTypeName = (code) => data?.account_types?.[code] || "—";

  // حالت‌های ویژه به ترتیب: خطای بارگذاری، در حال بارگذاری، ماژول غیرفعال،
  // کاربر بدون پرسنل، اطلاعات پرسنلی ناقص
  if (loadError) {
    return (
      <Box sx={{ maxWidth: 1100, mx: "auto" }}>
        <BackLink to="/my-dashboard" />
        <Alert severity="error">{loadError}</Alert>
      </Box>
    );
  }
  if (!data || !form) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  const header = (
    <>
      <BackLink to="/my-dashboard" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }} ref={topRef}>
        فرم ثبت‌نام بیمه تکمیلی
      </Typography>
    </>
  );

  if (disabled) {
    return (
      <Box sx={{ maxWidth: 1100, mx: "auto" }}>
        {header}
        <Alert severity="warning" sx={{ mt: 2 }}>
          ثبت‌نام بیمه تکمیلی در حال حاضر غیرفعال است.
        </Alert>
      </Box>
    );
  }
  if (!employee) {
    return (
      <Box sx={{ maxWidth: 1100, mx: "auto" }}>
        {header}
        <Alert severity="info" sx={{ mt: 2 }}>
          این قابلیت فقط برای حساب‌های متصل به پرسنل در دسترس است.
        </Alert>
      </Box>
    );
  }
  if (employee.missing?.length) {
    return (
      <Box sx={{ maxWidth: 1100, mx: "auto" }}>
        {header}
        <Alert severity="warning" sx={{ mt: 2 }}>
          اطلاعات پرسنلی شما برای ثبت‌نام کامل نیست ({employee.missing.join("، ")}). لطفاً به واحد منابع انسانی اطلاع دهید.
        </Alert>
      </Box>
    );
  }

  // دیالوگ نتیجه‌ی ثبت یا خطای فرم (در هر دو حالت نمایش و فرم رندر می‌شود)
  const resultDialog = (
    <Dialog open={Boolean(result)} onClose={() => setResult(null)} fullWidth maxWidth="xs">
      <DialogContent sx={{ textAlign: "center", pt: 4 }}>
        {result?.severity === "success" ? <CheckCircleOutlineIcon color="success" sx={{ fontSize: 64 }} /> : <ErrorOutlineIcon color="error" sx={{ fontSize: 64 }} />}
        <Typography fontWeight={700} sx={{ mt: 1.5 }}>
          {result?.text}
        </Typography>
      </DialogContent>
      <DialogActions sx={{ justifyContent: "center", pb: 2.5 }}>
        <Button variant="contained" color={result?.severity === "success" ? "success" : "primary"} onClick={() => setResult(null)} autoFocus>
          متوجه شدم
        </Button>
      </DialogActions>
    </Dialog>
  );

  // نام خانوادگی نمایشی عضو (برای اعضایی که نام خانوادگی‌شان ثابت و برابر پرسنل است)
  const memberLastName = (m) => (employee.gender === 1 && ["son", "daughter", "father"].includes(m.member_type) ? employee.last_name : m.last_name);

  // حالت نمایش: خلاصه‌ی فقط‌خواندنی ثبت‌نام با دکمه‌ی «ویرایش ثبت نام»
  if (mode === "view") {
    const reg = data.registration;
    const rejected = members.filter(isDocRejected);
    return (
      <Box sx={{ maxWidth: 1100, mx: "auto" }}>
        {header}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} justifyContent="space-between" sx={{ mb: 2 }}>
          <Alert severity="success" icon={<CheckCircleOutlineIcon />} sx={{ flex: 1 }}>
            ثبت‌نام شما انجام شده است. اطلاعات ثبت‌شده در ادامه آمده است.
          </Alert>
          <Button variant="contained" startIcon={<EditOutlinedIcon />} onClick={() => setMode("edit")} sx={{ flexShrink: 0 }}>
            ویرایش ثبت نام
          </Button>
        </Stack>
        {rejected.length > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            مدرک ارائه‌شده برای {rejected.map((m) => `${m.first_name} ${memberLastName(m)}`).join("، ")} مورد تأیید نیست. لطفاً با «ویرایش ثبت نام» مدرک جدید آپلود کنید.
          </Alert>
        )}

        <SectionCard num="۱" title="اطلاعات شخص اصلی">
          <Grid container spacing={2}>
            {[
              ["کد پرسنلی", employee.personnel_code],
              ["نام", employee.first_name],
              ["نام خانوادگی", employee.last_name],
              ["جنسیت", GENDER_LABEL[employee.gender]],
              ["تاریخ استخدام", employee.employment_date],
              ["کد ملی", employee.national_id],
              ["تاریخ تولد", employee.birth_date],
              ["نام پدر", reg.father_name],
              ["شماره شناسنامه", reg.birth_certificate_no],
              ["شماره تماس", reg.mobile_number],
              ["وضعیت تاهل", MARITAL_LABEL[reg.marital_status]],
              ["شماره بیمه تأمین اجتماعی", reg.insurance_no],
            ].map(([l, v]) => (
              <Grid item xs={6} md={3} key={l}>
                <ReadOnlyField label={l} value={v} />
              </Grid>
            ))}
          </Grid>
        </SectionCard>

        <SectionCard num="۲" title="اطلاعات بانکی">
          <Grid container spacing={2}>
            {[
              ["بانک", bankName(reg.bank_code)],
              ["شماره حساب", reg.account_number],
              ["شماره شبا", reg.sheba ? `IR${reg.sheba}` : ""],
              ["نوع حساب", accountTypeName(reg.account_type)],
              ["کد ملی صاحب حساب", reg.account_owner_national_id],
              ["نام صاحب حساب", reg.account_owner],
            ].map(([l, v]) => (
              <Grid item xs={12} sm={6} md={4} key={l}>
                <ReadOnlyField label={l} value={v} />
              </Grid>
            ))}
          </Grid>
        </SectionCard>

        <SectionCard num="۳" title="اعضای خانواده" subtitle={members.length ? `(${members.length.toLocaleString("fa-IR")} نفر)` : ""}>
          {members.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              عضوی ثبت نشده است.
            </Typography>
          ) : (
            <Stack spacing={1.5}>
              {members.map((m) => {
                const idx = members.filter((x) => x.member_type === m.member_type).indexOf(m) + 1;
                const cfg = typeInfo[m.member_type];
                const title = cfg ? (cfg.max_count > 1 ? `${cfg.title} ${idx}` : cfg.title) : m.member_type;
                const bad = isDocRejected(m);
                return (
                  <Card key={m.key} variant="outlined" sx={{ borderRadius: 2, p: 2, borderColor: bad ? "warning.main" : "divider" }}>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
                      <Chip label={title} color={MEMBER_BUTTON_COLOR[m.member_type]} size="small" />
                      {m.kafala_status === "yes" && <Chip size="small" variant="outlined" color="success" label="تحت کفالت" />}
                      {m.kafala_status === "no" && <Chip size="small" variant="outlined" color="error" label="غیر تحت کفالت" />}
                      {m.document && <Chip size="small" icon={<CheckCircleOutlineIcon />} color="success" label="مدرک آپلود شده" />}
                      {bad && <Chip size="small" icon={<ErrorOutlineIcon />} color="warning" label="مدرک تأیید نشد" />}
                    </Stack>
                    <Grid container spacing={1.5}>
                      {[
                        ["نام و نام خانوادگی", `${m.first_name} ${memberLastName(m)}`],
                        ["نام پدر", employee.gender === 1 && ["son", "daughter"].includes(m.member_type) ? employee.first_name : m.father_name],
                        ["تاریخ تولد", m.birth_date],
                        ["کد ملی", m.national_id],
                        ["شماره شناسنامه", m.birth_certificate_no],
                        ["وضعیت تاهل", MARITAL_LABEL[m.marital_status]],
                      ].map(([l, v]) => (
                        <Grid item xs={6} md={2} key={l}>
                          <ReadOnlyField label={l} value={v} />
                        </Grid>
                      ))}
                    </Grid>
                    {bad && (
                      <Alert severity="warning" sx={{ mt: 1.5 }}>
                        {REJECTED_DOC_TEXT}
                      </Alert>
                    )}
                  </Card>
                );
              })}
            </Stack>
          )}
        </SectionCard>

        <SectionCard num="۴" title="جدول نرخ حق بیمه تکمیلی پرسنل">
          <InsuranceRateInfo rateTable={data.rate_table} notes={data.notes} />
        </SectionCard>

        <Box sx={{ display: "flex", justifyContent: "flex-end", mb: 4 }}>
          <Button variant="contained" size="large" startIcon={<EditOutlinedIcon />} onClick={() => setMode("edit")}>
            ویرایش ثبت نام
          </Button>
        </Box>
        {resultDialog}
      </Box>
    );
  }

  // انصراف از ویرایش: تغییرات فرم دور ریخته می‌شود و به نمایش ثبت‌نام برمی‌گردد
  function cancelEdit() {
    fillForm(data.registration, employee);
    topRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  // سازنده‌ی onChange برای فیلدهای شخص اصلی با تبدیل اختیاری مقدار (مثلاً فقط ارقام)
  const setF = (key, transform) => (e) => setForm({ ...form, [key]: transform ? transform(e.target.value) : e.target.value });
  // پراپ‌های خطا/راهنمای هر فیلد از روی state خطاها
  const fieldProps = (key) => ({ error: Boolean(errors[key]), helperText: errors[key] || "" });
  const showSpouseBtn = String(form.marital_status) !== "2"; // دکمه‌ی همسر برای مجرد پنهان است

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      {header}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {isEdit ? "در حال ویرایش ثبت‌نام قبلی هستید؛ پس از تغییر، دوباره ثبت کنید." : "اطلاعات خود و اعضای خانواده را برای بیمه تکمیلی تکمیل کنید."}
      </Typography>

      {/* بخش ۱: فیلدهای فقط‌خواندنی از رکورد پرسنل + فیلدهای قابل ویرایش */}
      <SectionCard num="۱" title="اطلاعات شخص اصلی">
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={6} md={3}><ReadOnlyField label="کد پرسنلی" value={employee.personnel_code} /></Grid>
          <Grid item xs={6} md={3}><ReadOnlyField label="نام" value={employee.first_name} /></Grid>
          <Grid item xs={6} md={3}><ReadOnlyField label="نام خانوادگی" value={employee.last_name} /></Grid>
          <Grid item xs={6} md={3}><ReadOnlyField label="جنسیت" value={GENDER_LABEL[employee.gender]} /></Grid>
          <Grid item xs={6} md={3}><ReadOnlyField label="تاریخ استخدام" value={employee.employment_date} /></Grid>
          <Grid item xs={6} md={3}><ReadOnlyField label="کد ملی" value={employee.national_id} /></Grid>
          <Grid item xs={6} md={3}><ReadOnlyField label="تاریخ تولد" value={employee.birth_date} /></Grid>
        </Grid>
        <Divider sx={{ mb: 2 }} />
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <TextField fullWidth required label="نام پدر" value={form.father_name} onChange={setF("father_name")} inputProps={{ maxLength: 100 }} {...fieldProps("father_name")} />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <TextField fullWidth required label="شماره شناسنامه" value={form.birth_certificate_no} onChange={setF("birth_certificate_no", (v) => digitsOnly(v, 20))} inputProps={{ dir: "ltr", style: { textAlign: "left" }, inputMode: "numeric" }} {...fieldProps("birth_certificate_no")} />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <TextField fullWidth required label="شماره تماس" value={form.mobile_number} onChange={setF("mobile_number", (v) => digitsOnly(v, 11))} inputProps={{ dir: "ltr", style: { textAlign: "left" }, inputMode: "numeric" }} {...fieldProps("mobile_number")} />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <TextField select fullWidth required label="وضعیت تاهل" value={form.marital_status} onChange={(e) => setMarital(e.target.value)} {...fieldProps("marital_status")}>
              <MenuItem value="">انتخاب کنید</MenuItem>
              <MenuItem value={2}>مجرد</MenuItem>
              <MenuItem value={3}>متاهل</MenuItem>
            </TextField>
          </Grid>
          <Grid item xs={12} sm={6} md={4}>
            <TextField fullWidth required label="شماره بیمه تأمین اجتماعی (۱۰ رقم)" value={form.insurance_no} onChange={setF("insurance_no", (v) => digitsOnly(v, 10))} inputProps={{ dir: "ltr", style: { textAlign: "left" }, inputMode: "numeric" }} {...fieldProps("insurance_no")} />
          </Grid>
        </Grid>
      </SectionCard>

      {/* بخش ۲: بانک، شماره حساب، شبا، نوع حساب و صاحب حساب */}
      <SectionCard num="۲" title="اطلاعات بانکی">
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={4}>
            <TextField select fullWidth required label="بانک" value={form.bank_code} onChange={setF("bank_code")} {...fieldProps("bank_code")}>
              <MenuItem value="">انتخاب بانک</MenuItem>
              {Object.entries(data.bank_codes).map(([code, name]) => (
                <MenuItem key={code} value={Number(code)}>
                  {name}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={6} md={4}>
            <TextField fullWidth required label="شماره حساب" value={form.account_number} onChange={setF("account_number", (v) => digitsOnly(v, 40))} inputProps={{ dir: "ltr", style: { textAlign: "left" }, inputMode: "numeric" }} {...fieldProps("account_number")} />
          </Grid>
          <Grid item xs={12} sm={6} md={4}>
            <TextField fullWidth required label="شماره شبا (۲۴ رقم بدون IR)" placeholder="24 رقم" value={form.sheba} onChange={setF("sheba", (v) => digitsOnly(v.replace(/^IR/i, ""), 24))} inputProps={{ dir: "ltr", style: { textAlign: "left" }, inputMode: "numeric" }} {...fieldProps("sheba")} />
          </Grid>
          <Grid item xs={12} sm={6} md={4}>
            <TextField select fullWidth required label="نوع حساب" value={form.account_type} onChange={setF("account_type")} {...fieldProps("account_type")}>
              <MenuItem value="">انتخاب کنید</MenuItem>
              {Object.entries(data.account_types).map(([code, name]) => (
                <MenuItem key={code} value={Number(code)}>
                  {name}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={6} md={4}>
            <TextField fullWidth required label="کد ملی صاحب حساب" value={form.account_owner_national_id} onChange={setF("account_owner_national_id", (v) => digitsOnly(v, 10))} inputProps={{ dir: "ltr", style: { textAlign: "left" }, inputMode: "numeric" }} {...fieldProps("account_owner_national_id")} />
          </Grid>
          <Grid item xs={12} sm={6} md={4}>
            <TextField fullWidth required label="نام صاحب حساب" value={form.account_owner} onChange={setF("account_owner")} inputProps={{ maxLength: 200 }} {...fieldProps("account_owner")} />
          </Grid>
        </Grid>
      </SectionCard>

      {/* بخش ۳: دکمه‌های افزودن عضو (تا سقف هر نوع) و کارت هر عضو */}
      <SectionCard num="۳" title="اعضای خانواده" subtitle="(اختیاری)">
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
          {MEMBER_ORDER.filter((t) => typeInfo[t]).map((t) => {
            const cfg = typeInfo[t];
            const atMax = (memberCounts[t] || 0) >= cfg.max_count;
            if (t === "spouse" && !showSpouseBtn) return null;
            return (
              <Button key={t} size="small" variant="outlined" color={MEMBER_BUTTON_COLOR[t]} onClick={() => addMember(t)} disabled={atMax}>
                + {cfg.title}
              </Button>
            );
          })}
        </Stack>
        {members.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            برای افزودن اعضای خانواده از دکمه‌های بالا استفاده کنید.
          </Typography>
        ) : (
          <Stack spacing={2}>
            {members.map((m) => {
              const idx = members.filter((x) => x.member_type === m.member_type).indexOf(m) + 1; // شماره‌ی عضو بین هم‌نوع‌ها

              return (
                <MemberCard
                  key={m.key}
                  member={m}
                  index={idx}
                  typeInfo={typeInfo}
                  employee={employee}
                  mainMobile={form.mobile_number}
                  errors={memberErrors[m.key]}
                  onChange={(next) => setMembers(members.map((x) => (x.key === m.key ? next : x)))}
                  onRemove={() => setMembers(members.filter((x) => x.key !== m.key))}
                />
              );
            })}
          </Stack>
        )}
      </SectionCard>

      {/* بخش ۴: جدول نرخ و نکات (محتوا از تنظیمات پنل) */}
      <SectionCard num="۴" title="جدول نرخ حق بیمه تکمیلی پرسنل">
        <InsuranceRateInfo rateTable={data.rate_table} notes={data.notes} />
      </SectionCard>

      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1.5, mb: 4 }}>
        {isEdit && (
          <Button size="large" onClick={cancelEdit}>
            انصراف از ویرایش
          </Button>
        )}
        <Button variant="contained" size="large" onClick={handleReview}>
          {isEdit ? "بررسی و ثبت ویرایش" : "بررسی و ثبت نهایی"}
        </Button>
      </Box>

      {/* پنجره‌ی بررسی نهایی: خلاصه‌ی شخص اصلی و اعضا قبل از ارسال به سرور */}
      <Dialog open={reviewOpen} onClose={() => !saving && setReviewOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>بررسی نهایی اطلاعات</DialogTitle>
        <DialogContent dividers>
          <Typography fontWeight={700} sx={{ mb: 1 }}>
            شخص اصلی
          </Typography>
          <Table size="small" sx={{ mb: 2 }}>
            <TableBody>
              {[
                ["کد پرسنلی", employee.personnel_code],
                ["نام و نام خانوادگی", `${employee.first_name} ${employee.last_name}`],
                ["نام پدر", form.father_name],
                ["تاریخ تولد", employee.birth_date],
                ["جنسیت", GENDER_LABEL[employee.gender]],
                ["وضعیت تاهل", MARITAL_LABEL[form.marital_status]],
                ["کد ملی", employee.national_id],
                ["شماره شناسنامه", form.birth_certificate_no],
                ["شماره تماس", form.mobile_number],
                ["تاریخ استخدام", employee.employment_date],
                ["شماره بیمه", form.insurance_no],
                ["بانک", bankName(form.bank_code)],
                ["شماره حساب", form.account_number],
                ["شماره شبا", form.sheba],
                ["نوع حساب", accountTypeName(form.account_type)],
                ["صاحب حساب", `${form.account_owner} (${form.account_owner_national_id})`],
              ].map(([l, v]) => (
                <TableRow key={l}>
                  <TableCell sx={{ color: "text.secondary", width: 180 }}>{l}</TableCell>
                  <TableCell>{v || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {members.length > 0 && (
            <>
              <Typography fontWeight={700} sx={{ mb: 1 }}>
                اعضای خانواده ({members.length.toLocaleString("fa-IR")} نفر)
              </Typography>
              <Table size="small">
                <TableBody>
                  {members.map((m) => {
                    const empMale = employee.gender === 1;
                    const last = empMale && ["son", "daughter", "father"].includes(m.member_type) ? employee.last_name : m.last_name;
                    const kaf = m.kafala_status === "yes" ? "تحت کفالت (با مدرک)" : m.kafala_status === "no" ? "غیر تحت کفالت" : "";
                    return (
                      <TableRow key={m.key}>
                        <TableCell sx={{ width: 110 }}>{typeInfo[m.member_type]?.title}</TableCell>
                        <TableCell>
                          {m.first_name} {last} — کد ملی {m.national_id} — متولد {m.birth_date}
                          {kaf ? ` — ${kaf}` : ""}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReviewOpen(false)} disabled={saving}>
            بازگشت و ویرایش
          </Button>
          <Button variant="contained" onClick={handleSubmit} disabled={saving} startIcon={saving ? <CircularProgress size={16} color="inherit" /> : null}>
            تأیید و ثبت
          </Button>
        </DialogActions>
      </Dialog>
      {resultDialog}
    </Box>
  );
}
