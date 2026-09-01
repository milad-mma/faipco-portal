import { apiClient } from "./client";

export async function submitFeedback({ category, title, message, isAnonymous }) {
  const { data } = await apiClient.post("/feedback", {
    category,
    title,
    message,
    is_anonymous: isAnonymous,
  });
  return data;
}

export async function fetchFeedback({ senderId, siteId, category, isAnonymous, dateFrom, dateTo } = {}) {
  const params = {};
  if (senderId) params.sender_id = senderId;
  if (siteId) params.site_id = siteId;
  if (category) params.category = category;
  if (isAnonymous !== undefined && isAnonymous !== "") params.is_anonymous = isAnonymous;
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
