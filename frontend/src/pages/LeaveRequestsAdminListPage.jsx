import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  IconButton,
  MenuItem,
  Snackbar,
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
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import CloseOutlinedIcon from "@mui/icons-material/CloseOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import BackLink from "../components/BackLink";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";
import TimeSelect24 from "../components/TimeSelect24";
import { useAuth } from "../context/AuthContext";
import { fetchSites } from "../api/sites";
import {
  adminDeleteLeaveRequest,
  adminUpdateLeaveRequest,
  exportLeaveRequests,
  fetchAllLeaveRequestsForSite,
  fetchLeaveRequestTypes,
} from "../api/leaveRequestsAdmin";

// برچسب و رنگ چیپ هر وضعیت درخواست
const STATUS_LABELS = { pending: "در حال بررسی", approved: "تائید شده", rejected: "رد شده", cancelled: "ابطال شده" };
const STATUS_COLORS = { pending: "warning", approved: "success", rejected: "error", cancelled: "default" };

// ساعت فشرده‌ی عددی (مثلاً 830) را به رشته‌ی «08:30» تبدیل می‌کند؛ null -> خط تیره
function formatCompactTime(compact) {
  if (compact == null) return "—";
  const hour = Math.floor(compact / 100);
  const minute = compact % 100;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

// آیا امروز جزو بازه‌ی خودِ مرخصی/ماموریت است (نه تاریخ ثبت)؛ ساعتی: تاریخ شروع = امروز، روزانه: امروز بین شروع و پایان.
// درخواست‌های رد/ابطال‌شده هرگز «امروز فعال» نیستند.
function isRequestActiveToday(item) {
  if (item.status === "rejected" || item.status === "cancelled" || !item.start_date) return false;
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

// رشته‌ی «HH:MM» را به عدد فشرده‌ی HHMM تبدیل می‌کند (فرمت ذخیره‌ی ساعت در سرور)
function timeStringToCompact(timeStr) {
  if (!timeStr) return null;
  const [h, m] = timeStr.split(":").map(Number);
  return h * 100 + m;
}

// عدد فشرده‌ی HHMM را به رشته‌ی «HH:MM» تبدیل می‌کند؛ null -> رشته‌ی خالی (برای مقدار اولیه‌ی فرم)
function compactTimeToString(compact) {
  if (compact == null) return "";
  const hour = Math.floor(compact / 100);
  const minute = compact % 100;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

// Date را به رشته‌ی YYYY-MM-DD به وقت محلی تبدیل می‌کند؛ null -> null
function toDateOnly(date) {
  if (!date) return null;
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// متن «مدت» که همیشه از شروع/پایان محاسبه می‌شود: ساعتی به ساعت و دقیقه، روزانه به تعداد روز؛ تردد فراموش‌شده مدت ندارد
function formatDuration(item) {
  if (item.is_forgotten_punch) return "—";
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

/**
 * متن قابل ویرایش درجا: با کلیک به فیلد متنی تبدیل می‌شود.
 * ورودی: مقدار فعلی، onSave(متن جدید) و multiline. Enter (تک‌خطی) ذخیره و Escape انصراف است.
 */
function EditableText({ value, onSave, multiline }) {
  const [editing, setEditing] = useState(false); // حالت ویرایش
  const [draft, setDraft] = useState(value || ""); // متن در حال ویرایش
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

  // ذخیره‌ی متن پیش‌نویس و خروج از حالت ویرایش
  async function handleSave() {
    setSaving(true);
    await onSave(draft);
    setSaving(false);
    setEditing(false);
  }
}

/**
 * انتخاب‌گر قابل ویرایش درجا: با کلیک به Select تبدیل می‌شود و با انتخاب گزینه بلافاصله ذخیره می‌کند.
 * ورودی: مقدار فعلی، گزینه‌ها ({ value, label })، onSave(مقدار جدید) و renderValue برای نمایش حالت غیرویرایش.
 */
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

// متن بازه‌ی یک درخواست: ساعتی «شروع تا پایان»، روزانه «تاریخ تا تاریخ»؛ تردد فراموش‌شده فقط یک لحظه (تاریخ + ساعت تردد)
function rangeLabel(item) {
  const fa = (d) => (d ? new Date(d).toLocaleDateString("fa-IR") : "—");
  if (item.is_forgotten_punch) return `${fa(item.start_date)} — تردد ساعت ${formatCompactTime(item.start_hour)}`;
  return item.start_hour != null
    ? `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
    : `${fa(item.start_date)} تا ${fa(item.end_date)}`;
}

// برچسب چیپ وضعیت؛ تردد فراموش‌شده‌ی منتظر مسئول نیروی انسانی برچسب جدا دارد
function statusChipLabel(item) {
  return item.awaiting_hr ? "در انتظار منابع انسانی" : STATUS_LABELS[item.status];
}

/**
 * بازه‌ی زمانی قابل ویرایش درجا؛ فیلدها بسته به نوع درخواست:
 * تردد فراموش‌شده (تاریخ + ساعت)، ساعتی (تاریخ + شروع + پایان)، روزانه (تاریخ شروع + پایان).
 * ورودی: درخواست و onSave(payload) با کلیدهای start_date/end_date/start_hour/end_hour.
 */
function EditableTimeRange({ item, onSave }) {
  const isHourly = item.start_hour != null; // درخواست ساعتی
  const isPunch = Boolean(item.is_forgotten_punch); // تردد فراموش‌شده
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [startDate, setStartDate] = useState(item.start_date ? new Date(item.start_date) : new Date());
  const [endDate, setEndDate] = useState(item.end_date ? new Date(item.end_date) : new Date());
  const [startTimeStr, setStartTimeStr] = useState(compactTimeToString(item.start_hour) || "08:00");
  const [endTimeStr, setEndTimeStr] = useState(compactTimeToString(item.end_hour) || "10:00");

  if (!editing) {
    const label = rangeLabel(item);
    return (
      <Box
        onClick={() => setEditing(true)}
        sx={{ cursor: "pointer", minHeight: 24, "&:hover": { bgcolor: "action.hover" }, borderRadius: 1, px: 0.5 }}
      >
        {label}
      </Box>
    );
  }

  // ساخت payload متناسب با نوع درخواست و ذخیره
  async function handleSave() {
    setSaving(true);
    const payload = { start_date: toDateOnly(startDate) };
    if (isPunch) {
      payload.start_hour = timeStringToCompact(startTimeStr);
    } else if (isHourly) {
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
      {isPunch ? (
        <>
          <JalaliDateTimePicker value={startDate} onChange={setStartDate} label="تاریخ تردد" showTime={false} />
          <TimeSelect24 label="ساعت تردد" value={startTimeStr} onChange={setStartTimeStr} />
        </>
      ) : isHourly ? (
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

// گزینه‌های تغییر وضعیت توسط مدیر (ابطال‌شده قابل انتخاب نیست)
const STATUS_OPTIONS = [
  { value: "pending", label: "در حال بررسی" },
  { value: "approved", label: "تائید شده" },
  { value: "rejected", label: "رد شده" },
];

/**
 * صفحه‌ی مدیریتی لیست همه‌ی درخواست‌های مرخصی/ماموریت یک سایت.
 * شامل کارت «امروز» (بدون فیلتر)، فیلترهای سمت سرور (وضعیت/نوع/واحد/بازه‌ی تاریخ)، جست‌وجو و مرتب‌سازی سمت کلاینت،
 * ویرایش درجا و حذف (با مجوز مدیریت) و خروجی Excel. نقش محدود به نوع (مثل حراست) خروجی Excel و فیلتر تاریخ ندارد.
 */
export default function LeaveRequestsAdminListPage() {
  const { user } = useAuth();
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState(""); // سایت انتخابی
  const [requests, setRequests] = useState(null); // درخواست‌های سایت با فیلترهای سرور؛ null = هنوز بارگذاری نشده
  const [todaySourceRequests, setTodaySourceRequests] = useState(null); // داده‌ی بدون فیلتر برای کارت «امروز»، جدا از requests
  const [types, setTypes] = useState([]); // نوع‌های درخواست سایت (برای فیلتر و ویرایش نوع)
  const [error, setError] = useState("");
  const [search, setSearch] = useState(""); // جست‌وجوی متنی سمت کلاینت
  const [sortField, setSortField] = useState("submitted_at"); // ستون مرتب‌سازی
  const [sortDir, setSortDir] = useState("desc"); // جهت مرتب‌سازی
  const [statusFilter, setStatusFilter] = useState(""); // فیلتر وضعیت (سرور)
  const [typeFilter, setTypeFilter] = useState(""); // فیلتر نوع (سرور)
  const [departmentFilter, setDepartmentFilter] = useState(""); // فیلتر واحد (سرور)
  const [dateFrom, setDateFrom] = useState(null); // فیلتر بازه‌ی تاریخ مرخصی: از
  const [dateTo, setDateTo] = useState(null); // فیلتر بازه‌ی تاریخ مرخصی: تا
  const [isExporting, setIsExporting] = useState(false); // در حال تهیه‌ی خروجی Excel
  const [deletingId, setDeletingId] = useState(null); // شناسه‌ی درخواست در حال حذف
  const [toast, setToast] = useState(""); // پیام موفقیت
  const [page, setPage] = useState(0); // صفحه‌ی جاری (صفحه‌بندی سمت کلاینت)
  const [rowsPerPage, setRowsPerPage] = useState(25);

  // فیلترهایی که سمت سرور اعمال می‌شوند، تا خروجی Excel دقیقاً همان چیزی باشد که کاربر روی صفحه می‌بیند
  const serverFilters = useMemo(() => {
    const f = {};
    if (statusFilter) f.status_filter = statusFilter;
    if (typeFilter) f.type_id = typeFilter;
    if (departmentFilter) f.department = departmentFilter;
    if (dateFrom) f.date_from = toDateOnly(dateFrom);
    if (dateTo) f.date_to = toDateOnly(dateTo);
    return f;
  }, [statusFilter, typeFilter, departmentFilter, dateFrom, dateTo]);

  // بارگذاری سایت‌ها و انتخاب اولین سایت
  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      if (data.length > 0) setSiteId(data[0].id);
    });
  }, []);

  // بارگذاری درخواست‌های سایت: دو درخواست هم‌زمان، یکی بدون فیلتر برای کارت «امروز» و یکی با فیلترهای سرور برای جدول.
  // کارت «امروز» باید همیشه تصویر کامل روز را نشان دهد؛ سطح دسترسی (از جمله محدودیت نوع) سمت سرور اعمال می‌شود.
  function load() {
    if (!siteId) return;
    setError("");
    Promise.all([
      fetchAllLeaveRequestsForSite(siteId),
      fetchAllLeaveRequestsForSite(siteId, serverFilters),
    ])
      .then(([todayData, filteredData]) => {
        setTodaySourceRequests(todayData);
        setRequests(filteredData);
      })
      .catch((err) => {
        // اگر کاربر برای این سایت مجوز ندارد (403)، خودکار سراغ سایت بعدی لیست می‌رود
        // (مثلاً نقش حراست فقط برای یک سایت خاص مجوز دارد)
        if (err.response?.status === 403 && sites.length > 1) {
          const currentIndex = sites.findIndex((s) => s.id === siteId);
          const nextSite = sites[currentIndex + 1];
          if (nextSite) {
            setSiteId(nextSite.id);
            return;
          }
        }
        setTodaySourceRequests([]);
        setError(err.response?.data?.detail || "دریافت درخواست‌ها با خطا مواجه شد.");
      });
  }

  useEffect(load, [siteId, serverFilters]);

  // حذف مدیریتی یک درخواست پس از تأیید کاربر؛ هر درخواستی در هر مرحله‌ای قابل حذف است
  async function handleDelete(item) {
    const who = item.requester_name || item.emp_no;
    if (!window.confirm(`درخواست «${item.type_title || "—"}» برای ${who} حذف شود؟ این عمل قابل بازگشت نیست.`)) {
      return;
    }
    setError("");
    setDeletingId(item.request_id);
    try {
      await adminDeleteLeaveRequest(siteId, item.request_id);
      setToast("درخواست حذف شد.");
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف درخواست با خطا مواجه شد.");
    } finally {
      setDeletingId(null);
    }
  }

  // دریافت فایل Excel با همان فیلترهای سرور و دانلود آن در مرورگر
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

  const canEdit = Boolean(user?.can_manage_leave_requests); // مجوز ویرایش/حذف درجا
  // نقش محدود به نوع (مثل حراست): فقط مجوز به‌تفکیک نوع دارد؛ بدون خروجی Excel و بدون فیلتر بازه‌ی تاریخ (سرور هم اعمال می‌کند)
  const isTypeRestricted = Boolean(user?.leave_requests_type_restricted);

  // بارگذاری نوع‌های درخواست سایت (فقط برای کاربر دارای مجوز ویرایش)
  useEffect(() => {
    if (!siteId || !canEdit) return;
    fetchLeaveRequestTypes(siteId)
      .then(setTypes)
      .catch(() => setTypes([]));
  }, [siteId, canEdit]);

  // ذخیره‌ی ویرایش درجای یک فیلد درخواست و بارگذاری مجدد لیست
  async function handleFieldSave(requestId, payload) {
    setError("");
    try {
      await adminUpdateLeaveRequest(siteId, requestId, payload);
      setToast("تغییرات ذخیره شد.");
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره تغییرات با خطا مواجه شد.");
    }
  }

  // کلیک روی سرستون: همان ستون جهت را برعکس می‌کند، ستون جدید صعودی شروع می‌شود
  function handleSort(field) {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  // فهرست واحدها از خودِ داده‌ی بارگذاری‌شده ساخته می‌شود؛ فقط واحدهایی که درخواست دارند در فیلتر ظاهر می‌شوند
  const availableDepartments = useMemo(() => {
    if (!requests) return [];
    return [...new Set(requests.map((item) => item.requester_department).filter(Boolean))].sort();
  }, [requests]);

  // درخواست‌هایی که امروز جزو بازه‌ی آن‌هاست (برای کارت «امروز»)
  const todayRequests = useMemo(() => {
    if (!todaySourceRequests) return [];
    return todaySourceRequests.filter((item) => isRequestActiveToday(item));
  }, [todaySourceRequests]);

  // با تغییر جست‌وجو/فیلترها/سایت به صفحه‌ی اول برمی‌گردد تا کاربر روی صفحه‌ای بدون ردیف نماند
  useEffect(() => {
    setPage(0);
  }, [search, statusFilter, typeFilter, departmentFilter, dateFrom, dateTo, siteId]);

  // ردیف‌های جدول: اعمال جست‌وجوی متنی (نام، نوع، توضیحات، شماره پرسنلی) و سپس مرتب‌سازی
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
    // ستون‌های تاریخ به‌صورت عددی (timestamp) و بقیه به‌صورت رشته مقایسه می‌شوند
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

      {/* نوار فیلتر: سایت، جست‌وجو، وضعیت، نوع، واحد و دکمه‌ی خروجی Excel */}
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
          {/* گزینه‌ی «در حال بررسی» برای همه هست؛ محدودیت نقش محدود به نوع فقط شامل انواع ساعتی است و سمت سرور اعمال می‌شود */}
          <MenuItem value="pending">در حال بررسی</MenuItem>
          <MenuItem value="approved">تائید شده</MenuItem>
          <MenuItem value="rejected">رد شده</MenuItem>
          <MenuItem value="cancelled">ابطال شده</MenuItem>
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

      {/* کارت «امروز»: همیشه نمایش داده می‌شود، در حالت خالی با پیام روشن */}
      {todaySourceRequests !== null && (
        <Card variant="outlined" sx={{ mb: 3, p: 2, borderColor: "primary.main", borderWidth: 2 }}>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 1.5 }}>
            درخواست‌های مرخصی و ماموریت امروز ({todayRequests.length})
          </Typography>
          {todayRequests.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {isTypeRestricted
                ? "برای امروز درخواست تأیید یا رد شده‌ای وجود ندارد."
                : "برای امروز درخواستی وجود ندارد."}
            </Typography>
          ) : (
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
                    <TableCell>{rangeLabel(item)}</TableCell>
                    <TableCell>
                      <Chip size="small" color={STATUS_COLORS[item.status]} label={statusChipLabel(item)} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          )}
        </Card>
      )}

      {/* پیام نبودن درخواست */}
      {requests !== null && requests.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          هیچ درخواستی برای این سایت یافت نشد.
        </Typography>
      )}

      {/* جدول اصلی با سرستون‌های قابل مرتب‌سازی، سلول‌های قابل ویرایش درجا (با مجوز) و صفحه‌بندی */}
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
                {canEdit && <TableCell>حذف</TableCell>}
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
                    ) : (
                      rangeLabel(item)
                    )}
                  </TableCell>
                  <TableCell>{formatDuration(item)}</TableCell>
                  <TableCell>
                    {/* وضعیت: قابل تغییر با مجوز، به جز ابطال‌شده که در کاراوب ثبت شده و از پرتال قابل تغییر نیست */}
                    {canEdit && item.status !== "cancelled" ? (
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
                      <Chip size="small" color={STATUS_COLORS[item.status]} label={statusChipLabel(item)} />
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
                  {/* حذف مدیریتی: هر درخواستی در هر مرحله‌ای قابل حذف است (ردیف WF_Reviews هم پاک می‌شود) */}
                  {canEdit && (
                    <TableCell>
                      <IconButton
                        size="small"
                        color="error"
                        disabled={deletingId === item.request_id}
                        onClick={() => handleDelete(item)}
                        aria-label="حذف"
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  )}
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

      {/* فیلتر بازه‌ی تاریخ مرخصی/ماموریت زیر جدول؛ برای نقش محدود به نوع نمایش داده نمی‌شود */}
      {!isTypeRestricted && (
        <Card variant="outlined" sx={{ mt: 2, p: 2, borderRadius: 2 }}>
          <Typography variant="body2" fontWeight={700} sx={{ mb: 1.5 }}>
            فیلتر بر اساس بازه تاریخ مرخصی/ماموریت
          </Typography>
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="center">
            {/* پیش‌فرض هر دو تاریخ خالی است (بدون فیلتر) */}
            <JalaliDateTimePicker clearable value={dateFrom} onChange={setDateFrom} label="از تاریخ" showTime={false} />
            <JalaliDateTimePicker clearable value={dateTo} onChange={setDateTo} label="تا تاریخ" showTime={false} />
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

      {/* پیام موفقیت */}
      <Snackbar
        open={Boolean(toast)}
        autoHideDuration={4000}
        onClose={() => setToast("")}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity="success" variant="filled" onClose={() => setToast("")} sx={{ width: "100%" }}>
          {toast}
        </Alert>
      </Snackbar>
    </Box>
  );
}
