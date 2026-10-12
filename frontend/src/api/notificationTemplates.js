// متن اعلان‌ها/اطلاعیه‌های خودکار ماژول‌های سراسری (اطلاعیه‌ها، ارزیابی، تبریک تولد، انتقادات، امنیت ورود، خانوادگی)
import { apiClient } from "./client";

export async function fetchNotificationTemplates(module) {
  const { data } = await apiClient.get(`/notification-templates/${module}`);
  return data;
}

export async function saveNotificationTemplates(module, texts) {
  const { data } = await apiClient.put(`/notification-templates/${module}`, { texts });
  return data;
}
