/* api.js — Centralised API helper. All backend calls go through here. */

const API_BASE = "http://localhost:5000";

function getToken() {
  return localStorage.getItem("fd_token");
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    throw new Error(data.error || "Unauthorized");
  }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function parseFilenameFromResponse(response) {
  const disposition = response.headers.get("Content-Disposition");
  if (!disposition) return null;
  const match = /filename=([^;]+)/.exec(disposition);
  return match ? match[1].replace(/['\"]+/g, "") : null;
}

async function apiDownload(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) throw new Error(data.error || "Unauthorized");
    throw new Error(data.error || `HTTP ${res.status}`);
  }

  const blob = await res.blob();
  const filename = parseFilenameFromResponse(res) || "download.csv";
  return { blob, filename };
}

// ── Auth ──────────────────────────────────────────────────────────────────────
const AuthAPI = {
  login:          (u, p)   => apiFetch("/auth/login",  { method: "POST", body: JSON.stringify({ username: u, password: p }) }),
  register:       (data)   => apiFetch("/auth/register",{ method: "POST", body: JSON.stringify(data) }),
  me:             ()       => apiFetch("/auth/me"),
  changePassword: (o, n)   => apiFetch("/auth/change-password", { method: "PUT", body: JSON.stringify({ old_password: o, new_password: n }) }),
};

// ── Sensors ───────────────────────────────────────────────────────────────────
const SensorAPI = {
  list:   ()      => apiFetch("/api/sensors"),
  get:    (id)    => apiFetch(`/api/sensors/${id}`),
  create: (data)  => apiFetch("/api/sensors",      { method: "POST",   body: JSON.stringify(data) }),
  delete: (id)    => apiFetch(`/api/sensors/${id}`, { method: "DELETE" }),
  readings:(id, limit=100) => apiFetch(`/api/sensors/${id}/readings?limit=${limit}`),
  addReading: (id, value)  => apiFetch(`/api/sensors/${id}/readings`, { method: "POST", body: JSON.stringify({ value }) }),
};

// ── Faults ────────────────────────────────────────────────────────────────────
const FaultAPI = {
  list:    (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiFetch(`/api/faults${qs ? "?" + qs : ""}`);
  },
  resolve: (id) => apiFetch(`/api/faults/${id}/resolve`, { method: "PUT" }),
};

// ── Alerts ────────────────────────────────────────────────────────────────────
const AlertAPI = {
  list:       ()    => apiFetch("/api/alerts"),
  markRead:   (id)  => apiFetch(`/api/alerts/${id}/read`, { method: "PUT" }),
  markAllRead: ()   => apiFetch("/api/alerts/read-all",   { method: "PUT" }),
};

// ── Dashboard ─────────────────────────────────────────────────────────────────
const DashboardAPI = {
  summary: () => apiFetch("/api/dashboard/summary"),
};

// ── Reports ───────────────────────────────────────────────────────────────────
const ReportsAPI = {
  analytics:       (days = 7) => apiFetch(`/reports/analytics?days=${days}`),
  exportFaults:    (days = 30) => apiDownload(`/reports/export/csv?days=${days}`),
  exportReadings:  (sid)       => apiDownload(`/reports/export/readings/csv${sid ? "?sensor_id=" + sid : ""}`),
};

// ── ML ────────────────────────────────────────────────────────────────────────
const MLAPI = {
  train: (sensor_type, values) =>
    apiFetch(`/api/train/${sensor_type}`, { method: "POST", body: JSON.stringify({ values }) }),
};

// ── Demo ──────────────────────────────────────────────────────────────────────
const DemoAPI = {
  generate: () => apiFetch("/api/demo/generate", { method: "POST" }),
};