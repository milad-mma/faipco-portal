import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import JalaliMonthYearFilter from "../components/JalaliMonthYearFilter";
import BackLink from "../components/BackLink";
import { fetchMonthlyAttendanceReport } from "../api/monthlyAttendance";
import AccessGateDialog from "../components/AccessGateDialog";
import { useAccessGateStatus } from "../hooks/useAccessGateStatus";

/**
 * گزارش تردد ماهانه شخصی — از دستگاه‌های حضور و غیاب واقعی، در همان SQL
 * Server سایت خودِ کاربر (فقط اگر برای آن سایت یک نگاشت تردد تنظیم شده
 * باشد). ستون‌های تردد کاملاً پویا هستند — بر اساس بیشترین تعداد تردد در
 * بین همه روزهای همان ماه.
 *
 * ⚠️ طبق درخواست صریح: داده خام را دقیقاً همان‌طور که در دیتابیس ثبت
 * شده نشان می‌دهد — گروه‌بندی فقط بر اساس همان ستون تاریخ خام دستگاه
 * است، بدون هیچ پردازش/ترکیب اضافه‌ای. به‌جای «ورود/خروج» (که فرض
 * می‌کرد رکورد اول = ورود، دوم = خروج)، هر تردد فقط با شماره ترتیبی
 * («تردد ۱»، «تردد ۲»، ...) نمایش داده می‌شود.
 *
 * روزهای تعطیل (طبق نگاشت تقویم اختیاری هر سایت) با رنگ قرمز مشخص
 * می‌شوند — اگر آن سایت نگاشت تقویم نداشته باشد، is_holiday همیشه false
 * است و هیچ روزی رنگی نمی‌شود.
 *
 * ⚠️ نام روز هفته (weekday، شنبه تا جمعه) یک محاسبه خالص تقویمی از خودِ
 * تاریخ است (Backend: jalali_weekday_name) — نه داده‌ای که از جدول
 * تقویم/تعطیلات خوانده شود؛ پس همیشه در دسترس است، حتی برای سایتی که
 * اصلاً نگاشت تقویم ندارد.
 *
 * ⚠️ طبق بازخورد صریح، نمایش کارتی برای موبایل حذف شد - همیشه همین
 * جدول (در همه اندازه صفحه) با یک اسکرول‌بار افقی *بالای* جدول هم
 * (علاوه‌بر اسکرول‌بار طبیعی پایین خودِ جدول، کاملاً هماهنگ با آن) - تا
 * برای دیدن ستون‌های سمت راست/چپ وقتی تعداد ستون‌های تردد زیاد است،
 * نیازی به اسکرول‌کردن تا پایین صفحه نباشد.
 *
 * ⚠️ کاملاً مستقل از صفحه «گزارش ورود و خروج» (ClockInOutReportPage —
 * سیستم آزمایشی GPS) — این یک منبع داده متفاوت (دستگاه حضور و غیاب واقعی
 * کارخانه) و یک صفحه کاملاً جدا است.
 */
// ⚠️ مرخصی/ماموریت (فقط سایت‌های کاراوب): روزانه از Mor_Mam، ساعتی از
// علامت (Status) خودِ تردد - بازه از همان تردد تا تردد بعدی.
// ⚠️ طبق درخواست صریح کاربر: تعطیل و غیبت هم مثل مرخصی/ماموریت برچسب
// دارند - غیبت (زرد) = روز کاری گذشته بدون تردد و بدون مرخصی/ماموریت.
const KIND_COLOR = { leave: "success", mission: "info", other: "warning" };
const STATUS_CHIPS = {
  holiday: { label: "تعطیل", color: "error" },
  absent: { label: "غیبت", color: "warning" },
};

function formatMinutes(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}:${String(m).padStart(2, "0")}`;
}

// طبق خواست کاربر فقط عنوان و مدت - مثلاً «مرخصی ساعتی استحقاقی (1:43)»
function hourlyText(mark) {
  return mark.minutes ? `${mark.label} (${formatMinutes(mark.minutes)})` : mark.label;
}

// برچسب کوچک و قابل‌شکستن در چند خط - تا جدول در موبایل جا شود
const compactChipSx = {
  height: "auto",
  fontSize: { xs: "0.62rem", sm: "0.7rem" },
  "& .MuiChip-label": { px: 0.75, py: 0.25, whiteSpace: "normal", lineHeight: 1.35 },
};

export default function MonthlyAttendanceReportPage() {
  const theme = useTheme();
  const [period, setPeriod] = useState({ year: null, month: null }); // مقدار اولیه از پاسخ سرور پر می‌شود
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  // ⚠️ از Hook مشترک استفاده می‌شود تا وضعیت با برگشت به صفحه یا
  // بازگشت فوکوس خودکار تازه شود - بدون نیاز به رفرش دستی.
  const { status: gateStatus } = useAccessGateStatus();
  const [gateOpen, setGateOpen] = useState(false);

  // ⚠️ با هر تغییر وضعیت، دیالوگ هم‌گام می‌شود: اگر کاربر پیش‌نیاز را
  // انجام داد و برگشت، دیالوگ خودکار بسته می‌شود (نه اینکه هشدار
  // قدیمی تا رفرش دستی باقی بماند).
  useEffect(() => {
    if (!gateStatus) return;
    setGateOpen(Boolean(gateStatus.blocked_features?.["attendance_report"]));
  }, [gateStatus]);


  const topScrollRef = useRef(null);
  const tableScrollRef = useRef(null);
  const [tableScrollWidth, setTableScrollWidth] = useState(0);
  const isSyncingScroll = useRef(false); // جلوگیری از حلقه بی‌نهایت بین دو onScroll

  useEffect(() => {
    setIsLoading(true);
    setError("");
    fetchMonthlyAttendanceReport({ year: period.year, month: period.month })
      .then((data) => {
        setReport(data);
        setPeriod({ year: data.year, month: data.month });
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت گزارش تردد با خطا مواجه شد."))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period.year, period.month]);

  const transitColumnCount = report?.max_transits_in_month || 1; // حداقل یک ستون، حتی اگر ماه کلاً خالی باشد
  // ستون «مرخصی / ماموریت» فقط وقتی نمایش داده می‌شود که در این ماه واقعاً موردی باشد
  const hasAbsences = Boolean(
    report?.days?.some((d) => d.day_status || (d.hourly_absences && d.hourly_absences.length))
  );

  function rowBackground(day) {
    if (day.is_holiday) return "rgba(211, 47, 47, 0.08)";
    if (day.daily_absence) return alpha(theme.palette[KIND_COLOR[day.daily_absence.kind]].main, 0.1);
    if (day.day_status === "absent") return alpha(theme.palette.warning.main, 0.14);
    return undefined;
  }

  // بعد از هر رندر جدول (تغییر داده یا تعداد ستون‌ها)، عرض واقعی قابل‌اسکرول
  // جدول را اندازه می‌گیریم تا اسکرول‌بار بالایی هم دقیقاً همان عرض را داشته باشد.
  useEffect(() => {
    if (tableScrollRef.current) {
      setTableScrollWidth(tableScrollRef.current.scrollWidth);
    }
  }, [report, transitColumnCount]);

  function handleTopScroll() {
    if (isSyncingScroll.current) return;
    isSyncingScroll.current = true;
    if (tableScrollRef.current && topScrollRef.current) {
      tableScrollRef.current.scrollLeft = topScrollRef.current.scrollLeft;
    }
    isSyncingScroll.current = false;
  }

  function handleTableScroll() {
    if (isSyncingScroll.current) return;
    isSyncingScroll.current = true;
    if (tableScrollRef.current && topScrollRef.current) {
      topScrollRef.current.scrollLeft = tableScrollRef.current.scrollLeft;
    }
    isSyncingScroll.current = false;
  }

  return (
    <Box>
      <BackLink to="/my-dashboard" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        گزارش تردد ماهانه
      </Typography>

      <Alert severity="info" sx={{ mb: 3 }}>
        همکار گرامی، گزارش حاضر بر اساس اطلاعات ثبت‌شده مربوط به ورود و خروج شما، از طریق دستگاه‌های ثبت
        و کنترل تردد مستقر در محوطه کارخانه، تهیه و تنظیم گردیده است.
      </Alert>

      <Box sx={{ mb: 3 }}>
        <JalaliMonthYearFilter
          year={period.year}
          month={period.month}
          onChange={(next) => setPeriod(next)}
          disabled={isLoading}
        />
      </Box>

      {hasAbsences && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
          <Chip size="small" color="success" variant="outlined" label="مرخصی" />
          <Chip size="small" color="info" variant="outlined" label="ماموریت" />
          <Chip size="small" color="error" variant="outlined" label="تعطیل" />
          <Chip size="small" color="warning" variant="outlined" label="غیبت" />
        </Stack>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {isLoading && !report ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : report ? (
        <>
          <Box ref={topScrollRef} onScroll={handleTopScroll} sx={{ overflowX: "auto", overflowY: "hidden", mb: 0.5 }}>
            <Box sx={{ width: tableScrollWidth, height: 1 }} />
          </Box>
          <TableContainer
            ref={tableScrollRef}
            onScroll={handleTableScroll}
            component={Paper}
            variant="outlined"
            sx={{ borderRadius: 2 }}
          >
            <Table
              size="small"
              sx={{
                // ⚠️ طبق درخواست کاربر: فشرده‌تر تا در موبایل کامل دیده شود
                "& .MuiTableCell-root": {
                  px: { xs: 0.5, sm: 1 },
                  py: { xs: 0.5, sm: 0.75 },
                  fontSize: { xs: "0.7rem", sm: "0.8rem" },
                  whiteSpace: "nowrap",
                },
              }}
            >
              <TableHead>
                <TableRow>
                  <TableCell>روز</TableCell>
                  <TableCell>تاریخ</TableCell>
                  {hasAbsences && <TableCell>وضعیت</TableCell>}
                  {Array.from({ length: transitColumnCount }, (_, i) => (
                    <TableCell key={i} align="center">
                      {`تردد ${i + 1}`}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {report.days.map((day) => (
                  <TableRow key={day.date} hover sx={{ bgcolor: rowBackground(day) }}>
                    <TableCell sx={{ color: day.is_holiday ? "error.main" : undefined, fontWeight: day.is_holiday ? 700 : undefined }}>
                      {day.weekday}
                    </TableCell>
                    <TableCell
                      sx={{
                        fontFamily: "monospace",
                        color: day.is_holiday ? "error.main" : undefined,
                        fontWeight: day.is_holiday ? 700 : undefined,
                      }}
                    >
                      {/* در موبایل بدون سال (۰۶/۲۱) تا ستون باریک‌تر شود */}
                      <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
                        {day.date}
                      </Box>
                      <Box component="span" sx={{ display: { xs: "inline", sm: "none" } }}>
                        {day.date.slice(5)}
                      </Box>
                    </TableCell>
                    {hasAbsences && (
                      <TableCell sx={{ "&&": { whiteSpace: "normal" }, minWidth: { xs: 84, sm: 120 }, maxWidth: 220 }}>
                        {/* طبق خواست کاربر: چند مرخصی/ماموریت در یک روز زیر هم، نه کنار هم */}
                        <Stack direction="column" spacing={0.5} alignItems="flex-start">
                          {day.daily_absence ? (
                            <Chip
                              size="small"
                              color={KIND_COLOR[day.daily_absence.kind]}
                              label={day.daily_absence.label}
                              sx={compactChipSx}
                            />
                          ) : (
                            STATUS_CHIPS[day.day_status] && (
                              <Chip
                                size="small"
                                color={STATUS_CHIPS[day.day_status].color}
                                label={STATUS_CHIPS[day.day_status].label}
                                sx={compactChipSx}
                              />
                            )
                          )}
                          {(day.hourly_absences || []).map((mark, idx) => (
                            <Chip
                              key={idx}
                              size="small"
                              variant="outlined"
                              color={KIND_COLOR[mark.kind]}
                              label={hourlyText(mark)}
                              sx={compactChipSx}
                            />
                          ))}
                        </Stack>
                      </TableCell>
                    )}
                    {Array.from({ length: transitColumnCount }, (_, i) => {
                      const mark = day.transit_marks?.[i];
                      const cell = (
                        <TableCell
                          key={i}
                          align="center"
                          sx={{
                            fontFamily: "monospace",
                            color: mark
                              ? `${KIND_COLOR[mark.kind]}.main`
                              : day.is_holiday
                                ? "error.main"
                                : undefined,
                            fontWeight: mark ? 700 : undefined,
                          }}
                        >
                          {day.transits[i] || "—"}
                        </TableCell>
                      );
                      return mark ? (
                        <Tooltip key={i} title={hourlyText(mark)} arrow>
                          {cell}
                        </Tooltip>
                      ) : (
                        cell
                      );
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      ) : null}

      <AccessGateDialog
        open={gateOpen}
        gate={gateStatus?.blocked_features?.["attendance_report"]}
        count={
          gateStatus?.blocked_features?.["attendance_report"] === "pending_evaluations"
            ? gateStatus?.pending_evaluations
            : gateStatus?.unread_notices
        }
        byPeriod={gateStatus?.pending_by_period}
        onClose={() => setGateOpen(false)}
      />
    </Box>
  );
}
