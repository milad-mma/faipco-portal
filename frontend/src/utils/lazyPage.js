// بارگذاری تنبل یک صفحه با React.lazy و محافظت در برابر chunk قدیمی.
// بعد از استقرار نسخه‌ی جدید، تبی که از قبل باز بوده ممکن است نام فایل chunk قدیمی را بخواهد
// که دیگر روی سرور نیست (ChunkLoadError). در این حالت صفحه یک‌بار بازخوانی می‌شود تا نسخه‌ی جدید
// بارگذاری شود؛ پرچم sessionStorage جلوی حلقه‌ی بی‌پایان بازخوانی را می‌گیرد.
import { lazy } from "react";

const RELOAD_FLAG = "faipco_chunk_reload";

export default function lazyPage(factory) {
  return lazy(() =>
    factory()
      .then((mod) => {
        try {
          sessionStorage.removeItem(RELOAD_FLAG);
        } catch {
          /* sessionStorage در دسترس نیست */
        }
        return mod;
      })
      .catch((err) => {
        let alreadyReloaded = false;
        try {
          alreadyReloaded = sessionStorage.getItem(RELOAD_FLAG) === "1";
          if (!alreadyReloaded) sessionStorage.setItem(RELOAD_FLAG, "1");
        } catch {
          alreadyReloaded = true; // بدون sessionStorage ریسک حلقه نمی‌کنیم
        }
        if (!alreadyReloaded && navigator.onLine !== false) {
          window.location.reload();
          return new Promise(() => {}); // تا بازخوانی، چیزی رندر نشود
        }
        throw err;
      })
  );
}
