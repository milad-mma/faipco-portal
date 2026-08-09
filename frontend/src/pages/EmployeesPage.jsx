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
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import LockResetOutlinedIcon from "@mui/icons-material/LockResetOutlined";
import { fetchEmployees, setEmployeeActive, setEmployeePassword } from "../api/employees";
import { fetchSites } from "../api/sites";
import { monoFontSx } from "../theme";

function SetPasswordDialog({ employee, onClose }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setPassword("");
    setConfirmPassword("");
    setError("");
    setSuccess(false);
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
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || "تعیین رمز عبور ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={Boolean(employee)} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        تعیین رمز عبور — {employee.first_name} {employee.last_name}
        <Typography variant="caption" color="text.secondary" display="block">
          کد پرسنلی: {employee.personnel_code}
        </Typography>
      </DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}
        {success && (
          <Alert severity="success">
            رمز عبور با موفقیت تنظیم شد. این پرسنل از این پس می‌تواند هم با «کد پرسنلی + این رمز» و هم مثل
            قبل با «کد پرسنلی + کد ملی» وارد شود.
          </Alert>
        )}
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
      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={onClose}>{success ? "بستن" : "انصراف"}</Button>
        {!success && (
          <Button variant="contained" onClick={handleSave} disabled={isSaving}>
            {isSaving ? "در حال ذخیره..." : "ذخیره رمز عبور"}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

export default function EmployeesPage() {
  const [employees, setEmployees] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedSite, setSelectedSite] = useState("");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [togglingId, setTogglingId] = useState(null);
  const [passwordEmployee, setPasswordEmployee] = useState(null);

  useEffect(() => {
    fetchSites().then(setSites);
  }, []);

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

  async function handleToggleActive(employee) {
    const nextActive = !employee.is_active;
    if (
      !window.confirm(
        nextActive
          ? `${employee.first_name} ${employee.last_name} دوباره فعال شود؟`
          : `${employee.first_name} ${employee.last_name} غیرفعال شود؟ این پرسنل دیگر نمی‌تواند وارد پنل شود.`
      )
    ) {
      return;
    }
    setTogglingId(employee.id);
    try {
      const updated = await setEmployeeActive(employee.id, nextActive);
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
                <TableCell>کد پرسنلی</TableCell>
                <TableCell>نام و نام خانوادگی</TableCell>
                <TableCell>کد ملی</TableCell>
                <TableCell>موبایل</TableCell>
                <TableCell>سایت</TableCell>
                <TableCell align="center">وضعیت</TableCell>
                <TableCell align="center">رمز عبور</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {!isLoading && employees.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                      {search
                        ? "با این عبارت جستجو، پرسنلی یافت نشد."
                        : "هیچ پرسنلی یافت نشد. ابتدا از بخش «مدیریت Sync»، همگام‌سازی را اجرا کنید."}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {employees.map((emp) => (
                <TableRow key={emp.id} hover sx={!emp.is_active ? { opacity: 0.6 } : undefined}>
                  <TableCell sx={monoFontSx}>{emp.personnel_code}</TableCell>
                  <TableCell>
                    {emp.first_name} {emp.last_name}
                  </TableCell>
                  <TableCell sx={monoFontSx}>{emp.national_code || "—"}</TableCell>
                  <TableCell sx={monoFontSx}>{emp.mobile || "—"}</TableCell>
                  <TableCell>{siteNameById[emp.site_id] || emp.site_id}</TableCell>
                  <TableCell align="center">
                    <Stack direction="row" spacing={0.5} alignItems="center" justifyContent="center">
                      <Chip
                        size="small"
                        label={emp.is_active ? "فعال" : "غیرفعال"}
                        color={emp.is_active ? "success" : "default"}
                        variant="outlined"
                      />
                      <Tooltip title={emp.is_active ? "غیرفعال کردن" : "فعال کردن"}>
                        <span>
                          <Switch
                            size="small"
                            checked={emp.is_active}
                            disabled={togglingId === emp.id}
                            onChange={() => handleToggleActive(emp)}
                          />
                        </span>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="تعیین رمز عبور ورود">
                      <IconButton size="small" onClick={() => setPasswordEmployee(emp)}>
                        <LockResetOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      <SetPasswordDialog employee={passwordEmployee} onClose={() => setPasswordEmployee(null)} />
    </Box>
  );
}
