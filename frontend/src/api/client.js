import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  // بدون Timeout، اگر بک‌اند از دسترس خارج بشه یا در حال Restart گیر کنه،
  // درخواست‌ها (مثلاً همون GET /auth/me موقع باز شدن اپ) می‌تونن برای همیشه
  // معلق بمونن و کل پنل فقط روی «در حال بارگذاری» گیر کنه، بدون هیچ خطای
  // قابل‌مشاهده‌ای. با این Timeout، حداکثر بعد از ۲۰ ثانیه با خطا Reject
  // می‌شه و برنامه می‌تونه به‌درستی به صفحه ورود برگرده.
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

let isRefreshing = false;
let pendingQueue = [];

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
    // فقط خودِ اندپوینت‌های ورود (که ۴۰۱ یعنی رمز/کد ملی اشتباه است، نه توکن
    // منقضی) و رفرش (برای جلوگیری از حلقه بی‌نهایت اگر رفرش‌توکن هم نامعتبر
    // باشد) از تلاش مجدد با Refresh معاف‌اند. قبلاً هر مسیری که شامل "/auth/"
    // بود معاف می‌شد — که یعنی GET /auth/me (که هر بار باز شدن اپ صدا زده
    // می‌شود) هرگز فرصت Refresh نمی‌گرفت و کاربر با هر انقضای معمولی
    // access_token (یا هر Reload خودکار بعد از Deploy) کامل Logout می‌شد.
    if (
      !refreshToken ||
      originalRequest.url?.includes("/auth/login") ||
      originalRequest.url?.includes("/auth/refresh")
    ) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      }).then((token) => {
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return apiClient(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

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
      // فقط اگر سرور واقعاً رفرش‌توکن را رد کرد (۴۰۱، یعنی واقعاً منقضی/باطل
      // شده) پاک کن و به صفحه ورود بفرست — نه برای خطای شبکه (آفلاین بودن)،
      // چون در آن حالت رفرش‌توکن هنوز کاملاً معتبر است، فقط همین لحظه
      // قابل‌تأیید نیست. AuthContext همین که اینترنت برگردد، دوباره تلاش
      // می‌کند؛ پاک‌کردن توکن اینجا آن تلاش بعدی را هم خراب می‌کرد.
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
