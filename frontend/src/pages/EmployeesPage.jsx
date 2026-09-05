import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControlLabel,
  IconButton,
  InputAdornment,
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
  TableSortLabel,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import LockResetOutlinedIcon from "@mui/icons-material/LockResetOutlined";
import CleaningServicesOutlinedIcon from "@mui/icons-material/CleaningServicesOutlined";
import PersonAddOutlinedIcon from "@mui/icons-material/PersonAddOutlined";
import {
  createEmployee,
  executeOrphanedInactiveCleanup,
  fetchEmployees,
  previewOrphanedInactiveCleanup,
  resetEmployeePassword,
  setEmployeeEnabled,
  setEmployeePassword,
} from "../api/employees";
import { fetchDepartments } from "../api/departments";
import { fetchSites } from "../api/sites";
import { monoFontSx } from "../theme";
import { useAuth } from "../context/AuthContext";

// ستون‌های جدول پرسنل — key همان چیزی است که به سرور به‌عنوان sort_by فرستاده
// می‌شود (مطابق با نگاشت _SORT_COLUMNS در بک‌اند). Sort کاملاً سمت سرور انجام
// می‌شود، نه روی داده‌های همین صفحه — چون این جدول حالا صفحه‌بندی سمت سرور دارد.
const EMPLOYEE_COLUMNS = [
  { key: "personnel_code", label: "کد پرسنلی" },
  { key: "full_name", label: "نام و نام خانوادگی" },
  { key: "national_code", label: "کد ملی" },
  { key: "mobile", label: "موبایل" },
  { key: "site_name", label: "سایت" },
  { key: "department_name", label: "واحد سازمانی" },
  { key: "is_enabled", label: "فعال در پرتال", align: "center" },
];

const ROWS_PER_PAGE_OPTIONS = [25, 50, 100];

function SetPasswordDialog({ employee, onClose, onChanged }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setPassword("");
    setConfirmPassword("");
    setError("");
    setSuccess("");
  }, [employee]);

  if (!employee) return null;

  async function handleSave() {
    setError("");
    if (password.length < 10 || !/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/[0-9]/.test(password)) {
      setError("رمز عبور باید حداقل ۱۰ کاراکتر باشد و شامل حرف کوچک، حرف بزرگ، و عدد باشد.");
      return;
    }
    if (password !== confirmPassword) {
      setError("تکرار رمز عبور با رمز عبور یکسان نیست.");
      return;
    }
    setIsSaving(true);
    try {
      await setEmployeePassword(employee.id, password);
      setSuccess(
        "رمز عبور با موفقیت تنظیم شد. از این پس ورود این پرسنل فقط با «کد پرسنلی + این رمز» ممکن است — روش قبلی ورود دیگر کار نمی‌کند. این پرسنل بعد از اولین ورود موفق، مجبور به تعیین یک رمز جدید (که فقط خودش می‌داند) خواهد شد."
      );
      onChanged?.();
    } catch (err) {
      setError(err.response?.data?.detail || "تعیین رمز عبور با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReset() {
    if (!window.confirm("رمز عبور اختصاصی این پرسنل حذف شود و روش ورود پیش‌فرض دوباره فعال شود؟")) return;
    setIsSaving(true);
    setError("");
    try {
      await resetEmployeePassword(employee.id);
      setSuccess("بازگردانده شد — این پرسنل از این پس دوباره با روش ورود پیش‌فرض وارد می‌شود.");
      onChanged?.();
    } catch (err) {
      setError(err.response?.data?.detail || "بازگرداندن با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={Boolean(employee)} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        رمز عبور ورود — {employee.first_name} {employee.last_name}
        <Typography variant="caption" color="text.secondary" display="block">
          کد پرسنلی: {employee.personnel_code} — روش فعلی ورود:{" "}
          {employee.has_custom_password ? "رمز عبور اختصاصی" : "روش پیش‌فرض (بدون رمز اختصاصی)"}
        </Typography>
      </DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {!success && (
          <>
            <TextField
              label="رمز عبور جدید"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSaving}
              autoFocus
              helperText="حداقل ۱۰ کاراکتر، شامل حرف کوچک، حرف بزرگ، و عدد"
            />
            <TextField
              label="تکرار رمز عبور"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={isSaving}
            />
          </>
        )}
        {error && <Alert severity="error">{error}</Alert>}
        {success && <Alert severity="success">{success}</Alert>}
      </DialogContent>
      <DialogActions sx={{ p: 2.5, justifyContent: "space-between" }}>
        <Box>
          {!success && employee.has_custom_password && (
            <Button color="warning" onClick={handleReset} disabled={isSaving}>
              بازگشت به روش ورود پیش‌فرض
            </Button>
          )}
        </Box>
        <Box>
          <Button onClick={onClose}>{success ? "بستن" : "انصراف"}</Button>
          {!success && (
            <Button variant="contained" onClick={handleSave} disabled={isSaving}>
              {isSaving ? "در حال ذخیره..." : "ذخیره رمز عبور"}
            </Button>
          )}
        </Box>
      </DialogActions>
    </Dialog>
  );
}

export default function EmployeesPage() {
  const { user } = useAuth();
  const [employees, setEmployees] = useState([]);
  const [total, setTotal] = useState(0);
  const [sites, setSites] = useState([]);
  const [selectedSite, setSelectedSite] = useState("");
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [cleanupDialogOpen, setCleanupDialogOpen] = useState(false);
  const [cleanupPreview, setCleanupPreview] = useState(null); // { count, items } | null
  const [isCleanupLoading, setIsCleanupLoading] = useState(false);
  const [isCleanupDeleting, setIsCleanupDeleting] = useState(false);
  const [cleanupResult, setCleanupResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [togglingId, setTogglingId] = useState(null);
  const [passwordEmployee, setPasswordEmployee] = useState(null);
  const [sortBy, setSortBy] = useState("personnel_code");
  const [sortDir, setSortDir] = useState("asc");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(ROWS_PER_PAGE_OPTIONS[0]);
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  useEffect(() => {
    fetchSites().then(setSites);
  }, []);

  function handleSort(columnKey) {
    if (sortBy === columnKey) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(columnKey);
      setSortDir("asc");
    }
    setPage(0);
  }

  function loadEmployees() {
    setIsLoading(true);
    return fetchEmployees({
      siteId: selectedSite || undefined,
      search: search || undefined,
      includeInactive: showInactive,
      includePortalDisabled: true, // پنل Admin همیشه پرسنل با پرتال غیرفعال را هم باید ببیند تا بتواند دوباره فعالشان کند
      page: page + 1,
      pageSize: rowsPerPage,
      sortBy,
      sortDir,
    })
      .then((data) => {
        setEmployees(data.items);
        setTotal(data.total);
      })
      .finally(() => setIsLoading(false));
  }

  // با تغییر فیلترها/Sort به صفحه اول برگرد (صفحه فعلی ممکن است دیگر معتبر نباشد)
  useEffect(() => {
    setPage(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSite, search, showInactive]);

  useEffect(() => {
    const timer = setTimeout(loadEmployees, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSite, search, showInactive, sortBy, sortDir, page, rowsPerPage]);

  async function handleToggleEnabled(employee) {
    const nextEnabled = !employee.is_enabled;
    if (
      !window.confirm(
        nextEnabled
          ? `${employee.first_name} ${employee.last_name} در پرتال دوباره فعال شود؟`
          : `${employee.first_name} ${employee.last_name} در پرتال غیرفعال شود؟ این پرسنل دیگر نمی‌تواند وارد پنل شود — این تنظیم مستقل از Sync است و با سینک بعدی تغییر نمی‌کند.`
      )
    ) {
      return;
    }
    setTogglingId(employee.id);
    try {
      const updated = await setEmployeeEnabled(employee.id, nextEnabled);
      // فقط is_enabled را از پاسخ Merge می‌کنیم؛ site_name/department_name را
      // PATCH پر نمی‌کند (فقط GET لیست این دو را با Join برمی‌گرداند)، پس اگر
      // کل updated را جایگزین کنیم این دو فیلد با null بازنویسی می‌شوند.
      setEmployees((prev) =>
        prev.map((e) => (e.id === employee.id ? { ...e, is_enabled: updated.is_enabled } : e))
      );
    } finally {
      setTogglingId(null);
    }
  }

  async function handleOpenCleanupDialog() {
    setCleanupDialogOpen(true);
    setCleanupResult(null);
    setIsCleanupLoading(true);
    try {
      const data = await previewOrphanedInactiveCleanup();
      setCleanupPreview(data);
    } catch (err) {
      setCleanupResult({ success: false, message: err.response?.data?.detail || "بررسی با خطا مواجه شد." });
    } finally {
      setIsCleanupLoading(false);
    }
  }

  async function handleExecuteCleanup() {
    if (!window.confirm(`${cleanupPreview.count} پرسنل برای همیشه حذف می‌شوند. این عمل قابل‌بازگشت نیست. مطمئن هستید؟`)) {
      return;
    }
    setIsCleanupDeleting(true);
    try {
      const { deleted_count } = await executeOrphanedInactiveCleanup();
      setCleanupResult({ success: true, message: `${deleted_count} پرسنل بدون سابقه حذف شدند.` });
      setCleanupPreview(null);
      // اگر همین الان تیک «نمایش پرسنل غیرفعال» روشن است، لیست را دوباره بگیر تا حذف‌شده‌ها دیگر دیده نشوند
      if (showInactive) loadEmployees();
    } catch (err) {
      setCleanupResult({ success: false, message: err.response?.data?.detail || "حذف با خطا مواجه شد." });
    } finally {
      setIsCleanupDeleting(false);
    }
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            پرسنل
          </Typography>
          <Typography variant="body2" color="text.secondary">
            فهرست پرسنل سینک‌شده از دیتابیس‌های سایت‌ها (از طریق Mapping تعریف‌شده در صفحه «سایت‌ها»).
            برای دادن دسترسی به کسی، از صفحه «مدیریت دسترسی» استفاده کنید.
          </Typography>
        </Box>
        {user?.can_create_employees && (
          <Button variant="contained" startIcon={<PersonAddOutlinedIcon />} onClick={() => setAddDialogOpen(true)} sx={{ flexShrink: 0 }}>
            افزودن دستی پرسنل
          </Button>
        )}
      </Stack>

      <Box sx={{ display: "flex", gap: 2, mb: 2, flexWrap: "wrap", alignItems: "center" }}>
        <TextField
          size="small"
          placeholder="جستجو بر اساس نام، کد پرسنلی یا کد ملی..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 280, flexGrow: 1 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlinedIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
        />
        <TextField
          select
          size="small"
          label="فیلتر بر اساس سایت"
          value={selectedSite}
          onChange={(e) => setSelectedSite(e.target.value)}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="">همه سایت‌ها</MenuItem>
          {sites.map((site) => (
            <MenuItem key={site.id} value={site.id}>
              {site.name}
            </MenuItem>
          ))}
        </TextField>
        <FormControlLabel
          control={<Checkbox checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />}
          label={
            <Tooltip title="پرسنلی که قبلاً وارد پرتال شده بودند ولی بعداً در دیتابیس مبدأ (طبق Mapping) غیرفعال/کات اعلام شدند — سوابقشان (فیش حقوقی و...) حفظ می‌شود، پیش‌فرض از این لیست کنار گذاشته می‌شوند. پرسنلی که اصلاً هرگز فعال نبوده‌اند، از ابتدا وارد پرتال نمی‌شوند و اینجا هم دیده نمی‌شوند.">
              <span>نمایش پرسنل غیرفعال (Sync)</span>
            </Tooltip>
          }
        />
        <Tooltip title="بررسی و پاک‌سازی پرسنل غیرفعالی که هیچ سابقه‌ای در پرتال ندارند — داده تاریخی از قبل از رفع باگ Sync">
          <Button
            size="small"
            variant="outlined"
            color="warning"
            startIcon={<CleaningServicesOutlinedIcon />}
            onClick={handleOpenCleanupDialog}
          >
            پاک‌سازی پرسنل بدون سابقه
          </Button>
        </Tooltip>
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                {EMPLOYEE_COLUMNS.map((col) => (
                  <TableCell key={col.key} align={col.align}>
                    <TableSortLabel
                      active={sortBy === col.key}
                      direction={sortBy === col.key ? sortDir : "asc"}
                      onClick={() => handleSort(col.key)}
                    >
                      {col.key === "is_enabled" ? (
                        <Tooltip title="تصمیم دستی Admin — کاملاً مستقل از Sync و با آن بازنویسی نمی‌شود">
                          <span>{col.label}</span>
                        </Tooltip>
                      ) : (
                        col.label
                      )}
                    </TableSortLabel>
                  </TableCell>
                ))}
                <TableCell align="center">رمز عبور</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {!isLoading && employees.length === 0 && (
                <TableRow>
                  <TableCell colSpan={EMPLOYEE_COLUMNS.length + 1}>
                    <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                      {search
                        ? "با این عبارت جستجو، پرسنلی یافت نشد."
                        : "هیچ پرسنلی یافت نشد. ابتدا از بخش «همگام‌سازی دیتابیس»، همگام‌سازی را اجرا کنید."}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {employees.map((emp) => (
                <TableRow
                  key={emp.id}
                  hover
                  sx={!emp.is_enabled || !emp.is_active ? { opacity: 0.6 } : undefined}
                >
                  <TableCell sx={monoFontSx}>{emp.personnel_code}</TableCell>
                  <TableCell>
                    {emp.first_name} {emp.last_name}
                    {!emp.is_active && (
                      <Chip size="small" variant="outlined" label="غیرفعال" sx={{ mr: 1 }} />
                    )}
                  </TableCell>
                  <TableCell sx={monoFontSx}>{emp.national_code || "—"}</TableCell>
                  <TableCell sx={monoFontSx}>{emp.mobile || "—"}</TableCell>
                  <TableCell>{emp.site_name || emp.site_id}</TableCell>
                  <TableCell>{emp.department_name || "—"}</TableCell>
                  <TableCell align="center">
                    <Stack direction="row" spacing={0.5} alignItems="center" justifyContent="center">
                      <Chip
                        size="small"
                        label={emp.is_enabled ? "فعال" : "غیرفعال"}
                        color={emp.is_enabled ? "success" : "error"}
                        variant="outlined"
                      />
                      <Tooltip title={emp.is_enabled ? "غیرفعال کردن در پرتال" : "فعال کردن در پرتال"}>
                        <span>
                          <Switch
                            size="small"
                            checked={emp.is_enabled}
                            disabled={togglingId === emp.id}
                            onChange={() => handleToggleEnabled(emp)}
                          />
                        </span>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title={emp.has_custom_password ? "دارای رمز عبور اختصاصی" : "تعیین رمز عبور"}>
                      <IconButton size="small" onClick={() => setPasswordEmployee(emp)}>
                        <LockResetOutlinedIcon
                          fontSize="small"
                          color={emp.has_custom_password ? "primary" : "inherit"}
                        />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        <TablePagination
          component="div"
          count={total}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(Number(e.target.value));
            setPage(0);
          }}
          rowsPerPageOptions={ROWS_PER_PAGE_OPTIONS}
          labelRowsPerPage="سطر در هر صفحه"
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
        />
      </Card>

      <SetPasswordDialog
        employee={passwordEmployee}
        onClose={() => setPasswordEmployee(null)}
        onChanged={loadEmployees}
      />

      <Dialog open={cleanupDialogOpen} onClose={() => setCleanupDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>پاک‌سازی پرسنل غیرفعال بدون سابقه</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            پرسنلی که <strong>هیچ سابقه‌ای</strong> در پرتال ندارند (نه فیش حقوقی، نه فیش کارکرد، نه
            ورود/خروج، نه Session آنلاین، نه حساب کاربری با رمز اختصاصی، نه خواندن هیچ اطلاعیه‌ای) —
            احتمالاً هرگز واقعاً فعال نبوده‌اند، فقط قبل از رفع باگ Sync اشتباهاً وارد پرتال شده بودند.
            پرسنلی که حتی یک نشانه از فعالیت واقعی داشته باشد، هرگز حذف نمی‌شود.
          </DialogContentText>

          {isCleanupLoading && (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress size={28} />
            </Box>
          )}

          {!isCleanupLoading && cleanupPreview && (
            <>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                {cleanupPreview.count} پرسنل برای حذف پیدا شد
              </Typography>
              {cleanupPreview.count > 0 && (
                <TableContainer sx={{ maxHeight: 300 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>کد پرسنلی</TableCell>
                        <TableCell>نام</TableCell>
                        <TableCell>سایت</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {cleanupPreview.items.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell>{item.personnel_code}</TableCell>
                          <TableCell>
                            {item.first_name} {item.last_name}
                          </TableCell>
                          <TableCell>{item.site_name}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </>
          )}
          {cleanupResult && (
            <Alert severity={cleanupResult.success ? "success" : "error"} sx={{ mt: 2 }}>
              {cleanupResult.message}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCleanupDialogOpen(false)}>بستن</Button>
          {cleanupPreview && cleanupPreview.count > 0 && !cleanupResult?.success && (
            <Button
              color="error"
              variant="contained"
              disabled={isCleanupDeleting}
              onClick={handleExecuteCleanup}
            >
              {isCleanupDeleting ? "در حال حذف..." : `حذف قطعی ${cleanupPreview.count} پرسنل`}
            </Button>
          )}
        </DialogActions>
      </Dialog>

      <AddEmployeeDialog
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        sites={sites}
        onCreated={() => {
          setAddDialogOpen(false);
          loadEmployees();
        }}
      />
    </Box>
  );
}

/**
 * دیالوگ «افزودن دستی پرسنل» — طبق قابلیت مجوز employees.create. فقط
 * برای مواردی که واقعاً در هیچ منبع Sync موجود نیست؛ نتیجه با یک نشانگر
 * (is_manually_created) از رکوردهای معمولی Sync متمایز می‌شود.
 */
function AddEmployeeDialog({ open, onClose, sites, onCreated }) {
  const [personnelCode, setPersonnelCode] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [siteId, setSiteId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [departments, setDepartments] = useState([]);
  const [nationalCode, setNationalCode] = useState("");
  const [mobile, setMobile] = useState("");
  const [positionTitle, setPositionTitle] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  // با هر بار باز شدن Dialog، فرم را از نو خالی می‌کنیم — نه این‌که
  // مقادیر دفعه قبل باقی بماند.
  useEffect(() => {
    if (open) {
      setPersonnelCode("");
      setFirstName("");
      setLastName("");
      setSiteId("");
      setDepartmentId("");
      setDepartments([]);
      setNationalCode("");
      setMobile("");
      setPositionTitle("");
      setError("");
    }
  }, [open]);

  useEffect(() => {
    if (!siteId) {
      setDepartments([]);
      return;
    }
    setDepartmentId("");
    fetchDepartments(siteId).then(setDepartments);
  }, [siteId]);

  const canSave = personnelCode.trim() && firstName.trim() && lastName.trim() && siteId && !isSaving;

  async function handleSave() {
    if (!canSave) return;
    setError("");
    setIsSaving(true);
    try {
      await createEmployee({
        personnel_code: personnelCode.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        site_id: siteId,
        department_id: departmentId || null,
        national_code: nationalCode.trim() || null,
        mobile: mobile.trim() || null,
        position_title: positionTitle.trim() || null,
      });
      onCreated();
    } catch (err) {
      setError(err.response?.data?.detail || "افزودن پرسنل با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>افزودن دستی پرسنل</DialogTitle>
      <DialogContent>
        <Alert severity="info" sx={{ mb: 2, mt: 1 }}>
          فقط برای پرسنلی استفاده کنید که واقعاً در دیتابیس مبدأ سایت (Sync) وجود ندارد. اگر بعداً
          همین کد پرسنلی در همان سایت از طریق Sync هم دیده شود، اطلاعاتش به‌طور خودکار به‌روزرسانی می‌شود.
        </Alert>
        <Stack spacing={2}>
          <Stack direction="row" spacing={2}>
            <TextField label="نام" value={firstName} onChange={(e) => setFirstName(e.target.value)} fullWidth />
            <TextField label="نام خانوادگی" value={lastName} onChange={(e) => setLastName(e.target.value)} fullWidth />
          </Stack>
          <TextField
            label="کد پرسنلی"
            value={personnelCode}
            onChange={(e) => setPersonnelCode(e.target.value)}
            fullWidth
            helperText="باید در همان سایت منحصربه‌فرد باشد"
          />
          <TextField select label="سایت" value={siteId} onChange={(e) => setSiteId(e.target.value)} fullWidth>
            {sites.map((site) => (
              <MenuItem key={site.id} value={site.id}>
                {site.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="واحد سازمانی (اختیاری)"
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            fullWidth
            disabled={!siteId}
          >
            <MenuItem value="">بدون واحد</MenuItem>
            {departments.map((dept) => (
              <MenuItem key={dept.id} value={dept.id}>
                {dept.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField label="سمت (اختیاری)" value={positionTitle} onChange={(e) => setPositionTitle(e.target.value)} fullWidth />
          <Stack direction="row" spacing={2}>
            <TextField label="کد ملی (اختیاری)" value={nationalCode} onChange={(e) => setNationalCode(e.target.value)} fullWidth />
            <TextField label="موبایل (اختیاری)" value={mobile} onChange={(e) => setMobile(e.target.value)} fullWidth />
          </Stack>
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={!canSave} onClick={handleSave}>
          {isSaving ? "در حال ثبت..." : "افزودن"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
