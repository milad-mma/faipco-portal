import { useEffect, useState } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Pagination,
  Stack,
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
import LoginOutlinedIcon from "@mui/icons-material/LoginOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import StarIcon from "@mui/icons-material/Star";
import {
  createManualAttendanceLog,
  deleteAttendanceLog,
  fetchAllAttendanceLogs,
  updateAttendanceLog,
} from "../api/attendance";
import { fetchEmployees } from "../api/employees";
import { fetchSites } from "../api/sites";
import { useAuth } from "../context/AuthContext";
import JalaliMonthYearFilter from "../components/JalaliMonthYearFilter";
import { groupLogsByDay } from "../utils/attendanceGrouping";
import { monoFontSx } from "../theme";

const PAGE_SIZE = 50;

// ورودی <input type="datetime-local"> رشته محلی بدون Timezone می‌خواهد (نه
// ISO با Z) — این تابع یک Date را به همان فرمت تبدیل می‌کند.
function toDatetimeLocalValue(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function LogEditDialog({ open, onClose, onSaved, mode, initialLog, employeeOptions, siteOptions }) {
  const [employee, setEmployee] = useState(null);
  const [logType, setLogType] = useState("check_in");
  const [dateTimeLocal, setDateTimeLocal] = useState("");
  const [site, setSite] = useState(null);
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError("");
    if (mode === "edit" && initialLog) {
      setLogType(initialLog.log_type);
      setDateTimeLocal(toDatetimeLocalValue(new Date(initialLog.created_at)));
      setSite(siteOptions.find((s) => s.id === initialLog.matched_site_id) || null);
      setEmployee(null);
    } else {
      setLogType("check_in");
      setDateTimeLocal(toDatetimeLocalValue(new Date()));
      setSite(null);
      setEmployee(null);
    }
  }, [open, mode, initialLog, siteOptions]);

  async function handleSave() {
    setError("");
    if (mode === "create" && !employee) {
      setError("پرسنل را انتخاب کنید.");
      return;
    }
    if (!dateTimeLocal) {
      setError("تاریخ و ساعت را وارد کنید.");
      return;
    }
    setIsSaving(true);
    try {
      const createdAtIso = new Date(dateTimeLocal).toISOString();
      if (mode === "create") {
        await createManualAttendanceLog({
          employeeId: employee.id,
          logType,
          createdAt: createdAtIso,
          siteId: site?.id || null,
        });
      } else {
        await updateAttendanceLog(initialLog.id, { logType, createdAt: createdAtIso, siteId: site?.id || null });
      }
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{mode === "create" ? "افزودن رکورد دستی" : "ویرایش رکورد"}</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}
        {mode === "create" && (
          <Autocomplete
            options={employeeOptions}
            getOptionLabel={(o) => `${o.first_name} ${o.last_name} (${o.personnel_code})`}
            value={employee}
            onChange={(_, value) => setEmployee(value)}
            renderInput={(params) => <TextField {...params} label="پرسنل" autoFocus />}
            isOptionEqualToValue={(o, v) => o.id === v.id}
          />
        )}
        <TextField select label="نوع رکورد" value={logType} onChange={(e) => setLogType(e.target.value)}>
          <MenuItem value="check_in">ورود</MenuItem>
          <MenuItem value="check_out">خروج</MenuItem>
        </TextField>
        <TextField
          label="تاریخ و ساعت"
          type="datetime-local"
          value={dateTimeLocal}
          onChange={(e) => setDateTimeLocal(e.target.value)}
          InputLabelProps={{ shrink: true }}
        />
        <Autocomplete
          options={siteOptions}
          getOptionLabel={(o) => o.name}
          value={site}
          onChange={(_, value) => setSite(value)}
          renderInput={(params) => <TextField {...params} label="سایت (اختیاری)" />}
          isOptionEqualToValue={(o, v) => o.id === v.id}
        />
      </DialogContent>
      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" onClick={handleSave} disabled={isSaving}>
          {isSaving ? "در حال ثبت..." : "ذخیره"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function LogChip({ log, type, canManage, onEdit, onDelete }) {
  if (!log) {
    return <Chip size="small" variant="outlined" label={type === "in" ? "بدون ورود" : "بدون خروج"} />;
  }
  const timeLabel = new Date(log.created_at).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  return (
    <Stack direction="row" spacing={0.25} alignItems="center">
      <Chip
        size="small"
        color={type === "in" ? "success" : "default"}
        icon={type === "in" ? <LoginOutlinedIcon fontSize="small" /> : <LogoutOutlinedIcon fontSize="small" />}
        label={
          <Stack direction="row" spacing={0.25} alignItems="center">
            <span>{timeLabel}</span>
            {log.is_manual && (
              <Tooltip title="این رکورد دستی ثبت/ویرایش شده">
                <StarIcon sx={{ fontSize: 14 }} />
              </Tooltip>
            )}
          </Stack>
        }
      />
      {canManage && (
        <>
          <IconButton size="small" onClick={() => onEdit(log)}>
            <EditOutlinedIcon sx={{ fontSize: 16 }} />
          </IconButton>
          <IconButton size="small" color="error" onClick={() => onDelete(log)}>
            <DeleteOutlineIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </>
      )}
    </Stack>
  );
}

export default function ClockInOutReportPage() {
  const { user } = useAuth();
  const canManage = Boolean(user?.can_manage_clock_records);

  const [groupedRows, setGroupedRows] = useState(null);
  const [page, setPage] = useState(1);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [period, setPeriod] = useState({ year: null, month: null });

  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [siteOptions, setSiteOptions] = useState([]);

  const [dialogMode, setDialogMode] = useState(null); // "create" | "edit" | null
  const [editingLog, setEditingLog] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setGroupedRows(null);
    Promise.all([
      fetchAllAttendanceLogs({
        page: 1,
        pageSize: 1000,
        employeeId: selectedEmployee?.id,
        logType: "check_in",
        year: period.year,
        month: period.month,
      }),
      fetchAllAttendanceLogs({
        page: 1,
        pageSize: 1000,
        employeeId: selectedEmployee?.id,
        logType: "check_out",
        year: period.year,
        month: period.month,
      }),
    ]).then(([inData, outData]) => {
      const combined = groupLogsByDay([...inData.items, ...outData.items]);
      setGroupedRows(combined);
      setPeriod({ year: inData.year, month: inData.month });
    });
  }, [page, selectedEmployee, period.year, period.month, reloadKey]);

  useEffect(() => {
    fetchEmployees({ search: employeeSearch, pageSize: 20 }).then((data) => setEmployeeOptions(data.items || []));
  }, [employeeSearch]);

  useEffect(() => {
    if (canManage) {
      fetchSites().then((data) => setSiteOptions(data || []));
    }
  }, [canManage]);

  function handleSaved() {
    setDialogMode(null);
    setEditingLog(null);
    setReloadKey((k) => k + 1);
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    await deleteAttendanceLog(deleteTarget.id);
    setDeleteTarget(null);
    setReloadKey((k) => k + 1);
  }

  const pageRows = groupedRows ? groupedRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : null;

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" rowGap={1}>
        <Box>
          <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
            گزارش ثبت ورود و خروج
          </Typography>
        </Box>
        {canManage && (
          <Button
            variant="contained"
            startIcon={<AddCircleOutlineIcon />}
            onClick={() => {
              setDialogMode("create");
              setEditingLog(null);
            }}
          >
            افزودن رکورد دستی
          </Button>
        )}
      </Stack>
      <Alert severity="warning" icon={<ScienceOutlinedIcon />} sx={{ mb: 3, mt: 1 }}>
        این قابلیت آزمایشی است. ثبت ورود/خروج رسمی همچنان باید از طریق دستگاه‌های تعبیه‌شده در
        کارخانه انجام شود.{canManage && " رکوردهایی که دستی ثبت/ویرایش شده‌اند با یک ⭐ کنار ساعت مشخص می‌شوند."}
      </Alert>

      <Stack direction="row" spacing={2} sx={{ mb: 3 }} flexWrap="wrap" rowGap={2} alignItems="center">
        <Autocomplete
          sx={{ minWidth: 260 }}
          options={employeeOptions}
          getOptionLabel={(o) => `${o.first_name} ${o.last_name} (${o.personnel_code})`}
          value={selectedEmployee}
          onChange={(_, value) => {
            setSelectedEmployee(value);
            setPage(1);
          }}
          onInputChange={(_, value) => setEmployeeSearch(value)}
          renderInput={(params) => <TextField {...params} label="فیلتر بر اساس پرسنل" size="small" />}
          isOptionEqualToValue={(o, v) => o.id === v.id}
        />
        <JalaliMonthYearFilter
          year={period.year}
          month={period.month}
          onChange={(next) => {
            setPeriod(next);
            setPage(1);
          }}
          disabled={groupedRows === null}
        />
      </Stack>

      {groupedRows === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : groupedRows.length === 0 ? (
        <Alert severity="info">هیچ رکوردی پیدا نشد.</Alert>
      ) : (
        <>
          <TableContainer sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>پرسنل</TableCell>
                  <TableCell>تاریخ</TableCell>
                  <TableCell>ورود/خروج‌ها</TableCell>
                  <TableCell>سایت مطابق</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pageRows.map((row) => (
                  <TableRow key={row.key}>
                    <TableCell>
                      <Typography variant="body2">{row.employeeName}</Typography>
                      <Typography variant="caption" color="text.secondary" sx={monoFontSx}>
                        {row.personnelCode}
                      </Typography>
                    </TableCell>
                    <TableCell sx={monoFontSx}>{row.dateLabel}</TableCell>
                    <TableCell>
                      <Stack spacing={0.75}>
                        {row.sessions.map((session, sessionIndex) => (
                          <Stack key={sessionIndex} direction="row" spacing={1} flexWrap="wrap" rowGap={0.5}>
                            <LogChip
                              log={session.checkIn}
                              type="in"
                              canManage={canManage}
                              onEdit={(log) => {
                                setDialogMode("edit");
                                setEditingLog(log);
                              }}
                              onDelete={(log) => setDeleteTarget(log)}
                            />
                            <LogChip
                              log={session.checkOut}
                              type="out"
                              canManage={canManage}
                              onEdit={(log) => {
                                setDialogMode("edit");
                                setEditingLog(log);
                              }}
                              onDelete={(log) => setDeleteTarget(log)}
                            />
                          </Stack>
                        ))}
                      </Stack>
                    </TableCell>
                    <TableCell>
                      {row.sessions[0]?.checkIn?.matched_site_name || row.sessions[0]?.checkOut?.matched_site_name || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {groupedRows.length > PAGE_SIZE && (
            <Stack alignItems="center" sx={{ mt: 3 }}>
              <Pagination
                count={Math.ceil(groupedRows.length / PAGE_SIZE)}
                page={page}
                onChange={(_, value) => setPage(value)}
                color="primary"
              />
            </Stack>
          )}
        </>
      )}

      <LogEditDialog
        open={dialogMode !== null}
        mode={dialogMode}
        initialLog={editingLog}
        employeeOptions={employeeOptions}
        siteOptions={siteOptions}
        onClose={() => {
          setDialogMode(null);
          setEditingLog(null);
        }}
        onSaved={handleSaved}
      />

      <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>حذف رکورد</DialogTitle>
        <DialogContent>
          <Typography variant="body2">این رکورد برای همیشه حذف می‌شود. مطمئن هستید؟</Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setDeleteTarget(null)}>انصراف</Button>
          <Button color="error" variant="contained" onClick={handleConfirmDelete}>
            حذف
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
