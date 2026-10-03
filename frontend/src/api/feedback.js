/**
 * توابع فراخوانی API انتقادات و پیشنهادات (Feedback).
 * ثبت بازخورد، گزارش صفحه‌بندی‌شده‌ی بازخوردها، حذف و مدیریت عبارات ممنوعه.
 */
import { apiClient } from "./client";

// POST /feedback؛ ثبت بازخورد (دسته، عنوان، متن، ناشناس بودن)؛ خروجی: بازخورد ثبت‌شده
export async function submitFeedback({ category, title, message, isAnonymous }) {
  const { data } = await apiClient.post("/feedback", {
    category,
    title,
    message,
    is_anonymous: isAnonymous,
  });
  return data;
}

// GET /feedback با فیلترهای فرستنده/سایت/دسته/ناشناس/وضعیت/بازه‌ی تاریخ؛ خروجی: { items, total, page, page_size }
export async function fetchFeedback({
  senderId,
  siteId,
  category,
  isAnonymous,
  status,
  dateFrom,
  dateTo,
  page,
  pageSize,
} = {}) {
  const params = {};
  if (senderId) params.sender_id = senderId;
  if (siteId) params.site_id = siteId;
  if (category) params.category = category;
  if (isAnonymous !== undefined && isAnonymous !== "") params.is_anonymous = isAnonymous;
  if (status) params.status = status;
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;
  if (page) params.page = page;
  if (pageSize) params.page_size = pageSize;
  // خروجی سرور صفحه‌بندی‌شده است: {items, total, page, page_size}
  const { data } = await apiClient.get("/feedback", { params });
  return data;
}

// DELETE /feedback/{id}؛ حذف یک بازخورد
export async function deleteFeedback(id) {
  await apiClient.delete(`/feedback/${id}`);
}

// GET /feedback/prohibited-phrases؛ خروجی: فهرست عبارات ممنوعه در متن بازخورد
export async function fetchProhibitedPhrases() {
  const { data } = await apiClient.get("/feedback/prohibited-phrases");
  return data;
}

// POST /feedback/prohibited-phrases؛ افزودن عبارت ممنوعه؛ خروجی: عبارت ساخته‌شده
export async function addProhibitedPhrase(phrase) {
  const { data } = await apiClient.post("/feedback/prohibited-phrases", { phrase });
  return data;
}

// DELETE /feedback/prohibited-phrases/{id}؛ حذف یک عبارت ممنوعه
export async function deleteProhibitedPhrase(id) {
  await apiClient.delete(`/feedback/prohibited-phrases/${id}`);
}

// GET /feedback/settings؛ خروجی: { profanity_reveal_enabled }
export async function fetchFeedbackSettings() {
  const { data } = await apiClient.get("/feedback/settings");
  return data;
}

// PUT /feedback/settings (فقط superuser)؛ روشن/خاموش کردن آشکار شدن هویت با الفاظ نامناسب
export async function saveFeedbackSettings(profanityRevealEnabled) {
  const { data } = await apiClient.put("/feedback/settings", { profanity_reveal_enabled: profanityRevealEnabled });
  return data;
}

// ---------- گفتگو (پاسخ بازبین / پیگیری فرستنده) ----------

// GET /feedback/mine؛ پیام‌های خودِ کاربر با وضعیت، تعداد پاسخ و has_new_reply
export async function fetchMyFeedback() {
  const { data } = await apiClient.get("/feedback/mine");
  return data;
}

// GET /feedback/mine/unread-count؛ خروجی: { count } — پیام‌های با پاسخ دیده‌نشده (نشانگر داشبورد)
export async function fetchMyFeedbackUnreadCount() {
  const { data } = await apiClient.get("/feedback/mine/unread-count");
  return data.count || 0;
}

// GET /feedback/mine/{id}؛ گفتگوی یکی از پیام‌های خودِ کاربر { message, replies } (و ثبت «دیده شد»)
export async function fetchMyFeedbackThread(id) {
  const { data } = await apiClient.get(`/feedback/mine/${id}`);
  return data;
}

// POST /feedback/mine/{id}/replies؛ پاسخ فرستنده؛ خروجی گفتگوی به‌روز (409 = گفتگو بسته است)
export async function replyToMyFeedback(id, body) {
  const { data } = await apiClient.post(`/feedback/mine/${id}/replies`, { body });
  return data;
}

// GET /feedback/{id}/replies؛ گفتگوی یک پیام برای بازبین { message, replies }
export async function fetchFeedbackThread(id) {
  const { data } = await apiClient.get(`/feedback/${id}/replies`);
  return data;
}

// POST /feedback/{id}/replies؛ پاسخ بازبین (feedback.reply)؛ خروجی گفتگوی به‌روز
export async function replyToFeedback(id, body) {
  const { data } = await apiClient.post(`/feedback/${id}/replies`, { body });
  return data;
}

// PUT /feedback/{id}/status؛ وضعیت: new | in_review | answered | closed (feedback.reply)
export async function setFeedbackStatus(id, status) {
  const { data } = await apiClient.put(`/feedback/${id}/status`, { status });
  return data;
}
