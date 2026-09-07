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

export async function addManager(siteId, employeeId, title) {
  const { data } = await apiClient.post(`/performance/sites/${siteId}/managers`, {
    employee_id: employeeId,
    title: title || null,
  });
  return data;
}

export async function updateManagerTitle(managerId, title) {
  const { data } = await apiClient.put(`/performance/managers/${managerId}/title`, { title: title || null });
  return data;
}

export async function removeManager(managerId) {
  await apiClient.delete(`/performance/managers/${managerId}`);
}

export async function addManagerTarget(managerId, targetEmployeeId) {
  const { data } = await apiClient.post(`/performance/managers/${managerId}/targets`, {
    target_employee_id: targetEmployeeId,
  });
  return data;
}

export async function removeManagerTarget(managerId, targetEmployeeId) {
  const { data } = await apiClient.delete(`/performance/managers/${managerId}/targets/${targetEmployeeId}`);
  return data;
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
