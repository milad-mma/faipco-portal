/**
 * جلوی «صفحه‌ی سفید» را می‌گیرد: اگر رندر صفحه‌ای خطا بدهد، به‌جای صفحه‌ی خالی پیام و دکمه‌ی «بارگذاری دوباره» نمایش
 * داده می‌شود و خطا (با Stack و صفحه) در «گزارش خطاها» ثبت می‌شود. خطای «بارگذاری فایل نسخه‌ی جدید» (بعد از آپدیت)
 * پیام مخصوص دارد چون با یک بار بارگذاری دوباره درست می‌شود.
 */
import { Component } from "react";
import { Box, Button, Typography } from "@mui/material";
import { reportClientError } from "../utils/errorReporter";

const CHUNK_RELOAD_KEY = "faipco_chunk_reload";
const CHUNK_ERROR = /Loading chunk|ChunkLoadError|Failed to fetch dynamically imported module|Importing a module script failed/i;

export default class AppErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // بعد از هر آپدیت، تب‌های باز قدیمی فایل‌های جدید را پیدا نمی‌کنند: خطای برنامه نیست (گزارش و ایمیل نمی‌شود) و
    // یک‌بار خودکار رفرش می‌شود تا کاربر کاری نکند. اگر بعد از رفرش هم تکرار شد، همان دکمه‌ی «بارگذاری» نمایش داده می‌شود.
    if (CHUNK_ERROR.test(error?.message || "")) {
      try {
        // حداکثر یک‌بار در هر دقیقه (حلقه‌ی رفرش نسازد؛ آپدیت بعدی در همین تب هم دوباره خودکار رفرش می‌شود)
        const last = Number(sessionStorage.getItem(CHUNK_RELOAD_KEY) || 0);
        if (Date.now() - last > 60_000) {
          sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()));
          window.location.reload();
        }
      } catch {
        /* sessionStorage در دسترس نیست */
      }
      return;
    }
    reportClientError({
      type: "crash",
      message: error?.message || String(error),
      stack: `${error?.stack || ""}\n\nComponent stack:${info?.componentStack || ""}`,
    });
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const isChunk = CHUNK_ERROR.test(error?.message || "");
    return (
      <Box sx={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center", p: 3 }}>
        <Box sx={{ maxWidth: 420, textAlign: "center" }}>
          <Typography variant="h6" fontWeight={800} sx={{ mb: 1 }}>
            {isChunk ? "نسخه‌ی جدید پرتال آماده است" : "این صفحه با خطا مواجه شد"}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {isChunk
              ? "پرتال به‌روز شده است؛ برای ادامه صفحه را دوباره بارگذاری کنید."
              : "خطا برای پشتیبانی ثبت شد. صفحه را دوباره بارگذاری کنید؛ اگر تکرار شد به مدیر سامانه اطلاع دهید."}
          </Typography>
          <Button variant="contained" onClick={() => window.location.reload()}>
            بارگذاری دوباره
          </Button>
        </Box>
      </Box>
    );
  }
}
