/**
 * Shared session state for FAIPCO.
 * During a PWA update the API can briefly be unavailable. This is not a
 * sign-out: preserve both credentials and the current protected route while
 * retrying /auth/me, and show a recoverable UI instead of navigating to /login.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { fetchCurrentUser, loginRequest } from "../api/auth";
import { apiClient } from "../api/client";
import { useOnlineStatus } from "./OnlineStatusContext";
import { setCacheOwner } from "../api/swrCache";
import { classifySessionRestoreError } from "../utils/authRestorePolicy";
import { connectReleaseNotifications } from "../utils/releaseSocket";

const AuthContext = createContext(null);
const RETRY_DELAYS_MS = [2500, 5000, 10000, 20000];

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [restoreError, setRestoreError] = useState(false);
  const [isRecovering, setIsRecovering] = useState(false);
  const [retrySequence, setRetrySequence] = useState(0);
  const { isOnline } = useOnlineStatus();
  const restorePromiseRef = useRef(null);
  const retryCountRef = useRef(0);
  // A logout or new login must invalidate an older, outstanding restore.
  const sessionEpochRef = useRef(0);
  const previouslyOnlineRef = useRef(isOnline);

  // A dedicated version socket is independent of presence/GPS and RBAC modules.
  // It exists only for authenticated sessions (including admins without employee_id).
  useEffect(() => {
    if (!user?.id) return undefined;
    return connectReleaseNotifications();
  }, [user?.id]);

  setCacheOwner(user?.id);

  const tryRestoreSession = useCallback(({ retry = false } = {}) => {
    if (restorePromiseRef.current) return restorePromiseRef.current;

    const token = localStorage.getItem("access_token");
    if (!token) {
      setUser(null);
      setRestoreError(false);
      setIsRecovering(false);
      setRetrySequence(0);
      setIsLoading(false);
      return Promise.resolve(null);
    }

    const epoch = sessionEpochRef.current;
    if (retry) {
      setIsRecovering(true);
    } else {
      setIsLoading(true);
      setRestoreError(false);
    }

    const currentPromise = (async () => {
      try {
        const currentUser = await fetchCurrentUser();
        if (epoch !== sessionEpochRef.current) return null;
        setUser(currentUser);
        setRestoreError(false);
        setRetrySequence(0);
        retryCountRef.current = 0;
        return currentUser;
      } catch (error) {
        if (epoch !== sessionEpochRef.current) return null;
        if (classifySessionRestoreError(error) === "invalid") {
          // Only a verified 401 warrants discarding the session. The axios
          // interceptor has already attempted a refresh for /auth/me.
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          setUser(null);
          setRestoreError(false);
        } else if (localStorage.getItem("access_token")) {
          // A network error, timeout, 502/503 or transient service worker
          // transition is NOT an invalid session. Keep the current URL.
          setRestoreError(true);
          retryCountRef.current += 1;
          setRetrySequence((count) => count + 1);
        } else {
          // An interceptor may have detected a verified invalid refresh token.
          setRestoreError(false);
        }
        return null;
      } finally {
        if (epoch === sessionEpochRef.current) {
          setIsLoading(false);
          setIsRecovering(false);
        }
      }
    })();

    restorePromiseRef.current = currentPromise;
    void currentPromise.finally(() => {
      if (restorePromiseRef.current === currentPromise) {
        restorePromiseRef.current = null;
      }
    });
    return currentPromise;
  }, []);

  // Initial restoration always runs once on page load (including SW reloads).
  useEffect(() => {
    void tryRestoreSession();
  }, [tryRestoreSession]);

  // When the update is faster than the backend, revalidate automatically with
  // bounded backoff. No redirect, token deletion or infinite spinner.
  useEffect(() => {
    if (!restoreError || !isOnline || !localStorage.getItem("access_token")) return undefined;
    const attempt = Math.min(retryCountRef.current - 1, RETRY_DELAYS_MS.length - 1);
    const retryTimer = setTimeout(() => { void tryRestoreSession({ retry: true }); }, RETRY_DELAYS_MS[Math.max(0, attempt)]);
    const retryOnReturn = () => {
      if (document.visibilityState === "visible") void tryRestoreSession({ retry: true });
    };
    window.addEventListener("focus", retryOnReturn);
    document.addEventListener("visibilitychange", retryOnReturn);
    return () => {
      clearTimeout(retryTimer);
      window.removeEventListener("focus", retryOnReturn);
      document.removeEventListener("visibilitychange", retryOnReturn);
    };
  }, [restoreError, retrySequence, isOnline, tryRestoreSession]);

  // Browser online status can turn true after a long disconnection, without
  // triggering the focus event (Android TWA). Resume restoration then too.
  useEffect(() => {
    if (isOnline && !previouslyOnlineRef.current && restoreError) {
      void tryRestoreSession({ retry: true });
    }
    previouslyOnlineRef.current = isOnline;
  }, [isOnline, restoreError, tryRestoreSession]);

  async function login(username, password, captcha = null) {
    const tokens = await loginRequest(username, password, captcha);
    sessionEpochRef.current += 1;
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
    setRestoreError(false);
    setIsRecovering(false);
    setRetrySequence(0);
    setIsLoading(false);
    retryCountRef.current = 0;
    return currentUser;
  }

  async function refetchUser() {
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
    setRestoreError(false);
    return currentUser;
  }

  function logout() {
    sessionEpochRef.current += 1;
    const token = localStorage.getItem("access_token");
    const refreshToken = localStorage.getItem("refresh_token");
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
    setRestoreError(false);
    setIsRecovering(false);
    setRetrySequence(0);
    setIsLoading(false);
    if (token || refreshToken) {
      apiClient.post(
        "/auth/logout",
        { refresh_token: refreshToken || null },
        { headers: { Authorization: `Bearer ${token}` }, timeout: 5000 },
      ).catch(() => {});
    }
  }

  return (
    <AuthContext.Provider value={{
      user, isLoading, restoreError, isRecovering, tryRestoreSession,
      login, logout, refetchUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth باید درون AuthProvider استفاده شود");
  return ctx;
}
