import { apiClient } from "./client";

export async function downloadBackupArchive() {
  const { data } = await apiClient.get("/backup/export", { responseType: "blob" });
  return data; // Blob از نوع application/zip
}
