/**
 * نمونه‌ی مشترک axios برای همه‌ی درخواست‌های API.
 * توکن دسترسی را به هر درخواست اضافه می‌کند و در پاسخ 401 یک‌بار توکن را رفرش کرده
 * و درخواست را تکرار می‌کند؛ درخواست‌های هم‌زمان در صف منتظر نتیجه‌ی رفرش می‌مانند.
 */
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1"; // آدرس پایه‌ی API از متغیر محیطی Vite؛ در نبود آن آدرس توسعه‌ی محلی

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  // اگر بک‌اند پاسخ ندهد، درخواست حداکثر پس از ۲۰ ثانیه با خطا رد می‌شود تا برنامه در حالت بارگذاری معلق نماند
  timeout: 20_000,
});

// --- تزریق خودکار Access Token در هر درخواست ---
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
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
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

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
