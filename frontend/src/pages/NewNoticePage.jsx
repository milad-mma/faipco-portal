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
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import ArrowForwardOutlinedIcon from "@mui/icons-material/ArrowForwardOutlined";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import {
  createAttendanceCardNotice,
  createNotice,
  createPayrollNotice,
  fetchAvailableTargets,
  publishNotice,
} from "../api/notices";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { fetchEmployees } from "../api/employees";
import PillTabs from "../components/PillTabs";

// برچسب و رنگ گزینه‌های اولویت
const PRIORITY_LABELS = {
  low: { label: "کم", color: "default" },
  normal: { label: "عادی", color: "info" },
  high: { label: "بالا", color: "warning" },
  urgent: { label: "فوری", color: "error" },
};

// مقدار اولیه فرم اطلاعیه متنی (employees: اشیای پرسنل انتخاب‌شده، supervisors: id سرپرستان)
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
export default function NewNoticePage() {
  const navigate = useNavigate();

  const [createMode, setCreateMode] = useState("normal"); // "normal" | "payroll" | "attendance_card"
  const [form, setForm] = useState(EMPTY_FORM);
  const [payrollForm, setPayrollForm] = useState(EMPTY_PAYROLL_FORM);
  const [payrollResult, setPayrollResult] = useState(null);  // پاسخ آپلود فیش حقوقی (matched_employee_count، missing_codes، invalid_row_count)
  const [attendanceCardForm, setAttendanceCardForm] = useState(EMPTY_ATTENDANCE_CARD_FORM);
  const [attendanceCardResult, setAttendanceCardResult] = useState(null);  // پاسخ آپلود فیش کارکرد، با همان ساختار
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // نتیجه نهایی ارسال — با رنگ سبز (موفق) یا قرمز (ناموفق) نمایش داده می‌شود
  const [result, setResult] = useState(null); // { success: boolean, message: string } | null

  const [availableTargets, setAvailableTargets] = useState(null);  // مقصدها و مجوزهای ارسال کاربر از سرور؛ null = در حال بارگذاری
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);

  const [employeeSearch, setEmployeeSearch] = useState("");
  const [employeeOptions, setEmployeeOptions] = useState([]);  // نتایج جست‌وجوی پرسنل برای «ارسال به شخص خاص»
  const [employeeSearchLoading, setEmployeeSearchLoading] = useState(false);

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
  const employeeScopeDepartmentIds = availableTargets?.employee_target_department_ids || null;

  // جست‌وجوی پرسنل با تأخیر ۳۰۰ میلی‌ثانیه (debounce)، محدود به واحدهای مجاز در صورت وجود
  useEffect(() => {
    if (!employeeSearch) {
      setEmployeeOptions([]);
      return;
    }
    setEmployeeSearchLoading(true);
    const timer = setTimeout(() => {
      fetchEmployees({
        search: employeeSearch,
        departmentIds: employeeScopeDepartmentIds || undefined,
      })
        .then((data) => setEmployeeOptions(data.items))
        .finally(() => setEmployeeSearchLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [employeeSearch, employeeScopeDepartmentIds]);

  // سایت‌ها و واحدهایی که کاربر اجازه ارسال به آن‌ها را دارد
  const allowedSites = useMemo(
    () => sites.filter((s) => availableTargets?.site_ids.includes(s.id)),
    [sites, availableTargets]
  );
  const allowedDepartments = useMemo(
    () => departments.filter((d) => availableTargets?.department_ids.includes(d.id)),
    [departments, availableTargets]
  );

  // کاربر حداقل یک نوع مخاطب برای اطلاعیه متنی دارد
  const canAnyNormalTarget =
    availableTargets &&
    (availableTargets.can_target_all ||
      allowedSites.length > 0 ||
      allowedDepartments.length > 0 ||
      availableTargets.can_target_employee);

  const allDepartmentsSelected =  // همه واحدهای مجاز انتخاب شده‌اند
    allowedDepartments.length > 0 && form.departmentIds.length === allowedDepartments.length;

  // افزودن/حذف یک واحد از مخاطبان
  function toggleDepartment(deptId) {
    setForm((prev) => ({
      ...prev,
      departmentIds: prev.departmentIds.includes(deptId)
        ? prev.departmentIds.filter((id) => id !== deptId)
        : [...prev.departmentIds, deptId],
    }));
  }

  // انتخاب همه واحدهای مجاز یا پاک کردن همه
  function toggleSelectAllDepartments() {
    setForm((prev) => ({
      ...prev,
      departmentIds: allDepartmentsSelected ? [] : allowedDepartments.map((d) => d.id),
    }));
  }

  const supervisorOptions = availableTargets?.supervisor_employees || [];  // سرپرستانی که کاربر می‌تواند به آن‌ها ارسال کند
  const allSupervisorsSelected =
    supervisorOptions.length > 0 && form.supervisors.length === supervisorOptions.length;

  // افزودن/حذف یک سرپرست از مخاطبان
  function toggleSupervisor(employeeId) {
    setForm((prev) => ({
      ...prev,
      supervisors: prev.supervisors.includes(employeeId)
        ? prev.supervisors.filter((id) => id !== employeeId)
        : [...prev.supervisors, employeeId],
    }));
  }

  // انتخاب همه سرپرستان یا پاک کردن همه
  function toggleSelectAllSupervisors() {
    setForm((prev) => ({
      ...prev,
      supervisors: allSupervisorsSelected ? [] : supervisorOptions.map((e) => e.id),
    }));
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
    form.siteIds.forEach((id) => targets.push({ target_type: "site", target_id: id }));
    form.departmentIds.forEach((id) => targets.push({ target_type: "department", target_id: id }));

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
    try {
      const created = await createNotice({
        title: form.title,
        body: form.body,
        priority: form.priority,
        targets,
      });
      await publishNotice(created.id);
      setResult({ success: true, message: "اطلاعیه با موفقیت ثبت و منتشر شد." });
      setForm(EMPTY_FORM);
    } catch (err) {
      const message =
        err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || "ثبت اطلاعیه با خطا مواجه شد.";
      setResult({ success: false, message });
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
      const message = `اطلاعیه فیش حقوقی ارسال شد. تعداد پرسنل منطبق (دریافت‌کننده): ${uploadResult.matched_employee_count}`;
      setResult({ success: true, message });
    } catch (err) {
      setResult({
        success: false,
        message: err.response?.data?.detail || "آپلود فیش حقوقی با خطا مواجه شد.",
      });
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
      setError("ماه/سالی که روی خودِ کارت چاپ می‌شود را وارد کنید (مثلاً «تیر ماه 1405»).");
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
      setResult({
        success: false,
        message: err.response?.data?.detail || "آپلود فیش کارکرد با خطا مواجه شد.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  // همه فرم‌ها و نتایج را پاک می‌کند تا اطلاعیه دیگری ارسال شود
  function handleSendAnother() {
    setResult(null);
    setError("");
    setForm(EMPTY_FORM);
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
  if (!canAnyNormalTarget && !availableTargets.can_upload_payroll && !availableTargets.can_upload_attendance_card) {
    return (
      <Box sx={{ maxWidth: 640, mx: "auto" }}>
        <Button startIcon={<ArrowForwardOutlinedIcon />} onClick={() => navigate("/notices")} sx={{ mb: 2 }}>
          بازگشت
        </Button>
        <Alert severity="warning">شما مجاز به ارسال هیچ نوع اطلاعیه‌ای نیستید.</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 3 }}>
        <Button startIcon={<ArrowForwardOutlinedIcon />} onClick={() => navigate("/notices")}>
          بازگشت
        </Button>
        <Typography variant="h5" fontWeight={700}>
          اطلاعیه جدید
        </Typography>
      </Stack>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        {/* پیام نتیجه ارسال؛ برای فیش‌ها کدهای پیدانشده و تعداد ردیف‌های بدون کد پرسنلی هم اضافه می‌شود */}
        {result && (
          <Alert severity={result.success ? "success" : "error"} sx={{ mb: 3, whiteSpace: "pre-line" }}>
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
            {((canAnyNormalTarget ? 1 : 0) +
              (availableTargets?.can_upload_payroll ? 1 : 0) +
              (availableTargets?.can_upload_attendance_card ? 1 : 0)) > 1 && (
              <PillTabs
                value={createMode}
                onChange={(k) => {
                  if (isSubmitting) return;
                  setCreateMode(k);
                  setError("");
                }}
                tabs={[
                  ...(canAnyNormalTarget ? [{ key: "normal", label: "اطلاعیه متنی" }] : []),
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
                  rows={3}
                  fullWidth
                  disabled={isSubmitting}
                />
                <TextField
                  select
                  label="اولویت"
                  value={form.priority}
                  onChange={(e) => setForm({ ...form, priority: e.target.value })}
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
                        onChange={(e) => setForm({ ...form, targetAll: e.target.checked })}
                        disabled={isSubmitting}
                      />
                    }
                    label="ارسال به کل سازمان (Broadcast)"
                  />
                )}

                {/* انتخاب چند سایت */}
                {allowedSites.length > 0 && (
                  <Autocomplete
                    multiple
                    disabled={isSubmitting}
                    options={allowedSites}
                    getOptionLabel={(s) => s.name}
                    value={allowedSites.filter((s) => form.siteIds.includes(s.id))}
                    onChange={(_, selected) => setForm({ ...form, siteIds: selected.map((s) => s.id) })}
                    renderInput={(params) => <TextField {...params} label="ارسال به کل این سایت‌ها" />}
                    renderTags={(value, getTagProps) =>
                      value.map((option, index) => (
                        <Chip size="small" label={option.name} {...getTagProps({ index })} key={option.id} />
                      ))
                    }
                  />
                )}

                {/* انتخاب واحدها با گزینه «انتخاب همه» */}
                {allowedDepartments.length > 0 && (
                  <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5 }}>
                    <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                      ارسال به یک یا چند واحد سازمانی
                    </Typography>
                    {allowedDepartments.length > 1 && (
                      <>
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={allDepartmentsSelected}
                              indeterminate={form.departmentIds.length > 0 && !allDepartmentsSelected}
                              onChange={toggleSelectAllDepartments}
                              disabled={isSubmitting}
                            />
                          }
                          label={<Typography fontWeight={600}>انتخاب همه واحدها</Typography>}
                        />
                        <Divider sx={{ my: 0.5 }} />
                      </>
                    )}
                    <FormGroup row>
                      {allowedDepartments.map((dept) => (
                        <FormControlLabel
                          key={dept.id}
                          sx={{ minWidth: 0 }}
                          control={
                            <Checkbox
                              checked={form.departmentIds.includes(dept.id)}
                              onChange={() => toggleDepartment(dept.id)}
                              disabled={isSubmitting}
                            />
                          }
                          label={dept.name}
                        />
                      ))}
                    </FormGroup>
                  </Box>
                )}

                {/* انتخاب سرپرستان واحد با گزینه «انتخاب همه» */}
                {supervisorOptions.length > 0 && (
                  <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5 }}>
                    <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                      ارسال به یک یا چند سرپرست واحد
                    </Typography>
                    {supervisorOptions.length > 1 && (
                      <>
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={allSupervisorsSelected}
                              indeterminate={form.supervisors.length > 0 && !allSupervisorsSelected}
                              onChange={toggleSelectAllSupervisors}
                              disabled={isSubmitting}
                            />
                          }
                          label={<Typography fontWeight={600}>انتخاب همه سرپرستان</Typography>}
                        />
                        <Divider sx={{ my: 0.5 }} />
                      </>
                    )}
                    <FormGroup row>
                      {supervisorOptions.map((emp) => (
                        <FormControlLabel
                          key={emp.id}
                          sx={{ minWidth: 0 }}
                          control={
                            <Checkbox
                              checked={form.supervisors.includes(emp.id)}
                              onChange={() => toggleSupervisor(emp.id)}
                              disabled={isSubmitting}
                            />
                          }
                          label={`${emp.first_name} ${emp.last_name} (${emp.personnel_code})`}
                        />
                      ))}
                    </FormGroup>
                  </Box>
                )}

                {/* انتخاب اشخاص خاص با جست‌وجوی سمت سرور (filterOptions بدون فیلتر محلی) */}
                {availableTargets?.can_target_employee && (
                  <Autocomplete
                    multiple
                    disabled={isSubmitting}
                    options={employeeOptions}
                    loading={employeeSearchLoading}
                    filterOptions={(x) => x}
                    getOptionLabel={(e) => `${e.first_name} ${e.last_name} (${e.personnel_code})`}
                    isOptionEqualToValue={(a, b) => a.id === b.id}
                    value={form.employees}
                    onChange={(_, selected) => setForm({ ...form, employees: selected })}
                    onInputChange={(_, value) => setEmployeeSearch(value)}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label={
                          employeeScopeDepartmentIds
                            ? "ارسال به یک یا چند نفر از پرسنل واحد خودم (جستجو کنید)"
                            : "ارسال به یک یا چند شخص خاص (جستجو کنید)"
                        }
                      />
                    )}
                    renderTags={(value, getTagProps) =>
                      value.map((option, index) => (
                        <Chip
                          size="small"
                          label={`${option.first_name} ${option.last_name}`}
                          {...getTagProps({ index })}
                          key={option.id}
                        />
                      ))
                    }
                    noOptionsText="برای جستجو تایپ کنید..."
                  />
                )}

                <Box>
                  {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                  <Button
                    variant="contained"
                    startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : <SendOutlinedIcon />}
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
                  فقط کارکنانی که کدشان در فایل باشد، به‌صورت خودکار مخاطب این اطلاعیه می‌شوند —
                  هرکس فقط فیش خودش را می‌بیند.
                </Alert>
                <TextField
                  label="عنوان اطلاعیه"
                  value={payrollForm.title}
                  onChange={(e) => setPayrollForm({ ...payrollForm, title: e.target.value })}
                  onKeyDown={handleTitleKeyDown}
                  fullWidth
                  disabled={isSubmitting}
                />
                <TextField
                  label="توضیح (اختیاری — برای همه دریافت‌کنندگان یکسان است)"
                  value={payrollForm.body}
                  onChange={(e) => setPayrollForm({ ...payrollForm, body: e.target.value })}
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
                  onChange={(e) => setPayrollForm({ ...payrollForm, priority: e.target.value })}
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
                  {payrollForm.file ? payrollForm.file.name : "انتخاب فایل XML یا XLSX فیش حقوقی"}
                  <input
                    type="file"
                    accept=".xml,text/xml,application/xml,.xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    hidden
                    onChange={(e) => setPayrollForm({ ...payrollForm, file: e.target.files?.[0] || null })}
                  />
                </Button>

                <Box>
                  {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                  <Button
                    variant="contained"
                    startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : <SendOutlinedIcon />}
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
                  فقط کارکنانی که کدشان در فایل باشد، به‌صورت خودکار مخاطب این اطلاعیه می‌شوند —
                  هرکس فقط کارت کارکرد خودش را می‌بیند.
                </Alert>
                <TextField
                  label="عنوان اطلاعیه"
                  value={attendanceCardForm.title}
                  onChange={(e) => setAttendanceCardForm({ ...attendanceCardForm, title: e.target.value })}
                  onKeyDown={handleTitleKeyDown}
                  fullWidth
                  disabled={isSubmitting}
                  helperText="این عنوان فقط در لیست اطلاعیه‌های دریافتی نمایش داده می‌شود"
                />
                <TextField
                  label="ماه/سال روی خودِ کارت"
                  value={attendanceCardForm.cardSubtitle}
                  onChange={(e) => setAttendanceCardForm({ ...attendanceCardForm, cardSubtitle: e.target.value })}
                  onKeyDown={handleTitleKeyDown}
                  fullWidth
                  disabled={isSubmitting}
                  placeholder="مثلاً: تیر ماه 1405"
                  helperText="این متن دقیقاً همان‌طور که وارد می‌کنید، به‌عنوان زیرعنوان روی خودِ کارت PDF چاپ می‌شود"
                />
                <TextField
                  label="توضیح (اختیاری — برای همه دریافت‌کنندگان یکسان است)"
                  value={attendanceCardForm.body}
                  onChange={(e) => setAttendanceCardForm({ ...attendanceCardForm, body: e.target.value })}
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
                  onChange={(e) => setAttendanceCardForm({ ...attendanceCardForm, priority: e.target.value })}
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
                  {attendanceCardForm.file ? attendanceCardForm.file.name : "انتخاب فایل اکسل فیش کارکرد"}
                  <input
                    type="file"
                    accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    hidden
                    onChange={(e) =>
                      setAttendanceCardForm({ ...attendanceCardForm, file: e.target.files?.[0] || null })
                    }
                  />
                </Button>

                <Box>
                  {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                  <Button
                    variant="contained"
                    startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : <SendOutlinedIcon />}
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
