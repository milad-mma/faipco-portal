/**
 * صفحه ایجاد اطلاعیه جدید با سه حالت (بسته به مجوزهای کاربر):
 * - اطلاعیه متنی: عنوان، متن، اولویت و مخاطبان (کل سازمان، سایت‌ها، واحدها، سرپرستان، اشخاص خاص)؛ ثبت و انتشار فوری.
 * - فیش حقوقی: آپلود فایل XML/XLSX؛ هر پرسنلِ موجود در فایل فقط فیش خودش را دریافت می‌کند.
 * - فیش کارکرد: آپلود فایل اکسل به‌همراه متن ماه/سال چاپ‌شده روی کارت PDF.
 * پس از ارسال، نتیجه (و کدهای پیدانشده/ردیف‌های نامعتبر فایل) نمایش داده می‌شود.
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  FormControlLabel,
  FormGroup,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import {
  createAttendanceCardNotice,
  createNotice,
  createPayrollNotice,
  deleteNotice,
  fetchAvailableTargets,
  resolveNoticeEmployeeCodes,
  downloadAttendanceCardSample,
  publishNotice,
  uploadNoticeAttachment,
} from "../api/notices";
import BackLink from "../components/BackLink";
import { useAuth } from "../context/AuthContext";
import NoticeAttachmentPicker from "../components/NoticeAttachmentPicker";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import EmployeeSearchField, { employeeToOption } from "../components/EmployeeSearchField";
import { toEn } from "../utils/family";
import PillTabs from "../components/PillTabs";
import { searchFilterOptions } from "../utils/searchText";

// برچسب و رنگ گزینه‌های اولویت
const PRIORITY_LABELS = {
  low: { label: "کم", color: "default" },
  normal: { label: "عادی", color: "info" },
  high: { label: "بالا", color: "warning" },
  urgent: { label: "فوری", color: "error" },
};

// مقدار اولیه فرم اطلاعیه متنی (employees: گزینه‌های {id, label, employee} انتخاب‌شده از EmployeeSearchField، supervisors: id سرپرستان)
const EMPTY_FORM = {
  title: "",
  body: "",
  priority: "normal",
  targetAll: false,
  siteIds: [],
  departmentIds: [],
  employees: [],
  supervisors: [],
};

// مقدار اولیه فرم فیش حقوقی
const EMPTY_PAYROLL_FORM = {
  title: "فیش حقوقی",
  body: "",
  priority: "normal",
  file: null,
};

// مقدار اولیه فرم فیش کارکرد (cardSubtitle: ماه/سال چاپ‌شده روی کارت)
const EMPTY_ATTENDANCE_CARD_FORM = {
  title: "فیش کارکرد",
  body: "",
  priority: "normal",
  cardSubtitle: "",
  file: null,
};

// کامپوننت صفحه؛ مجوزهای ارسال را بارگذاری و فرم متناسب با حالت انتخاب‌شده را رندر می‌کند
/**
 * فهرست تیک‌دار مخاطبان (واحدها یا مدیران واحد) با «انتخاب همه». اگر موارد از بیش از یک سایت باشند، زیر عنوان هر سایت
 * گروه‌بندی می‌شوند و هر سایت تیک «همه» دارد. ورودی: title، selectAllLabel، items [{id, label, siteId}]،
 * selected (شناسه‌ها)، onChange(ids)، siteNames {siteId: name}، disabled. بدون مورد چیزی نمایش داده نمی‌شود.
 */
function GroupedCheckboxes({ title, selectAllLabel, items, selected, onChange, siteNames, disabled }) {
  if (!items.length) return null;
  const selectedSet = new Set(selected);
  const allSelected = items.every((i) => selectedSet.has(i.id));
  const someSelected = items.some((i) => selectedSet.has(i.id));
  const toggle = (id) => onChange(selectedSet.has(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  const setMany = (ids, on) => {
    const next = new Set(selected);
    ids.forEach((id) => (on ? next.add(id) : next.delete(id)));
    onChange([...next]);
  };
  // گروه‌بندی به تفکیک سایت (به ترتیب اولین ظهور)
  const groups = [];
  const bySite = new Map();
  items.forEach((i) => {
    const key = i.siteId ?? "none";
    if (!bySite.has(key)) {
      bySite.set(key, []);
      groups.push(key);
    }
    bySite.get(key).push(i);
  });
  const renderItems = (list) => (
    <FormGroup row>
      {list.map((i) => (
        <FormControlLabel
          key={i.id}
          sx={{ minWidth: 0 }}
          control={<Checkbox checked={selectedSet.has(i.id)} onChange={() => toggle(i.id)} disabled={disabled} />}
          label={i.label}
        />
      ))}
    </FormGroup>
  );
  return (
    <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5 }}>
      <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
        {title}
      </Typography>
      {items.length > 1 && (
        <>
          <FormControlLabel
            control={
              <Checkbox
                checked={allSelected}
                indeterminate={someSelected && !allSelected}
                onChange={() => setMany(items.map((i) => i.id), !allSelected)}
                disabled={disabled}
              />
            }
            label={<Typography fontWeight={600}>{selectAllLabel}</Typography>}
          />
          <Divider sx={{ my: 0.5 }} />
        </>
      )}
      {groups.length <= 1
        ? renderItems(items)
        : groups.map((key) => {
            const list = bySite.get(key);
            const ids = list.map((i) => i.id);
            const all = ids.every((id) => selectedSet.has(id));
            const some = ids.some((id) => selectedSet.has(id));
            return (
              <Box key={key} sx={{ mt: 1 }}>
                <FormControlLabel
                  control={
                    <Checkbox
                      size="small"
                      checked={all}
                      indeterminate={some && !all}
                      onChange={() => setMany(ids, !all)}
                      disabled={disabled}
                    />
                  }
                  label={
                    <Typography variant="body2" fontWeight={700} color="primary">
                      {siteNames[key] || (key === "none" ? "بدون سایت" : `سایت ${key}`)} — همه
                    </Typography>
                  }
                />
                <Box sx={{ pr: 3 }}>{renderItems(list)}</Box>
              </Box>
            );
          })}
    </Box>
  );
}

export default function NewNoticePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const canAttach = Boolean(user?.can_attach_notice_files); // مجوز notices.attachments (سرور برای همه‌ی سایت‌های مخاطب هم چک می‌کند)
  const [attachments, setAttachments] = useState([]); // فایل‌های انتخاب‌شده برای اطلاعیه‌ی متنی (File[])

  const [createMode, setCreateMode] = useState("normal"); // "normal" | "payroll" | "attendance_card"
  const [form, setForm] = useState(EMPTY_FORM);
  const [payrollForm, setPayrollForm] = useState(EMPTY_PAYROLL_FORM);
  const [payrollResult, setPayrollResult] = useState(null); // پاسخ آپلود فیش حقوقی (matched_employee_count، missing_codes، invalid_row_count)
  const [attendanceCardForm, setAttendanceCardForm] = useState(
    EMPTY_ATTENDANCE_CARD_FORM,
  );
  const [attendanceCardResult, setAttendanceCardResult] = useState(null); // پاسخ آپلود فیش کارکرد، با همان ساختار
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // نتیجه نهایی ارسال — با رنگ سبز (موفق) یا قرمز (ناموفق) نمایش داده می‌شود
  const [result, setResult] = useState(null); // { success: boolean, message: string } | null

  const [availableTargets, setAvailableTargets] = useState(null); // مقصدها و مجوزهای ارسال کاربر از سرور؛ null = در حال بارگذاری
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);

  // بارگذاری اولیه مجوزهای ارسال، سایت‌ها و واحدها
  useEffect(() => {
    fetchAvailableTargets().then(setAvailableTargets);
    fetchSites().then(setSites);
    fetchDepartments().then(setDepartments);
  }, []);

  // اگر کاربر مجوز اطلاعیه متنی ندارد و فقط می‌تواند فیش حقوقی/کارکرد بفرستد
  // (مثل acc_manager یا hr-manager)، همان حالت به‌صورت پیش‌فرض انتخاب می‌شود
  useEffect(() => {
    if (!availableTargets) return;
    const hasNormal =
      availableTargets.can_target_all ||
      availableTargets.site_ids.length > 0 ||
      availableTargets.department_ids.length > 0 ||
      availableTargets.can_target_employee;
    if (!hasNormal && availableTargets.can_upload_payroll) {
      setCreateMode("payroll");
    } else if (!hasNormal && availableTargets.can_upload_attendance_card) {
      setCreateMode("attendance_card");
    }
  }, [availableTargets]);

  // محدودیت جستجوی «ارسال به شخص خاص» — اگر کاربر فقط سرپرست واحد است (نه
  // مدیر سایت/میانی)، سرور employee_target_department_ids را برمی‌گرداند و
  // جستجو باید فقط در همان واحد(های) خودش انجام شود، نه کل سازمان.
  // (جست‌وجوی خودِ پرسنل را EmployeeSearchField با همین departmentIds انجام می‌دهد)
  const employeeScopeDepartmentIds =
    availableTargets?.employee_target_department_ids || null;

  // سایت‌ها و واحدهایی که کاربر اجازه ارسال به آن‌ها را دارد
  const allowedSites = useMemo(
    () => sites.filter((s) => availableTargets?.site_ids.includes(s.id)),
    [sites, availableTargets],
  );
  const allowedDepartments = useMemo(
    () =>
      departments.filter((d) =>
        availableTargets?.department_ids.includes(d.id),
      ),
    [departments, availableTargets],
  );

  // کاربر حداقل یک نوع مخاطب برای اطلاعیه متنی دارد
  const canAnyNormalTarget =
    availableTargets &&
    (availableTargets.can_target_all ||
      allowedSites.length > 0 ||
      allowedDepartments.length > 0 ||
      availableTargets.can_target_employee);

  const supervisorOptions = availableTargets?.supervisor_employees || []; // مدیران واحدی که کاربر می‌تواند به آن‌ها ارسال کند
  // نام سایت‌ها برای عنوان گروه‌ها (سایتی که در فهرست نیست: «سایت N»)
  const siteNames = useMemo(() => Object.fromEntries(sites.map((s) => [s.id, s.name])), [sites]);

  // «پیست چند کد پرسنلی» در فیلد اشخاص خاص: چند کد (جداشده با خط جدید/فاصله/ویرگول/تب، ارقام فارسی هم) همه با هم
  // مخاطب می‌شوند. فقط وقتی متن پیست‌شده چند کد عددی است عمل می‌کند؛ پیست یک اسم یا یک کد همان جست‌وجوی عادی است.
  const [pasteResult, setPasteResult] = useState(null); // { busy, added, notFound: [], error }
  function handleEmployeePaste(text) {
    const codes = toEn(text)
      .split(/[\s,،;؛]+/)
      .map((t) => t.trim())
      .filter(Boolean);
    if (codes.length < 2 || !codes.every((c) => /^\d+$/.test(c))) return false;
    setPasteResult({ busy: true, added: 0, notFound: [] });
    resolveNoticeEmployeeCodes(codes)
      .then((res) => {
        const have = new Set(form.employees.map((e) => e.id));
        const extra = [];
        (res.employees || []).forEach((e) => {
          if (!have.has(e.id)) {
            have.add(e.id);
            extra.push(employeeToOption(e));
          }
        });
        setForm((prev) => {
          const ids = new Set(prev.employees.map((e) => e.id));
          return { ...prev, employees: [...prev.employees, ...extra.filter((o) => !ids.has(o.id))] };
        });
        setPasteResult({ busy: false, added: extra.length, notFound: res.not_found || [] });
      })
      .catch(() => setPasteResult({ busy: false, added: 0, notFound: [], error: true }));
    return true;
  }

  // در فیلدهای تک‌خطی (عنوان/زیرعنوان کارت) رفتار پیش‌فرض Enter را غیرفعال می‌کند؛ صفحه <form>
  // ندارد ولی بعضی کیبوردهای موبایل (IME فارسی/ایموجی) Enter را «تأیید» تفسیر می‌کنند.
  function handleTitleKeyDown(e) {
    if (e.key === "Enter") {
      e.preventDefault();
    }
  }

  // در فیلدهای چندخطی Enter همان خط جدید را درج می‌کند؛ فقط از انتشار رویداد به Listenerهای
  // بالاتر جلوگیری می‌شود و رفتار پیش‌فرض textarea تغییر نمی‌کند.
  function handleBodyKeyDown(e) {
    if (e.key === "Enter") {
      e.stopPropagation();
    }
  }

  // ثبت اطلاعیه متنی: فهرست targets را از انتخاب‌ها می‌سازد (سرپرستان و اشخاص بدون تکرار)،
  // مخاطب/عنوان/متن را اعتبارسنجی می‌کند، سپس اطلاعیه را ایجاد و بلافاصله منتشر می‌کند
  async function handleCreate() {
    if (isSubmitting) return; // جلوگیری از ارسال تکراری با کلیک چندباره
    setError("");
    setResult(null);

    const targets = [];
    if (form.targetAll) targets.push({ target_type: "all" });
    form.siteIds.forEach((id) =>
      targets.push({ target_type: "site", target_id: id }),
    );
    form.departmentIds.forEach((id) =>
      targets.push({ target_type: "department", target_id: id }),
    );

    const employeeIds = new Set();
    form.supervisors.forEach((id) => {
      if (!employeeIds.has(id)) {
        employeeIds.add(id);
        targets.push({ target_type: "employee", target_id: id });
      }
    });
    form.employees.forEach((emp) => {
      if (!employeeIds.has(emp.id)) {
        employeeIds.add(emp.id);
        targets.push({ target_type: "employee", target_id: emp.id });
      }
    });

    if (targets.length === 0) {
      setError("حداقل یک مخاطب (سایت، واحد یا شخص) انتخاب کنید.");
      return;
    }
    if (!form.title.trim()) {
      setError("عنوان اطلاعیه را وارد کنید.");
      return;
    }
    if (!form.body.trim()) {
      setError("متن اطلاعیه را وارد کنید.");
      return;
    }

    setIsSubmitting(true);
    let createdId = null;
    let publishing = false; // خطای حین انتشار بدون پاسخ سرور (قطع شبکه) ممکن است یعنی منتشر شده؛ آن‌وقت حذف نمی‌شود
    try {
      const created = await createNotice({
        title: form.title,
        body: form.body,
        priority: form.priority,
        targets,
      });
      createdId = created.id;
      // پیوست‌ها بین ساخت پیش‌نویس و انتشار آپلود می‌شوند؛ تا انتشار هیچ گیرنده‌ای اطلاعیه را نمی‌بیند
      for (const file of canAttach ? attachments : []) {
        try {
          await uploadNoticeAttachment(created.id, file);
        } catch (uploadErr) {
          // نام فایل مشکل‌دار به پیام اضافه می‌شود تا معلوم باشد کدام را باید عوض کرد
          const detail = uploadErr.response?.data?.detail;
          uploadErr.response = uploadErr.response && {
            ...uploadErr.response,
            data: {
              detail: `«${file.name}»: ${typeof detail === "string" ? detail : "آپلود ناموفق بود."}`,
            },
          };
          throw uploadErr;
        }
      }
      publishing = true;
      await publishNotice(created.id);
      createdId = null;
      setResult({
        success: true,
        message: "اطلاعیه با موفقیت ثبت و منتشر شد.",
      });
      setForm(EMPTY_FORM);
      setAttachments([]);
    } catch (err) {
      const message =
        err.response?.data?.detail?.[0]?.msg ||
        err.response?.data?.detail ||
        "ثبت اطلاعیه با خطا مواجه شد.";
      // اگر پیش‌نویس ساخته شد ولی آپلود/انتشار نشد، پیش‌نویس ناقص حذف می‌شود تا با تلاش دوباره تکراری نشود
      if (createdId && (!publishing || err.response))
        deleteNotice(createdId).catch(() => {});
      // خطا کنار دکمه‌ی ارسال نمایش داده می‌شود و فرم (متن، مخاطبان، پیوست‌ها) دست‌نخورده می‌ماند تا با اصلاح دوباره بفرستد
      setError(
        typeof message === "string" ? message : "ثبت اطلاعیه با خطا مواجه شد.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  // اعتبارسنجی و آپلود فایل فیش حقوقی؛ نتیجه شامل تعداد پرسنل منطبق در result و payrollResult قرار می‌گیرد
  async function handleCreatePayroll() {
    if (isSubmitting) return;
    setError("");
    setResult(null);
    setPayrollResult(null);

    if (!payrollForm.title.trim()) {
      setError("عنوان اطلاعیه را وارد کنید.");
      return;
    }
    if (!payrollForm.file) {
      setError("فایل XML فیش حقوقی را انتخاب کنید.");
      return;
    }

    setIsSubmitting(true);
    try {
      const uploadResult = await createPayrollNotice({
        title: payrollForm.title,
        body: payrollForm.body,
        priority: payrollForm.priority,
        file: payrollForm.file,
      });
      setPayrollResult(uploadResult);
      const loanPaid = uploadResult.loan_installments_paid
        ? ` — ${uploadResult.loan_installments_paid} قسط وام از روی همین فیش «پرداخت شد» ثبت شد`
        : "";
      const message = `اطلاعیه فیش حقوقی ارسال شد. تعداد پرسنل منطبق (دریافت‌کننده): ${uploadResult.matched_employee_count}${loanPaid}`;
      setResult({ success: true, message });
    } catch (err) {
      // فرم و فایل انتخاب‌شده می‌مانند؛ فقط پیام خطا نمایش داده می‌شود
      setError(
        err.response?.data?.detail || "آپلود فیش حقوقی با خطا مواجه شد.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  // اعتبارسنجی و آپلود فایل فیش کارکرد به‌همراه متن ماه/سال کارت؛ نتیجه در result و attendanceCardResult
  async function handleCreateAttendanceCard() {
    if (isSubmitting) return;
    setError("");
    setResult(null);
    setAttendanceCardResult(null);

    if (!attendanceCardForm.title.trim()) {
      setError("عنوان اطلاعیه را وارد کنید.");
      return;
    }
    if (!attendanceCardForm.cardSubtitle.trim()) {
      setError(
        "ماه/سالی که روی خودِ کارت چاپ می‌شود را وارد کنید (مثلاً «تیر ماه 1405»).",
      );
      return;
    }
    if (!attendanceCardForm.file) {
      setError("فایل اکسل فیش کارکرد را انتخاب کنید.");
      return;
    }

    setIsSubmitting(true);
    try {
      const uploadResult = await createAttendanceCardNotice({
        title: attendanceCardForm.title,
        body: attendanceCardForm.body,
        priority: attendanceCardForm.priority,
        cardSubtitle: attendanceCardForm.cardSubtitle,
        file: attendanceCardForm.file,
      });
      setAttendanceCardResult(uploadResult);
      const message = `اطلاعیه فیش کارکرد ارسال شد. تعداد پرسنل منطبق (دریافت‌کننده): ${uploadResult.matched_employee_count}`;
      setResult({ success: true, message });
    } catch (err) {
      // فرم و فایل انتخاب‌شده می‌مانند؛ فقط پیام خطا نمایش داده می‌شود
      setError(
        err.response?.data?.detail || "آپلود فیش کارکرد با خطا مواجه شد.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  // همه فرم‌ها و نتایج را پاک می‌کند تا اطلاعیه دیگری ارسال شود
  function handleSendAnother() {
    setResult(null);
    setError("");
    setForm(EMPTY_FORM);
    setAttachments([]);
    setPayrollForm(EMPTY_PAYROLL_FORM);
    setPayrollResult(null);
    setAttendanceCardForm(EMPTY_ATTENDANCE_CARD_FORM);
    setAttendanceCardResult(null);
  }

  // تا بارگذاری مجوزها، نشانگر بارگذاری نمایش داده می‌شود
  if (!availableTargets) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  // کاربری که هیچ مجوز ارسالی ندارد فقط پیام هشدار و دکمه بازگشت را می‌بیند
  if (
    !canAnyNormalTarget &&
    !availableTargets.can_upload_payroll &&
    !availableTargets.can_upload_attendance_card
  ) {
    return (
      <Box sx={{ maxWidth: 640, mx: "auto" }}>
        <BackLink to="/notices" label="بازگشت" />
        <Alert severity="warning">
          شما مجاز به ارسال هیچ نوع اطلاعیه‌ای نیستید.
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      {/* سرصفحه مثل بقیه‌ی صفحه‌ها: دکمه‌ی بازگشت مشترک و عنوان راست‌چین */}
      <BackLink to="/notices" label="بازگشت" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
        اطلاعیه جدید
      </Typography>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        {/* پیام نتیجه ارسال؛ برای فیش‌ها کدهای پیدانشده و تعداد ردیف‌های بدون کد پرسنلی هم اضافه می‌شود */}
        {result && (
          <Alert
            severity={result.success ? "success" : "error"}
            sx={{ mb: 3, whiteSpace: "pre-line" }}
          >
            {result.message}
            {result.success &&
              payrollResult?.missing_codes?.length > 0 &&
              `\nکدهای موجود در فایل که در سامانه پیدا نشدند (${payrollResult.missing_codes.length} مورد) — فیش برای این افراد ارسال نشد:\n${payrollResult.missing_codes.join("، ")}`}
            {result.success &&
              payrollResult?.out_of_scope_codes?.length > 0 &&
              `\nکدهایی که پرسنلشان در سایت‌های خارج از دسترسی شماست (${payrollResult.out_of_scope_codes.length} مورد) — فیش برای این افراد ارسال نشد:\n${payrollResult.out_of_scope_codes.join("، ")}`}
            {result.success &&
              payrollResult?.invalid_row_count > 0 &&
              `\n${payrollResult.invalid_row_count} ردیف در فایل فاقد کد پرسنلی بود و نادیده گرفته شد.`}
            {result.success &&
              attendanceCardResult?.missing_codes?.length > 0 &&
              `\nکدهای موجود در فایل که در سامانه پیدا نشدند (${attendanceCardResult.missing_codes.length} مورد) — کارت برای این افراد ارسال نشد:\n${attendanceCardResult.missing_codes.join("، ")}`}
            {result.success &&
              attendanceCardResult?.out_of_scope_codes?.length > 0 &&
              `\nکدهایی که پرسنلشان در سایت‌های خارج از دسترسی شماست (${attendanceCardResult.out_of_scope_codes.length} مورد) — کارت برای این افراد ارسال نشد:\n${attendanceCardResult.out_of_scope_codes.join("، ")}`}
            {result.success &&
              attendanceCardResult?.invalid_row_count > 0 &&
              `\n${attendanceCardResult.invalid_row_count} ردیف در فایل فاقد کد پرسنلی بود و نادیده گرفته شد.`}
          </Alert>
        )}

        {/* پس از ارسال: دکمه‌های «ارسال اطلاعیه دیگر» و بازگشت؛ در غیر این صورت فرم */}
        {result ? (
          <Stack direction="row" spacing={1.5}>
            <Button variant="contained" onClick={handleSendAnother}>
              ارسال اطلاعیه دیگر
            </Button>
            <Button variant="outlined" onClick={() => navigate("/notices")}>
              بازگشت به اطلاعیه‌ها
            </Button>
          </Stack>
        ) : (
          <Stack spacing={2}>
            {/* تب انتخاب حالت، فقط وقتی کاربر به بیش از یک حالت دسترسی دارد */}
            {(canAnyNormalTarget ? 1 : 0) +
              (availableTargets?.can_upload_payroll ? 1 : 0) +
              (availableTargets?.can_upload_attendance_card ? 1 : 0) >
              1 && (
              <PillTabs
                value={createMode}
                onChange={(k) => {
                  if (isSubmitting) return;
                  setCreateMode(k);
                  setError("");
                }}
                tabs={[
                  ...(canAnyNormalTarget
                    ? [{ key: "normal", label: "اطلاعیه متنی" }]
                    : []),
                  ...(availableTargets?.can_upload_payroll
                    ? [{ key: "payroll", label: "فیش حقوقی" }]
                    : []),
                  ...(availableTargets?.can_upload_attendance_card
                    ? [{ key: "attendance_card", label: "فیش کارکرد" }]
                    : []),
                ]}
                sx={{ mb: 1 }}
              />
            )}

            {/* حالت اطلاعیه متنی */}
            {createMode === "normal" && (
              <>
                <TextField
                  label="عنوان"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  onKeyDown={handleTitleKeyDown}
                  required
                  fullWidth
                  disabled={isSubmitting}
                />
                <TextField
                  label="متن اطلاعیه"
                  value={form.body}
                  onChange={(e) => setForm({ ...form, body: e.target.value })}
                  onKeyDown={handleBodyKeyDown}
                  required
                  multiline
                  minRows={8}
                  maxRows={20}
                  fullWidth
                  disabled={isSubmitting}
                />
                {canAttach && (
                  <NoticeAttachmentPicker
                    files={attachments}
                    onChange={setAttachments}
                    disabled={isSubmitting}
                  />
                )}
                <TextField
                  select
                  label="اولویت"
                  value={form.priority}
                  onChange={(e) =>
                    setForm({ ...form, priority: e.target.value })
                  }
                  disabled={isSubmitting}
                >
                  {Object.entries(PRIORITY_LABELS).map(([value, { label }]) => (
                    <MenuItem key={value} value={value}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>

                <Divider />
                <Typography variant="subtitle2" fontWeight={700}>
                  مخاطبان
                </Typography>

                {/* ارسال به کل سازمان */}
                {availableTargets?.can_target_all && (
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={form.targetAll}
                        onChange={(e) =>
                          setForm({ ...form, targetAll: e.target.checked })
                        }
                        disabled={isSubmitting}
                      />
                    }
                    label="ارسال به کل سازمان (Broadcast)"
                  />
                )}

                {/* انتخاب چند سایت */}
                {allowedSites.length > 0 && (
                  <Autocomplete
                    filterOptions={searchFilterOptions}
                    multiple
                    disabled={isSubmitting}
                    options={allowedSites}
                    getOptionLabel={(s) => s.name}
                    value={allowedSites.filter((s) =>
                      form.siteIds.includes(s.id),
                    )}
                    onChange={(_, selected) =>
                      setForm({ ...form, siteIds: selected.map((s) => s.id) })
                    }
                    renderInput={(params) => (
                      <TextField {...params} label="ارسال به کل این سایت‌ها" />
                    )}
                    renderTags={(value, getTagProps) =>
                      value.map((option, index) => (
                        <Chip
                          size="small"
                          label={option.name}
                          {...getTagProps({ index })}
                          key={option.id}
                        />
                      ))
                    }
                  />
                )}

                {/* انتخاب واحدها با «انتخاب همه»؛ با دسترسی چند سایت، به تفکیک سایت */}
                <GroupedCheckboxes
                  title="ارسال به یک یا چند واحد سازمانی"
                  selectAllLabel="انتخاب همه واحدها"
                  items={allowedDepartments.map((d) => ({ id: d.id, label: d.name, siteId: d.site_id }))}
                  selected={form.departmentIds}
                  onChange={(ids) => setForm((prev) => ({ ...prev, departmentIds: ids }))}
                  siteNames={siteNames}
                  disabled={isSubmitting}
                />

                {/* انتخاب مدیران واحد با «انتخاب همه»؛ با دسترسی چند سایت، به تفکیک سایت */}
                <GroupedCheckboxes
                  title="ارسال به یک یا چند مدیر واحد"
                  selectAllLabel="انتخاب همه مدیران"
                  items={supervisorOptions.map((emp) => ({
                    id: emp.id,
                    siteId: emp.site_id,
                    label: emp.personnel_code
                      ? `${emp.first_name} ${emp.last_name} (${emp.personnel_code})`
                      : `${emp.first_name} ${emp.last_name}`,
                  }))}
                  selected={form.supervisors}
                  onChange={(ids) => setForm((prev) => ({ ...prev, supervisors: ids }))}
                  siteNames={siteNames}
                  disabled={isSubmitting}
                />

                {/* انتخاب اشخاص خاص با انتخابگر مشترک پرسنل (جست‌وجوی سمت سرور؛ در حالت سرپرست محدود به واحدهای خودش) */}
                {availableTargets?.can_target_employee && (
                  <EmployeeSearchField
                    multiple
                    size="medium"
                    disabled={isSubmitting}
                    departmentIds={employeeScopeDepartmentIds || undefined}
                    value={form.employees}
                    onChange={(selected) =>
                      setForm({ ...form, employees: selected || [] })
                    }
                    onPasteText={handleEmployeePaste}
                    helperText="می‌توانید چند کد پرسنلی را یک‌جا کپی و این‌جا پیست کنید"
                    label={
                      employeeScopeDepartmentIds
                        ? "ارسال به یک یا چند نفر از پرسنل واحد خودم (جستجو کنید)"
                        : "ارسال به یک یا چند شخص خاص (جستجو کنید)"
                    }
                  />
                )}
                {pasteResult && (
                  <Alert
                    severity={pasteResult.error ? "error" : pasteResult.notFound.length ? "warning" : "success"}
                    onClose={pasteResult.busy ? undefined : () => setPasteResult(null)}
                  >
                    {pasteResult.busy
                      ? "در حال افزودن کدهای پرسنلی…"
                      : pasteResult.error
                        ? "افزودن کدهای پرسنلی با خطا مواجه شد."
                        : `${pasteResult.added.toLocaleString("fa-IR")} نفر به مخاطبان اضافه شد` +
                          (pasteResult.notFound.length
                            ? ` — ${pasteResult.notFound.length.toLocaleString("fa-IR")} کد پیدا نشد: ${pasteResult.notFound.join("، ")}`
                            : "")}
                  </Alert>
                )}

                <Box>
                  {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      {error}
                    </Alert>
                  )}
                  <Button
                    variant="contained"
                    startIcon={
                      isSubmitting ? (
                        <CircularProgress size={16} color="inherit" />
                      ) : (
                        <SendOutlinedIcon />
                      )
                    }
                    onClick={handleCreate}
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? "در حال ارسال..." : "ثبت و انتشار"}
                  </Button>
                </Box>
              </>
            )}

            {/* حالت فیش حقوقی */}
            {createMode === "payroll" && (
              <>
                <Alert severity="info">
                  فقط کارکنانی که کدشان در فایل باشد، به‌صورت خودکار مخاطب این
                  اطلاعیه می‌شوند — هرکس فقط فیش خودش را می‌بیند.
                </Alert>
                <TextField
                  label="عنوان اطلاعیه"
                  value={payrollForm.title}
                  onChange={(e) =>
                    setPayrollForm({ ...payrollForm, title: e.target.value })
                  }
                  onKeyDown={handleTitleKeyDown}
                  fullWidth
                  disabled={isSubmitting}
                />
                <TextField
                  label="توضیح (اختیاری — برای همه دریافت‌کنندگان یکسان است)"
                  value={payrollForm.body}
                  onChange={(e) =>
                    setPayrollForm({ ...payrollForm, body: e.target.value })
                  }
                  onKeyDown={handleBodyKeyDown}
                  multiline
                  rows={2}
                  fullWidth
                  disabled={isSubmitting}
                />
                <TextField
                  select
                  label="اولویت"
                  value={payrollForm.priority}
                  onChange={(e) =>
                    setPayrollForm({ ...payrollForm, priority: e.target.value })
                  }
                  disabled={isSubmitting}
                >
                  {Object.entries(PRIORITY_LABELS).map(([value, { label }]) => (
                    <MenuItem key={value} value={value}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>
                <Button
                  component="label"
                  variant="outlined"
                  startIcon={<UploadFileOutlinedIcon />}
                  disabled={isSubmitting}
                >
                  {payrollForm.file
                    ? payrollForm.file.name
                    : "انتخاب فایل XML یا XLSX فیش حقوقی"}
                  <input
                    type="file"
                    accept=".xml,text/xml,application/xml,.xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    hidden
                    onChange={(e) =>
                      setPayrollForm({
                        ...payrollForm,
                        file: e.target.files?.[0] || null,
                      })
                    }
                  />
                </Button>

                <Box>
                  {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      {error}
                    </Alert>
                  )}
                  <Button
                    variant="contained"
                    startIcon={
                      isSubmitting ? (
                        <CircularProgress size={16} color="inherit" />
                      ) : (
                        <SendOutlinedIcon />
                      )
                    }
                    onClick={handleCreatePayroll}
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? "در حال آپلود و ارسال..." : "آپلود و ارسال"}
                  </Button>
                </Box>
              </>
            )}

            {/* حالت فیش کارکرد */}
            {createMode === "attendance_card" && (
              <>
                <Alert severity="info">
                  فقط کارکنانی که کدشان در فایل باشد، به‌صورت خودکار مخاطب این
                  اطلاعیه می‌شوند — هرکس فقط کارت کارکرد خودش را می‌بیند.
                </Alert>
                <TextField
                  label="عنوان اطلاعیه"
                  value={attendanceCardForm.title}
                  onChange={(e) =>
                    setAttendanceCardForm({
                      ...attendanceCardForm,
                      title: e.target.value,
                    })
                  }
                  onKeyDown={handleTitleKeyDown}
                  fullWidth
                  disabled={isSubmitting}
                  helperText="این عنوان فقط در لیست اطلاعیه‌های دریافتی نمایش داده می‌شود"
                />
                <TextField
                  label="ماه/سال روی خودِ کارت"
                  value={attendanceCardForm.cardSubtitle}
                  onChange={(e) =>
                    setAttendanceCardForm({
                      ...attendanceCardForm,
                      cardSubtitle: e.target.value,
                    })
                  }
                  onKeyDown={handleTitleKeyDown}
                  fullWidth
                  disabled={isSubmitting}
                  placeholder="مثلاً: تیر ماه 1405"
                  helperText="این متن دقیقاً همان‌طور که وارد می‌کنید، به‌عنوان زیرعنوان روی خودِ کارت PDF چاپ می‌شود"
                />
                <TextField
                  label="توضیح (اختیاری — برای همه دریافت‌کنندگان یکسان است)"
                  value={attendanceCardForm.body}
                  onChange={(e) =>
                    setAttendanceCardForm({
                      ...attendanceCardForm,
                      body: e.target.value,
                    })
                  }
                  onKeyDown={handleBodyKeyDown}
                  multiline
                  rows={2}
                  fullWidth
                  disabled={isSubmitting}
                />
                <TextField
                  select
                  label="اولویت"
                  value={attendanceCardForm.priority}
                  onChange={(e) =>
                    setAttendanceCardForm({
                      ...attendanceCardForm,
                      priority: e.target.value,
                    })
                  }
                  disabled={isSubmitting}
                >
                  {Object.entries(PRIORITY_LABELS).map(([value, { label }]) => (
                    <MenuItem key={value} value={value}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>
                <Button
                  component="label"
                  variant="outlined"
                  startIcon={<UploadFileOutlinedIcon />}
                  disabled={isSubmitting}
                >
                  {attendanceCardForm.file
                    ? attendanceCardForm.file.name
                    : "انتخاب فایل اکسل فیش کارکرد"}
                  <input
                    type="file"
                    accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    hidden
                    onChange={(e) =>
                      setAttendanceCardForm({
                        ...attendanceCardForm,
                        file: e.target.files?.[0] || null,
                      })
                    }
                  />
                </Button>
                {/* نمونه‌ی ساختار فایل فیش کارکرد (فقط شیت قالب، بدون اطلاعات پرسنل) */}
                <Button
                  onClick={async () => {
                    // از API با توکن (فقط دارندگان مجوز ارسال فیش کارکرد)، نه فایل عمومی
                    try {
                      const blob = await downloadAttendanceCardSample();
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = "نمونه-فیش-کارکرد.xlsx";
                      a.click();
                      setTimeout(() => URL.revokeObjectURL(url), 1000);
                    } catch {
                      setError("دانلود فایل نمونه با خطا مواجه شد.");
                    }
                  }}
                  size="small"
                  startIcon={<DownloadOutlinedIcon />}
                  sx={{ alignSelf: "flex-start" }}
                >
                  دانلود فایل نمونه‌ی فیش کارکرد
                </Button>

                <Box>
                  {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      {error}
                    </Alert>
                  )}
                  <Button
                    variant="contained"
                    startIcon={
                      isSubmitting ? (
                        <CircularProgress size={16} color="inherit" />
                      ) : (
                        <SendOutlinedIcon />
                      )
                    }
                    onClick={handleCreateAttendanceCard}
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? "در حال آپلود و ارسال..." : "آپلود و ارسال"}
                  </Button>
                </Box>
              </>
            )}
          </Stack>
        )}
      </Card>
    </Box>
  );
}
