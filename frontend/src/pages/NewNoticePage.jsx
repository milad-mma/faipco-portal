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
  createNotice,
  createPayrollNotice,
  fetchAvailableTargets,
  publishNotice,
} from "../api/notices";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { fetchEmployees } from "../api/employees";

const PRIORITY_LABELS = {
  low: { label: "کم", color: "default" },
  normal: { label: "عادی", color: "info" },
  high: { label: "بالا", color: "warning" },
  urgent: { label: "فوری", color: "error" },
};

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

const EMPTY_PAYROLL_FORM = {
  title: "فیش حقوقی",
  body: "",
  priority: "normal",
  file: null,
};

export default function NewNoticePage() {
  const navigate = useNavigate();

  const [createMode, setCreateMode] = useState("normal"); // "normal" | "payroll"
  const [form, setForm] = useState(EMPTY_FORM);
  const [payrollForm, setPayrollForm] = useState(EMPTY_PAYROLL_FORM);
  const [payrollResult, setPayrollResult] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // نتیجه نهایی ارسال — با رنگ سبز (موفق) یا قرمز (ناموفق) نمایش داده می‌شود
  const [result, setResult] = useState(null); // { success: boolean, message: string } | null

  const [availableTargets, setAvailableTargets] = useState(null);
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);

  const [employeeSearch, setEmployeeSearch] = useState("");
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearchLoading, setEmployeeSearchLoading] = useState(false);

  useEffect(() => {
    fetchAvailableTargets().then(setAvailableTargets);
    fetchSites().then(setSites);
    fetchDepartments().then(setDepartments);
  }, []);

  // اگر کاربر فقط می‌تواند فیش حقوقی بفرستد (مثل acc_manager)، مستقیم همان حالت باز شود
  useEffect(() => {
    if (!availableTargets) return;
    const hasNormal =
      availableTargets.can_target_all ||
      availableTargets.site_ids.length > 0 ||
      availableTargets.department_ids.length > 0 ||
      availableTargets.can_target_employee;
    if (!hasNormal && availableTargets.can_upload_payroll) {
      setCreateMode("payroll");
    }
  }, [availableTargets]);

  // محدودیت جستجوی «ارسال به شخص خاص» — اگر کاربر فقط سرپرست واحد است (نه
  // مدیر سایت/میانی)، سرور employee_target_department_ids را برمی‌گرداند و
  // جستجو باید فقط در همان واحد(های) خودش انجام شود، نه کل سازمان.
  const employeeScopeDepartmentIds = availableTargets?.employee_target_department_ids || null;

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
        .then(setEmployeeOptions)
        .finally(() => setEmployeeSearchLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [employeeSearch, employeeScopeDepartmentIds]);

  const allowedSites = useMemo(
    () => sites.filter((s) => availableTargets?.site_ids.includes(s.id)),
    [sites, availableTargets]
  );
  const allowedDepartments = useMemo(
    () => departments.filter((d) => availableTargets?.department_ids.includes(d.id)),
    [departments, availableTargets]
  );

  const canAnyNormalTarget =
    availableTargets &&
    (availableTargets.can_target_all ||
      allowedSites.length > 0 ||
      allowedDepartments.length > 0 ||
      availableTargets.can_target_employee);

  const allDepartmentsSelected =
    allowedDepartments.length > 0 && form.departmentIds.length === allowedDepartments.length;

  function toggleDepartment(deptId) {
    setForm((prev) => ({
      ...prev,
      departmentIds: prev.departmentIds.includes(deptId)
        ? prev.departmentIds.filter((id) => id !== deptId)
        : [...prev.departmentIds, deptId],
    }));
  }

  function toggleSelectAllDepartments() {
    setForm((prev) => ({
      ...prev,
      departmentIds: allDepartmentsSelected ? [] : allowedDepartments.map((d) => d.id),
    }));
  }

  const supervisorOptions = availableTargets?.supervisor_employees || [];
  const allSupervisorsSelected =
    supervisorOptions.length > 0 && form.supervisors.length === supervisorOptions.length;

  function toggleSupervisor(employeeId) {
    setForm((prev) => ({
      ...prev,
      supervisors: prev.supervisors.includes(employeeId)
        ? prev.supervisors.filter((id) => id !== employeeId)
        : [...prev.supervisors, employeeId],
    }));
  }

  function toggleSelectAllSupervisors() {
    setForm((prev) => ({
      ...prev,
      supervisors: allSupervisorsSelected ? [] : supervisorOptions.map((e) => e.id),
    }));
  }

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
        err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || "ثبت اطلاعیه ناموفق بود.";
      setResult({ success: false, message });
    } finally {
      setIsSubmitting(false);
    }
  }

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
        message: err.response?.data?.detail || "آپلود فیش حقوقی ناموفق بود.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleSendAnother() {
    setResult(null);
    setError("");
    setForm(EMPTY_FORM);
    setPayrollForm(EMPTY_PAYROLL_FORM);
    setPayrollResult(null);
  }

  if (!availableTargets) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!canAnyNormalTarget && !availableTargets.can_upload_payroll) {
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
        {result && (
          <Alert severity={result.success ? "success" : "error"} sx={{ mb: 3, whiteSpace: "pre-line" }}>
            {result.message}
            {result.success &&
              payrollResult?.missing_codes?.length > 0 &&
              `\nکدهای موجود در فایل که در سامانه پیدا نشدند (${payrollResult.missing_codes.length} مورد) — فیش برای این افراد ارسال نشد:\n${payrollResult.missing_codes.join("، ")}`}
            {result.success &&
              payrollResult?.invalid_row_count > 0 &&
              `\n${payrollResult.invalid_row_count} ردیف در فایل فاقد کد پرسنلی بود و نادیده گرفته شد.`}
          </Alert>
        )}

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
            {error && <Alert severity="error">{error}</Alert>}

            {canAnyNormalTarget && availableTargets?.can_upload_payroll && (
              <Tabs
                value={createMode}
                onChange={(_, v) => {
                  setCreateMode(v);
                  setError("");
                }}
                variant="fullWidth"
                sx={{ mb: 1 }}
              >
                <Tab value="normal" label="اطلاعیه متنی" disabled={isSubmitting} />
                <Tab value="payroll" label="فیش حقوقی (Payroll)" disabled={isSubmitting} />
              </Tabs>
            )}

            {createMode === "normal" && (
              <>
                <TextField
                  label="عنوان"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  fullWidth
                  disabled={isSubmitting}
                />
                <TextField
                  label="متن اطلاعیه"
                  value={form.body}
                  onChange={(e) => setForm({ ...form, body: e.target.value })}
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
                  fullWidth
                  disabled={isSubmitting}
                />
                <TextField
                  label="توضیح (اختیاری — برای همه دریافت‌کنندگان یکسان است)"
                  value={payrollForm.body}
                  onChange={(e) => setPayrollForm({ ...payrollForm, body: e.target.value })}
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
          </Stack>
        )}
      </Card>
    </Box>
  );
}
