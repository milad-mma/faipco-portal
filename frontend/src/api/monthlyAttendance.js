import { apiClient } from "./client";

/**
 * گزارش تردد ماهانه — از دستگاه‌های حضور و غیاب واقعی، کاملاً مستقل از
 * سیستم آزمایشی GPS (api/attendance.js). year/month اختیاری — بدونشان،
 * Backend خودش ماه شمسی جاری را پیش‌فرض می‌گیرد.
 */
export async function fetchMonthlyAttendanceReport({ year, month } = {}) {
  const params = {};
  if (year) params.year = year;
  if (month) params.month = month;
  const { data } = await apiClient.get("/monthly-attendance/report", {
    params,
  });
  return data;
}

/** فهرست «پرسنل من» سرپرست (زیرمجموعه‌ها به معنای تأییدکننده‌ی مرخصی، با واحدهای زیرمجموعه)؛ برای غیرسرپرست []. */
export async function fetchMyStaff() {
  const { data } = await apiClient.get("/monthly-attendance/my-staff");
  return data;
}

/** گزارش تردد ماهانه‌ی یکی از «پرسنل من» (فقط برای سرپرست او). */
export async function fetchMyStaffAttendanceReport(
  employeeId,
  { year, month } = {},
) {
  const params = {};
  if (year) params.year = year;
  if (month) params.month = month;
  const { data } = await apiClient.get(
    `/monthly-attendance/my-staff/${employeeId}/report`,
    { params },
  );
  return data;
}
