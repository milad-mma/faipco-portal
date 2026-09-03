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

export async function forgotPasswordRequest(identifier) {
  const { data } = await apiClient.post("/auth/forgot-password", { identifier });
  return data;
}

export async function resetPasswordRequest(token, newPassword) {
  const { data } = await apiClient.post("/auth/reset-password", { token, new_password: newPassword });
  return data;
}

export async function updateMyContactInfo({ email, mobile }) {
  const payload = {};
  if (email !== undefined) payload.email = email;
  if (mobile !== undefined) payload.mobile = mobile;
  const { data } = await apiClient.put("/auth/me/contact-info", payload);
  return data;
}
