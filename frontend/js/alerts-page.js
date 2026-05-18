const AlertsState = { alerts: [] };

function setAlertsLoading() {
  const container = document.getElementById("alerts-list");
  if (!container) return;
  container.innerHTML = '<div class="loading-spinner">Loading alerts…</div>';
}

function updateAlertBadgeCount() {
  const unread = AlertsState.alerts.filter(a => !a.is_read).length;
  document.querySelectorAll("#alert-badge").forEach(el => el.textContent = unread);
}

function renderAlerts() {
  const container = document.getElementById("alerts-list");
  if (!container) return;

  const severity = document.getElementById("filter-alert-severity")?.value;
  const readState = document.getElementById("filter-alert-read")?.value;

  const filtered = AlertsState.alerts.filter(alert => {
    if (severity && alert.severity !== severity) return false;
    if (readState === "unread" && alert.is_read) return false;
    if (readState === "read" && !alert.is_read) return false;
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div class="loading-spinner">No alerts found.</div>';
    return;
  }

  container.innerHTML = filtered.map(alert => {
    const statusClass = alert.is_read ? "unread" : "";
    return `
      <div class="alert-item ${alert.severity} ${statusClass}">
        <div class="alert-icon">${alert.severity === "critical" ? "🚨" : alert.severity === "high" ? "⚠️" : "ℹ️"}</div>
        <div class="alert-body">
          <div class="alert-msg">${alert.message}</div>
          <div class="alert-meta">${formatTimestamp(alert.created_at)} • ${alert.severity.toUpperCase()}</div>
        </div>
        <div class="alert-actions">
          ${alert.is_read ? "" : `<button class="btn-sm" onclick="markAlertRead(${alert.id})">Mark read</button>`}
        </div>
      </div>`;
  }).join("");
}

async function loadAlerts() {
  setAlertsLoading();
  try {
    const alerts = await AlertAPI.list();
    AlertsState.alerts = alerts;
    updateAlertBadgeCount();
    renderAlerts();
  } catch (err) {
    const container = document.getElementById("alerts-list");
    if (container) {
      container.innerHTML = `<div class="loading-spinner">Failed to load alerts: ${err.message}</div>`;
    }
    showToast?.(err.message, "error");
  }
}

async function markAlertRead(id) {
  try {
    await AlertAPI.markRead(id);
    const alert = AlertsState.alerts.find(a => a.id === id);
    if (alert) alert.is_read = true;
    updateAlertBadgeCount();
    renderAlerts();
  } catch (err) {
    showToast?.(err.message, "error");
  }
}

async function markAllRead() {
  try {
    await AlertAPI.markAllRead();
    AlertsState.alerts.forEach(a => a.is_read = true);
    updateAlertBadgeCount();
    renderAlerts();
    showToast?.("All alerts marked read", "success");
  } catch (err) {
    showToast?.(err.message, "error");
  }
}

window.loadAlerts = loadAlerts;
window.markAlertRead = markAlertRead;
window.markAllRead = markAllRead;

document.addEventListener("DOMContentLoaded", loadAlerts);
