/**
 * گزارش خطاهای مرورگر به سرور («گزارش خطاها»؛ docs/error-logs.md):
 * - خطای JavaScript و Promise ردشده (window error / unhandledrejection)
 * - از کار افتادن صفحه (ErrorBoundary ← type="crash")
 * - درخواستی که به سرور نرسید یا در زمان مجاز جواب نگرفت (apiClient ← type="network")
 * با fetch مستقیم (نه apiClient) تا خطای خودِ گزارش، گزارش تازه نسازد. خطای یکسان در هر دقیقه یک‌بار و در هر بار
 * باز شدن صفحه حداکثر ۳۰ گزارش. خطاهای افزونه‌های مرورگر و «ResizeObserver» نادیده گرفته می‌شوند.
 */
import { isAndroidApp } from "./androidApp";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
const MAX_PER_PAGE_LOAD = 30;
const DEDUPE_MS = 60_000;
const IGNORE = [/ResizeObserver loop/i, /chrome-extension:\/\//i, /moz-extension:\/\//i, /Script error\.?$/i];

let sent = 0;
const recent = new Map(); // متن خطا → زمان آخرین ارسال

export function reportClientError({ type = "error", message, stack, source, api, requestId }) {
  try {
    const text = String(message || "").slice(0, 2000);
    if (!text || IGNORE.some((re) => re.test(text) || re.test(String(stack || "")))) return;
    if (sent >= MAX_PER_PAGE_LOAD) return;
    // قطعی شبکه یک «حادثه» است نه چند خطا: وقتی اینترنت گوشی قطع می‌شود همه‌ی درخواست‌های هم‌زمان صفحه (داشبورد ۶ تا)
    // با هم شکست می‌خورند؛ فقط اولی گزارش می‌شود و تا یک دقیقه قطعی‌های بعدی (هر API) نادیده گرفته می‌شوند
    const key = type === "network" ? "network" : `${type}|${text}|${api || ""}`;
    const now = Date.now();
    if (now - (recent.get(key) || 0) < DEDUPE_MS) return;
    recent.set(key, now);
    sent += 1;
    const token = localStorage.getItem("access_token");
    fetch(`${API_BASE_URL}/error-logs/client`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      keepalive: true,
      body: JSON.stringify({
        type,
        message: text,
        stack: stack ? String(stack).slice(0, 12000) : null,
        page: (window.location.pathname + window.location.search).slice(0, 500),
        source: source ? String(source).slice(0, 200) : null,
        api: api ? String(api).slice(0, 300) : null,
        request_id: requestId ? String(requestId).slice(0, 16) : null,
        in_android_app: isAndroidApp(),
      }),
    }).catch(() => {});
  } catch {
    /* گزارش خطا هرگز نباید خودش خطا بدهد */
  }
}

// یک‌بار در شروع برنامه (main.jsx)
export function installGlobalErrorReporting() {
  window.addEventListener("error", (event) => {
    reportClientError({
      message: event.message || event.error?.message,
      stack: event.error?.stack || `${event.filename || ""}:${event.lineno || ""}:${event.colno || ""}`,
      source: event.filename,
    });
  });
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    // خطاهای HTTP خودِ apiClient (که صفحه آن‌ها را مدیریت می‌کند) گزارش نمی‌شوند؛ فقط خطاهای واقعی برنامه
    if (reason?.isAxiosError) return;
    reportClientError({ message: reason?.message || String(reason), stack: reason?.stack });
  });
}
