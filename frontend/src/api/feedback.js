import { apiClient } from "./client";

export async function submitFeedback({ message, isAnonymous }) {
  const { data } = await apiClient.post("/feedback", { message, is_anonymous: isAnonymous });
  return data;
}

export async function fetchFeedback() {
  const { data } = await apiClient.get("/feedback");
  return data;
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
