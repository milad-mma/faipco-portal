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
 * گزارش تردد ماهانه‌ی شخصی از دستگاه‌های حضور و غیاب کارخانه.
 * داده از SQL Server سایت خودِ کاربر خوانده می‌شود (فقط اگر برای آن سایت نگاشت تردد تنظیم شده باشد).
 * هر روز ماه یک ردیف است و ترددها با شماره‌ی ترتیبی («تردد ۱»، «تردد ۲»، ...) نمایش داده می‌شوند؛
 * تعداد ستون‌های تردد پویا و برابر بیشترین تعداد تردد در روزهای همان ماه است.
 * روزهای تعطیل (از نگاشت تقویم سایت) قرمز، غیبت زرد و مرخصی/ماموریت روزانه و ساعتی با چیپ مشخص می‌شوند.
 * نام روز هفته در Backend از خود تاریخ محاسبه می‌شود و همیشه موجود است.
 * جدول در همه‌ی اندازه‌ها یک اسکرول‌بار افقی بالای خود دارد که با اسکرول خود جدول همگام است.
 * این صفحه از «گزارش ورود و خروج» GPS (ClockInOutReportPage) مستقل است و منبع داده‌ی متفاوتی دارد.
 * دسترسی به گزارش با AccessGateDialog محدود می‌شود (ارزیابی‌های معوق یا اطلاعیه‌های نخوانده).
 */
// رنگ چیپ هر نوع غیبت: مرخصی (سبز)، ماموریت (آبی)، سایر (زرد)
// مرخصی/ماموریت روزانه از جدول Mor_Mam و ساعتی از علامت (Status) خودِ تردد می‌آید
const KIND_COLOR = { leave: "success", mission: "info", other: "warning" };
// چیپ وضعیت روز: تعطیل (قرمز) و غیبت (زرد = روز کاری گذشته بدون تردد و بدون مرخصی/ماموریت)
const STATUS_CHIPS = {
  holiday: { label: "تعطیل", color: "error" },
  absent: { label: "غیبت", color: "warning" },
};

// تعداد دقیقه را به رشته‌ی «ساعت:دقیقه» تبدیل می‌کند (مثلاً 103 -> 1:43)
function formatMinutes(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}:${String(m).padStart(2, "0")}`;
}

// متن چیپ/تولتیپ یک غیبت ساعتی: عنوان به همراه مدت در پرانتز، مثلاً «مرخصی ساعتی استحقاقی (1:43)»
function hourlyText(mark) {
  return mark.minutes ? `${mark.label} (${formatMinutes(mark.minutes)})` : mark.label;
}

// استایل چیپ فشرده با متن قابل‌شکستن در چند خط، تا جدول در موبایل جا شود
const compactChipSx = {
  height: "auto",
  fontSize: { xs: "0.62rem", sm: "0.7rem" },
  "& .MuiChip-label": { px: 0.75, py: 0.25, whiteSpace: "normal", lineHeight: 1.35 },
};

/**
 * کامپوننت صفحه‌ی گزارش تردد ماهانه.
 * ماه انتخابی را از سرور می‌گیرد و جدول روزانه‌ی ترددها را با ستون‌های پویا رندر می‌کند.
 */
export default function MonthlyAttendanceReportPage() {
  const theme = useTheme();
  const [period, setPeriod] = useState({ year: null, month: null }); // ماه انتخابی؛ مقدار اولیه از پاسخ سرور (ماه جاری) پر می‌شود
  const [report, setReport] = useState(null); // پاسخ سرور: { year, month, days, max_transits_in_month }
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  // وضعیت محدودیت دسترسی از Hook مشترک؛ با برگشت به صفحه یا بازگشت فوکوس خودکار تازه می‌شود
  const { status: gateStatus } = useAccessGateStatus();
  const [gateOpen, setGateOpen] = useState(false); // باز بودن دیالوگ محدودیت دسترسی

  // با هر تغییر وضعیت، دیالوگ همگام می‌شود: اگر کاربر پیش‌نیاز را انجام داد و برگشت، دیالوگ خودکار بسته می‌شود
  useEffect(() => {
    if (!gateStatus) return;
    setGateOpen(Boolean(gateStatus.blocked_features?.["attendance_report"]));
  }, [gateStatus]);


  const topScrollRef = useRef(null); // ظرف اسکرول‌بار افقی بالای جدول
  const tableScrollRef = useRef(null); // ظرف خود جدول (TableContainer)
  const [tableScrollWidth, setTableScrollWidth] = useState(0); // عرض قابل‌اسکرول جدول برای هم‌عرض کردن اسکرول‌بار بالا
  const isSyncingScroll = useRef(false); // جلوگیری از حلقه بی‌نهایت بین دو onScroll

  // با هر تغییر ماه/سال، گزارش را از سرور می‌گیرد و period را با پاسخ سرور همگام می‌کند
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

  // رنگ پس‌زمینه‌ی ردیف یک روز: تعطیل قرمز کم‌رنگ، غیبت روزانه به رنگ نوع آن، غیبت زرد، در غیر این صورت بدون رنگ
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

  // اسکرول افقی نوار بالایی را به جدول منتقل می‌کند (با قفل برای جلوگیری از حلقه‌ی رفت‌وبرگشت)
  function handleTopScroll() {
    if (isSyncingScroll.current) return;
    isSyncingScroll.current = true;
    if (tableScrollRef.current && topScrollRef.current) {
      tableScrollRef.current.scrollLeft = topScrollRef.current.scrollLeft;
    }
    isSyncingScroll.current = false;
  }

  // اسکرول افقی جدول را به نوار بالایی منتقل می‌کند
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

      {/* توضیح منبع داده‌ی گزارش */}
      <Alert severity="info" sx={{ mb: 3 }}>
        همکار گرامی، گزارش حاضر بر اساس اطلاعات ثبت‌شده مربوط به ورود و خروج شما، از طریق دستگاه‌های ثبت
        و کنترل تردد مستقر در محوطه کارخانه، تهیه و تنظیم گردیده است.
      </Alert>

      {/* فیلتر ماه/سال شمسی */}
      <Box sx={{ mb: 3 }}>
        <JalaliMonthYearFilter
          year={period.year}
          month={period.month}
          onChange={(next) => setPeriod(next)}
          disabled={isLoading}
        />
      </Box>

      {/* راهنمای رنگ چیپ‌ها؛ فقط وقتی در این ماه غیبت/مرخصی/تعطیلی وجود دارد */}
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

      {/* بارگذاری اولیه / جدول گزارش با اسکرول‌بار افقی بالایی همگام‌شده */}
      {isLoading && !report ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : report ? (
        <>
          {/* اسکرول‌بار افقی بالای جدول: یک Box خالی هم‌عرض جدول */}
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
                // سلول‌های فشرده تا جدول در موبایل کامل دیده شود
                "& .MuiTableCell-root": {
                  px: { xs: 0.5, sm: 1 },
                  py: { xs: 0.5, sm: 0.75 },
                  fontSize: { xs: "0.7rem", sm: "0.8rem" },
                  whiteSpace: "nowrap",
                },
              }}
            >
              {/* سرستون‌ها: روز، تاریخ، وضعیت (اختیاری) و ستون‌های پویای تردد */}
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
              {/* یک ردیف به ازای هر روز ماه */}
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
                        {/* چیپ غیبت روزانه یا وضعیت روز، و زیر آن چیپ‌های غیبت ساعتی (زیر هم) */}
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
                    {/* ستون‌های تردد: ساعت هر تردد؛ اگر تردد علامت مرخصی/ماموریت داشته باشد رنگی و با تولتیپ */}
                    {Array.from({ length: transitColumnCount }, (_, i) => {
                      const mark = day.transit_marks?.[i]; // علامت مرخصی/ماموریت ساعتی متصل به این تردد
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

      {/* دیالوگ محدودیت دسترسی: ارزیابی‌های معوق یا اطلاعیه‌های نخوانده */}
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
