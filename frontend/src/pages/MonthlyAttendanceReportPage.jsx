import { Fragment, useEffect, useState } from "react";
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
 * باشد). ستون‌های ورود/خروج کاملاً پویا هستند — بر اساس بیشترین تعداد
 * جفت ورود/خروج در بین همه روزهای همان ماه.
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

  const pairCount = report?.max_pairs_in_month || 1; // حداقل یک ستون ورود/خروج، حتی اگر ماه کلاً خالی باشد

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
                <TableCell rowSpan={2}>روز</TableCell>
                {Array.from({ length: pairCount }, (_, i) => (
                  <TableCell key={i} colSpan={2} align="center">
                    {pairCount > 1 ? `تردد ${i + 1}` : "تردد"}
                  </TableCell>
                ))}
              </TableRow>
              <TableRow>
                {Array.from({ length: pairCount }, (_, i) => (
                  <Fragment key={i}>
                    <TableCell align="center">ورود</TableCell>
                    <TableCell align="center">خروج</TableCell>
                  </Fragment>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {report.days.map((day) => (
                <TableRow key={day.date} hover>
                  <TableCell sx={{ fontFamily: "monospace" }}>{day.date}</TableCell>
                  {Array.from({ length: pairCount }, (_, i) => {
                    const pair = day.pairs[i];
                    return (
                      <Fragment key={i}>
                        <TableCell align="center" sx={{ fontFamily: "monospace" }}>
                          {pair?.entry || "—"}
                        </TableCell>
                        <TableCell align="center" sx={{ fontFamily: "monospace" }}>
                          {pair?.exit || "—"}
                        </TableCell>
                      </Fragment>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}
    </Box>
  );
}
