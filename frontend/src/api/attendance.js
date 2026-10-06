/**
 * توابع فراخوانی API حضور و غیاب.
 * لاگ‌های ورود/خروج و نشست‌های «پرسنل آنلاین / آنلاین در محیط کار» همه‌ی پرسنل (مدیر) و ثبت/ویرایش/حذف دستی لاگ.
 * (ثبت دستی ورود/خروج توسط خود پرسنل حذف شد؛ ورود/خروج خودکار با اپ اندروید است.)
 */
import { apiClient } from "./client";

// لاگ‌های همه‌ی پرسنل را با فیلتر پرسنل/نوع/ماه/سایت و صفحه‌بندی برمی‌گرداند (ویژه‌ی مدیر)
export async function fetchAllAttendanceLogs({ page = 1, pageSize = 50, employeeId, logType, year, month, siteId } = {}) {
  const { data } = await apiClient.get("/attendance/logs", {
    params: {
      page,
      page_size: pageSize,
      employee_id: employeeId || undefined,
      log_type: logType || undefined,
      year: year || undefined,
      month: month || undefined,
      site_id: siteId ?? undefined,
    },
  });
  return data; // { items, total, year, month }
}

// جلسات حضور (جفت ورود-خروج) را با فیلتر پرسنل/فقط حاضرین/سایت و صفحه‌بندی برمی‌گرداند
// kind: "app" = باز بودن پرتال (همه‌ی پرسنل)، "gps" = «آنلاین در محیط کار» (پرتال باز یا اپ در پس‌زمینه)
export async function fetchPresenceSessions({ page = 1, pageSize = 50, employeeId, onlyOnline, siteId, kind = "app" } = {}) {
  const { data } = await apiClient.get("/attendance/presence-sessions", {
    params: {
      page,
      page_size: pageSize,
      employee_id: employeeId || undefined,
      only_online: onlyOnline || undefined,
      site_id: siteId ?? undefined,
      kind,
    },
  });
  return data; // { items, total }
}

// یک لاگ ورود/خروج دستی برای یک پرسنل در زمان مشخص ثبت می‌کند (ویژه‌ی مدیر)
export async function createManualAttendanceLog({ employeeId, logType, createdAt, siteId }) {
  const { data } = await apiClient.post("/attendance/logs", {
    employee_id: employeeId,
    log_type: logType,
    created_at: createdAt,
    site_id: siteId || null,
  });
  return data;
}

// نوع، زمان یا سایت یک لاگ موجود را ویرایش می‌کند؛ فیلدهای خالی ارسال نمی‌شوند
export async function updateAttendanceLog(logId, { logType, createdAt, siteId } = {}) {
  const { data } = await apiClient.put(`/attendance/logs/${logId}`, {
    log_type: logType || undefined,
    created_at: createdAt || undefined,
    site_id: siteId ?? undefined,
  });
  return data;
}

// یک لاگ ورود/خروج را با شناسه‌ی آن حذف می‌کند
export async function deleteAttendanceLog(logId) {
  await apiClient.delete(`/attendance/logs/${logId}`);
}
