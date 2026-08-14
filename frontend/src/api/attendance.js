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

export async function fetchMyAttendanceLogs() {
  const { data } = await apiClient.get("/attendance/my-logs");
  return data;
}

export async function fetchAllAttendanceLogs({ page = 1, pageSize = 50, employeeId, logType } = {}) {
  const { data } = await apiClient.get("/attendance/logs", {
    params: {
      page,
      page_size: pageSize,
      employee_id: employeeId || undefined,
      log_type: logType || undefined,
    },
  });
  return data; // { items, total }
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
