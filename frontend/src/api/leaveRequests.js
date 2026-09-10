import { apiClient } from "./client";

export async function fetchActiveLeaveRequestTypes() {
  const { data } = await apiClient.get("/leave-requests/types");
  return data;
}

export async function submitLeaveRequest(payload) {
  const { data } = await apiClient.post("/leave-requests/submit", payload);
  return data;
}

export async function fetchMyLeaveRequests() {
  const { data } = await apiClient.get("/leave-requests/my-requests");
  return data;
}

export async function fetchPendingLeaveRequestsForMe() {
  const { data } = await apiClient.get("/leave-requests/pending-for-me");
  return data;
}

export async function decideLeaveRequest(requestId, approved, managerIdea) {
  const { data } = await apiClient.post(`/leave-requests/${requestId}/decide`, {
    approved,
    manager_idea: managerIdea || "",
  });
  return data;
}
