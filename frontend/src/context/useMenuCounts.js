import { useEffect, useState } from "react";
import { apiClient } from "../api/client";

const modules = /^\/(careers|family|loans|advances|feedback)(\/|$)/;

export function useMenuCounts(user, online) {
  const [result, setResult] = useState(null);
  const owner = user?.id;
  const eligible = Boolean(user?.can_manage_careers || user?.can_manage_family || user?.can_reply_feedback
    || user?.can_admin_loans || user?.can_admin_advances);

  useEffect(() => {
    if (!owner || !eligible || !online) return;
    let active = true;
    let busy = false;
    let dirty = false;
    async function refresh() {
      if (!active || document.hidden) return;
      if (busy) {
        dirty = true;
        return;
      }
      busy = true;
      try {
        const { data } = await apiClient.get("/auth/me/menu-counts");
        if (active) setResult({ owner, counts: data });
      } catch {
        // Keep the last successful count during a temporary connection failure.
      } finally {
        busy = false;
        if (dirty && active) {
          dirty = false;
          void refresh();
        }
      }
    }
    const interceptor = apiClient.interceptors.response.use((response) => {
      if (modules.test(response.config.url) && /^(post|put|patch|delete)$/i.test(response.config.method)) {
        void refresh();
      }
      return response;
    });
    void refresh();
    const timer = setInterval(refresh, 60000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      active = false;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
      apiClient.interceptors.response.eject(interceptor);
    };
  }, [owner, eligible, online]);

  return eligible && result?.owner === owner ? result.counts : {};
}
