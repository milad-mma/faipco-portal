/**
 * Separate a temporary /auth/me failure from a verified sign-out.
 * A temporary backend restart, timeout or offline transition must never
 * redirect a signed-in user to /login simply because user data is unavailable.
 */
export function classifySessionRestoreError(error) {
  return error?.response?.status === 401 ? "invalid" : "retryable";
}

export function getProtectedRouteState({ isLoading, user, restoreError, hasToken }) {
  if (isLoading) return "loading";
  if (user) return "ready";
  if (restoreError && hasToken) return "reconnect";
  return "login";
}
