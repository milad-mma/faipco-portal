import { apiClient } from "./client";

export async function loginRequest(username, password) {
  const { data } = await apiClient.post("/auth/login", { username, password });
  return data; // { access_token, refresh_token, token_type }
}

export async function fetchCurrentUser() {
  const { data } = await apiClient.get("/auth/me");
  return data;
}

export async function changePasswordRequest(currentPassword, newPassword) {
  await apiClient.put("/auth/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}
