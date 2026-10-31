import { useEffect, useState } from "react";
import { swr } from "../api/swrCache";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
  Tab,
  Tabs,
  TextField,
  Typography,
  useMediaQuery,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import BackLink from "../components/BackLink";
import { compactTableSx, faDateTime, hideXs, onlyXs } from "../utils/dateTimeFa";
import { useAuth } from "../context/AuthContext";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";
import { gregorianToJalali, JALALI_MONTH_NAMES } from "../utils/jalaliDate";
import TimeSelect24 from "../components/TimeSelect24";
import AccessGateDialog from "../components/AccessGateDialog";
import PillTabs from "../components/PillTabs";
import { useAccessGateStatus } from "../hooks/useAccessGateStatus";
import {
  decideLeaveRequest,
  fetchDecidedLeaveRequestsByMe,
  deleteLeaveRequest,
  fetchActiveLeaveRequestTypes,
  fetchMyLeaveRequests,
  fetchPendingLeaveRequestsForMe,
  fetchShiftWindow,
  submitLeaveRequest,
} from "../api/leaveRequests";

// برچسب و رنگ چیپ هر وضعیت درخواست
const STATUS_LABELS = { pending: "در حال بررسی", approved: "تائید شده", rejected: "رد شده", cancelled: "ابطال شده" };
const STATUS_COLORS = { pending: "warning", approved: "success", rejected: "error", cancelled: "default" };

// برچسب وضعیت یک درخواست؛ تردد فراموش‌شده‌ای که سرپرست تأیید کرده و منتظر مسئول نیروی انسانی است برچسب جدا دارد
function statusLabel(item) {
  return item.awaiting_hr ? "در انتظار منابع انسانی" : STATUS_LABELS[item.status];
}

// بازه‌ی تاریخ قابل ثبت یک نوع (تنظیمات «مهلت ثبت»؛ اعتبارسنجی اصلی در سرور): {min, max} از Date یا null
function submitBounds(type) {
  if (!type) return { min: null, max: null };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const shift = (days) => {
    const d = new Date(today);
    d.setDate(d.getDate() + days);
    return d;
  };
  const past = type.max_past_days;
  const future = type.is_forgotten_punch ? 0 : type.max_future_days; // تردد آینده همیشه ممنوع است
  return { min: past != null ? shift(-past) : null, max: future != null ? shift(future) : null };
}

// «۴ آبان» (با سال اگر سال جاری نیست)
function faDay(date) {
  const { jy, jm, jd } = gregorianToJalali(date);
  const sameYear = jy === gregorianToJalali(new Date()).jy;
  const fa = (n) => Number(n).toLocaleString("fa-IR", { useGrouping: false });
  return `${fa(jd)} ${JALALI_MONTH_NAMES[jm - 1]}${sameYear ? "" : ` ${fa(jy)}`}`;
}

// «درخواست مرخصی روزانه از امروز به بعد قابل ثبت است.»؛ بدون محدودیت → ""
function submitWindowText(type) {
  if (!type) return "";
  const { min, max } = submitBounds(type);
  if (!min && !max) return "";
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const label = (d) => (d.getTime() === today.getTime() ? "امروز" : faDay(d));
  const title = String(type.title || "").trim();
  const name = title.startsWith("درخواست") ? title : `درخواست ${title}`;
  let range;
  if (min && max) {
    range =
      min.getTime() === max.getTime()
        ? `فقط برای ${label(min)}`
        : `از ${label(min)} تا ${label(max)}`;
  } else if (min) {
    range = `از ${label(min)} به بعد`;
  } else {
    range = `تا ${label(max)}`;
  }
  return `${name} ${range} قابل ثبت است.`;
}

// درخواست الان دست چه کسی است / چه کسی تصمیم گرفت (فقط نام؛ docs/leave-requests.md)
function approverLine(item) {
  if (item.status === "pending") {
    const who = item.current_approver_name || (item.awaiting_hr ? "منابع انسانی" : "");
    if (!who) return "";
    const sub = item.current_approver_substitute_name ? ` (یا جانشین: ${item.current_approver_substitute_name})` : "";
    return `در انتظار تأیید: ${who}${sub}`;
  }
  if (item.status === "approved" || item.status === "rejected") {
    const name = item.approved_by_name || item.current_approver_name;
    return name ? `${item.status === "approved" ? "تأیید" : "رد"} توسط: ${name}` : "";
  }
  return "";
}

// ساعت فشرده‌ی عددی (مثلاً 830) را به رشته‌ی «08:30» تبدیل می‌کند؛ null -> خط تیره
function formatCompactTime(compact) {
  if (compact == null) return "—";
  const hour = Math.floor(compact / 100);
  const minute = compact % 100;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

// متن مدت یک درخواست: ساعت تردد (تردد فراموش‌شده)، بازه‌ی ساعتی (مرخصی ساعتی) یا تعداد روز
function formatDuration(item) {
  if (item.is_forgotten_punch) return `تردد ساعت ${formatCompactTime(item.start_hour)}`;
  if (item.is_exit_permit) return `خروج ساعت ${formatCompactTime(item.start_hour)}`;
  return item.start_hour != null
    ? `${formatCompactTime(item.start_hour)} تا ${formatCompactTime(item.end_hour)}`
    : `${item.duration} روز`;
}

// رشته‌ی «HH:MM» را به عدد فشرده‌ی HHMM تبدیل می‌کند (فرمت ذخیره‌ی ساعت در سرور)
function timeStringToCompact(timeStr) {
  if (!timeStr) return null;
  const [h, m] = timeStr.split(":").map(Number);
  return h * 100 + m;
}

// تاریخ (Date) را به رشته‌ی YYYY-MM-DD به وقت محلی تبدیل می‌کند
function toDateOnly(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// بازه‌ی ساعت‌های صحیح بین دو ساعت فشرده (شامل هر دو سر)، مثلاً 630 تا 1430 -> [6..14]
function hourRange(fromHour, toHour) {
  const out = [];
  for (let h = fromHour; h <= toHour; h += 1) out.push(h);
  return out;
}

// ساعت‌های مجاز Dropdown بر اساس شیفت روز: مرخصی ساعتی داخل شیفت، مجوز خروج از پایان شیفت به بعد
// اگر شیفت روز دو بازه‌ی قابل قبول دارد (کارکرد روزانه‌ی کاراوب + تقویم گروه شیفت جدید)، اجتماع ساعت‌ها
function hoursOfWindow(w, isExit) {
  const sh = Math.floor(w.start / 100);
  const eh = Math.floor(w.end / 100);
  if (isExit) return w.crosses_midnight ? hourRange(eh, sh) : hourRange(eh, 23);
  return w.crosses_midnight ? [...hourRange(sh, 23), ...hourRange(0, eh)] : hourRange(sh, eh);
}

function allowedHoursFor(shift, isExit) {
  if (!shift?.found || shift.off_day) return null;
  const windows = shift.windows?.length ? shift.windows : [shift];
  return [...new Set(windows.flatMap((w) => hoursOfWindow(w, isExit)))];
}

// زودترین شروع شیفت روز (برای راهنمای تردد فراموش‌شده)
function earliestStart(shift) {
  const windows = shift.windows?.length ? shift.windows : [shift];
  return Math.min(...windows.map((w) => w.start));
}

// ساعت فشرده -> «HH:MM»
function compactToTimeString(compact) {
  return `${String(Math.floor(compact / 100)).padStart(2, "0")}:${String(compact % 100).padStart(2, "0")}`;
}

/**
 * فرم ثبت درخواست جدید مرخصی/ماموریت/تردد فراموش‌شده/مجوز خروج.
 * ورودی: onSubmitted(isForgottenPunch, approverName) که بعد از ثبت موفق صدا زده می‌شود.
 * فیلدها بسته به نوع انتخابی (روزانه/ساعتی/ماموریت/تردد فراموش‌شده) تغییر می‌کنند.
 */
function SubmitRequestForm({ onSubmitted }) {
  const [types, setTypes] = useState(null); // انواع فعال درخواست؛ null = هنوز بارگذاری نشده
  const [typeId, setTypeId] = useState(""); // شناسه‌ی نوع انتخابی
  const [startDate, setStartDate] = useState(new Date()); // تاریخ شروع مرخصی/ماموریت
  const [endDate, setEndDate] = useState(new Date()); // تاریخ پایان (فقط انواع روزانه)
  const [startTimeStr, setStartTimeStr] = useState("08:00"); // ساعت شروع (فقط انواع ساعتی)
  const [endTimeStr, setEndTimeStr] = useState("10:00"); // ساعت پایان (فقط انواع ساعتی)
  const [description, setDescription] = useState("");
  const [source, setSource] = useState(""); // مبدأ (فقط ماموریت)
  const [destination, setDestination] = useState(""); // مقصد (فقط ماموریت)
  // تردد فراموش‌شده: هر درخواست فقط یک تردد (تاریخ + ساعت)
  const [punchDate, setPunchDate] = useState(new Date());
  const [punchTime, setPunchTime] = useState("07:00");
  const [exitTime, setExitTime] = useState("14:30"); // مجوز خروج: فقط ساعت خروج
  const [shift, setShift] = useState(null); // شیفت روز انتخابی (برای مرخصی ساعتی و مجوز خروج)
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // بارگذاری انواع فعال درخواست
  useEffect(() => {
    swr("leave:types", fetchActiveLeaveRequestTypes, setTypes).catch(() => {});
  }, []);

  const selectedType = types?.find((t) => t.id === Number(typeId)); // شیء نوع انتخابی
  const bounds = submitBounds(selectedType); // بازه‌ی تاریخ قابل ثبت این نوع
  const isExit = Boolean(selectedType?.is_exit_permit);
  // مرخصی ساعتی (نه مأموریت) و مجوز خروج به ساعت شیفت همان روز محدودند
  const shiftLimited =
    Boolean(selectedType) &&
    !selectedType.is_forgotten_punch &&
    (isExit || (selectedType.is_hourly && !selectedType.is_mission));
  const shiftKey = shiftLimited ? `${isExit ? "exit" : "hourly"}|${toDateOnly(startDate)}` : "";

  // با تغییر نوع یا تاریخ، شیفت آن روز خوانده و ساعت‌های پیش‌فرض روی بازه‌ی شیفت گذاشته می‌شوند
  useEffect(() => {
    if (!shiftKey) return undefined;
    let alive = true;
    const [kind, day] = shiftKey.split("|");
    fetchShiftWindow(day)
      .then((data) => {
        if (!alive) return;
        setShift(data);
        if (data?.found && !data.off_day) {
          if (kind === "exit") setExitTime(compactToTimeString(data.end));
          else {
            setStartTimeStr(compactToTimeString(data.start));
            setEndTimeStr(compactToTimeString(data.end));
          }
        }
      })
      .catch(() => alive && setShift(null));
    return () => {
      alive = false;
    };
  }, [shiftKey]);

  // تردد فراموش‌شده: شروع شیفت روز تردد (تردد قبل از آن ثبت نمی‌شود؛ پایان مهم نیست)
  const punchKey = selectedType?.is_forgotten_punch ? toDateOnly(punchDate) : "";
  const [punchShift, setPunchShift] = useState(null);
  useEffect(() => {
    if (!punchKey) return undefined;
    let alive = true;
    fetchShiftWindow(punchKey)
      .then((data) => alive && setPunchShift(data))
      .catch(() => alive && setPunchShift(null));
    return () => {
      alive = false;
    };
  }, [punchKey]);
  const activePunchShift = punchKey ? punchShift : null;

  const activeShift = shiftKey ? shift : null;
  const allowedHours = activeShift ? allowedHoursFor(activeShift, isExit) : null;
  const offDayBlocked = Boolean(!isExit && shiftLimited && activeShift?.found && activeShift.off_day);

  // اعتبارسنجی و ارسال درخواست: برای تردد فراموش‌شده payload با punches، در غیر این صورت با بازه‌ی تاریخ/ساعت
  async function handleSubmit() {
    setError("");
    if (!selectedType) {
      setError("لطفاً نوع درخواست را انتخاب کنید");
      return;
    }
    // مسیر تردد فراموش‌شده
    if (selectedType.is_forgotten_punch) {
      const punches = [{ punch_date: toDateOnly(punchDate), time: timeStringToCompact(punchTime) }];
      setIsSubmitting(true);
      try {
        const res = await submitLeaveRequest({
          leave_type_id: selectedType.id,
          start_date: punches[0].punch_date,
          description,
          punches,
        });
        setDescription("");
        onSubmitted(true, res?.approver_name);
      } catch (err) {
        setError(err.response?.data?.detail || "ثبت درخواست با خطا مواجه شد.");
      } finally {
        setIsSubmitting(false);
      }
      return;
    }
    if (offDayBlocked) {
      setError("این روز طبق شیفت شما روز کاری نیست");
      return;
    }
    // مسیر مرخصی/ماموریت/مجوز خروج: فیلدهای ساعتی و ماموریت فقط در صورت نیاز پر می‌شوند
    setIsSubmitting(true);
    try {
      const res = await submitLeaveRequest({
        leave_type_id: selectedType.id,
        start_date: toDateOnly(startDate),
        end_date: selectedType.is_hourly || isExit ? null : toDateOnly(endDate),
        start_hour: isExit
          ? timeStringToCompact(exitTime)
          : selectedType.is_hourly
            ? timeStringToCompact(startTimeStr)
            : null,
        end_hour: !isExit && selectedType.is_hourly ? timeStringToCompact(endTimeStr) : null,
        description,
        source: selectedType.is_mission ? source : null,
        destination: selectedType.is_mission ? destination : null,
      });
      setDescription("");
      setSource("");
      setDestination("");
      onSubmitted(false, res?.approver_name);
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت درخواست با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (types === null) return null; // هنوز بارگذاری نشده

  // هیچ نوعی برای سایت کاربر تعریف نشده
  if (types.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        هنوز هیچ نوع درخواستی برای سایت شما تعریف نشده - لطفاً با منابع انسانی هماهنگ کنید.
      </Typography>
    );
  }

  return (
    <Card variant="outlined" sx={{ p: 2, maxWidth: 480 }}>
      <Stack spacing={2}>
        {/* انتخاب نوع درخواست — با تغییر نوع، خطای نوع قبلی پاک می‌شود */}
        <TextField
          select
          label="نوع درخواست"
          value={typeId}
          onChange={(e) => {
            setTypeId(e.target.value);
            setError("");
          }}
        >
          {types.map((t) => (
            <MenuItem key={t.id} value={t.id}>
              {t.title}
            </MenuItem>
          ))}
        </TextField>

        {/* مهلت ثبت این نوع (تنظیمات مرخصی/ماموریت؛ اعتبارسنجی اصلی در سرور) */}
        {submitWindowText(selectedType) && (
          <Typography variant="caption" color="text.secondary">
            {submitWindowText(selectedType)}
          </Typography>
        )}

        {/* فرم تردد فراموش‌شده: تاریخ و ساعت یک تردد، توضیحات و دکمه‌ی ثبت */}
        {selectedType?.is_forgotten_punch && (
          <>
            <Stack spacing={2}>
              <JalaliDateTimePicker
                value={punchDate}
                onChange={setPunchDate}
                label="تاریخ تردد"
                showTime={false}
                minDate={bounds.min}
                maxDate={bounds.max}
              />
              <TimeSelect24 label="ساعت تردد" value={punchTime} onChange={setPunchTime} />
            </Stack>
            {activePunchShift?.found && !activePunchShift.off_day && (
              <Alert severity="info" sx={{ py: 0 }}>
                شروع شیفت شما در این روز: {compactToTimeString(earliestStart(activePunchShift))} — تردد قبل از آن قابل ثبت نیست
                {activePunchShift.windows?.some((w) => w.crosses_midnight) || activePunchShift.crosses_midnight ? " (به‌جز خروج بامداد بعد از شبکاری روز قبل)." : "."}
              </Alert>
            )}
            <Typography variant="caption" color="text.secondary" textAlign="center">
              برای هر تردد فراموش شده باید یک درخواست جداگانه ثبت شود. درخواست ابتدا توسط سرپرست و سپس مسئول نیروی
              انسانی تأیید و بعد در سیستم حضور و غیاب ثبت می‌شود.
            </Typography>
            <TextField
              label="توضیحات"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              multiline
              minRows={2}
            />
            {error && <Alert severity="error">{error}</Alert>}
            <Button
              variant="contained"
              onClick={handleSubmit}
              disabled={isSubmitting}
              startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : null}
            >
              {isSubmitting ? "در حال ثبت..." : "ثبت درخواست"}
            </Button>
          </>
        )}

        {/* فرم مرخصی/ماموریت: تاریخ شروع، بازه‌ی ساعتی یا تاریخ پایان، مبدأ/مقصد برای ماموریت، توضیحات و دکمه‌ی ثبت */}
        {selectedType && !selectedType.is_forgotten_punch && (
          <>
            <JalaliDateTimePicker
              value={startDate}
              onChange={setStartDate}
              label={isExit ? "تاریخ" : "تاریخ مرخصی/ماموریت"}
              showTime={false}
              minDate={bounds.min}
              maxDate={bounds.max}
            />
            {isExit ? (
              <TimeSelect24
                label="ساعت خروج"
                value={exitTime}
                onChange={setExitTime}
                allowedHours={allowedHours}
              />
            ) : selectedType.is_hourly ? (
              <Stack direction="row" spacing={1.5}>
                <TimeSelect24
                  label="ساعت شروع"
                  value={startTimeStr}
                  onChange={setStartTimeStr}
                  allowedHours={allowedHours}
                  sx={{ flex: 1 }}
                />
                <TimeSelect24
                  label="ساعت پایان"
                  value={endTimeStr}
                  onChange={setEndTimeStr}
                  allowedHours={allowedHours}
                  sx={{ flex: 1 }}
                />
              </Stack>
            ) : (
              <JalaliDateTimePicker
                value={endDate}
                onChange={setEndDate}
                label="تاریخ پایان"
                showTime={false}
                minDate={startDate}
              />
            )}

            {shiftLimited && activeShift?.found && (
              <Alert severity={offDayBlocked ? "warning" : "info"} sx={{ py: 0 }}>
                {activeShift.off_day && isExit ? "این روز طبق شیفت شما روز کاری نیست." : activeShift.label}
                {isExit && !activeShift.off_day && " — ساعت خروج باید از پایان شیفت به بعد باشد."}
                {!isExit &&
                  !activeShift.off_day &&
                  activeShift.crosses_midnight &&
                  " — می‌توانید از نیمه‌شب عبور کنید (مثلاً ۲۳:۰۰ تا ۰۱:۰۰). برای بعد از پایان شیفت «مجوز خروج» ثبت کنید."}
                {!activeShift.off_day && activeShift.crosses_midnight && (
                  <Box component="span" sx={{ display: "block", fontSize: 12, mt: 0.5 }}>
                    تاریخ بالا تاریخ شروع شیفت است؛ درخواستی که بعد از ۰۰:۰۰ شروع شود خودکار با تاریخ روز بعد ثبت می‌شود.
                  </Box>
                )}
              </Alert>
            )}
            {isExit && (
              <Typography variant="caption" color="text.secondary">
                مجوز خروج فقط برای خروج بعد از پایان شیفت است و مرخصی یا ماموریت ثبت نمی‌کند؛ با تأیید سرپرست نهایی
                می‌شود.
              </Typography>
            )}

            {selectedType.is_mission && (
              <Stack direction="row" spacing={1.5}>
                <TextField label="مبدأ" value={source} onChange={(e) => setSource(e.target.value)} sx={{ flex: 1 }} />
                <TextField
                  label="مقصد"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  sx={{ flex: 1 }}
                />
              </Stack>
            )}

            <TextField
              label="توضیحات"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              multiline
              minRows={2}
            />

            {error && <Alert severity="error">{error}</Alert>}
            <Button
              variant="contained"
              onClick={handleSubmit}
              disabled={isSubmitting || offDayBlocked}
              startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : null}
            >
              {isSubmitting ? "در حال ثبت..." : "ثبت درخواست"}
            </Button>
          </>
        )}
      </Stack>
    </Card>
  );
}

/**
 * لیست درخواست‌های خودِ کاربر.
 * ورودی: آیتم‌ها و onDeleted که بعد از حذف موفق صدا زده می‌شود.
 * در موبایل به صورت کارت و در دسکتاپ به صورت جدول؛ درخواست‌های در حال بررسی قابل حذف‌اند.
 */
function MyRequestsTable({ items, onDeleted }) {
  const isMobile = useMediaQuery((theme) => theme.breakpoints.down("sm"));
  const [deletingId, setDeletingId] = useState(null); // شناسه‌ی درخواستی که در حال حذف است
  const [error, setError] = useState("");

  // حذف یک درخواست پس از تأیید کاربر و اطلاع به والد
  async function handleDelete(requestId) {
    if (!window.confirm("این درخواست حذف شود؟")) return;
    setError("");
    setDeletingId(requestId);
    try {
      await deleteLeaveRequest(requestId);
      onDeleted();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف درخواست با خطا مواجه شد.");
    } finally {
      setDeletingId(null);
    }
  }

  if (items.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        هنوز هیچ درخواستی ثبت نکرده‌اید.
      </Typography>
    );
  }

  // مرتب‌سازی: جدیدترین‌ها (بر اساس تاریخ ثبت) بالا
  const sortedItems = [...items].sort(
    (a, b) => new Date(b.submitted_at || 0).getTime() - new Date(a.submitted_at || 0).getTime()
  );

  // نمایش کارتی در موبایل: عنوان نوع، تاریخ‌ها، چیپ وضعیت، دکمه‌ی حذف، توضیحات، مدت و نظر تأییدکننده
  if (isMobile) {
    return (
      <Stack spacing={1.5}>
        {error && <Alert severity="error">{error}</Alert>}
        {sortedItems.map((item) => (
          <Card key={item.request_id} variant="outlined" sx={{ borderRadius: 2, p: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 1 }}>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="body2" fontWeight={700} noWrap>
                  {item.type_title || "—"}
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  ثبت: {faDateTime(item.submitted_at)}
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  شروع: {item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"}
                  {item.approved_at && item.status !== "pending" ? ` — تصمیم: ${faDateTime(item.approved_at)}` : ""}
                </Typography>
              </Box>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ flexShrink: 0 }}>
                <Chip size="small" color={STATUS_COLORS[item.status]} label={statusLabel(item)} />
                {item.status === "pending" && (
                  <IconButton
                    size="small"
                    color="error"
                    disabled={deletingId === item.request_id}
                    onClick={() => handleDelete(item.request_id)}
                    aria-label="حذف"
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                )}
              </Stack>
            </Stack>
            {item.description && (
              <Typography variant="body2" sx={{ mb: 0.5 }}>
                {item.description}
              </Typography>
            )}
            <Typography variant="caption" color="text.secondary" display="block">
              {item.is_forgotten_punch || item.is_exit_permit ? "" : "مدت: "}
              {formatDuration(item)}
            </Typography>
            {approverLine(item) && (
              <Typography
                variant="caption"
                color={item.status === "pending" ? "warning.main" : "text.secondary"}
                fontWeight={700}
                display="block"
                sx={{ mt: 0.5 }}
              >
                {approverLine(item)}
              </Typography>
            )}
            {item.manager_idea && (
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                نظر تأییدکننده: {item.manager_idea}
              </Typography>
            )}
          </Card>
        ))}
      </Stack>
    );
  }

  // نمایش جدولی در دسکتاپ
  return (
    <Stack spacing={1.5}>
      {error && <Alert severity="error">{error}</Alert>}
      <TableContainer component={Card} variant="outlined">
        <Table size="small" sx={compactTableSx}>
          <TableHead>
            <TableRow>
              <TableCell>نوع درخواست</TableCell>
              <TableCell>توضیحات</TableCell>
              <TableCell>تاریخ ثبت</TableCell>
              <TableCell>تاریخ مرخصی/ماموریت</TableCell>
              <TableCell>مدت</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>نظر تأییدکننده</TableCell>
              <TableCell>حذف</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedItems.map((item) => (
              <TableRow key={item.request_id}>
                <TableCell>{item.type_title || "—"}</TableCell>
                <TableCell>{item.description || "—"}</TableCell>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{faDateTime(item.submitted_at)}</TableCell>
                <TableCell>{item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"}</TableCell>
                <TableCell>{formatDuration(item)}</TableCell>
                <TableCell>
                  <Chip size="small" color={STATUS_COLORS[item.status]} label={statusLabel(item)} />
                  {approverLine(item) && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5, whiteSpace: "nowrap" }}>
                      {approverLine(item)}
                    </Typography>
                  )}
                  {item.approved_at && item.status !== "pending" && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5, whiteSpace: "nowrap" }}>
                      {faDateTime(item.approved_at)}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>{item.manager_idea || "—"}</TableCell>
                <TableCell>
                  {item.status === "pending" && (
                    <IconButton
                      size="small"
                      color="error"
                      disabled={deletingId === item.request_id}
                      onClick={() => handleDelete(item.request_id)}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}

/**
 * دیالوگ تصمیم تأییدکننده روی یک درخواست.
 * ورودی: درخواست، onClose و onDecided(approved) که بعد از ثبت موفق تصمیم صدا زده می‌شود.
 * نظر اختیاری را می‌گیرد و با دکمه‌ی تأیید یا رد تصمیم را به سرور می‌فرستد.
 */
function DecideDialog({ item, onClose, onDecided }) {
  const [managerIdea, setManagerIdea] = useState(""); // نظر اختیاری تأییدکننده
  const [pendingAction, setPendingAction] = useState(null); // null | "approve" | "reject": کدام دکمه در حال ارسال است (لودینگ روی همان دکمه)
  const [error, setError] = useState("");
  const isSubmitting = pendingAction !== null;

  // ثبت تصمیم (تأیید یا رد) به همراه نظر و اطلاع به والد
  async function handleDecide(approved) {
    setError("");
    setPendingAction(approved ? "approve" : "reject");
    try {
      await decideLeaveRequest(item.request_id, approved, managerIdea);
      onDecided(approved);
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت تصمیم با خطا مواجه شد.");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <Dialog open onClose={isSubmitting ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>تصمیم برای درخواست</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <Typography variant="body2" fontWeight={700}>
          {item.type_title || "—"}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {item.requester_name ? `${item.requester_name} — ` : ""}ثبت: {faDateTime(item.submitted_at)}
        </Typography>
        {item.description && <Typography variant="body2">{item.description}</Typography>}
        {item.is_forgotten_punch && (
          <Typography variant="body2" color="text.secondary">
            {item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"} — {formatDuration(item)}
          </Typography>
        )}
        {/* برای تردد فراموش‌شده در مرحله‌ی سرپرست: یادآوری تأیید نهایی توسط نیروی انسانی */}
        {item.is_forgotten_punch && !item.awaiting_hr && (
          <Alert severity="info">
            پس از تأیید شما، درخواست برای تأیید نهایی به مسئول نیروی انسانی ارسال می‌شود.
          </Alert>
        )}
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          label="نظر (اختیاری)"
          value={managerIdea}
          onChange={(e) => setManagerIdea(e.target.value)}
          multiline
          minRows={2}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSubmitting}>
          انصراف
        </Button>
        <Button
          color="error"
          onClick={() => handleDecide(false)}
          disabled={isSubmitting}
          startIcon={pendingAction === "reject" ? <CircularProgress size={16} color="inherit" /> : null}
        >
          {pendingAction === "reject" ? "در حال رد..." : "رد"}
        </Button>
        <Button
          variant="contained"
          color="success"
          onClick={() => handleDecide(true)}
          disabled={isSubmitting}
          startIcon={pendingAction === "approve" ? <CircularProgress size={16} color="inherit" /> : null}
        >
          {pendingAction === "approve" ? "در حال تائید..." : "تائید"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/**
 * جدول درخواست‌های در انتظار تصمیم کاربر جاری (کارتابل).
 * ورودی: آیتم‌ها و onDecide(item) برای باز کردن دیالوگ تصمیم.
 */
function PendingApprovalTable({ items, onDecide }) {
  if (items.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        فعلاً هیچ درخواستی در انتظار شما نیست.
      </Typography>
    );
  }

  // مرتب‌سازی: جدیدترین‌ها (بر اساس تاریخ ثبت) بالا
  const sorted = [...items].sort(
    (a, b) => new Date(b.submitted_at || 0).getTime() - new Date(a.submitted_at || 0).getTime()
  );

  return (
    <TableContainer component={Card} variant="outlined">
      <Table size="small" sx={compactTableSx}>
        <TableHead>
          <TableRow>
            <TableCell>نام و نام خانوادگی</TableCell>
            <TableCell sx={hideXs}>واحد</TableCell>
            <TableCell>نوع درخواست</TableCell>
            <TableCell sx={hideXs}>توضیحات</TableCell>
            <TableCell sx={hideXs}>تاریخ و ساعت ثبت</TableCell>
            <TableCell sx={hideXs}>تاریخ مرخصی/ماموریت</TableCell>
            <TableCell sx={hideXs}>مدت</TableCell>
            <TableCell>عملیات</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sorted.map((item) => (
            <TableRow key={item.request_id}>
              {/* موبایل: واحد و زمان ثبت زیر نام؛ تاریخ، مدت و توضیحات زیر نوع (بدون اسکرول افقی) */}
              <TableCell>
                {item.requester_name || item.emp_no}
                {item.as_substitute_for_name && (
                  <Typography variant="caption" color="info.main" fontWeight={700} display="block">
                    به جانشینی از {item.as_substitute_for_name}
                  </Typography>
                )}
                <Typography variant="caption" color="text.secondary" sx={onlyXs}>
                  {item.requester_department || "—"}
                  <br />
                  ثبت: {faDateTime(item.submitted_at)}
                </Typography>
              </TableCell>
              <TableCell sx={hideXs}>{item.requester_department || "—"}</TableCell>
              <TableCell>
                {item.type_title || "—"}
                <Typography variant="caption" color="text.secondary" sx={onlyXs}>
                  {item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"} — {formatDuration(item)}
                  {item.description ? <><br />{item.description}</> : null}
                </Typography>
              </TableCell>
              <TableCell sx={hideXs}>{item.description || "—"}</TableCell>
              <TableCell sx={{ ...hideXs, whiteSpace: "nowrap" }}>{faDateTime(item.submitted_at)}</TableCell>
              <TableCell sx={hideXs}>{item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"}</TableCell>
              <TableCell sx={hideXs}>{formatDuration(item)}</TableCell>
              <TableCell>
                <Button size="small" variant="outlined" onClick={() => onDecide(item)}>
                  بررسی
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}


/**
 * جدول سوابق درخواست‌هایی که کاربر جاری قبلاً تأیید/رد کرده است.
 * ورودی: reloadKey که با تغییر آن داده دوباره از سرور گرفته می‌شود.
 * جدیدترین تصمیم بالا، با صفحه‌بندی سمت سرور.
 */
function DecidedHistoryTable({ reloadKey }) {
  const [page, setPage] = useState(0); // صفحه‌ی جاری (از صفر)
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [data, setData] = useState(null); // پاسخ سرور: { items, total }؛ null = هنوز بارگذاری نشده
  const [error, setError] = useState("");

  // بارگذاری صفحه‌ی جاری سوابق با هر تغییر صفحه/اندازه/reloadKey
  useEffect(() => {
    setError("");
    fetchDecidedLeaveRequestsByMe(page, rowsPerPage)
      .then(setData)
      .catch((err) => setError(err.response?.data?.detail || "دریافت سوابق با خطا مواجه شد."));
  }, [page, rowsPerPage, reloadKey]);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (data === null) return null;
  if (data.total === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        هنوز درخواستی را تأیید یا رد نکرده‌اید.
      </Typography>
    );
  }

  return (
    <TableContainer component={Card} variant="outlined">
      <Table size="small" sx={compactTableSx}>
        <TableHead>
          <TableRow>
            <TableCell>نام و نام خانوادگی</TableCell>
            <TableCell sx={hideXs}>واحد</TableCell>
            <TableCell>نوع درخواست</TableCell>
            <TableCell sx={hideXs}>تاریخ مرخصی/ماموریت</TableCell>
            <TableCell sx={hideXs}>مدت</TableCell>
            <TableCell>وضعیت</TableCell>
            <TableCell sx={hideXs}>تاریخ و ساعت ثبت</TableCell>
            <TableCell sx={hideXs}>تاریخ و ساعت تصمیم</TableCell>
            <TableCell sx={hideXs}>نظر شما</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.items.map((item) => (
            <TableRow key={item.request_id}>
              <TableCell>
                {item.requester_name || item.emp_no}
                <Typography variant="caption" color="text.secondary" sx={onlyXs}>
                  {item.requester_department || "—"}
                  <br />
                  ثبت: {faDateTime(item.submitted_at)}
                </Typography>
              </TableCell>
              <TableCell sx={hideXs}>{item.requester_department || "—"}</TableCell>
              <TableCell>
                {item.type_title || "—"}
                <Typography variant="caption" color="text.secondary" sx={onlyXs}>
                  {item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"} — {formatDuration(item)}
                  {item.manager_idea ? <><br />نظر شما: {item.manager_idea}</> : null}
                </Typography>
              </TableCell>
              <TableCell sx={hideXs}>{item.start_date ? new Date(item.start_date).toLocaleDateString("fa-IR") : "—"}</TableCell>
              <TableCell sx={hideXs}>{formatDuration(item)}</TableCell>
              <TableCell>
                <Chip size="small" color={STATUS_COLORS[item.status]} label={statusLabel(item)} />
                <Typography variant="caption" color="text.secondary" sx={onlyXs}>
                  {faDateTime(item.approved_at)}
                </Typography>
              </TableCell>
              <TableCell sx={{ ...hideXs, whiteSpace: "nowrap" }}>{faDateTime(item.submitted_at)}</TableCell>
              <TableCell sx={{ ...hideXs, whiteSpace: "nowrap" }}>{faDateTime(item.approved_at)}</TableCell>
              <TableCell sx={hideXs}>{item.manager_idea || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <TablePagination
        component="div"
        count={data.total}
        page={page}
        onPageChange={(_, newPage) => setPage(newPage)}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={(e) => {
          setRowsPerPage(parseInt(e.target.value, 10));
          setPage(0);
        }}
        rowsPerPageOptions={[10, 25, 50]}
        labelRowsPerPage="تعداد در هر صفحه:"
        labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
      />
    </TableContainer>
  );
}

/**
 * صفحه‌ی درخواست مرخصی/ماموریت (نقطه‌ی ورود).
 * اگر ماژول برای سایت این پرسنل از صفحه‌ی «تنظیمات درخواست مرخصی/ماموریت» غیرفعال شده باشد،
 * فقط یک هشدار نشان می‌دهد (سرور هم مستقل بررسی می‌کند)؛ وگرنه محتوای اصلی را رندر می‌کند.
 */
export default function LeaveRequestPage() {
  const { user } = useAuth();
  if (user?.leave_requests_disabled) {
    return (
      <Box sx={{ maxWidth: 1100, mx: "auto" }}>
        <BackLink to="/requests" label="بازگشت به کارتابل درخواست" />
        <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
          درخواست مرخصی/ماموریت
        </Typography>
        <Alert severity="warning">درخواست مرخصی/ماموریت در حال حاضر غیرفعال است.</Alert>
      </Box>
    );
  }
  return <LeaveRequestPageContent />;
}

/**
 * محتوای اصلی صفحه‌ی درخواست مرخصی/ماموریت با سه تب:
 * ثبت درخواست جدید، درخواست‌های من و کارتابل تأیید (فقط برای کسی که درخواست در انتظار یا سابقه‌ی تصمیم دارد).
 * تب جاری در query string نگه داشته می‌شود.
 */
function LeaveRequestPageContent() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = ["submit", "my-requests", "pending"].indexOf(searchParams.get("tab")); // ایندکس تب از URL؛ -1 اگر نامعتبر
  const [tab, setTab] = useState(tabFromUrl >= 0 ? tabFromUrl : 0); // ایندکس تب فعال
  const [myRequests, setMyRequests] = useState(null); // درخواست‌های خود کاربر؛ null = هنوز بارگذاری نشده
  const [pending, setPending] = useState(null); // درخواست‌های در انتظار تصمیم کاربر
  const [decidingItem, setDecidingItem] = useState(null); // درخواستی که دیالوگ تصمیم برایش باز است
  const [error, setError] = useState("");
  const [toast, setToast] = useState(""); // پیام موفقیت پس از ثبت/تأیید/رد/حذف
  // تعداد کل سوابق تصمیم این فرد؛ تب کارتابل برای کسی که درخواست در انتظار ندارد ولی قبلاً تصمیم گرفته هم نمایش داده می‌شود
  const [decidedTotal, setDecidedTotal] = useState(0);
  const [historyReloadKey, setHistoryReloadKey] = useState(0); // با افزایش، جدول سوابق دوباره بارگذاری می‌شود
  // وضعیت پیش‌نیازهای دسترسی برای هشدار پیش از کلیک (سرور هم مستقل بررسی می‌کند)؛
  // از Hook مشترک تا با برگشت به صفحه یا بازگشت فوکوس خودکار تازه شود
  const { status: gateStatus } = useAccessGateStatus();
  const [gateOpen, setGateOpen] = useState(false); // باز بودن دیالوگ محدودیت دسترسی

  // با هر تغییر وضعیت، دیالوگ همگام می‌شود: اگر کاربر پیش‌نیاز را انجام داد و برگشت، دیالوگ خودکار بسته می‌شود
  useEffect(() => {
    if (!gateStatus) return;
    setGateOpen(Boolean(gateStatus.blocked_features?.["leave_request"]));
  }, [gateStatus]);


  // بارگذاری درخواست‌های خود کاربر
  function loadMyRequests() {
    // آخرین فهرست Cache شده فوراً نمایش داده و با پاسخ تازه جایگزین می‌شود
    swr("leave:my", fetchMyLeaveRequests, setMyRequests)
      .catch((err) => setError(err.response?.data?.detail || "دریافت درخواست‌های من با خطا مواجه شد."));
  }

  // بارگذاری کارتابل (درخواست‌های در انتظار تصمیم کاربر)؛ در خطا لیست خالی
  function loadPending() {
    swr("leave:pending", fetchPendingLeaveRequestsForMe, setPending).catch(() => setPending((prev) => prev ?? []));
  }

  // فقط تعداد کل سوابق تصمیم را می‌گیرد (یک آیتم درخواست می‌شود) تا نمایش تب کارتابل تعیین شود
  function loadDecidedTotal() {
    swr("leave:decidedTotal", () => fetchDecidedLeaveRequestsByMe(0, 1), (data) => setDecidedTotal(data.total)).catch(
      () => setDecidedTotal((prev) => prev || 0)
    );
  }

  // بارگذاری اولیه‌ی هر سه لیست
  useEffect(() => {
    loadMyRequests();
    loadPending();
    loadDecidedTotal();
  }, []);

  // تغییر تب و همگام کردن آن با query string
  function handleTabChange(newIndex) {
    setTab(newIndex);
    setSearchParams({ tab: ["submit", "my-requests", "pending"][newIndex] });
  }

  const pendingCount = pending?.length || 0;
  const hasPending = pendingCount > 0;
  const showInbox = hasPending || decidedTotal > 0; // نمایش تب کارتابل

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      <BackLink to="/requests" label="بازگشت به کارتابل درخواست" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        درخواست مرخصی/ماموریت
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* تب‌ها با کلید رشته‌ای (نه ایندکس)، چون تب سوم شرطی است و پنهان شدنش نباید شماره‌ها را جابه‌جا کند */}
      <PillTabs
        value={["new", "mine", "pending"][tab]}
        onChange={(k) => handleTabChange(["new", "mine", "pending"].indexOf(k))}
        tabs={[
          { key: "new", label: "ثبت درخواست جدید" },
          { key: "mine", label: "درخواست‌های من" },
          ...(showInbox
            ? [{ key: "pending", label: hasPending ? `کارتابل تأیید (${pendingCount})` : "کارتابل تأیید" }]
            : []),
        ]}
      />

      {/* تب ثبت درخواست: بعد از ثبت، پیام موفقیت و انتقال به تب «درخواست‌های من» */}
      {tab === 0 && (
        <SubmitRequestForm
          onSubmitted={(isForgottenPunch, approverName) => {
            const kind = isForgottenPunch ? "درخواست تردد فراموش‌شده" : "درخواست شما";
            setToast(
              approverName
                ? `${kind} ثبت شد و برای «${approverName}» ارسال شد.`
                : `${kind} ثبت شد و برای ${isForgottenPunch ? "سرپرست" : "تأییدکننده"} ارسال شد.`
            );
            handleTabChange(1);
            loadMyRequests();
          }}
        />
      )}

      {/* تب درخواست‌های من */}
      {tab === 1 && myRequests !== null && <MyRequestsTable
          items={myRequests}
          onDeleted={() => {
            setToast("درخواست حذف شد.");
            loadMyRequests();
          }}
        />}

      {/* تب کارتابل: درخواست‌های در انتظار تصمیم و زیر آن سوابق تصمیم‌های قبلی */}
      {tab === 2 && showInbox && (
        <Stack spacing={3}>
          <Box>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1.5 }}>
              در انتظار تصمیم شما {hasPending ? `(${pendingCount})` : ""}
            </Typography>
            <PendingApprovalTable items={pending || []} onDecide={setDecidingItem} />
          </Box>
          <Box>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1.5 }}>
              سوابق تصمیم‌های قبلی
            </Typography>
            <DecidedHistoryTable reloadKey={historyReloadKey} />
          </Box>
        </Stack>
      )}

      {/* دیالوگ تصمیم: بعد از تصمیم همه‌ی لیست‌ها تازه می‌شوند */}
      {decidingItem && (
        <DecideDialog
          item={decidingItem}
          onClose={() => setDecidingItem(null)}
          onDecided={(approved) => {
            setToast(approved ? "درخواست تأیید شد." : "درخواست رد شد.");
            setDecidingItem(null);
            loadPending();
            loadMyRequests();
            loadDecidedTotal();
            setHistoryReloadKey((k) => k + 1);
          }}
        />
      )}

      {/* دیالوگ محدودیت دسترسی: ارزیابی‌های معوق یا اطلاعیه‌های نخوانده */}
      <AccessGateDialog
        open={gateOpen}
        gate={gateStatus?.blocked_features?.["leave_request"]}
        count={
          gateStatus?.blocked_features?.["leave_request"] === "pending_evaluations"
            ? gateStatus?.pending_evaluations
            : gateStatus?.unread_notices
        }
        byPeriod={gateStatus?.pending_by_period}
        onClose={() => setGateOpen(false)}
      />

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
