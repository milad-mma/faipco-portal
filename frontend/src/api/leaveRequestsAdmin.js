import { apiClient } from "./client";

export async function fetchLeaveRequestMapping(siteId) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/mapping`);
  return data;
}

export async function saveLeaveRequestMapping(siteId, payload) {
  const { data } = await apiClient.put(`/leave-requests/sites/${siteId}/mapping`, payload);
  return data;
}

export async function deleteLeaveRequestMapping(siteId) {
  await apiClient.delete(`/leave-requests/sites/${siteId}/mapping`);
}

export async function fetchLeaveRequestTypes(siteId) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/types`);
  return data;
}

export async function addLeaveRequestType(siteId, payload) {
  const { data } = await apiClient.post(`/leave-requests/sites/${siteId}/types`, payload);
  return data;
}

export async function updateLeaveRequestType(typeId, payload) {
  const { data } = await apiClient.put(`/leave-requests/types/${typeId}`, payload);
  return data;
}

export async function deleteLeaveRequestType(typeId) {
  await apiClient.delete(`/leave-requests/types/${typeId}`);
}

export async function fetchLeaveRequestApprovers(siteId) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/approvers`);
  return data;
}

export async function setLeaveRequestApprover(departmentId, approverEmployeeId) {
  const { data } = await apiClient.put(`/leave-requests/departments/${departmentId}/approver`, {
    approver_employee_id: approverEmployeeId,
  });
  return data;
}

export async function removeLeaveRequestApprover(departmentId) {
  await apiClient.delete(`/leave-requests/departments/${departmentId}/approver`);
}

export async function fetchLeaveRequestModuleStatus(siteId) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/module-status`);
  return data; // { has_mapping, is_disabled }
}

export async function setLeaveRequestModuleDisabled(siteId, isDisabled) {
  const { data } = await apiClient.put(`/leave-requests/sites/${siteId}/module-status`, { is_disabled: isDisabled });
  return data;
}

export async function fetchLeaveRequestHrOfficer(siteId) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/hr-officer`);
  return data;
}

export async function setLeaveRequestHrOfficer(siteId, employeeId) {
  const { data } = await apiClient.put(`/leave-requests/sites/${siteId}/hr-officer`, { employee_id: employeeId });
  return data;
}

export async function removeLeaveRequestHrOfficer(siteId) {
  await apiClient.delete(`/leave-requests/sites/${siteId}/hr-officer`);
}

export async function fetchAllLeaveRequestsForSite(siteId, filters = {}) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/all`, { params: filters });
  return data;
}

export async function exportLeaveRequests(siteId, filters = {}) {
  const response = await apiClient.get(`/leave-requests/sites/${siteId}/export`, {
    params: filters,
    responseType: "blob",
  });
  return response.data;
}

export async function fetchActionLookup(siteId) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/action-lookup`);
  return data;
}

export async function fetchOperationLookup(siteId) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/operation-lookup`);
  return data;
}

export async function fetchCardLookup(siteId) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/card-lookup`);
  return data;
}

export async function adminUpdateLeaveRequest(siteId, requestId, payload) {
  const { data } = await apiClient.put(`/leave-requests/sites/${siteId}/requests/${requestId}`, payload);
  return data;
}

export async function adminDeleteLeaveRequest(siteId, requestId) {
  await apiClient.delete(`/leave-requests/sites/${siteId}/requests/${requestId}`);
}

export async function fetchKaraSchemaDefaults() {
  const { data } = await apiClient.get("/leave-requests/kara-schema-defaults");
  return data;
}
