import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import JalaliMonthYearFilter from "../components/JalaliMonthYearFilter";
import { fetchMonthlyAttendanceReport } from "../api/monthlyAttendance";

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
export default function MonthlyAttendanceReportPage() {
  const [period, setPeriod] = useState({ year: null, month: null }); // مقدار اولیه از پاسخ سرور پر می‌شود
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

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
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>روز هفته</TableCell>
                  <TableCell>تاریخ</TableCell>
                  {Array.from({ length: transitColumnCount }, (_, i) => (
                    <TableCell key={i} align="center">
                      {`تردد ${i + 1}`}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {report.days.map((day) => (
                  <TableRow key={day.date} hover sx={day.is_holiday ? { bgcolor: "rgba(211, 47, 47, 0.08)" } : undefined}>
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
                      {day.date}
                    </TableCell>
                    {Array.from({ length: transitColumnCount }, (_, i) => (
                      <TableCell
                        key={i}
                        align="center"
                        sx={{ fontFamily: "monospace", color: day.is_holiday ? "error.main" : undefined }}
                      >
                        {day.transits[i] || "—"}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      ) : null}
    </Box>
  );
}
