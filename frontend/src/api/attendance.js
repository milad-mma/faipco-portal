import { apiClient } from "./client";

export async function logGpsPresence({ latitude, longitude, accuracyMeters, siteId }) {
  const { data } = await apiClient.post("/attendance/presence", {
    latitude,
    longitude,
    accuracy_meters: accuracyMeters,
    site_id: siteId || null,
  });
  return data; // { is_within_geofence, matched_site_name, distance_meters }
}

export async function clockIn({ latitude, longitude, accuracyMeters, siteId }) {
  const { data } = await apiClient.post("/attendance/clock-in", {
    latitude,
    longitude,
    accuracy_meters: accuracyMeters,
    site_id: siteId || null,
  });
  return data;
}

export async function clockOut({ latitude, longitude, accuracyMeters, siteId }) {
  const { data } = await apiClient.post("/attendance/clock-out", {
    latitude,
    longitude,
    accuracy_meters: accuracyMeters,
    site_id: siteId || null,
  });
  return data;
}

export async function fetchMyAttendanceLogs({ year, month } = {}) {
  const { data } = await apiClient.get("/attendance/my-logs", {
    params: { year: year || undefined, month: month || undefined },
  });
  return data; // { items, year, month }
}

export async function fetchAllAttendanceLogs({ page = 1, pageSize = 50, employeeId, logType, year, month } = {}) {
  const { data } = await apiClient.get("/attendance/logs", {
    params: {
      page,
      page_size: pageSize,
      employee_id: employeeId || undefined,
      log_type: logType || undefined,
      year: year || undefined,
      month: month || undefined,
    },
  });
  return data; // { items, total, year, month }
}

export async function fetchPresenceSessions({ page = 1, pageSize = 50, employeeId, onlyOnline } = {}) {
  const { data } = await apiClient.get("/attendance/presence-sessions", {
    params: {
      page,
      page_size: pageSize,
      employee_id: employeeId || undefined,
      only_online: onlyOnline || undefined,
    },
  });
  return data; // { items, total }
}

export async function createManualAttendanceLog({ employeeId, logType, createdAt, siteId }) {
  const { data } = await apiClient.post("/attendance/logs", {
    employee_id: employeeId,
    log_type: logType,
    created_at: createdAt,
    site_id: siteId || null,
  });
  return data;
}

export async function updateAttendanceLog(logId, { logType, createdAt, siteId } = {}) {
  const { data } = await apiClient.put(`/attendance/logs/${logId}`, {
    log_type: logType || undefined,
    created_at: createdAt || undefined,
    site_id: siteId ?? undefined,
  });
  return data;
}

export async function deleteAttendanceLog(logId) {
  await apiClient.delete(`/attendance/logs/${logId}`);
}
