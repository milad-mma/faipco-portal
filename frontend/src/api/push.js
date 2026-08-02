import { apiClient } from "./client";

export async function fetchVapidPublicKey() {
  const { data } = await apiClient.get("/push/vapid-public-key");
  return data.public_key;
}

export async function subscribePush(subscription) {
  await apiClient.post("/push/subscribe", subscription);
}

export async function unsubscribePush(endpoint) {
  await apiClient.post("/push/unsubscribe", { endpoint });
}
