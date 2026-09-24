/**
 * توابع فراخوانی API اطلاعیه‌ها.
 * صندوق اطلاعیه‌های کاربر، ایجاد/انتشار/حذف اطلاعیه، خوانده‌شده و آرشیو، گزارش‌های مدیر و سایت،
 * ارسال مجدد Push و اطلاعیه‌های فیش حقوقی و کارت حضور به همراه دانلود فایل شخصی هر کاربر.
 */
import { apiClient } from "./client";

// GET /notices/me با صفحه‌بندی و فیلتر نوع/آرشیو؛ خروجی: { items, total, unread_total }
export async function fetchMyNotices({ page = 1, pageSize = 10, noticeType, archived } = {}) {
  // archived: "exclude" (پیش‌فرض، صندوق ورودی عادی) | "only" (تب آرشیو) |
  // "all" (بدون فیلتر آرشیو — ویجت «اطلاعیه‌های اخیر» داشبورد)
  const { data } = await apiClient.get("/notices/me", {
    params: { page, page_size: pageSize, notice_type: noticeType ?? undefined, archived: archived ?? undefined },
  });
  return data; // { items, total, unread_total }
}

// POST /notices؛ ایجاد اطلاعیه؛ خروجی: اطلاعیه‌ی ساخته‌شده
export async function createNotice(payload) {
  const { data } = await apiClient.post("/notices", payload);
  return data;
}

// POST /notices/{id}/publish؛ انتشار اطلاعیه‌ی پیش‌نویس؛ خروجی: اطلاعیه‌ی منتشرشده
export async function publishNotice(noticeId) {
  const { data } = await apiClient.post(`/notices/${noticeId}/publish`);
  return data;
}

// GET /notices/available-targets؛ خروجی: مخاطبانی (سایت/واحد/نقش/پرسنل) که کاربر مجاز به ارسال به آن‌هاست
export async function fetchAvailableTargets() {
  const { data } = await apiClient.get("/notices/available-targets");
  return data;
}

// POST /notices/{id}/read؛ ثبت خوانده شدن اطلاعیه توسط کاربر جاری
export async function markNoticeRead(noticeId) {
  await apiClient.post(`/notices/${noticeId}/read`);
}

// POST /notices/{id}/archive؛ انتقال اطلاعیه به آرشیو کاربر
export async function archiveNotice(noticeId) {
  await apiClient.post(`/notices/${noticeId}/archive`);
}

// POST /notices/{id}/unarchive؛ خارج کردن اطلاعیه از آرشیو کاربر
export async function unarchiveNotice(noticeId) {
  await apiClient.post(`/notices/${noticeId}/unarchive`);
}

// GET /notices/sent-by-me؛ خروجی: اطلاعیه‌های ارسالی کاربر جاری (صفحه‌بندی‌شده)
export async function fetchSentByMe(page = 1, pageSize = 10) {
  const { data } = await apiClient.get("/notices/sent-by-me", { params: { page, page_size: pageSize } });
  return data; // { items, total, unread_total }
}

// GET /notices/admin-report (اختیاری به تفکیک سایت)؛ خروجی: گزارش همه‌ی اطلاعیه‌ها برای مدیر
export async function fetchAdminReport(page = 1, pageSize = 10, siteId = null) {
  const { data } = await apiClient.get("/notices/admin-report", {
    params: { page, page_size: pageSize, site_id: siteId ?? undefined },
  });
  return data; // { items, total, unread_total }
}

// GET /notices/site-report؛ خروجی: گزارش اطلاعیه‌های سایت‌های تحت مدیریت کاربر
export async function fetchSiteReport(page = 1, pageSize = 10, siteId = null) {
  const { data } = await apiClient.get("/notices/site-report", {
    params: { page, page_size: pageSize, site_id: siteId ?? undefined },
  });
  return data; // { items, total, unread_total }
}

// GET /notices/stats-summary؛ خروجی: خلاصه‌ی آمار (تعداد منتشرشده در هفته‌ی جاری)
export async function fetchNoticeStatsSummary() {
  const { data } = await apiClient.get("/notices/stats-summary");
  return data; // { published_this_week }
}

// GET /notices/{id}/readers؛ خروجی: فهرست مخاطبان و وضعیت خواندن اطلاعیه
export async function fetchNoticeReaders(noticeId) {
  const { data } = await apiClient.get(`/notices/${noticeId}/readers`);
  return data;
}

// POST /notices/{id}/resend-push؛ ارسال دوباره‌ی اعلان Push به مخاطبان؛ خروجی: تعداد ارسال‌شده
export async function resendNoticePush(noticeId) {
  // Timeout شصت ثانیه‌ای (بیشتر از پیش‌فرض ۲۰ ثانیه) چون ارسال به چند صد مخاطب ممکن است طول بکشد
  const { data } = await apiClient.post(`/notices/${noticeId}/resend-push`, null, { timeout: 60_000 });
  return data; // { sent_count }
}

// DELETE /notices/{id}؛ حذف اطلاعیه
export async function deleteNotice(noticeId) {
  await apiClient.delete(`/notices/${noticeId}`);
}

// POST /notices/payroll (multipart)؛ ایجاد اطلاعیه‌ی فیش حقوقی با فایل PDF تجمیعی؛ خروجی: اطلاعیه‌ی ساخته‌شده
export async function createPayrollNotice({ title, body, priority, file }) {
  const formData = new FormData();
  formData.append("title", title);
  formData.append("body", body || "");
  formData.append("priority", priority);
  formData.append("file", file);
  const { data } = await apiClient.post("/notices/payroll", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 2 * 60 * 1000, // فایل‌های حجیم ممکن است بیشتر از حالت پیش‌فرض طول بکشند
  });
  return data;
}

// GET /notices/{id}/payroll/mine؛ خروجی: فیش حقوقی کاربر جاری به صورت Blob
export async function fetchMyPayrollReceiptBlob(noticeId) {
  const { data } = await apiClient.get(`/notices/${noticeId}/payroll/mine`, {
    responseType: "blob",
  });
  return data; // Blob از نوع application/pdf — فقط فیش خودِ کاربر جاری
}

// POST /notices/attendance-card (multipart)؛ ایجاد اطلاعیه‌ی کارت حضور با فایل PDF تجمیعی؛ خروجی: اطلاعیه‌ی ساخته‌شده
export async function createAttendanceCardNotice({ title, body, priority, cardSubtitle, file }) {
  const formData = new FormData();
  formData.append("title", title);
  formData.append("body", body || "");
  formData.append("priority", priority);
  formData.append("card_subtitle", cardSubtitle);
  formData.append("file", file);
  const { data } = await apiClient.post("/notices/attendance-card", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 2 * 60 * 1000, // فایل‌های حجیم ممکن است بیشتر از حالت پیش‌فرض طول بکشند
  });
  return data;
}

// GET /notices/{id}/attendance-card/mine؛ خروجی: کارت حضور کاربر جاری به صورت Blob
export async function fetchMyAttendanceCardBlob(noticeId) {
  const { data } = await apiClient.get(`/notices/${noticeId}/attendance-card/mine`, {
    responseType: "blob",
  });
  return data; // Blob از نوع application/pdf — فقط کارت خودِ کاربر جاری
}
