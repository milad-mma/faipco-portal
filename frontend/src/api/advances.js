import { apiClient } from "./client";

/** ماژول «درخواست مساعده» — پرسنل، کارتابل تأیید (گروهی) و مدیریت (docs/advances.md). */

// ---------- پرسنل ----------
export async function fetchMyAdvances() {
  const { data } = await apiClient.get("/advances/me");
  return data;
}

// amount فقط در حالت «مبلغ دلخواه در محدوده» (ریال)
export async function submitAdvance(reason, amount = null) {
  const { data } = await apiClient.post("/advances", {
    reason: reason || null,
    amount: amount || null,
  });
  return data;
}

export async function cancelAdvance(id) {
  const { data } = await apiClient.post(`/advances/${id}/cancel`);
  return data;
}

export async function fetchAdvanceInbox() {
  const { data } = await apiClient.get("/advances/inbox");
  return data;
}

export async function fetchAdvanceInboxCount() {
  const { data } = await apiClient.get("/advances/inbox/count");
  return data;
}

/** تأیید/رد گروهی مدیر واحد / مدیر سایت → {done:[id], failed:[{id,error}]} */
export async function decideAdvances(requestIds, approve, note) {
  const { data } = await apiClient.post("/advances/inbox/decide", {
    request_ids: requestIds,
    approve,
    note: note || null,
  });
  return data;
}

// ---------- مدیریت ----------
export async function fetchAdvanceAdminSites() {
  const { data } = await apiClient.get("/advances/admin/sites");
  return data;
}

export async function updateAdvanceSite(siteId, payload) {
  const { data } = await apiClient.put(`/advances/admin/sites/${siteId}`, payload);
  return data;
}

// انتقال درخواست‌های در حال تأیید مساعده به تأییدکننده‌های امروز؛ خروجی { changed, unresolved }
export async function reassignAdvanceApprovers(siteId) {
  const { data } = await apiClient.post(`/advances/admin/sites/${siteId}/reassign-approvers`);
  return data;
}

export async function searchAdvanceSiteEmployees(siteId, q) {
  const { data } = await apiClient.get(
    `/advances/admin/sites/${siteId}/employees`,
    { params: { q: q || undefined } },
  );
  return data;
}

export async function fetchAdvanceRequests(
  siteId,
  { status, month, q, page = 1, pageSize = 20 } = {},
) {
  const { data } = await apiClient.get(
    `/advances/admin/sites/${siteId}/requests`,
    {
      params: {
        status: status || undefined,
        month: month || undefined,
        q: q || undefined,
        page,
        page_size: pageSize,
      },
    },
  );
  return data;
}

/** خروجی Excel درخواست‌ها (همان فیلترهای فهرست) همراه با اطلاعات بانکی پرسنل */
export async function exportAdvanceRequests(siteId, { status, month, q } = {}) {
  const { data } = await apiClient.get(`/advances/admin/sites/${siteId}/export`, {
    params: { status: status || undefined, month: month || undefined, q: q || undefined },
    responseType: "blob",
  });
  return data;
}

/** تأیید/رد گروهی واحد مالی */
export async function financeDecideAdvances(siteId, requestIds, approve, note) {
  const { data } = await apiClient.post(
    `/advances/admin/sites/${siteId}/decide`,
    {
      request_ids: requestIds,
      approve,
      note: note || null,
    },
  );
  return data;
}

/** ثبت پرداخت گروهی (paidDate شمسی YYYY/MM/DD؛ خالی = امروز) */
export async function payAdvances(siteId, requestIds, paidDate, note) {
  const { data } = await apiClient.post(`/advances/admin/sites/${siteId}/pay`, {
    request_ids: requestIds,
    paid_date: paidDate || null,
    note: note || null,
  });
  return data;
}

export async function fetchAdvanceNotificationTemplates(siteId) {
  const { data } = await apiClient.get(
    `/advances/admin/sites/${siteId}/notification-templates`,
  );
  return data;
}

export async function saveAdvanceNotificationTemplates(siteId, texts) {
  const { data } = await apiClient.put(
    `/advances/admin/sites/${siteId}/notification-templates`,
    { texts },
  );
  return data;
}
