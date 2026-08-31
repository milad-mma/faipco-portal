import { apiClient } from "./client";

export async function submitFeedback({ title, message, isAnonymous }) {
  const { data } = await apiClient.post("/feedback", { title, message, is_anonymous: isAnonymous });
  return data;
}

export async function fetchFeedback({ senderId, siteId, dateFrom, dateTo } = {}) {
  const params = {};
  if (senderId) params.sender_id = senderId;
  if (siteId) params.site_id = siteId;
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;
  const { data } = await apiClient.get("/feedback", { params });
  return data;
}

export async function deleteFeedback(id) {
  await apiClient.delete(`/feedback/${id}`);
}

export async function fetchProhibitedPhrases() {
  const { data } = await apiClient.get("/feedback/prohibited-phrases");
  return data;
}

export async function addProhibitedPhrase(phrase) {
  const { data } = await apiClient.post("/feedback/prohibited-phrases", { phrase });
  return data;
}

export async function deleteProhibitedPhrase(id) {
  await apiClient.delete(`/feedback/prohibited-phrases/${id}`);
}
