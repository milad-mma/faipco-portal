import { useEffect, useState } from "react";
import {
  Alert,
  Autocomplete,
  Backdrop,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import MailOutlineIcon from "@mui/icons-material/MailOutline";
import DraftsOutlinedIcon from "@mui/icons-material/DraftsOutlined";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";
import {
  createNotice,
  createPayrollNotice,
  fetchAvailableTargets,
  fetchMyNotices,
  fetchMyPayrollReceiptBlob,
  fetchSentByMe,
  markNoticeRead,
  publishNotice,
} from "../api/notices";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { fetchEmployees } from "../api/employees";
import NoticeReportTable from "../components/NoticeReportTable";

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

async function downloadPayrollReceipt(noticeId, setDownloadError) {
  setDownloadError("");
  try {
    const blob = await fetchMyPayrollReceiptBlob(noticeId);
    const url = window.URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    setDownloadError(
      err.response?.status === 404
        ? "فیشی برای شما در این اطلاعیه یافت نشد."
        : "دانلود فیش ناموفق بود."
    );
  }
}

function ReceivedNoticeCard({ notice, onOpened }) {
  const [expanded, setExpanded] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const isUnread = !notice.is_read;
  const isPayroll = notice.notice_type === "payroll";

  function handleToggle() {
    if (!expanded && isUnread) {
      markNoticeRead(notice.id).catch(() => {});
      onOpened?.(notice.id);
    }
    setExpanded((v) => !v);
  }

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        overflow: "hidden",
        borderInlineStart: isUnread ? "4px solid" : "4px solid transparent",
        borderInlineStartColor: isUnread ? "secondary.main" : "transparent",
        backgroundColor: isUnread ? "rgba(224, 164, 88, 0.06)" : "transparent",
      }}
    >
      <Box
        onClick={handleToggle}
        sx={{
          p: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
          gap: 2,
          "&:hover": { backgroundColor: "action.hover" },
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minWidth: 0 }}>
          {isUnread ? <MailOutlineIcon color="secondary" /> : <DraftsOutlinedIcon color="disabled" />}
          <Box sx={{ minWidth: 0 }}>
            <Typography
              variant="body1"
              fontWeight={isUnread ? 700 : 400}
              color={isUnread ? "text.primary" : "text.secondary"}
              noWrap
            >
              {notice.title}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {new Date(notice.created_at).toLocaleString("fa-IR")}
            </Typography>
          </Box>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          {isPayroll && <Chip size="small" label="فیش حقوقی" color="secondary" variant="outlined" />}
          <Chip
            size="small"
            label={PRIORITY_LABELS[notice.priority]?.label}
            color={PRIORITY_LABELS[notice.priority]?.color}
          />
        </Stack>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2 }}>
          {notice.body && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: isPayroll ? 1.5 : 0 }}>
              {notice.body}
            </Typography>
          )}
          {isPayroll && (
            <>
              {notice.has_my_payroll_receipt ? (
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<PictureAsPdfOutlinedIcon />}
                  onClick={(e) => {
                    e.stopPropagation();
                    downloadPayrollReceipt(notice.id, setDownloadError);
                  }}
                >
                  دانلود فیش من (PDF)
                </Button>
              ) : (
                <Typography variant="caption" color="text.secondary">
                  فیشی برای شما در این اطلاعیه یافت نشد.
                </Typography>
              )}
              {downloadError && (
                <Alert severity="error" sx={{ mt: 1 }}>
                  {downloadError}
                </Alert>
              )}
            </>
          )}
        </Box>
      </Collapse>
    </Card>
  );
}

export default function NoticesPage() {
  const [tab, setTab] = useState("received");
  const [notices, setNotices] = useState([]);
  const [sentNotices, setSentNotices] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [createMode, setCreateMode] = useState("normal"); // "normal" | "payroll"
  const [form, setForm] = useState(EMPTY_FORM);
  const [payrollForm, setPayrollForm] = useState(EMPTY_PAYROLL_FORM);
  const [payrollResult, setPayrollResult] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [availableTargets, setAvailableTargets] = useState(null);
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);

  const [employeeSearch, setEmployeeSearch] = useState("");
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearchLoading, setEmployeeSearchLoading] = useState(false);

  function loadNotices() {
    fetchMyNotices().then(setNotices);
  }

  function loadSentNotices() {
    fetchSentByMe().then(setSentNotices);
  }

  useEffect(() => {
    loadNotices();
    fetchAvailableTargets().then(setAvailableTargets);
    fetchSites().then(setSites);
    fetchDepartments().then(setDepartments);
  }, []);

  // پیام از Service Worker وقتی یک Push جدید می‌رسد — لیست را بدون Reload
  // صفحه، دوباره از سرور می‌خوانیم (چه در تب دریافتی، چه ارسالی من).
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    function handleMessage(event) {
      if (event.data?.type === "faipco-notice-push") {
        loadNotices();
        if (tab === "sent") loadSentNotices();
      }
    }
    navigator.serviceWorker.addEventListener("message", handleMessage);
    return () => navigator.serviceWorker.removeEventListener("message", handleMessage);
  }, [tab]);

  useEffect(() => {
    if (tab === "sent") loadSentNotices();
  }, [tab]);

  useEffect(() => {
    if (!employeeSearch) {
      setEmployeeOptions([]);
      return;
    }
    setEmployeeSearchLoading(true);
    const timer = setTimeout(() => {
      fetchEmployees({ search: employeeSearch })
        .then(setEmployeeOptions)
        .finally(() => setEmployeeSearchLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [employeeSearch]);

  const canCreateAnything =
    availableTargets &&
    (availableTargets.can_target_all ||
      availableTargets.site_ids.length > 0 ||
      availableTargets.department_ids.length > 0 ||
      availableTargets.can_target_employee ||
      availableTargets.can_upload_payroll);

  const allowedSites = sites.filter((s) => availableTargets?.site_ids.includes(s.id));
  const allowedDepartments = departments.filter((d) => availableTargets?.department_ids.includes(d.id));

  const canAnyNormalTarget =
    availableTargets &&
    (availableTargets.can_target_all ||
      allowedSites.length > 0 ||
      allowedDepartments.length > 0 ||
      availableTargets.can_target_employee);

  function openDialog() {
    setError("");
    setForm(EMPTY_FORM);
    setPayrollForm(EMPTY_PAYROLL_FORM);
    setPayrollResult(null);
    setEmployeeSearch("");
    setEmployeeOptions([]);
    // اگر کاربر فقط می‌تواند فیش حقوقی بفرستد (مثل acc_manager)، مستقیم همان حالت باز شود
    setCreateMode(!canAnyNormalTarget && availableTargets?.can_upload_payroll ? "payroll" : "normal");
    setDialogOpen(true);
  }

  function handleMarkedRead(noticeId) {
    setNotices((prev) => prev.map((n) => (n.id === noticeId ? { ...n, is_read: true } : n)));
  }

  async function handleCreate() {
    if (isSubmitting) return; // جلوگیری از ارسال تکراری با کلیک چندباره
    setError("");

    const targets = [];
    if (form.targetAll) targets.push({ target_type: "all" });
    form.siteIds.forEach((id) => targets.push({ target_type: "site", target_id: id }));
    form.departmentIds.forEach((id) => targets.push({ target_type: "department", target_id: id }));

    const employeeIds = new Set();
    [...form.employees, ...form.supervisors].forEach((emp) => {
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
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      loadNotices();
      if (tab === "sent") loadSentNotices();
    } catch (err) {
      setError(err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || "ثبت اطلاعیه ناموفق بود");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreatePayroll() {
    if (isSubmitting) return;
    setError("");
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
      const result = await createPayrollNotice({
        title: payrollForm.title,
        body: payrollForm.body,
        priority: payrollForm.priority,
        file: payrollForm.file,
      });
      setPayrollResult(result);
      loadNotices();
      if (tab === "sent") loadSentNotices();
    } catch (err) {
      setError(err.response?.data?.detail || "آپلود فیش حقوقی ناموفق بود");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            اطلاعیه‌ها
          </Typography>
        </Box>
        {canCreateAnything && (
          <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={openDialog}>
            اطلاعیه جدید
          </Button>
        )}
      </Box>

      {canCreateAnything && (
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
          <Tab value="received" label="دریافتی" />
          <Tab value="sent" label="ارسالی من" />
        </Tabs>
      )}

      {tab === "received" && (
        <Stack spacing={1.5}>
          {notices.length === 0 && (
            <Card variant="outlined" sx={{ p: 4, borderRadius: 3, textAlign: "center" }}>
              <Typography variant="body2" color="text.secondary">
                در حال حاضر اطلاعیه‌ای برای شما ثبت نشده است.
              </Typography>
            </Card>
          )}
          {notices.map((notice) => (
            <ReceivedNoticeCard key={notice.id} notice={notice} onOpened={handleMarkedRead} />
          ))}
        </Stack>
      )}

      {tab === "sent" && (
        <Card variant="outlined" sx={{ borderRadius: 3, p: 1 }}>
          <NoticeReportTable
            notices={sentNotices}
            showSender={false}
            allowDelete
            onChanged={loadSentNotices}
          />
        </Card>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => !isSubmitting && setDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>اطلاعیه جدید</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1, position: "relative" }}>
          {/* حین ارسال، کل فرم غیرقابل‌دستکاری می‌شود تا کلیک چندباره ممکن نباشد */}
          <Backdrop
            open={isSubmitting}
            sx={{
              position: "absolute",
              zIndex: 10,
              backgroundColor: "rgba(255,255,255,0.7)",
              borderRadius: 2,
            }}
          >
            <Stack alignItems="center" spacing={1}>
              <CircularProgress size={32} />
              <Typography variant="caption" color="text.secondary">
                در حال ثبت و انتشار...
              </Typography>
            </Stack>
          </Backdrop>

          {error && <Alert severity="error">{error}</Alert>}

          {canAnyNormalTarget && availableTargets?.can_upload_payroll && (
            <Tabs
              value={createMode}
              onChange={(_, v) => {
                setCreateMode(v);
                setError("");
                setPayrollResult(null);
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

              <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 1 }}>
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
                <Autocomplete
                  multiple
                  disabled={isSubmitting}
                  options={allowedDepartments}
                  getOptionLabel={(d) => d.name}
                  value={allowedDepartments.filter((d) => form.departmentIds.includes(d.id))}
                  onChange={(_, selected) => setForm({ ...form, departmentIds: selected.map((d) => d.id) })}
                  renderInput={(params) => <TextField {...params} label="ارسال به یک یا چند واحد سازمانی" />}
                  renderTags={(value, getTagProps) =>
                    value.map((option, index) => (
                      <Chip size="small" label={option.name} {...getTagProps({ index })} key={option.id} />
                    ))
                  }
                />
              )}

              {availableTargets?.supervisor_employees?.length > 0 && (
                <Autocomplete
                  multiple
                  disabled={isSubmitting}
                  options={availableTargets.supervisor_employees}
                  getOptionLabel={(e) => `${e.first_name} ${e.last_name} (${e.personnel_code})`}
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                  value={form.supervisors}
                  onChange={(_, selected) => setForm({ ...form, supervisors: selected })}
                  renderInput={(params) => (
                    <TextField {...params} label="میان‌بر: ارسال به یک یا چند سرپرست واحد" />
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
                />
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
                    <TextField {...params} label="ارسال به یک یا چند شخص خاص (جستجو کنید)" />
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
            </>
          )}

          {createMode === "payroll" && (
            <>
              {payrollResult ? (
                <Alert severity="success" sx={{ whiteSpace: "pre-line" }}>
                  {`اطلاعیه فیش حقوقی ارسال شد.
تعداد پرسنل منطبق (دریافت‌کننده): ${payrollResult.matched_employee_count}`}
                  {payrollResult.missing_codes.length > 0 &&
                    `\nکدهای موجود در XML که در سامانه پیدا نشدند (${payrollResult.missing_codes.length} مورد) — فیش برای این افراد ارسال نشد:\n${payrollResult.missing_codes.join("، ")}`}
                  {payrollResult.invalid_row_count > 0 &&
                    `\n${payrollResult.invalid_row_count} ردیف در XML فاقد کد پرسنلی بود و نادیده گرفته شد.`}
                </Alert>
              ) : (
                <>
                  <Alert severity="info">
                    فقط کارکنانی که کدشان در فایل XML باشد، به‌صورت خودکار مخاطب این اطلاعیه می‌شوند —
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
                </>
              )}
            </>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => setDialogOpen(false)}
            disabled={isSubmitting}
          >
            {payrollResult ? "بستن" : "انصراف"}
          </Button>
          {!payrollResult && (
            <Button
              variant="contained"
              onClick={createMode === "payroll" ? handleCreatePayroll : handleCreate}
              disabled={isSubmitting}
              startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : null}
            >
              {isSubmitting
                ? createMode === "payroll"
                  ? "در حال آپلود و ارسال..."
                  : "در حال ارسال..."
                : createMode === "payroll"
                  ? "آپلود و ارسال"
                  : "ثبت و انتشار"}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
}
