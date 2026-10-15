import { useEffect, useRef, useState } from "react";
import { Alert, Box, CircularProgress, Stack, Typography } from "@mui/material";
import JalaliMonthYearFilter from "../components/JalaliMonthYearFilter";
import BackLink from "../components/BackLink";
import MonthlyAttendanceTable from "../components/MonthlyAttendanceTable";
import {
  fetchMyStaff,
  fetchMyStaffAttendanceReport,
} from "../api/monthlyAttendance";
import { swr } from "../api/swrCache";
import { gregorianToJalali } from "../utils/jalaliDate";
import { searchKey } from "../utils/searchText";
import EmployeeSearchField from "../components/EmployeeSearchField";

/**
 * «تردد پرسنل من» — سرپرست یکی از زیرمجموعه‌هایش را انتخاب می‌کند و گزارش تردد ماهانه‌ی او را می‌بیند.
 * فهرست زیرمجموعه‌ها را سرور از زنجیره‌ی سازمانی کاراوب (همان تأییدکننده‌ی مرخصی) با واحدهای زیرمجموعه
 * می‌سازد؛ این صفحه فقط همان فهرست را (با نام، کد پرسنلی و واحد) جست‌وجوپذیر نشان می‌دهد.
 * جدول گزارش همان MonthlyAttendanceTable صفحه‌ی شخصی است.
 */
const { jy: CURRENT_YEAR, jm: CURRENT_MONTH } = gregorianToJalali(new Date());

// برچسب هر نفر در فهرست: «نام نام‌خانوادگی (کد پرسنلی)» تا جست‌وجو با کد هم کار کند
function staffLabel(e) {
  if (!e || typeof e !== "object") return ""; // MUI ممکن است با مقدار خالی هم صدا بزند
  return `${e.first_name} ${e.last_name} (${e.personnel_code})`;
}

export default function MyStaffAttendancePage() {
  const [staff, setStaff] = useState(null); // null = هنوز بارگذاری نشده
  const [staffError, setStaffError] = useState("");
  // همان فیلد جست‌وجوی مشترک پرسنل، ولی روی فهرست «پرسنل من» که یک بار از سرور آمده (کلیدواژه: نام/کد/واحد)
  const staffFetcher = async (q) => {
    const key = searchKey(q);
    return (staff || [])
      .filter(
        (e) =>
          !key ||
          searchKey(`${staffLabel(e)} ${e.department_name || ""}`).includes(
            key,
          ),
      )
      .slice(0, 30)
      .map((e) => ({
        id: e.id,
        label: e.department_name
          ? `${staffLabel(e)} — ${e.department_name}`
          : staffLabel(e),
        employee: e,
      }));
  };
  const [selected, setSelected] = useState(null); // پرسنل انتخاب‌شده
  const [period, setPeriod] = useState({
    year: CURRENT_YEAR,
    month: CURRENT_MONTH,
  });
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const latestRequest = useRef(0); // فقط پاسخ آخرین درخواست اعمال می‌شود

  // فهرست «پرسنل من» (همان کش صفحه‌ی گزارش شخصی)
  useEffect(() => {
    swr("monthly:my-staff", fetchMyStaff, (data) =>
      setStaff(Array.isArray(data) ? data : []),
    ).catch((err) => {
      setStaff([]);
      setStaffError(
        err.response?.data?.detail || "دریافت فهرست پرسنل با خطا مواجه شد.",
      );
    });
  }, []);

  // با تغییر پرسنل یا ماه، گزارش او گرفته می‌شود (کش جدا برای هر نفر/ماه)
  useEffect(() => {
    if (!selected) {
      setReport(null);
      return;
    }
    const requestId = ++latestRequest.current;
    const params = { year: period.year, month: period.month };
    setIsLoading(true);
    setError("");
    let shownFromCache = false;
    swr(
      `monthly:staff:${selected.id}:${params.year}-${params.month}`,
      () => fetchMyStaffAttendanceReport(selected.id, params),
      (data, fromCache) => {
        if (requestId !== latestRequest.current) return;
        if (fromCache) shownFromCache = true;
        setReport(data);
        setIsLoading(false);
      },
    )
      .catch((err) => {
        if (requestId !== latestRequest.current || shownFromCache) return;
        setReport(null);
        setError(
          err.response?.data?.detail || "دریافت گزارش تردد با خطا مواجه شد.",
        );
      })
      .finally(
        () => requestId === latestRequest.current && setIsLoading(false),
      );
  }, [selected, period.year, period.month]);

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      <BackLink to="/monthly-attendance" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        تردد پرسنل من
      </Typography>

      {staff === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : staff.length === 0 ? (
        <Alert severity={staffError ? "error" : "info"}>
          {staffError || "پرسنلی زیر نظر شما ثبت نشده است."}
        </Alert>
      ) : (
        <>
          {/* انتخاب پرسنل + ماه/سال */}
          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={1.5}
            alignItems={{ xs: "stretch", sm: "center" }}
            flexWrap="wrap"
            useFlexGap
            sx={{ mb: 3 }}
          >
            <EmployeeSearchField
              size="small"
              fetcher={staffFetcher}
              value={
                selected
                  ? {
                      id: selected.id,
                      label: staffLabel(selected),
                      employee: selected,
                    }
                  : null
              }
              onChange={(opt) => setSelected(opt ? opt.employee : null)}
              label="پرسنل"
              sx={{ flexGrow: 1, minWidth: 260 }}
            />
            <JalaliMonthYearFilter
              year={period.year}
              month={period.month}
              onChange={(next) => setPeriod(next)}
              disabled={isLoading}
            />
          </Stack>

          {!selected && (
            <Alert severity="info" sx={{ mb: 2 }}>
              یکی از پرسنل را انتخاب کنید تا گزارش تردد ماهانه‌ی او نمایش داده
              شود. ({staff.length} نفر زیر نظر شما)
            </Alert>
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
          ) : report && selected ? (
            <>
              <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1.5 }}>
                {staffLabel(selected)}
                {selected.department_name
                  ? ` — ${selected.department_name}`
                  : ""}
              </Typography>
              <MonthlyAttendanceTable report={report} />
            </>
          ) : null}
        </>
      )}
    </Box>
  );
}
