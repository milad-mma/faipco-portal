import { apiClient } from "./client";

export async function fetchEvaluationSiteStructure(siteId) {
  const { data } = await apiClient.get(`/performance/sites/${siteId}/structure`);
  return data;
}

export async function setDepartmentSupervisor(departmentId, employeeId) {
  const { data } = await apiClient.put(`/performance/departments/${departmentId}/supervisor`, {
    employee_id: employeeId,
  });
  return data;
}

export async function removeDepartmentSupervisor(departmentId) {
  await apiClient.delete(`/performance/departments/${departmentId}/supervisor`);
}

export async function addSiteManager(siteId, employeeId) {
  const { data } = await apiClient.post(`/performance/sites/${siteId}/managers`, { employee_id: employeeId });
  return data;
}

export async function removeSiteManager(managerId) {
  await apiClient.delete(`/performance/managers/${managerId}`);
}

export async function addOtherManager(siteId, employeeId) {
  const { data } = await apiClient.post(`/performance/sites/${siteId}/other-managers`, {
    employee_id: employeeId,
  });
  return data;
}

export async function removeOtherManager(managerId) {
  await apiClient.delete(`/performance/other-managers/${managerId}`);
}

export async function addShiftLead(departmentId, employeeId) {
  const { data } = await apiClient.post(`/performance/departments/${departmentId}/shift-leads`, {
    employee_id: employeeId,
  });
  return data;
}

export async function removeShiftLead(shiftLeadId) {
  await apiClient.delete(`/performance/shift-leads/${shiftLeadId}`);
}

export async function setShiftAssignment(employeeId, shiftLeadId) {
  const { data } = await apiClient.put("/performance/shift-assignments", {
    employee_id: employeeId,
    shift_lead_id: shiftLeadId,
  });
  return data;
}

export async function removeShiftAssignment(employeeId) {
  await apiClient.delete(`/performance/shift-assignments/${employeeId}`);
}
