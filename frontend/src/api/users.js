import { apiClient } from "./client";

export async function fetchRoles() {
  const { data } = await apiClient.get("/users/roles");
  return data;
}

export async function removeRoleAssignment(userRoleId) {
  await apiClient.delete(`/users/roles/${userRoleId}`);
}

export async function fetchAccessOverview() {
  const { data } = await apiClient.get("/users/access-overview");
  return data;
}

export async function fetchPermissions() {
  const { data } = await apiClient.get("/users/permissions");
  return data;
}

export async function fetchRoleDetail(roleId) {
  const { data } = await apiClient.get(`/users/role-catalog/${roleId}`);
  return data;
}

export async function createRole(payload) {
  const { data } = await apiClient.post("/users/role-catalog", payload);
  return data;
}

export async function updateRole(roleId, payload) {
  const { data } = await apiClient.patch(`/users/role-catalog/${roleId}`, payload);
  return data;
}

export async function deleteRole(roleId) {
  await apiClient.delete(`/users/role-catalog/${roleId}`);
}

export async function bulkAssignRole({ roleId, employeeIds, siteId, departmentId }) {
  const { data } = await apiClient.post("/users/bulk-assign-role", {
    role_id: roleId,
    employee_ids: employeeIds || undefined,
    site_id: siteId || undefined,
    department_id: departmentId || undefined,
  });
  return data; // { assigned_count, already_had_count, not_found_count, total_matched }
}
