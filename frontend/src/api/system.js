import { apiClient } from "./client";

export async function bustAppCache() {
  const { data } = await apiClient.post("/system/cache-bust");
  return data; // { success, version, message }
}
