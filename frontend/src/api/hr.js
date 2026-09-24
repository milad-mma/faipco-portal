/**
 * توابع فراخوانی API منابع انسانی: پیام‌های تبریک تولد.
 * قالب‌های پیام، ساعت ارسال خودکار، فعال/غیرفعال‌سازی و ارسال فوری تبریک‌ها.
 */
import { apiClient } from "./client";

// GET /hr/birthday-templates؛ خروجی: فهرست قالب‌های پیام تبریک
export async function fetchBirthdayTemplates() {
  const { data } = await apiClient.get("/hr/birthday-templates");
  return data;
}

// POST /hr/birthday-templates؛ افزودن قالب پیام؛ خروجی: قالب ساخته‌شده
export async function addBirthdayTemplate(text) {
  const { data } = await apiClient.post("/hr/birthday-templates", { text });
  return data;
}

// DELETE /hr/birthday-templates/{id}؛ حذف یک قالب پیام
export async function deleteBirthdayTemplate(templateId) {
  await apiClient.delete(`/hr/birthday-templates/${templateId}`);
}

// GET /hr/birthday-send-time؛ خروجی: ساعت و دقیقه‌ی ارسال خودکار
export async function fetchBirthdaySendTime() {
  const { data } = await apiClient.get("/hr/birthday-send-time");
  return data; // { hour, minute }
}

// PUT /hr/birthday-send-time؛ ذخیره‌ی ساعت ارسال خودکار؛ خروجی: مقدار ذخیره‌شده
export async function updateBirthdaySendTime({ hour, minute }) {
  const { data } = await apiClient.put("/hr/birthday-send-time", { hour, minute });
  return data;
}

// GET /hr/birthday-enabled؛ خروجی: فعال بودن ارسال خودکار تبریک (boolean)
export async function fetchBirthdayEnabled() {
  const { data } = await apiClient.get("/hr/birthday-enabled");
  return data.enabled;
}

// PUT /hr/birthday-enabled؛ فعال/غیرفعال کردن ارسال خودکار؛ خروجی: وضعیت جدید (boolean)
export async function updateBirthdayEnabled(enabled) {
  const { data } = await apiClient.put("/hr/birthday-enabled", { enabled });
  return data.enabled;
}

// POST /hr/birthday-send-now؛ ارسال فوری تبریک به متولدین امروز؛ خروجی: تعداد ارسال و پیام
export async function sendBirthdayGreetingsNow() {
  const { data } = await apiClient.post("/hr/birthday-send-now");
  return data; // { sent_count, message }
}
