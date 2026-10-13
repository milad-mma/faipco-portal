import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Typography,
} from "@mui/material";
import GroupsIcon from "@mui/icons-material/Groups";
import { useNavigate } from "react-router-dom";
import JalaliMonthYearFilter from "../components/JalaliMonthYearFilter";
import BackLink from "../components/BackLink";
import MonthlyAttendanceTable from "../components/MonthlyAttendanceTable";
import {
  fetchMonthlyAttendanceReport,
  fetchMyStaff,
} from "../api/monthlyAttendance";
import { swr } from "../api/swrCache";
import AccessGateDialog from "../components/AccessGateDialog";
import { useAccessGateStatus } from "../hooks/useAccessGateStatus";

/**
 * گزارش تردد ماهانه‌ی شخصی از دستگاه‌های حضور و غیاب کارخانه.
 * داده از SQL Server سایت خودِ کاربر خوانده می‌شود (فقط اگر برای آن سایت نگاشت تردد تنظیم شده باشد).
 * خودِ جدول در components/MonthlyAttendanceTable.jsx است (مشترک با «تردد پرسنل من»).
 * اگر کاربر سرپرست باشد (فهرست «پرسنل من» خالی نباشد)، انتهای صفحه دکمه‌ی «تردد پرسنل من» نمایش داده می‌شود.
 * دسترسی به گزارش با AccessGateDialog محدود می‌شود (ارزیابی‌های معوق یا اطلاعیه‌های نخوانده).
 */
export default function MonthlyAttendanceReportPage() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState({ year: null, month: null }); // ماه انتخابی؛ مقدار اولیه از پاسخ سرور (ماه جاری) پر می‌شود
  const [report, setReport] = useState(null); // پاسخ سرور: { year, month, days, max_transits_in_month }
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [hasStaff, setHasStaff] = useState(false); // آیا کاربر زیرمجموعه دارد (دکمه‌ی «تردد پرسنل من»)
  // وضعیت محدودیت دسترسی از Hook مشترک؛ با برگشت به صفحه یا بازگشت فوکوس خودکار تازه می‌شود
  const { status: gateStatus } = useAccessGateStatus();
  const [gateOpen, setGateOpen] = useState(false); // باز بودن دیالوگ محدودیت دسترسی

  // با هر تغییر وضعیت، دیالوگ همگام می‌شود
  useEffect(() => {
    if (!gateStatus) return;
    setGateOpen(Boolean(gateStatus.blocked_features?.["attendance_report"]));
  }, [gateStatus]);

  // فهرست «پرسنل من» در پس‌زمینه؛ فقط برای تصمیم نمایش دکمه (خطا = بدون دکمه)
  useEffect(() => {
    swr("monthly:my-staff", fetchMyStaff, (data) =>
      setHasStaff(Array.isArray(data) && data.length > 0),
    ).catch(() => {});
  }, []);

  // وقتی period فقط برای همگام شدن با ماه برگشتی سرور عوض می‌شود، درخواست دوباره لازم نیست
  const skipNextFetch = useRef(false);
  const latestRequest = useRef(0); // فقط پاسخ آخرین درخواست (بعد از تغییر سریع ماه) اعمال می‌شود

  // با هر تغییر ماه/سال، گزارش را از سرور می‌گیرد و period را با پاسخ سرور همگام می‌کند.
  useEffect(() => {
    if (skipNextFetch.current) {
      skipNextFetch.current = false;
      return;
    }
    const requestId = ++latestRequest.current;
    const requested = { year: period.year, month: period.month };
    const cacheKey =
      requested.year == null
        ? "monthly:current"
        : `monthly:${requested.year}-${requested.month}`;
    setIsLoading(true);
    setError("");
    const params = { ...requested };
    let shownFromCache = false;
    swr(
      cacheKey,
      () => fetchMonthlyAttendanceReport(params),
      (data, fromCache) => {
        if (requestId !== latestRequest.current) return;
        if (fromCache) shownFromCache = true;
        setReport(data);
        setIsLoading(false);
        if (data.year !== requested.year || data.month !== requested.month) {
          skipNextFetch.current = true; // بار اول (ماه جاری): همان گزارش دوباره گرفته نشود
          setPeriod({ year: data.year, month: data.month });
          requested.year = data.year;
          requested.month = data.month;
        }
      },
    )
      .catch((err) => {
        if (requestId !== latestRequest.current || shownFromCache) return;
        setError(
          err.response?.data?.detail || "دریافت گزارش تردد با خطا مواجه شد.",
        );
      })
      .finally(
        () => requestId === latestRequest.current && setIsLoading(false),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period.year, period.month]);

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      <BackLink to="/my-dashboard" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        گزارش تردد ماهانه
      </Typography>

      <Alert severity="info" sx={{ mb: 3 }}>
        همکار گرامی، گزارش حاضر بر اساس اطلاعات ثبت‌شده مربوط به ورود و خروج
        شما، از طریق دستگاه‌های ثبت و کنترل تردد مستقر در محوطه کارخانه، تهیه و
        تنظیم گردیده است.
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
      ) : (
        <MonthlyAttendanceTable report={report} />
      )}

      {/* فقط سرپرست‌ها: ورود به گزارش تردد زیرمجموعه‌ها */}
      {hasStaff && (
        <Box sx={{ mt: 3, display: "flex", justifyContent: "flex-start" }}>
          <Button
            variant="outlined"
            startIcon={<GroupsIcon />}
            onClick={() => navigate("/monthly-attendance/my-staff")}
          >
            تردد پرسنل من
          </Button>
        </Box>
      )}

      <AccessGateDialog
        open={gateOpen}
        gate={gateStatus?.blocked_features?.["attendance_report"]}
        count={
          gateStatus?.blocked_features?.["attendance_report"] ===
          "pending_evaluations"
            ? gateStatus?.pending_evaluations
            : gateStatus?.unread_notices
        }
        byPeriod={gateStatus?.pending_by_period}
        onClose={() => setGateOpen(false)}
      />
    </Box>
  );
}
