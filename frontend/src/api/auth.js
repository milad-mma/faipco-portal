/**
 * توابع فراخوانی API احراز هویت و حساب کاربری جاری.
 * ورود، گرفتن کاربر جاری، تغییر رمز، فراموشی/بازنشانی رمز و ویرایش اطلاعات تماس.
 */
import { apiClient } from "./client";

// POST /auth/login با نام کاربری و رمز (و در صورت نیاز کپچا: { captcha_id, captcha_answer })؛
// خروجی: توکن‌های دسترسی و رفرش. پاسخ 401 فیلد captcha_required دارد.
export async function loginRequest(username, password, captcha = null) {
  const { data } = await apiClient.post("/auth/login", { username, password, ...(captcha || {}) });
  return data; // { access_token, refresh_token, token_type }
}

// GET /auth/me؛ خروجی: اطلاعات و مجوزهای کاربر واردشده
export async function fetchCurrentUser() {
  const { data } = await apiClient.get("/auth/me");
  return data;
}

// PUT /auth/me/password؛ تغییر رمز کاربر جاری با رمز فعلی و رمز جدید؛ خروجی ندارد
export async function changePasswordRequest(currentPassword, newPassword) {
  await apiClient.put("/auth/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

// POST /auth/forgot-password؛ ارسال کد بازیابی از طریق کانال انتخابی (پیش‌فرض پیامک)؛ خروجی: پاسخ سرور
export async function forgotPasswordRequest(identifier, channel = "sms", captcha = null) {
  const { data } = await apiClient.post("/auth/forgot-password", { identifier, channel, ...(captcha || {}) });
  return data;
}

// POST /auth/verify-reset-code؛ اعتبارسنجی کد/توکن بازیابی؛ خروجی: نتیجه‌ی بررسی
export async function verifyResetCodeRequest(token) {
  const { data } = await apiClient.post("/auth/verify-reset-code", { token });
  return data;
}

// POST /auth/reset-password؛ تنظیم رمز جدید با توکن بازیابی؛ خروجی: پاسخ سرور
export async function resetPasswordRequest(token, newPassword) {
  const { data } = await apiClient.post("/auth/reset-password", { token, new_password: newPassword });
  return data;
}

// PUT /auth/me/contact-info؛ فقط فیلدهای ارسال‌شده (ایمیل/موبایل) را به‌روز می‌کند؛ خروجی: اطلاعات به‌روزشده
export async function updateMyContactInfo({ email, mobile }) {
  const payload = {};
  if (email !== undefined) payload.email = email;
  if (mobile !== undefined) payload.mobile = mobile;
  const { data } = await apiClient.put("/auth/me/contact-info", payload);
  return data;
}

// GET /auth/captcha؛ کپچای تصویری داخلی. purpose: "login" | "forgot"
// خروجی: { required, captcha_id?, image? (data URL), expires_in? }
export async function fetchCaptcha(purpose = "login") {
  const { data } = await apiClient.get("/auth/captcha", { params: { purpose } });
  return data;
}
