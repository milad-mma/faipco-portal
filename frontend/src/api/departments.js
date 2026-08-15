import { apiClient } from "./client";

export async function fetchDepartments(siteId) {
  const { data } = await apiClient.get("/departments", {
    params: siteId ? { site_id: siteId } : {},
  });
  return data;
}

export async function createDepartment(payload) {
  const { data } = await apiClient.post("/departments", payload);
  return data;
}

export async function assignDepartmentSupervisor(departmentId, employeeId) {
  const { data } = await apiClient.put(`/departments/${departmentId}/supervisor`, {
    employee_id: employeeId,
  });
  return data;
}
