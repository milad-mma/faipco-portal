import { apiClient } from "./client";

export async function fetchEmployees({ siteId, search } = {}) {
  const params = {};
  if (siteId) params.site_id = siteId;
  if (search) params.search = search;
  const { data } = await apiClient.get("/employees", { params });
  return data;
}

export async function fetchEmployeeCount(siteId) {
  const { data } = await apiClient.get("/employees/count", {
    params: siteId ? { site_id: siteId } : {},
  });
  return data.count;
}

export async function fetchEmployeeRoles(employeeId) {
  const { data } = await apiClient.get(`/employees/${employeeId}/roles`);
  return data;
}

export async function assignRoleToEmployee(employeeId, roleId, siteId) {
  const { data } = await apiClient.post(`/employees/${employeeId}/roles`, {
    role_id: roleId,
    site_id: siteId || null,
  });
  return data;
}

export async function fetchSupervisedDepartments(employeeId) {
  const { data } = await apiClient.get(`/employees/${employeeId}/supervised-departments`);
  return data; // آرایه‌ای از شناسه واحدهایی که این پرسنل سرپرست آن‌هاست
}
