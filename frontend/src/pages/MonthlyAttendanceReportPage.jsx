import { useEffect, useState } from "react";
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
 * ⚠️ به‌جای «ورود/خروج» (که فرض می‌کرد رکورد اول = ورود، دوم = خروج)،
 * هر تردد فقط با شماره ترتیبی («تردد ۱»، «تردد ۲»، ...) نمایش داده
 * می‌شود — چون برای پرسنل شب‌کار/گردشی، تشخیص قطعی «کدام ورود و کدام
 * خروج است» ممکن نیست. Backend ترددهای نزدیک نیمه‌شب را طبق «ساعت مرز
 * شبانه‌روز کاری» (تنظیم‌شده در پنل سایت) به روز درست نسبت می‌دهد — تا
 * شیفتی که از نیمه‌شب می‌گذرد، یک واحد باقی بماند.
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

  useEffect(() => {
    setIsLoading(true);
    setError("");
    fetchMonthlyAttendanceReport({ year: period.year, month: period.month })
      .then((data) => {
        setReport(data);
        setPeriod({ year: data.year, month: data.month });
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت گزارش تردد ناموفق بود."))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period.year, period.month]);

  const transitColumnCount = report?.max_transits_in_month || 1; // حداقل یک ستون، حتی اگر ماه کلاً خالی باشد

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        گزارش تردد ماهانه
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        بر اساس دستگاه‌های حضور و غیاب واقعی — فقط تردد خودِ شما.
      </Typography>

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
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>روز</TableCell>
                {Array.from({ length: transitColumnCount }, (_, i) => (
                  <TableCell key={i} align="center">
                    {`تردد ${i + 1}`}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {report.days.map((day) => (
                <TableRow key={day.date} hover>
                  <TableCell sx={{ fontFamily: "monospace" }}>{day.date}</TableCell>
                  {Array.from({ length: transitColumnCount }, (_, i) => (
                    <TableCell key={i} align="center" sx={{ fontFamily: "monospace" }}>
                      {day.transits[i] || "—"}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}
    </Box>
  );
}
