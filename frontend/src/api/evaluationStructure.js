/**
 * توابع API ساختار ارزیابی سایت: سرپرست واحدها، مدیران و ارزیابی‌شوندگان هر مدیر،
 * سرشیفت‌ها و تخصیص پرسنل به سرشیفت.
 */
import { apiClient } from "./client";

// GET /performance/sites/{id}/structure؛ ساختار ارزیابی سایت (واحدها، سرپرستان، مدیران، سرشیفت‌ها) را برمی‌گرداند
export async function fetchEvaluationSiteStructure(siteId) {
  const { data } = await apiClient.get(`/performance/sites/${siteId}/structure`);
  return data;
}

// PUT /performance/departments/{id}/supervisor؛ سرپرست واحد را تعیین می‌کند و نتیجه را برمی‌گرداند
export async function setDepartmentSupervisor(departmentId, employeeId) {
  const { data } = await apiClient.put(`/performance/departments/${departmentId}/supervisor`, {
    employee_id: employeeId,
  });
  return data;
}

// DELETE /performance/departments/{id}/supervisor؛ سرپرست واحد را برمی‌دارد
export async function removeDepartmentSupervisor(departmentId) {
  await apiClient.delete(`/performance/departments/${departmentId}/supervisor`);
}

// GET /performance/sites/{id}/manager-candidates؛ فهرست پرسنل قابل انتخاب به‌عنوان مدیر را برمی‌گرداند
export async function fetchManagerCandidates(siteId) {
  const { data } = await apiClient.get(`/performance/sites/${siteId}/manager-candidates`);
  return data;
}

// POST /performance/sites/{id}/managers؛ مدیر جدید (با عنوان اختیاری) اضافه می‌کند و رکورد مدیر را برمی‌گرداند
export async function addManager(siteId, employeeId, title) {
  const { data } = await apiClient.post(`/performance/sites/${siteId}/managers`, {
    employee_id: employeeId,
    title: title || null,
  });
  return data;
}

// PUT /performance/managers/{id}/title؛ عنوان مدیر را تغییر می‌دهد
export async function updateManagerTitle(managerId, title) {
  const { data } = await apiClient.put(`/performance/managers/${managerId}/title`, { title: title || null });
  return data;
}

// DELETE /performance/managers/{id}؛ مدیر را حذف می‌کند
export async function removeManager(managerId) {
  await apiClient.delete(`/performance/managers/${managerId}`);
}

// POST /performance/managers/{id}/targets؛ یک پرسنل را به ارزیابی‌شوندگان مدیر اضافه می‌کند
export async function addManagerTarget(managerId, targetEmployeeId) {
  const { data } = await apiClient.post(`/performance/managers/${managerId}/targets`, {
    target_employee_id: targetEmployeeId,
  });
  return data;
}

// DELETE /performance/managers/{id}/targets/{employeeId}؛ پرسنل را از ارزیابی‌شوندگان مدیر حذف می‌کند
export async function removeManagerTarget(managerId, targetEmployeeId) {
  const { data } = await apiClient.delete(`/performance/managers/${managerId}/targets/${targetEmployeeId}`);
  return data;
}

// POST /performance/departments/{id}/shift-leads؛ سرشیفت جدید برای واحد اضافه می‌کند
export async function addShiftLead(departmentId, employeeId) {
  const { data } = await apiClient.post(`/performance/departments/${departmentId}/shift-leads`, {
    employee_id: employeeId,
  });
  return data;
}

// DELETE /performance/shift-leads/{id}؛ سرشیفت را حذف می‌کند
export async function removeShiftLead(shiftLeadId) {
  await apiClient.delete(`/performance/shift-leads/${shiftLeadId}`);
}

// PUT /performance/shift-assignments؛ پرسنل را به یک سرشیفت تخصیص می‌دهد
export async function setShiftAssignment(employeeId, shiftLeadId) {
  const { data } = await apiClient.put("/performance/shift-assignments", {
    employee_id: employeeId,
    shift_lead_id: shiftLeadId,
  });
  return data;
}

// DELETE /performance/shift-assignments/{employeeId}؛ تخصیص سرشیفت پرسنل را حذف می‌کند
export async function removeShiftAssignment(employeeId) {
  await apiClient.delete(`/performance/shift-assignments/${employeeId}`);
}
