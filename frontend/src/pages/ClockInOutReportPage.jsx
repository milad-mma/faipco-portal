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

const PAGE_SIZE = 50; // تعداد ردیف (روز-پرسنل) در هر صفحه
const ATTENDANCE_PILOT_ROLE = "attendance-pilot"; // نقش پرسنلی که مجاز به ثبت ورود/خروج GPS هستند

// تاریخ/ساعت پیش‌فرض برای ثبت رکورد در یک اسلات خالی: اگر روز، امروز باشد «همین لحظه»، وگرنه ساعت ۰۸:۰۰ همان روز
function buildPresetDate(dayDate) {
  const d = new Date(dayDate);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) return now;
  d.setHours(8, 0, 0, 0);
  return d;
}

/**
 * دیالوگ ثبت/ویرایش دستی یک رکورد ورود/خروج.
 * ورودی: mode یکی از "create" (دکمه‌ی بالای صفحه، انتخاب آزاد پرسنل) | "createForSlot" (آیکون + کنار اسلات خالی؛
 * پرسنل و نوع از preset می‌آید) | "edit" (ویرایش initialLog)، به همراه لیست سایت‌ها و callbackهای بستن/ذخیره.
 */
function LogEditDialog({ open, onClose, onSaved, mode, initialLog, preset, siteOptions }) {
  const [employee, setEmployee] = useState(null); // پرسنل انتخابی؛ در حالت edit همیشه null (پرسنل رکورد ثابت است)
  const [employeeOptions, setEmployeeOptions] = useState([]); // نتایج جستجوی پرسنل برای Autocomplete
  const [employeeSearch, setEmployeeSearch] = useState(""); // متن جستجوی پرسنل
  const [logType, setLogType] = useState("check_in"); // نوع رکورد: check_in | check_out
  const [dateValue, setDateValue] = useState(new Date()); // تاریخ و ساعت رکورد
  const [site, setSite] = useState(null); // سایت انتخابی (اختیاری)
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // با هر بار باز شدن دیالوگ، فیلدها را بر اساس mode مقداردهی اولیه می‌کند
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

  // جستجوی پرسنل برای حالت create؛ فقط پرسنلی که نقش attendance-pilot دارند (تنها همان‌ها مجاز به این قابلیت‌اند)
  useEffect(() => {
    if (mode !== "create") return;
    fetchEmployees({ search: employeeSearch, pageSize: 20, hasRole: ATTENDANCE_PILOT_ROLE }).then((data) =>
      setEmployeeOptions(data.items || [])
    );
  }, [mode, employeeSearch]);

  // اعتبارسنجی و ذخیره: در حالت edit رکورد را به‌روز می‌کند، در غیر این صورت رکورد جدید می‌سازد و onSaved را صدا می‌زند
  async function handleSave() {
    setError("");
    // انتخاب پرسنل فقط برای create/createForSlot لازم است؛ در حالت edit پرسنل رکورد از قبل مشخص است
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
      setError(err.response?.data?.detail || "ثبت با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  const employeeIsLocked = mode === "createForSlot" || mode === "edit"; // پرسنل قابل تغییر نیست؛ فقط نمایش داده می‌شود

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        {mode === "create" && "افزودن رکورد دستی"}
        {mode === "createForSlot" && "ثبت رکورد"}
        {mode === "edit" && "ویرایش رکورد"}
      </DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {/* پرسنل: فیلد غیرفعال (قفل‌شده) یا Autocomplete جستجو */}
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

        {/* نوع رکورد (در createForSlot ثابت است)، تاریخ/ساعت شمسی و سایت اختیاری */}
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
        {error && <Alert severity="error">{error}</Alert>}
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

/**
 * سلول یک ورود یا خروج در جدول.
 * ورودی: لاگ (یا undefined برای اسلات خالی)، نوع "in"/"out"، مجوز مدیریت، ردیف و callbackهای ویرایش/افزودن/حذف.
 * اسلات خالی: خط تیره یا دکمه‌ی افزودن؛ لاگ موجود: چیپ ساعت (با ستاره برای رکورد دستی) و دکمه‌های ویرایش/حذف.
 */
function LogCell({ log, type, canManage, row, onEdit, onAdd, onDelete }) {
  // اسلات خالی
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

/**
 * صفحه‌ی گزارش ثبت ورود و خروج GPS (آزمایشی) برای مدیران.
 * لاگ‌های همه‌ی پرسنل را با فیلتر سایت/پرسنل/ماه می‌گیرد، به ازای هر پرسنل-روز گروه‌بندی می‌کند
 * و در جدولی با ستون‌های پویای ورود/خروج نمایش می‌دهد. کاربران دارای مجوز می‌توانند رکورد دستی ثبت، ویرایش یا حذف کنند.
 */
export default function ClockInOutReportPage() {
  const { user } = useAuth();
  const canManage = Boolean(user?.can_manage_clock_records); // مجوز ثبت/ویرایش/حذف دستی رکوردها

  const [groupedRows, setGroupedRows] = useState(null); // ردیف‌های گروه‌بندی‌شده به ازای پرسنل-روز؛ null = در حال بارگذاری
  const [page, setPage] = useState(1); // صفحه‌ی جاری (صفحه‌بندی سمت کلاینت)
  const [selectedEmployee, setSelectedEmployee] = useState(null); // فیلتر پرسنل
  const [selectedSiteId, setSelectedSiteId] = useState(null); // فیلتر سایت
  const [period, setPeriod] = useState({ year: null, month: null }); // ماه شمسی انتخابی؛ null = ماه جاری از سرور

  const [employeeOptions, setEmployeeOptions] = useState([]); // نتایج جستجوی پرسنل برای فیلتر
  const [employeeSearch, setEmployeeSearch] = useState(""); // متن جستجوی پرسنل
  const [siteOptions, setSiteOptions] = useState([]); // سایت‌های قابل انتخاب در دیالوگ ثبت/ویرایش

  const [dialogMode, setDialogMode] = useState(null); // "create" | "createForSlot" | "edit" | null (بسته)
  const [editingLog, setEditingLog] = useState(null); // لاگ در حال ویرایش
  const [slotPreset, setSlotPreset] = useState(null); // پرسنل/نوع/روز از پیش تعیین‌شده برای اسلات خالی
  const [deleteTarget, setDeleteTarget] = useState(null); // لاگ در انتظار تأیید حذف
  const [reloadKey, setReloadKey] = useState(0); // با افزایش، لیست دوباره بارگذاری می‌شود

  // بارگذاری لاگ‌ها: ورودها و خروج‌های ماه را جداگانه می‌گیرد، ترکیب و به ازای پرسنل-روز گروه‌بندی می‌کند
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

  // جستجوی پرسنل برای فیلتر بالای صفحه
  useEffect(() => {
    fetchEmployees({ search: employeeSearch, pageSize: 20 }).then((data) => setEmployeeOptions(data.items || []));
  }, [employeeSearch]);

  // سایت‌های قابل انتخاب در دیالوگ: فقط سایت‌هایی که کاربر برایشان مجوز مدیریت رکورد دارد
  // (اگر مجوز بدون محدودیت سایت باشد، همه‌ی سایت‌ها)
  useEffect(() => {
    if (canManage) {
      fetchMyAccessibleSites("attendance.manage_clock_records").then(({ unrestricted, sites }) => {
        if (unrestricted) {
          fetchSites().then((data) => setSiteOptions(data || []));
        } else {
          setSiteOptions(sites);
        }
      });
    }
  }, [canManage]);

  // بعد از ذخیره‌ی موفق دیالوگ: بستن دیالوگ و بارگذاری مجدد لیست
  function handleSaved() {
    setDialogMode(null);
    setEditingLog(null);
    setSlotPreset(null);
    setReloadKey((k) => k + 1);
  }

  // حذف لاگ انتخاب‌شده پس از تأیید کاربر و بارگذاری مجدد لیست
  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    await deleteAttendanceLog(deleteTarget.id);
    setDeleteTarget(null);
    setReloadKey((k) => k + 1);
  }

  // باز کردن دیالوگ ثبت برای یک اسلات خالی (ورود یا خروج) با پرسنل و روز همان ردیف
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

  const pageRows = groupedRows ? groupedRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : null; // ردیف‌های صفحه‌ی جاری

  // تعداد زوج‌ستون‌های ورود/خروج: بیشترین تعداد نوبت در بین ردیف‌های همین صفحه (حداقل ۱)؛
  // ردیف‌هایی با نوبت کمتر، ستون‌های اضافه را خالی می‌بینند
  const maxSessions = useMemo(() => {
    if (!pageRows) return 1;
    return Math.max(1, ...pageRows.map((r) => r.sessions.length));
  }, [pageRows]);

  return (
    <Box>
      {/* عنوان صفحه و دکمه‌ی افزودن رکورد دستی (فقط با مجوز مدیریت) */}
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
      {/* هشدار آزمایشی بودن سیستم GPS */}
      <Alert severity="warning" icon={<ScienceOutlinedIcon />} sx={{ mb: 3, mt: 1 }}>
        این قابلیت آزمایشی است. ثبت ورود/خروج رسمی همچنان باید از طریق دستگاه‌های تعبیه‌شده در
        کارخانه انجام شود.{canManage && " رکوردهایی که دستی ثبت/ویرایش شده‌اند با یک ⭐ کنار ساعت مشخص می‌شوند."}
      </Alert>

      {/* فیلترها: سایت، پرسنل و ماه/سال؛ هر تغییر صفحه را به ۱ برمی‌گرداند */}
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

      {/* در حال بارگذاری / بدون رکورد / جدول ردیف‌های پرسنل-روز با صفحه‌بندی */}
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
              {/* سرستون‌ها: پرسنل، تاریخ، زوج‌ستون‌های پویای ورود/خروج و سایت مطابق */}
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
                    {/* به ازای هر نوبت، یک سلول ورود و یک سلول خروج */}
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

          {/* صفحه‌بندی سمت کلاینت */}
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

      {/* دیالوگ ثبت/ویرایش رکورد */}
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

      {/* دیالوگ تأیید حذف رکورد */}
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
