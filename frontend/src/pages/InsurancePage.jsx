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
 * فرم ثبت‌نام بیمه تکمیلی پرسنل - بازسازی دقیق dashboard.php + form.js سامانه
 * قدیمی (insurance.faipco.ir). ⚠️ طبق درخواست کاربر، رفتار فیلدها عیناً حفظ
 * شده: فیلدهای پرسنلی فقط‌نمایشی، «شماره تماس» و «نام صاحب حساب» با پیش‌فرض ولی
 * قابل ویرایش، قواعد اعضای خانواده و مدرک کفالت مثل قبل. اعتبارسنجی نهایی سمت
 * سرور (core/insurance_rules.py) است.
 */

const MEMBER_ORDER = ["spouse", "son", "daughter", "father", "mother"];
const MEMBER_BUTTON_COLOR = { spouse: "primary", son: "success", daughter: "info", father: "warning", mother: "error" };
const GENDER_LABEL = { 1: "مرد", 2: "زن" };
const MARITAL_LABEL = { 2: "مجرد", 3: "متاهل" };
const toEn = (v) => String(v ?? "").replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d));
const digitsOnly = (v, max) => toEn(v).replace(/\D/g, "").slice(0, max);

function validateNationalId(raw) {
  let id = toEn(raw).trim();
  if (id.length === 9) id = "0" + id;
  if (!/^\d{10}$/.test(id) || /^(\d)\1{9}$/.test(id)) return false;
  let sum = 0;
  for (let i = 0; i < 9; i++) sum += parseInt(id[i], 10) * (10 - i);
  const rem = sum % 11;
  const check = parseInt(id[9], 10);
  return rem < 2 ? check === rem : check === 11 - rem;
}
const validateJalali = (d) => /^\d{4}\/\d{2}\/\d{2}$/.test(toEn(d).trim());

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

function MemberCard({ member, index, typeInfo, employee, mainMobile, onChange, onRemove, errors, disabled }) {
  const cfg = typeInfo[member.member_type];
  const type = member.member_type;
  const empMale = employee.gender === 1;
  // قواعد form.js
  const genderFixed = type === "spouse" ? (empMale ? 2 : 1) : type === "son" || type === "father" ? 1 : 2;
  const maritalFixed = type === "spouse" ? 3 : null;
  const fatherFixed = empMale && (type === "son" || type === "daughter") ? employee.first_name : null;
  const familyFixed = empMale && (type === "son" || type === "daughter" || type === "father") ? employee.last_name : null;
  const needsKafala = employee.gender === 2 || type === "father" || type === "mother";
  const [uploadPct, setUploadPct] = useState(null);
  const [uploadErr, setUploadErr] = useState("");
  const fileRef = useRef(null);
  const set = (key) => (e) => onChange({ ...member, [key]: e.target.value });
  const err = errors || {};

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
      setUploadErr(e2.response?.data?.detail || "آپلود فایل با خطا مواجه شد.");
    } finally {
      setUploadPct(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleRemoveDoc() {
    if (member.document?.id) {
      try {
        await deleteMyInsuranceDocument(member.document.id);
      } catch {
        // مدرک قبلاً به ثبت‌نام وصل شده (ویرایش) - فقط از فرم جدا می‌شود
      }
    }
    onChange({ ...member, document: null, document_id: null });
  }

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
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
        جنسیت: {GENDER_LABEL[genderFixed]}
        {maritalFixed ? " — وضعیت تاهل: متاهل" : ""}
        {familyFixed ? ` — نام خانوادگی: ${familyFixed}` : ""}
        {fatherFixed ? ` — نام پدر: ${fatherFixed}` : ""}
        {` — شماره تماس: ${mainMobile || "—"}`}
      </Typography>

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

let memberSeq = 0;

export default function InsurancePage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [form, setForm] = useState(null);
  const [members, setMembers] = useState([]);
  const [errors, setErrors] = useState({});
  const [memberErrors, setMemberErrors] = useState({});
  const [reviewOpen, setReviewOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const topRef = useRef(null);

  useEffect(() => {
    fetchMyInsurance()
      .then((d) => {
        setData(d);
        const reg = d.registration;
        const emp = d.employee;
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
            }))
        );
      })
      .catch((e) => setLoadError(e.response?.data?.detail || "دریافت اطلاعات با خطا مواجه شد."));
  }, []);

  const employee = data?.employee;
  const typeInfo = data?.member_types || {};
  const isEdit = Boolean(data?.registration?.insurance_no);
  const disabled = Boolean(user?.insurance_disabled) || data?.enabled === false;

  const memberCounts = useMemo(() => {
    const c = {};
    for (const m of members) c[m.member_type] = (c[m.member_type] || 0) + 1;
    return c;
  }, [members]);

  function addMember(type) {
    const cfg = typeInfo[type];
    if (!cfg || (memberCounts[type] || 0) >= cfg.max_count) return;
    setMembers([
      ...members,
      { key: ++memberSeq, member_type: type, first_name: "", last_name: "", father_name: "", birth_date: "", marital_status: type === "spouse" ? 3 : "", national_id: "", birth_certificate_no: "", kafala_status: null, document: null, document_id: null },
    ]);
  }

  function setMarital(value) {
    setForm({ ...form, marital_status: value });
    // مجرد → همسر حذف می‌شود و دکمه‌اش پنهان (form.js)
    if (String(value) === "2") setMembers(members.filter((m) => m.member_type !== "spouse"));
  }

  function validate() {
    const e = {};
    const norm = (v) => (toEn(v).length === 9 ? "0" + toEn(v) : toEn(v));
    const req = ["father_name", "birth_certificate_no", "mobile_number", "marital_status", "insurance_no", "bank_code", "account_number", "sheba", "account_type", "account_owner", "account_owner_national_id"];
    for (const k of req) if (String(form[k] ?? "").trim() === "") e[k] = "این فیلد الزامی است.";
    if (norm(form.account_owner_national_id) !== norm(employee.national_id || "")) e.account_owner_national_id = "کد ملی صاحب حساب باید با کد ملی شخص اصلی یکسان باشد.";
    if (!/^\d{24}$/.test(toEn(form.sheba).replace(/^IR/i, ""))) e.sheba = "شماره شبا باید دقیقاً ۲۴ رقم باشد (بدون IR).";
    if (!/^\d{10}$/.test(toEn(form.insurance_no))) e.insurance_no = "شماره بیمه تامین اجتماعی باید دقیقاً ۱۰ رقم باشد.";
    if (!/^0?9\d{9}$/.test(toEn(form.mobile_number).trim())) e.mobile_number = "شماره موبایل معتبر نیست.";
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

  function handleReview() {
    setMessage(null);
    if (!validate()) {
      setMessage({ severity: "error", text: "لطفاً خطاهای فرم را برطرف کنید." });
      topRef.current?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    setReviewOpen(true);
  }

  async function handleSubmit() {
    setSaving(true);
    setMessage(null);
    try {
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
      setReviewOpen(false);
      setMessage({ severity: "success", text: isEdit ? "ویرایش ثبت‌نام با موفقیت انجام شد." : "ثبت‌نام شما با موفقیت انجام شد." });
      topRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      setReviewOpen(false);
      setMessage({ severity: "error", text: e.response?.data?.detail || "ثبت اطلاعات با خطا مواجه شد." });
    } finally {
      setSaving(false);
    }
  }

  const bankName = (code) => data?.bank_codes?.[code] || "—";
  const accountTypeName = (code) => data?.account_types?.[code] || "—";

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

  const setF = (key, transform) => (e) => setForm({ ...form, [key]: transform ? transform(e.target.value) : e.target.value });
  const fieldProps = (key) => ({ error: Boolean(errors[key]), helperText: errors[key] || "" });
  const showSpouseBtn = String(form.marital_status) !== "2";

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      {header}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {isEdit ? "شما قبلاً ثبت‌نام کرده‌اید؛ می‌توانید اطلاعات را ویرایش و دوباره ثبت کنید." : "اطلاعات خود و اعضای خانواده را برای بیمه تکمیلی تکمیل کنید."}
      </Typography>
      {message && (
        <Alert severity={message.severity} sx={{ mb: 2 }}>
          {message.text}
        </Alert>
      )}

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
              const idx = members.filter((x) => x.member_type === m.member_type).indexOf(m) + 1;
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

      <SectionCard num="۴" title="جدول نرخ حق بیمه تکمیلی پرسنل">
        <InsuranceRateInfo rateTable={data.rate_table} notes={data.notes} />
      </SectionCard>

      <Box sx={{ display: "flex", justifyContent: "flex-end", mb: 4 }}>
        <Button variant="contained" size="large" onClick={handleReview}>
          {isEdit ? "بررسی و ثبت ویرایش" : "بررسی و ثبت نهایی"}
        </Button>
      </Box>

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
    </Box>
  );
}
