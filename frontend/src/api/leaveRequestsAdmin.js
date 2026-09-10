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

export async function fetchAllLeaveRequestsForSite(siteId) {
  const { data } = await apiClient.get(`/leave-requests/sites/${siteId}/all`);
  return data;
}

export async function adminUpdateLeaveRequest(siteId, requestId, payload) {
  const { data } = await apiClient.put(`/leave-requests/sites/${siteId}/requests/${requestId}`, payload);
  return data;
}
