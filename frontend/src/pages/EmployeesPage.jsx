import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
  TableRow,
  TableSortLabel,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import LockResetOutlinedIcon from "@mui/icons-material/LockResetOutlined";
import { fetchEmployees, resetEmployeePassword, setEmployeeEnabled, setEmployeePassword } from "../api/employees";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { monoFontSx } from "../theme";
import { sortRows } from "../utils/tableSort";

// تعریف ستون‌های قابل Sort جدول پرسنل — key همان فیلدی است که در ردیف‌های
// محاسبه‌شده (rows) برای Sort استفاده می‌شود؛ چند ستون (نام، سایت، واحد) از
// روی lookup map ساخته می‌شوند، نه مستقیماً از EmployeeOut.
const EMPLOYEE_COLUMNS = [
  { key: "personnel_code", label: "کد پرسنلی" },
  { key: "full_name", label: "نام و نام خانوادگی" },
  { key: "national_code", label: "کد ملی" },
  { key: "mobile", label: "موبایل" },
  { key: "site_name", label: "سایت" },
  { key: "department_name", label: "واحد سازمانی" },
  { key: "is_active", label: "وضعیت Sync", align: "center" },
  { key: "is_enabled", label: "فعال در پرتال", align: "center" },
];

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
    if (password.length < 6) {
      setError("رمز عبور باید حداقل ۶ کاراکتر باشد.");
      return;
    }
    if (password !== confirmPassword) {
      setError("تکرار رمز عبور با رمز عبور یکسان نیست.");
      return;
    }
    setIsSaving(true);
    try {
      await setEmployeePassword(employee.id, password);
      setSuccess("رمز عبور با موفقیت تنظیم شد. از این پس ورود این پرسنل فقط با «کد پرسنلی + این رمز» ممکن است — کد ملی دیگر کار نمی‌کند.");
      onChanged?.();
    } catch (err) {
      setError(err.response?.data?.detail || "تعیین رمز عبور ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReset() {
    if (!window.confirm("رمز عبور اختصاصی این پرسنل حذف شود و ورود دوباره با کد ملی فعال شود؟")) return;
    setIsSaving(true);
    setError("");
    try {
      await resetEmployeePassword(employee.id);
      setSuccess("بازگردانده شد — این پرسنل از این پس دوباره با کد پرسنلی + کد ملی وارد می‌شود.");
      onChanged?.();
    } catch (err) {
      setError(err.response?.data?.detail || "بازگرداندن ناموفق بود.");
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
          {employee.has_custom_password ? "رمز عبور اختصاصی" : "کد ملی (پیش‌فرض)"}
        </Typography>
      </DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}
        {success && <Alert severity="success">{success}</Alert>}
        {!success && (
          <>
            <TextField
              label="رمز عبور جدید"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSaving}
              autoFocus
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
      </DialogContent>
      <DialogActions sx={{ p: 2.5, justifyContent: "space-between" }}>
        <Box>
          {!success && employee.has_custom_password && (
            <Button color="warning" onClick={handleReset} disabled={isSaving}>
              بازگشت به ورود با کد ملی
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
  const [employees, setEmployees] = useState([]);
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedSite, setSelectedSite] = useState("");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [togglingId, setTogglingId] = useState(null);
  const [passwordEmployee, setPasswordEmployee] = useState(null);
  const [order, setOrder] = useState("asc");
  const [orderBy, setOrderBy] = useState(null);

  useEffect(() => {
    fetchSites().then(setSites);
    fetchDepartments().then(setDepartments);
  }, []);

  function handleSort(columnKey) {
    if (orderBy === columnKey) {
      setOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setOrderBy(columnKey);
      setOrder("asc");
    }
  }

  function loadEmployees() {
    setIsLoading(true);
    return fetchEmployees({ siteId: selectedSite || undefined, search: search || undefined, includeInactive: true })
      .then(setEmployees)
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    const timer = setTimeout(loadEmployees, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSite, search]);

  const siteNameById = Object.fromEntries(sites.map((s) => [s.id, s.name]));
  const departmentNameById = Object.fromEntries(departments.map((d) => [d.id, d.name]));

  // ردیف‌های نمایشی همراه با فیلدهای محاسبه‌شده (نام کامل، نام سایت، نام واحد)
  // که برای هم نمایش و هم Sort روی همه‌ی سرستون‌ها استفاده می‌شوند.
  const rows = employees.map((emp) => ({
    ...emp,
    full_name: `${emp.first_name} ${emp.last_name}`,
    site_name: siteNameById[emp.site_id] || null,
    department_name: emp.department_id ? departmentNameById[emp.department_id] || null : null,
  }));
  const sortedRows = sortRows(rows, order, orderBy);

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
      setEmployees((prev) => prev.map((e) => (e.id === employee.id ? updated : e)));
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight={700}>
          پرسنل
        </Typography>
        <Typography variant="body2" color="text.secondary">
          فهرست پرسنل سینک‌شده از دیتابیس‌های سایت‌ها. برای دادن دسترسی به کسی، از
          صفحه «مدیریت دسترسی» استفاده کنید.
        </Typography>
      </Box>

      <Box sx={{ display: "flex", gap: 2, mb: 3, flexWrap: "wrap" }}>
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
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                {EMPLOYEE_COLUMNS.map((col) => (
                  <TableCell key={col.key} align={col.align}>
                    <TableSortLabel
                      active={orderBy === col.key}
                      direction={orderBy === col.key ? order : "asc"}
                      onClick={() => handleSort(col.key)}
                    >
                      {col.key === "is_active" ? (
                        <Tooltip title="وضعیت خودکار — از روی Mapping دیتابیس مبدأ (مثل IsCut)، فقط با Sync تغییر می‌کند">
                          <span>{col.label}</span>
                        </Tooltip>
                      ) : col.key === "is_enabled" ? (
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
              {!isLoading && sortedRows.length === 0 && (
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
              {sortedRows.map((emp) => (
                <TableRow key={emp.id} hover sx={!emp.is_enabled ? { opacity: 0.6 } : undefined}>
                  <TableCell sx={monoFontSx}>{emp.personnel_code}</TableCell>
                  <TableCell>
                    {emp.first_name} {emp.last_name}
                  </TableCell>
                  <TableCell sx={monoFontSx}>{emp.national_code || "—"}</TableCell>
                  <TableCell sx={monoFontSx}>{emp.mobile || "—"}</TableCell>
                  <TableCell>{emp.site_name || emp.site_id}</TableCell>
                  <TableCell>{emp.department_name || "—"}</TableCell>
                  <TableCell align="center">
                    <Chip
                      size="small"
                      label={emp.is_active ? "فعال" : "غیرفعال"}
                      color={emp.is_active ? "success" : "default"}
                      variant="outlined"
                    />
                  </TableCell>
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
      </Card>

      <SetPasswordDialog
        employee={passwordEmployee}
        onClose={() => setPasswordEmployee(null)}
        onChanged={loadEmployees}
      />
    </Box>
  );
}
