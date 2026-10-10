/**
 * نمونه‌ی مشترک axios برای همه‌ی درخواست‌های API.
 * توکن دسترسی را به هر درخواست اضافه می‌کند و در پاسخ 401 یک‌بار توکن را رفرش کرده
 * و درخواست را تکرار می‌کند؛ درخواست‌های هم‌زمان در صف منتظر نتیجه‌ی رفرش می‌مانند.
 */
import axios from "axios";
import { normalizeSearchText } from "../utils/searchText";
import { isAndroidApp } from "../utils/androidApp";
import { reportClientError } from "../utils/errorReporter";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1"; // آدرس پایه‌ی API از متغیر محیطی Vite؛ در نبود آن آدرس توسعه‌ی محلی

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  // اگر بک‌اند پاسخ ندهد، درخواست حداکثر پس از ۲۰ ثانیه با خطا رد می‌شود تا برنامه در حالت بارگذاری معلق نماند
  timeout: 20_000,
});

// خطای اعتبارسنجی FastAPI (422) فهرستی از اشیای {type, loc, msg, ...} است، نه متن. صفحه‌هایی که
// err.response.data.detail را مستقیم نمایش می‌دهند با این شیء از کار می‌افتادند (React error #31 / صفحه‌ی سفید)؛
// همین‌جا یک‌بار به متن فارسی تبدیل می‌شود تا همه‌ی صفحه‌ها همیشه رشته بگیرند.
const FIELD_LABELS = {
  email: "ایمیل",
  mobile: "موبایل",
  mobile_number: "موبایل",
  current_password: "رمز فعلی",
  new_password: "رمز جدید",
  password: "رمز عبور",
  username: "نام کاربری",
  national_id: "کد ملی",
  title: "عنوان",
  body: "متن",
  file: "فایل",
};
function validationMessage(item) {
  const loc = Array.isArray(item?.loc) ? item.loc.filter((p) => p !== "body" && p !== "query") : [];
  const field = loc.length ? String(loc[loc.length - 1]) : "";
  const label = FIELD_LABELS[field] || field;
  const ctx = item?.ctx || {};
  const type = item?.type || "";
  let text;
  if (type === "missing") text = "الزامی است";
  else if (type === "string_too_short") text = ctx.min_length > 1 ? `حداقل ${ctx.min_length} نویسه باشد` : "نباید خالی باشد";
  else if (type === "string_too_long") text = `حداکثر ${ctx.max_length} نویسه مجاز است`;
  else if (type === "value_error" && /email/i.test(item?.msg || "")) text = "معتبر نیست";
  else if (type === "value_error") text = String(item?.msg || "").replace(/^Value error,\s*/, "") || "معتبر نیست";
  else text = "معتبر نیست";
  return label ? `${label}: ${text}` : text;
}
function normalizeErrorDetail(error) {
  const data = error?.response?.data;
  if (data && Array.isArray(data.detail)) {
    data.detail = data.detail.map(validationMessage).join("، ") || "اطلاعات واردشده معتبر نیست.";
  }
}

// درخواست‌های پس‌زمینه که کاربر نتیجه‌شان را مستقیم نمی‌بیند (یا در نبودشان صفحه با پیش‌فرض کار می‌کند)، و پرسش‌های
// دوره‌ای وضعیت آپدیت/بازیابی که هنگام ری‌استارت سرور قطعی‌شان طبیعی است: قطعی شبکه‌ی این‌ها در «گزارش خطاها» ثبت
// نمی‌شود — فقط قطعی‌هایی که کاربر واقعاً با آن‌ها به مشکل می‌خورد (ورود، ذخیره‌ی فرم، باز کردن فیش، ...).
const BACKGROUND_PATHS = [
  "/system/version",
  "/system/branding",
  "/system/update-status",
  "/system/check-status",
  "/system/server-stats",
  "/system/usage-stats",
  "/system/ip-blocked-message",
  "/system/mobile-app-feature",
  "/backup/restore-status",
  "/auth/captcha-status",
  "/announcement/current",
  "/feedback/mine/unread-count",
  "/mobile/app/latest",
  "/mobile/me",
];
function isBackgroundRequest(config) {
  // فقط خواندن (GET)؛ ذخیره‌ی مدیر روی همین مسیرها (مثلاً PUT /system/branding/...) کار کاربر است و گزارش می‌شود
  if (String(config?.method || "get").toLowerCase() !== "get") return false;
  const path = String(config?.url || "").split("?")[0];
  return BACKGROUND_PATHS.includes(path);
}

const SEARCH_PARAM_KEYS = ["search", "q"]; // نام پارامترهای جست‌وجو که قبل از ارسال یکسان‌سازی می‌شوند

// --- تزریق خودکار Access Token در هر درخواست ---
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // پرتال داخل اپ اندروید (فقط اطلاعاتی؛ تصمیم امنیتی سمت سرور با وضعیت گوشی گرفته می‌شود)
  if (isAndroidApp()) config.headers["X-Client-App"] = "android";
  // متن جست‌وجو (پارامتر search/q) با ارقام فارسی/عربی و ي/ك عربی هم مقادیر لاتین/فارسی را پیدا کند
  if (config.params) {
    for (const key of SEARCH_PARAM_KEYS) {
      if (typeof config.params[key] === "string") {
        config.params = { ...config.params, [key]: normalizeSearchText(config.params[key]) };
      }
    }
  }
  return config;
});

let isRefreshing = false; // آیا یک درخواست رفرش توکن در جریان است
let pendingQueue = []; // درخواست‌های 401 که منتظر پایان رفرش جاری هستند

// همه‌ی درخواست‌های صف را با توکن جدید resolve یا با خطا reject می‌کند و صف را خالی می‌کند
function resolvePendingQueue(error, token) {
  pendingQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token);
  });
  pendingQueue = [];
}

// --- در صورت دریافت 401، یک‌بار تلاش برای Refresh و تکرار درخواست ---
apiClient.interceptors.response.use(
  (response) => {
    // تغییر رمز همه‌ی توکن‌های قبلی کاربر را باطل می‌کند و سرور جفت توکن تازه برمی‌گرداند؛
    // همین‌جا ذخیره می‌شود تا نشست جاری بدون ورود مجدد ادامه یابد
    if (response.config?.url?.includes("/auth/me/password") && response.data?.access_token) {
      localStorage.setItem("access_token", response.data.access_token);
      if (response.data.refresh_token) localStorage.setItem("refresh_token", response.data.refresh_token);
    }
    return response;
  },
  async (error) => {
    const originalRequest = error.config;
    normalizeErrorDetail(error);

    // درخواستی که اصلاً جواب نگرفت (قطع ارتباط، Timeout) — نه خطای HTTP — در «گزارش خطاها» ثبت می‌شود تا کندی/قطعی
    // بین مرورگر و سرور دیده شود. وقتی خود مرورگر آفلاین است گزارش نمی‌شود (آن مشکل اینترنت کاربر است).
    // درخواستی که با رفتن از صفحه / رفرش / رفتن اپ به پس‌زمینه قطع شد هم خطا نیست.
    if (
      !error.response &&
      error.code !== "ERR_CANCELED" &&
      error.message !== "Request aborted" &&
      navigator.onLine !== false &&
      document.visibilityState !== "hidden" &&
      !isBackgroundRequest(originalRequest)
    ) {
      reportClientError({
        type: "network",
        message: `${error.code || "NETWORK"}: ${error.message}`,
        api: `${(originalRequest?.method || "get").toUpperCase()} ${originalRequest?.url || ""}`,
      });
    }

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    const refreshToken = localStorage.getItem("refresh_token");
    // فقط اندپوینت ورود (401 یعنی رمز اشتباه، نه توکن منقضی) و خود رفرش (جلوگیری از حلقه‌ی بی‌نهایت)
    // از تلاش مجدد معاف‌اند؛ بقیه‌ی مسیرها از جمله GET /auth/me رفرش می‌شوند
    if (
      !refreshToken ||
      originalRequest.url?.includes("/auth/login") ||
      originalRequest.url?.includes("/auth/refresh")
    ) {
      return Promise.reject(error);
    }

    // اگر رفرش دیگری در جریان است، درخواست در صف می‌ماند و پس از گرفتن توکن جدید تکرار می‌شود
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      }).then((token) => {
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return apiClient(originalRequest);
      });
    }

    // علامت‌گذاری درخواست تا فقط یک‌بار دوباره تلاش شود
    originalRequest._retry = true;
    isRefreshing = true;

    // گرفتن توکن‌های جدید، ذخیره در localStorage، آزاد کردن صف و تکرار درخواست اصلی
    try {
      const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      resolvePendingQueue(null, data.access_token);
      originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      resolvePendingQueue(refreshError, null);
      // توکن‌ها فقط وقتی پاک می‌شوند و کاربر به صفحه‌ی ورود می‌رود که سرور رفرش‌توکن را با 401 رد کند؛
      // در خطای شبکه (آفلاین) توکن‌ها می‌مانند تا AuthContext پس از وصل شدن اینترنت دوباره تلاش کند
      if (refreshError.response?.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);
