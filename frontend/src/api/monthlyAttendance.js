import { apiClient } from "./client";

/**
 * گزارش تردد ماهانه — از جدول DataFile نرم‌افزار «کاراوب»، کاملاً مستقل از
 * سیستم آزمایشی GPS (api/attendance.js). year/month اختیاری — بدونشان،
 * Backend خودش ماه شمسی جاری را پیش‌فرض می‌گیرد.
 */
export async function fetchMonthlyAttendanceReport({ year, month } = {}) {
  const params = {};
  if (year) params.year = year;
  if (month) params.month = month;
  const { data } = await apiClient.get("/monthly-attendance/report", { params });
  return data;
}
