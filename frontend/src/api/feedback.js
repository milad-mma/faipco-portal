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

// GET /feedback با فیلترهای فرستنده/سایت/دسته/ناشناس/بازه‌ی تاریخ؛ خروجی: { items, total, page, page_size }
export async function fetchFeedback({
  senderId,
  siteId,
  category,
  isAnonymous,
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
