import { apiClient } from "./client";

export async function fetchUsers() {
  const { data } = await apiClient.get("/users");
  return data;
}

export async function fetchRoles() {
  const { data } = await apiClient.get("/users/roles");
  return data;
}

export async function fetchUserRoles(userId) {
  const { data } = await apiClient.get(`/users/${userId}/roles`);
  return data;
}

export async function assignRole(userId, roleId, siteId) {
  const { data } = await apiClient.post(`/users/${userId}/roles`, {
    role_id: roleId,
    site_id: siteId || null,
  });
  return data;
}

export async function removeRoleAssignment(userRoleId) {
  await apiClient.delete(`/users/roles/${userRoleId}`);
}

export async function fetchAccessOverview() {
  const { data } = await apiClient.get("/users/access-overview");
  return data;
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
