import { apiClient } from "./client";

export async function fetchEmployees({ siteId } = {}) {
  const { data } = await apiClient.get("/employees", {
    params: siteId ? { site_id: siteId } : {},
  });
  return data;
}
