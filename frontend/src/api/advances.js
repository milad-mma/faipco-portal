import { apiClient } from "./client";

/** ماژول «درخواست مساعده» — پرسنل، کارتابل تأیید (گروهی) و مدیریت (docs/advances.md). */

// ---------- پرسنل ----------
export async function fetchMyAdvances() {
  const { data } = await apiClient.get("/advances/me");
  return data;
}

export async function submitAdvance(reason) {
  const { data } = await apiClient.post("/advances", {
    reason: reason || null,
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
  await apiClient.put(`/advances/admin/sites/${siteId}`, payload);
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
