import { useEffect, useMemo, useState } from "react";
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
import { fetchMyAccessibleSites, fetchSites } from "../api/sites";
import { useAuth } from "../context/AuthContext";
import JalaliMonthYearFilter from "../components/JalaliMonthYearFilter";
import SiteFilterSelect from "../components/SiteFilterSelect";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";
import { groupLogsByDay } from "../utils/attendanceGrouping";
import { monoFontSx } from "../theme";

const PAGE_SIZE = 50;
const ATTENDANCE_PILOT_ROLE = "attendance-pilot";

// وقتی از دکمه «افزودن» کنار یک اسلات خالی (بدون ورود/بدون خروج) باز می‌شود،
// پرسنل و نوع رکورد از قبل مشخص است — فقط تاریخ/ساعت باید تعیین شود. اگر
// خودِ روز گذشته باشد، ساعت پیش‌فرض ۰۸:۰۰ منطقی‌تر از «همین لحظه» است.
function buildPresetDate(dayDate) {
  const d = new Date(dayDate);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) return now;
  d.setHours(8, 0, 0, 0);
  return d;
}

function LogEditDialog({ open, onClose, onSaved, mode, initialLog, preset, siteOptions }) {
  // mode: "create" (دکمه بالای صفحه، انتخاب پرسنل آزاد) | "createForSlot"
  // (آیکون + کنار یک اسلات خالی، پرسنل/نوع از قبل مشخص) | "edit"
  const [employee, setEmployee] = useState(null);
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [logType, setLogType] = useState("check_in");
  const [dateValue, setDateValue] = useState(new Date());
  const [site, setSite] = useState(null);
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError("");
    if (mode === "edit" && initialLog) {
      setLogType(initialLog.log_type);
      setDateValue(new Date(initialLog.created_at));
      setSite(siteOptions.find((s) => s.id === initialLog.matched_site_id) || null);
      setEmployee(null);
    } else if (mode === "createForSlot" && preset) {
      setLogType(preset.logType);
      setDateValue(buildPresetDate(preset.dayDate));
      setSite(null);
      setEmployee({ id: preset.employeeId, first_name: preset.employeeName, last_name: "", personnel_code: preset.personnelCode });
    } else {
      setLogType("check_in");
      setDateValue(new Date());
      setSite(null);
      setEmployee(null);
    }
  }, [open, mode, initialLog, preset, siteOptions]);

  useEffect(() => {
    if (mode !== "create") return;
    // فقط پرسنلی که نقش attendance-pilot را دارند — چون فقط همان‌ها اصلاً
    // مجاز به استفاده از این قابلیت هستند
    fetchEmployees({ search: employeeSearch, pageSize: 20, hasRole: ATTENDANCE_PILOT_ROLE }).then((data) =>
      setEmployeeOptions(data.items || [])
    );
  }, [mode, employeeSearch]);

  async function handleSave() {
    setError("");
    // اعتبارسنجی «پرسنل انتخاب شود» فقط برای create/createForSlot معنا دارد
    // — در حالت edit، عمداً employee همیشه null است (چون ویرایش نیازی به
    // انتخاب دوباره پرسنل ندارد؛ پرسنل رکورد از قبل مشخص است). این چک قبلاً
    // بدون توجه به mode اجرا می‌شد و همیشه جلوی ذخیره در حالت ویرایش را می‌گرفت.
    if (mode !== "edit" && !employee) {
      setError("پرسنل را انتخاب کنید.");
      return;
    }
    setIsSaving(true);
    try {
      const createdAtIso = dateValue.toISOString();
      if (mode === "edit") {
        await updateAttendanceLog(initialLog.id, { logType, createdAt: createdAtIso, siteId: site?.id || null });
      } else {
        await createManualAttendanceLog({
          employeeId: employee.id,
          logType,
          createdAt: createdAtIso,
          siteId: site?.id || null,
        });
      }
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  const employeeIsLocked = mode === "createForSlot" || mode === "edit";

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        {mode === "create" && "افزودن رکورد دستی"}
        {mode === "createForSlot" && "ثبت رکورد"}
        {mode === "edit" && "ویرایش رکورد"}
      </DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}

        {employeeIsLocked ? (
          <TextField
            label="پرسنل"
            value={
              mode === "edit"
                ? `${initialLog?.employee_name || ""} (${initialLog?.personnel_code || ""})`
                : `${employee?.first_name || ""} (${employee?.personnel_code || ""})`
            }
            disabled
          />
        ) : (
          <Autocomplete
            options={employeeOptions}
            getOptionLabel={(o) => `${o.first_name} ${o.last_name} (${o.personnel_code})`}
            value={employee}
            onChange={(_, value) => setEmployee(value)}
            onInputChange={(_, value) => setEmployeeSearch(value)}
            renderInput={(params) => (
              <TextField {...params} label="پرسنل (فقط دارای دسترسی ثبت ورود/خروج)" autoFocus />
            )}
            isOptionEqualToValue={(o, v) => o.id === v.id}
            noOptionsText="پرسنلی با این مشخصات (و دسترسی ثبت ورود/خروج) پیدا نشد"
          />
        )}

        <TextField
          select
          label="نوع رکورد"
          value={logType}
          onChange={(e) => setLogType(e.target.value)}
          disabled={mode === "createForSlot"}
          SelectProps={{ native: true }}
        >
          <option value="check_in">ورود</option>
          <option value="check_out">خروج</option>
        </TextField>

        <JalaliDateTimePicker value={dateValue} onChange={setDateValue} label="تاریخ و ساعت (شمسی)" />

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

function LogCell({ log, type, canManage, row, onEdit, onAdd, onDelete }) {
  if (!log) {
    if (!canManage) {
      return (
        <Typography variant="caption" color="text.secondary">
          —
        </Typography>
      );
    }
    return (
      <Tooltip title={type === "in" ? "ثبت ورود" : "ثبت خروج"}>
        <IconButton size="small" onClick={() => onAdd(row, type)}>
          <AddCircleOutlineIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    );
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
  const [selectedSiteId, setSelectedSiteId] = useState(null);
  const [period, setPeriod] = useState({ year: null, month: null });

  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [siteOptions, setSiteOptions] = useState([]);

  const [dialogMode, setDialogMode] = useState(null); // "create" | "createForSlot" | "edit" | null
  const [editingLog, setEditingLog] = useState(null);
  const [slotPreset, setSlotPreset] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setGroupedRows(null);
    Promise.all([
      fetchAllAttendanceLogs({
        page: 1,
        pageSize: 1000,
        employeeId: selectedEmployee?.id,
        siteId: selectedSiteId,
        logType: "check_in",
        year: period.year,
        month: period.month,
      }),
      fetchAllAttendanceLogs({
        page: 1,
        pageSize: 1000,
        employeeId: selectedEmployee?.id,
        siteId: selectedSiteId,
        logType: "check_out",
        year: period.year,
        month: period.month,
      }),
    ]).then(([inData, outData]) => {
      const combined = groupLogsByDay([...inData.items, ...outData.items]);
      setGroupedRows(combined);
      setPeriod({ year: inData.year, month: inData.month });
    });
  }, [page, selectedEmployee, selectedSiteId, period.year, period.month, reloadKey]);

  useEffect(() => {
    fetchEmployees({ search: employeeSearch, pageSize: 20 }).then((data) => setEmployeeOptions(data.items || []));
  }, [employeeSearch]);

  useEffect(() => {
    if (canManage) {
      // ⚠️ رفع یک نقص واقعی: قبلاً از fetchSites (همه سایت‌های سیستم)
      // استفاده می‌شد — یعنی کسی با attendance.manage_clock_records فقط
      // برای یک سایت، در این دراپ‌داون همه سایت‌های دیگر را هم می‌دید
      // (که انتخابشان فقط نتیجه خالی می‌داد، بدون هیچ توضیحی) — به‌اشتباه
      // به‌نظر می‌رسید فیلتر سایتی اصلاً کار نمی‌کند.
      fetchMyAccessibleSites("attendance.manage_clock_records").then(({ unrestricted, sites }) => {
        if (unrestricted) {
          fetchSites().then((data) => setSiteOptions(data || []));
        } else {
          setSiteOptions(sites);
        }
      });
    }
  }, [canManage]);

  function handleSaved() {
    setDialogMode(null);
    setEditingLog(null);
    setSlotPreset(null);
    setReloadKey((k) => k + 1);
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    await deleteAttendanceLog(deleteTarget.id);
    setDeleteTarget(null);
    setReloadKey((k) => k + 1);
  }

  function handleAddMissing(row, type) {
    setSlotPreset({
      employeeId: row.employeeId,
      employeeName: row.employeeName,
      personnelCode: row.personnelCode,
      logType: type === "in" ? "check_in" : "check_out",
      dayDate: row.sessions[0]?.checkIn?.created_at || row.sessions[0]?.checkOut?.created_at || new Date(),
    });
    setDialogMode("createForSlot");
  }

  const pageRows = groupedRows ? groupedRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : null;

  // تعداد ستون‌های ورود/خروج پویا است — بر اساس بیشترین تعداد نوبت در بین
  // ردیف‌های همین صفحه، نه یک عدد ثابت. اگر یک پرسنل آن روز ۳ بار ورود/خروج
  // زده باشد، ۳ زوج ستون نشان داده می‌شود؛ ردیف‌های دیگر همان ستون‌های اضافه
  // را خالی می‌بینند.
  const maxSessions = useMemo(() => {
    if (!pageRows) return 1;
    return Math.max(1, ...pageRows.map((r) => r.sessions.length));
  }, [pageRows]);

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
              setSlotPreset(null);
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
        <SiteFilterSelect
          value={selectedSiteId}
          permission="attendance.view_clock_records"
          onChange={(value) => {
            setSelectedSiteId(value);
            setPage(1);
          }}
        />
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
          <TableContainer sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>پرسنل</TableCell>
                  <TableCell>تاریخ</TableCell>
                  {Array.from({ length: maxSessions }, (_, i) => i).flatMap((i) => [
                    <TableCell key={`h-in-${i}`}>{maxSessions > 1 ? `ورود ${i + 1}` : "ورود"}</TableCell>,
                    <TableCell key={`h-out-${i}`}>{maxSessions > 1 ? `خروج ${i + 1}` : "خروج"}</TableCell>,
                  ])}
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
                    {Array.from({ length: maxSessions }, (_, i) => i).flatMap((i) => {
                      const session = row.sessions[i];
                      return [
                        <TableCell key={`in-${i}`}>
                          <LogCell
                            log={session?.checkIn}
                            type="in"
                            canManage={canManage}
                            row={row}
                            onEdit={(log) => {
                              setDialogMode("edit");
                              setEditingLog(log);
                            }}
                            onAdd={handleAddMissing}
                            onDelete={(log) => setDeleteTarget(log)}
                          />
                        </TableCell>,
                        <TableCell key={`out-${i}`}>
                          <LogCell
                            log={session?.checkOut}
                            type="out"
                            canManage={canManage}
                            row={row}
                            onEdit={(log) => {
                              setDialogMode("edit");
                              setEditingLog(log);
                            }}
                            onAdd={handleAddMissing}
                            onDelete={(log) => setDeleteTarget(log)}
                          />
                        </TableCell>,
                      ];
                    })}
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
        preset={slotPreset}
        siteOptions={siteOptions}
        onClose={() => {
          setDialogMode(null);
          setEditingLog(null);
          setSlotPreset(null);
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
