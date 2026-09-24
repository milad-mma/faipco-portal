/**
 * توابع فراخوانی API واحدهای سازمانی (Departments).
 */
import { apiClient } from "./client";

// GET /departments (در صورت ارسال siteId فقط واحدهای آن سایت)؛ خروجی: فهرست واحدها
export async function fetchDepartments(siteId) {
  const { data } = await apiClient.get("/departments", {
    params: siteId ? { site_id: siteId } : {},
  });
  return data;
}

// PUT /departments/{id}/supervisor؛ تعیین سرپرست واحد؛ خروجی: واحد به‌روزشده
export async function assignDepartmentSupervisor(departmentId, employeeId) {
  const { data } = await apiClient.put(`/departments/${departmentId}/supervisor`, {
    employee_id: employeeId,
  });
  return data;
}
