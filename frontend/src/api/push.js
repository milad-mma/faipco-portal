/**
 * توابع فراخوانی API اعلان‌های Push (Web Push).
 */
import { apiClient } from "./client";

// GET /push/vapid-public-key؛ خروجی: کلید عمومی VAPID برای ساخت اشتراک Push
export async function fetchVapidPublicKey() {
  const { data } = await apiClient.get("/push/vapid-public-key");
  return data.public_key;
}

// POST /push/subscribe؛ ثبت اشتراک Push مرورگر برای کاربر جاری
export async function subscribePush(subscription) {
  await apiClient.post("/push/subscribe", subscription);
}

// POST /push/unsubscribe؛ حذف اشتراک Push با endpoint آن
export async function unsubscribePush(endpoint) {
  await apiClient.post("/push/unsubscribe", { endpoint });
}
