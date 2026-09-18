import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  IconButton,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  TextField,
  Typography,
} from "@mui/material";
import CheckOutlinedIcon from "@mui/icons-material/CheckOutlined";
import CloseOutlinedIcon from "@mui/icons-material/CloseOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import BackLink from "../components/BackLink";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";
import TimeSelect24 from "../components/TimeSelect24";
import { useAuth } from "../context/AuthContext";
import { fetchSites } from "../api/sites";
import {
  adminUpdateLeaveRequest,
  exportLeaveRequests,
  fetchAllLeaveRequestsForSite,
  fetchLeaveRequestTypes,
} from "../api/leaveRequestsAdmin";

const STATUS_LABELS = { pending: "در حال بررسی", approved: "تائید شده", rejected: "رد شده" };
const STATUS_COLORS = { pending: "warning", approved: "success", rejected: "error" };

function formatCompactTime(compact) {
  if (compact == null) return "—";
  const hour = Math.floor(compact / 100);
  const minute = compact % 100;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

// ⚠️ طبق درخواست صریح کاربر: «امروز» یعنی امروز جزو بازه‌ی خودِ
// مرخصی/ماموریت است (نه تاریخ ثبت درخواست) - حراست باید بداند امروز
// چه کسانی مرخصی/ماموریت هستند، نه چه کسانی امروز برای روزی دیگر
// درخواست ثبت کرده‌اند. درخواست‌های رد‌شده هرگز «امروز فعال» نیستند.
function isRequestActiveToday(item) {
  if (item.status === "rejected" || !item.start_date) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (item.start_hour != null) {
    const start = new Date(item.start_date);
    start.setHours(0, 0, 0, 0);
    return start.getTime() === today.getTime();
  }
  const start = new Date(item.start_date);
  start.setHours(0, 0, 0, 0);
  const end = item.end_date ? new Date(item.end_date) : start;
  end.setHours(0, 0, 0, 0);
  return today.getTime() >= start.getTime() && today.getTime() <= end.getTime();
}

function timeStringToCompact(timeStr) {
  if (!timeStr) return null;
  const [h, m] = timeStr.split(":").map(Number);
  return h * 100 + m;
}

function compactTimeToString(compact) {
  if (compact == null) return "";
  const hour = Math.floor(compact / 100);
  const minute = compact % 100;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function toDateOnly(date) {
  if (!date) return null;
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// ⚠️ طبق درخواست صریح کاربر: «مدت» دیگر یک فیلد خام نیست - همیشه از
// روی ساعت/تاریخ شروع و پایان محاسبه و نمایش داده می‌شود (نه ویرایش
// مستقیم) - ساعتی: به ساعت و دقیقه؛ روزانه: به تعداد روز.
function formatDuration(item) {
  if (item.start_hour != null && item.end_hour != null) {
    const startMinutes = Math.floor(item.start_hour / 100) * 60 + (item.start_hour % 100);
    const endMinutes = Math.floor(item.end_hour / 100) * 60 + (item.end_hour % 100);
    const diff = endMinutes - startMinutes;
    if (diff <= 0) return "—";
    const h = Math.floor(diff / 60);
    const m = diff % 60;
    return h > 0 ? `${h} ساعت${m > 0 ? ` و ${m} دقیقه` : ""}` : `${m} دقیقه`;
  }
  if (item.start_date && item.end_date) {
    const start = new Date(item.start_date);
    const end = new Date(item.end_date);
    const days = Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1;
    return days > 0 ? `${days} روز` : "—";
  }
  return "—";
}

function EditableText({ value, onSave, multiline }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || "");
  const [saving, setSaving] = useState(false);

  if (!editing) {
    return (
      <Box
        onClick={() => {
          setDraft(value || "");
          setEditing(true);
        }}
        sx={{ cursor: "pointer", minHeight: 24, "&:hover": { bgcolor: "action.hover" }, borderRadius: 1, px: 0.5 }}
      >
        {value || "—"}
      </Box>
    );
  }
  return (
    <Stack direction="row" spacing={0.5} alignItems="center">
      <TextField
        size="small"
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        multiline={multiline}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !multiline) handleSave();
          if (e.key === "Escape") setEditing(false);
        }}
      />
      <IconButton size="small" color="success" disabled={saving} onClick={handleSave}>
        <CheckOutlinedIcon fontSize="small" />
      </IconButton>
      <IconButton size="small" onClick={() => setEditing(false)} disabled={saving}>
        <CloseOutlinedIcon fontSize="small" />
      </IconButton>
    </Stack>
  );

  async function handleSave() {
    setSaving(true);
    await onSave(draft);
    setSaving(false);
    setEditing(false);
  }
}

function EditableSelect({ value, options, onSave, renderValue }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  if (!editing) {
    return (
      <Box
        onClick={() => setEditing(true)}
        sx={{ cursor: "pointer", minHeight: 24, "&:hover": { bgcolor: "action.hover" }, borderRadius: 1, px: 0.5 }}
      >
        {renderValue(value)}
      </Box>
    );
  }
  return (
    <TextField
      select
      size="small"
      autoFocus
      value={value}
      disabled={saving}
      onChange={async (e) => {
        setSaving(true);
        await onSave(e.target.value);
        setSaving(false);
        setEditing(false);
      }}
      onBlur={() => setEditing(false)}
      sx={{ minWidth: 140 }}
    >
      {options.map((o) => (
        <MenuItem key={o.value} value={o.value}>
          {o.label}
        </MenuItem>
      ))}
    </TextField>
  );
}

function EditableTimeRange({ item, onSave }) {
  const isHourly = item.start_hour != null;
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [startDate, setStartDate] = useState(item.start_date ? new Date(item.start_date) : new Date());
  const [endDate, setEndDate] = useState(item.end_date ? new Date(item.end_date) : new Date());
  const [startTimeStr, setStartTimeStr] = useState(compactTimeToString(item.start_hour) || "08:00");
  const [endTimeStr, setEndTimeStr] = useState(compactTimeToString(item.end_hour) || "10:00");

  if (!editing) {
    const label = isHourly
      ? `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
      : `${item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"} تا ${
          item.end_date ? new Date(item.end_date).toLocaleDateString("fa-IR") : "—"
        }`;
    return (
      <Box
        onClick={() => setEditing(true)}
        sx={{ cursor: "pointer", minHeight: 24, "&:hover": { bgcolor: "action.hover" }, borderRadius: 1, px: 0.5 }}
      >
        {label}
      </Box>
    );
  }

  async function handleSave() {
    setSaving(true);
    const payload = { start_date: toDateOnly(startDate) };
    if (isHourly) {
      payload.start_hour = timeStringToCompact(startTimeStr);
      payload.end_hour = timeStringToCompact(endTimeStr);
    } else {
      payload.end_date = toDateOnly(endDate);
    }
    await onSave(payload);
    setSaving(false);
    setEditing(false);
  }

  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 260 }}>
      {isHourly ? (
        <>
          <JalaliDateTimePicker value={startDate} onChange={setStartDate} label="تاریخ" showTime={false} />
          <TimeSelect24 label="شروع" value={startTimeStr} onChange={setStartTimeStr} />
          <TimeSelect24 label="پایان" value={endTimeStr} onChange={setEndTimeStr} />
        </>
      ) : (
        <>
          <JalaliDateTimePicker value={startDate} onChange={setStartDate} label="تاریخ مرخصی/ماموریت" showTime={false} />
          <JalaliDateTimePicker value={endDate} onChange={setEndDate} label="تاریخ پایان" showTime={false} />
        </>
      )}
      <IconButton size="small" color="success" disabled={saving} onClick={handleSave}>
        <CheckOutlinedIcon fontSize="small" />
      </IconButton>
      <IconButton size="small" onClick={() => setEditing(false)} disabled={saving}>
        <CloseOutlinedIcon fontSize="small" />
      </IconButton>
    </Stack>
  );
}

const STATUS_OPTIONS = [
  { value: "pending", label: "در حال بررسی" },
  { value: "approved", label: "تائید شده" },
  { value: "rejected", label: "رد شده" },
];

export default function LeaveRequestsAdminListPage() {
  const { user } = useAuth();
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("");
  const [requests, setRequests] = useState(null);
  // ⚠️ داده‌ی مستقل و بدون فیلترِ کارت «امروز» - جدا از requests که
  // فیلترهای انتخابی کاربر روی آن اعمال شده است.
  const [todaySourceRequests, setTodaySourceRequests] = useState(null);
  const [types, setTypes] = useState([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState("submitted_at");
  const [sortDir, setSortDir] = useState("desc");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [dateFrom, setDateFrom] = useState(null);
  const [dateTo, setDateTo] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  // ⚠️ فیلترهایی که سمت سرور اعمال می‌شوند (نه فقط روی داده‌ی لودشده) -
  // تا خروجی Excel هم دقیقاً همان چیزی باشد که کاربر روی صفحه می‌بیند.
  const serverFilters = useMemo(() => {
    const f = {};
    if (statusFilter) f.status_filter = statusFilter;
    if (typeFilter) f.type_id = typeFilter;
    if (departmentFilter) f.department = departmentFilter;
    if (dateFrom) f.date_from = toDateOnly(dateFrom);
    if (dateTo) f.date_to = toDateOnly(dateTo);
    return f;
  }, [statusFilter, typeFilter, departmentFilter, dateFrom, dateTo]);

  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      if (data.length > 0) setSiteId(data[0].id);
    });
  }, []);

  function load() {
    if (!siteId) return;
    setError("");
    // ⚠️ کارت «درخواست‌های مرخصی و ماموریت امروز» عمداً داده‌ی خودش را
    // جداگانه و بدون هیچ فیلتری می‌گیرد - وگرنه با انتخاب هر فیلتری
    // (مثلاً وضعیت یا واحد) بی‌صدا کوچک می‌شد، در حالی که این کارت باید
    // همیشه تصویر کاملِ «امروز چه کسانی مرخصی/ماموریت هستند» را نشان
    // دهد. سطح دسترسی (از جمله محدودیت به‌تفکیک نوع برای حراست) همچنان
    // سمت سرور اعمال می‌شود، پس هرکس فقط نوع‌های مجاز خودش را می‌بیند.
    fetchAllLeaveRequestsForSite(siteId)
      .then(setTodaySourceRequests)
      .catch(() => setTodaySourceRequests([]));
    fetchAllLeaveRequestsForSite(siteId, serverFilters)
      .then(setRequests)
      .catch((err) => {
        // ⚠️ طبق تصمیم صریح کاربر: سایت پیش‌فرض (اولین سایت لیست) لزوماً
        // همان سایتی نیست که این کاربر مجوز مشاهده‌اش را دارد (مثلاً
        // نقشی مثل «حراست» فقط برای یک نوع در یک سایت خاص مجوز دارد) -
        // اگر همین سایت ۴۰۳ داد، خودکار سراغ سایت بعدیِ لیست می‌رویم، به‌
        // جای اینکه کاربر با صفحه خالی/خطا بماند.
        if (err.response?.status === 403 && sites.length > 1) {
          const currentIndex = sites.findIndex((s) => s.id === siteId);
          const nextSite = sites[currentIndex + 1];
          if (nextSite) {
            setSiteId(nextSite.id);
            return;
          }
        }
        setError(err.response?.data?.detail || "دریافت درخواست‌ها با خطا مواجه شد.");
      });
  }

  useEffect(load, [siteId, serverFilters]);

  async function handleExport() {
    setError("");
    setIsExporting(true);
    try {
      const blob = await exportLeaveRequests(siteId, serverFilters);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `leave-requests-${siteId}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.response?.data?.detail || "تهیه خروجی Excel با خطا مواجه شد.");
    } finally {
      setIsExporting(false);
    }
  }

  const canEdit = Boolean(user?.can_manage_leave_requests);
  // ⚠️ نقشی مثل «حراست» - فقط مجوز به‌تفکیک نوع دارد، نه مجوز سراسری.
  // برای این افراد: بدون درخواست‌های در حال بررسی، بدون خروجی Excel،
  // بدون فیلتر بازه تاریخ (همه این محدودیت‌ها سمت سرور هم اعمال می‌شوند).
  const isTypeRestricted = Boolean(user?.leave_requests_type_restricted);

  useEffect(() => {
    if (!siteId || !canEdit) return;
    fetchLeaveRequestTypes(siteId)
      .then(setTypes)
      .catch(() => setTypes([]));
  }, [siteId, canEdit]);

  async function handleFieldSave(requestId, payload) {
    setError("");
    try {
      await adminUpdateLeaveRequest(siteId, requestId, payload);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره تغییرات با خطا مواجه شد.");
    }
  }

  function handleSort(field) {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  // ⚠️ فهرست واحدها از خودِ داده‌ی لودشده ساخته می‌شود (نه یک درخواست
  // اضافه) - فقط واحدهایی که واقعاً درخواستی دارند در فیلتر ظاهر می‌شوند.
  const availableDepartments = useMemo(() => {
    if (!requests) return [];
    return [...new Set(requests.map((item) => item.requester_department).filter(Boolean))].sort();
  }, [requests]);

  const todayRequests = useMemo(() => {
    if (!todaySourceRequests) return [];
    return todaySourceRequests.filter((item) => isRequestActiveToday(item));
  }, [todaySourceRequests]);

  // ⚠️ با تغییر جست‌وجو/فیلترها، به صفحه اول برگرد - وگرنه ممکن است
  // کاربر روی صفحه‌ای بماند که دیگر ردیفی ندارد و جدول خالی به‌نظر برسد.
  useEffect(() => {
    setPage(0);
  }, [search, statusFilter, typeFilter, departmentFilter, dateFrom, dateTo, siteId]);

  const visibleRequests = useMemo(() => {
    if (!requests) return [];
    const term = search.trim().toLowerCase();
    let filtered = requests;
    if (term) {
      filtered = requests.filter((item) =>
        [item.requester_name, item.type_title, item.description, String(item.emp_no)]
          .filter(Boolean)
          .some((field) => String(field).toLowerCase().includes(term))
      );
    }
    const sorted = [...filtered].sort((a, b) => {
      let av = a[sortField];
      let bv = b[sortField];
      if (sortField === "start_date" || sortField === "submitted_at") {
        av = av ? new Date(av).getTime() : 0;
        bv = bv ? new Date(bv).getTime() : 0;
      } else {
        av = (av ?? "").toString();
        bv = (bv ?? "").toString();
      }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [requests, search, sortField, sortDir]);

  return (
    <Box>
      <BackLink to="/access" label="بازگشت" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        درخواست‌های مرخصی/ماموریت
      </Typography>

      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
        <TextField select label="سایت" value={siteId} onChange={(e) => setSiteId(e.target.value)} sx={{ minWidth: 240 }}>
          {sites.map((site) => (
            <MenuItem key={site.id} value={site.id}>
              {site.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="جست‌وجو"
          placeholder="نام، نوع، توضیحات..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 240 }}
        />
        <TextField
          select
          label="وضعیت"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="">همه</MenuItem>
          {/* ⚠️ گزینه «در حال بررسی» برای همه در دسترس است - محدودیت نقشِ
              محدود به نوع (حراست) فقط شامل انواع **ساعتی** است و سمت
              سرور اعمال می‌شود؛ انواع روزانه در حال بررسی را می‌بیند. */}
          <MenuItem value="pending">در حال بررسی</MenuItem>
          <MenuItem value="approved">تائید شده</MenuItem>
          <MenuItem value="rejected">رد شده</MenuItem>
        </TextField>
        <TextField
          select
          label="نوع درخواست"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="">همه</MenuItem>
          {types.map((t) => (
            <MenuItem key={t.id} value={t.id}>
              {t.title}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="واحد"
          value={departmentFilter}
          onChange={(e) => setDepartmentFilter(e.target.value)}
          sx={{ minWidth: 180 }}
        >
          <MenuItem value="">همه</MenuItem>
          {availableDepartments.map((d) => (
            <MenuItem key={d} value={d}>
              {d}
            </MenuItem>
          ))}
        </TextField>
        {!isTypeRestricted && (
          <Button
            variant="outlined"
            startIcon={<FileDownloadOutlinedIcon />}
            onClick={handleExport}
            disabled={isExporting || !siteId}
          >
            {isExporting ? "در حال آماده‌سازی..." : "خروجی Excel"}
          </Button>
        )}
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {todayRequests.length > 0 && (
        <Card variant="outlined" sx={{ mb: 3, p: 2, borderColor: "primary.main", borderWidth: 2 }}>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 1.5 }}>
            درخواست‌های مرخصی و ماموریت امروز ({todayRequests.length})
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>نام و نام خانوادگی</TableCell>
                  <TableCell>واحد</TableCell>
                  <TableCell>نوع درخواست</TableCell>
                  <TableCell>بازه زمانی</TableCell>
                  <TableCell>وضعیت</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {todayRequests.map((item) => (
                  <TableRow key={item.request_id}>
                    <TableCell>{item.requester_name || item.emp_no}</TableCell>
                    <TableCell>{item.requester_department || "—"}</TableCell>
                    <TableCell>{item.type_title || "—"}</TableCell>
                    <TableCell>
                      {item.start_hour != null
                        ? `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
                        : `${item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"} تا ${
                            item.end_date ? new Date(item.end_date).toLocaleDateString("fa-IR") : "—"
                          }`}
                    </TableCell>
                    <TableCell>
                      <Chip size="small" color={STATUS_COLORS[item.status]} label={STATUS_LABELS[item.status]} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Card>
      )}

      {requests !== null && requests.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          هیچ درخواستی برای این سایت یافت نشد.
        </Typography>
      )}

      {requests !== null && requests.length > 0 && (
        <TableContainer component={Card} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel
                    active={sortField === "requester_name"}
                    direction={sortField === "requester_name" ? sortDir : "asc"}
                    onClick={() => handleSort("requester_name")}
                  >
                    نام و نام خانوادگی
                  </TableSortLabel>
                </TableCell>
                <TableCell>واحد</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === "type_title"}
                    direction={sortField === "type_title" ? sortDir : "asc"}
                    onClick={() => handleSort("type_title")}
                  >
                    نوع درخواست
                  </TableSortLabel>
                </TableCell>
                <TableCell>توضیحات</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === "submitted_at"}
                    direction={sortField === "submitted_at" ? sortDir : "asc"}
                    onClick={() => handleSort("submitted_at")}
                  >
                    تاریخ ثبت
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === "start_date"}
                    direction={sortField === "start_date" ? sortDir : "asc"}
                    onClick={() => handleSort("start_date")}
                  >
                    تاریخ مرخصی/ماموریت
                  </TableSortLabel>
                </TableCell>
                <TableCell>مدت</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === "status"}
                    direction={sortField === "status" ? sortDir : "asc"}
                    onClick={() => handleSort("status")}
                  >
                    وضعیت
                  </TableSortLabel>
                </TableCell>
                <TableCell>نظر تأییدکننده</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {visibleRequests.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage).map((item) => (
                <TableRow key={item.request_id}>
                  <TableCell>{item.requester_name || item.emp_no}</TableCell>
                  <TableCell>{item.requester_department || "—"}</TableCell>
                  <TableCell>
                    {canEdit && types.length > 0 ? (
                      <EditableSelect
                        value={item.type_id || ""}
                        options={types.map((t) => ({ value: t.id, label: t.title }))}
                        renderValue={() => item.type_title || "—"}
                        onSave={(v) => handleFieldSave(item.request_id, { leave_type_id: v })}
                      />
                    ) : (
                      item.type_title || "—"
                    )}
                  </TableCell>
                  <TableCell>
                    {canEdit ? (
                      <EditableText
                        value={item.description}
                        multiline
                        onSave={(v) => handleFieldSave(item.request_id, { description: v })}
                      />
                    ) : (
                      item.description || "—"
                    )}
                  </TableCell>
                  <TableCell>
                    {item.submitted_at ? new Date(item.submitted_at).toLocaleDateString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>
                    {canEdit ? (
                      <EditableTimeRange item={item} onSave={(payload) => handleFieldSave(item.request_id, payload)} />
                    ) : item.start_hour != null ? (
                      `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
                    ) : (
                      `${item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"} تا ${
                        item.end_date ? new Date(item.end_date).toLocaleDateString("fa-IR") : "—"
                      }`
                    )}
                  </TableCell>
                  <TableCell>{formatDuration(item)}</TableCell>
                  <TableCell>
                    {canEdit ? (
                      <EditableSelect
                        value={item.status}
                        options={STATUS_OPTIONS}
                        renderValue={(v) => <Chip size="small" color={STATUS_COLORS[v]} label={STATUS_LABELS[v]} />}
                        onSave={(v) =>
                          handleFieldSave(item.request_id, {
                            is_final_approved: v === "approved" ? true : v === "rejected" ? false : null,
                          })
                        }
                      />
                    ) : (
                      <Chip size="small" color={STATUS_COLORS[item.status]} label={STATUS_LABELS[item.status]} />
                    )}
                  </TableCell>
                  <TableCell>
                    {canEdit ? (
                      <EditableText
                        value={item.manager_idea}
                        multiline
                        onSave={(v) => handleFieldSave(item.request_id, { manager_idea: v })}
                      />
                    ) : (
                      item.manager_idea || "—"
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={visibleRequests.length}
            page={page}
            onPageChange={(_, newPage) => setPage(newPage)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[10, 25, 50, 100]}
            labelRowsPerPage="تعداد در هر صفحه:"
            labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
          />
        </TableContainer>
      )}

      {/* ⚠️ طبق درخواست صریح کاربر: فیلتر بازه تاریخ زیر جدول قرار گرفت
          (نه بالای آن). برای نقش محدود به نوع (حراست) اصلاً نمایش داده
          نمی‌شود - همان محدودیت سمت سرور هم اعمال می‌شود. */}
      {!isTypeRestricted && (
        <Card variant="outlined" sx={{ mt: 2, p: 2, borderRadius: 2 }}>
          <Typography variant="body2" fontWeight={700} sx={{ mb: 1.5 }}>
            فیلتر بر اساس بازه تاریخ مرخصی/ماموریت
          </Typography>
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="center">
            <JalaliDateTimePicker value={dateFrom} onChange={setDateFrom} label="از تاریخ" showTime={false} />
            <JalaliDateTimePicker value={dateTo} onChange={setDateTo} label="تا تاریخ" showTime={false} />
            {(dateFrom || dateTo) && (
              <Button
                size="small"
                onClick={() => {
                  setDateFrom(null);
                  setDateTo(null);
                }}
              >
                حذف فیلتر تاریخ
              </Button>
            )}
          </Stack>
        </Card>
      )}
    </Box>
  );
}
