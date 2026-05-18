/* main.js — Dashboard page logic */

// ── Clock ─────────────────────────────────────────────────────────────────────
function startClock() {
  const el = document.getElementById("clock");
  if (!el) return;
  const tick = () => { el.textContent = new Date().toLocaleTimeString(); };
  tick();
  setInterval(tick, 1000);
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = "info", duration = 3500) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => t.remove(), duration);
}
window.showToast = showToast;

// ── Live Feed ─────────────────────────────────────────────────────────────────
function addFeedEntry(msg, severity = "info") {
  const feed = document.getElementById("live-feed");
  if (!feed) return;
  const placeholder = feed.querySelector(".feed-placeholder");
  if (placeholder) placeholder.remove();

  const icons = { critical: "🚨", high: "⚠️", medium: "🟡", normal: "✅", info: "ℹ️" };
  const entry = document.createElement("div");
  entry.className = `feed-entry`;
  entry.textContent = `${icons[severity] || "•"} [${new Date().toLocaleTimeString()}] ${msg}`;
  feed.prepend(entry);
  if (feed.children.length > 60) feed.lastChild.remove();
}

function clearFeed() {
  const feed = document.getElementById("live-feed");
  if (feed) feed.innerHTML = '<div class="feed-placeholder">Feed cleared.</div>';
}

// ── Dashboard Summary ─────────────────────────────────────────────────────────
async function loadSummary() {
  try {
    const data = await DashboardAPI.summary();
    document.getElementById("kpi-sensors-val").textContent  = data.total_sensors;
    document.getElementById("kpi-faults-val").textContent   = data.open_faults;
    document.getElementById("kpi-critical-val").textContent = data.critical_faults;
    document.getElementById("kpi-alerts-val").textContent   = data.unread_alerts;

    const badge = document.getElementById("alert-badge");
    if (badge) badge.textContent = data.unread_alerts;

    renderFaultsTable(data.recent_faults);
    // If the system appears empty, auto-generate demo data once per session
    try {
      const already = sessionStorage.getItem('fd_demo_generated');
      if (!already && (data.total_sensors === 0 || data.open_faults === 0)) {
        sessionStorage.setItem('fd_demo_generated', '1');
        showToast('Initializing demo data…', 'info');
        // generateDemo will refresh summary/charts after insertion
        await generateDemo();
      }
    } catch (e) { /* ignore sessionStorage errors */ }
  } catch (err) {
    console.error("Summary error:", err);
  }
}

// ── Faults Table ──────────────────────────────────────────────────────────────
function severityChip(s) {
  return `<span class="severity-chip ${s}">${s}</span>`;
}
function statusChip(s) {
  return `<span class="status-chip ${s}">${s}</span>`;
}

function renderFaultsTable(faults) {
  const tbody = document.getElementById("faults-tbody");
  if (!tbody) return;

  if (!faults || faults.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No faults detected 🎉</td></tr>';
    return;
  }

  tbody.innerHTML = faults.map(f => `
    <tr>
      <td>#${f.id}</td>
      <td>Sensor ${f.sensor_id}</td>
      <td>${severityChip(f.severity)}</td>
      <td>${f.fault_type || "—"}</td>
      <td>${f.value ?? "—"}</td>
      <td>${new Date(f.detected_at).toLocaleString()}</td>
      <td>${statusChip(f.status)}</td>
      <td>
        ${f.status === "open"
          ? `<button class="btn-resolve" onclick="resolveFault(${f.id}, this)">Resolve</button>`
          : "—"}
      </td>
    </tr>`).join("");
}

async function resolveFault(id, btn) {
  try {
    btn.disabled = true;
    await FaultAPI.resolve(id);
    btn.closest("tr").classList.add("flash-row");
    btn.textContent = "Resolved ✓";
    showToast("Fault resolved", "success");
    setTimeout(loadSummary, 800);
  } catch (err) {
    showToast(err.message, "error");
    btn.disabled = false;
  }
}

// ── Charts ────────────────────────────────────────────────────────────────────
async function refreshCharts() {
  try {
    const data = await ReportsAPI.analytics(7);
    const trend = data.by_day;
    renderTrendChart("sidebar-trend-chart", Object.keys(trend), Object.values(trend));
    renderTrendChart("trend-chart", Object.keys(trend), Object.values(trend));
    renderSeverityChart("severity-chart", data.by_severity);
  } catch (err) {
    console.error("Chart error:", err);
  }
}

function showDashboardPanel(panel, button) {
  ["trend", "severity", "feed"].forEach(name => {
    const el = document.getElementById(`panel-${name}`);
    if (el) el.classList.toggle("hidden", name !== panel);
  });

  document.querySelectorAll(".sidebar-btn").forEach(btn => {
    btn.classList.toggle("active", btn === button);
  });
}

// ── Demo Data ─────────────────────────────────────────────────────────────────
async function generateDemo() {
  const msg = document.getElementById("demo-msg");
  msg.textContent = "Generating…";
  try {
    const data = await DemoAPI.generate();
    msg.textContent = `✓ ${data.inserted} readings injected`;
    showToast("Demo data generated!", "success");
    addFeedEntry(`Demo: ${data.inserted} readings added`, "info");
    setTimeout(() => { loadSummary(); refreshCharts(); }, 500);
  } catch (err) {
    msg.textContent = "Failed: " + err.message;
    showToast(err.message, "error");
  }
}

// ── WebSocket Live Updates ────────────────────────────────────────────────────
function initWebSocket() {
  if (typeof io === "undefined") return;
  try {
    const socket = io("http://localhost:5000");
    socket.on("fault_detected", (fault) => {
      addFeedEntry(`Fault on sensor ${fault.sensor_id}: ${fault.severity}`, fault.severity);
      showToast(`⚠️ ${fault.severity.toUpperCase()} fault detected!`, "warning");
      loadSummary();
    });
    socket.on("connect",    () => addFeedEntry("Connected to live feed", "info"));
    socket.on("disconnect", () => addFeedEntry("Disconnected from live feed", "info"));
  } catch {}
}

// ── Alert badge ───────────────────────────────────────────────────────────────
async function refreshAlertBadge() {
  try {
    const alerts = await AlertAPI.list();
    const unread = alerts.filter(a => !a.is_read).length;
    document.querySelectorAll("#alert-badge").forEach(el => el.textContent = unread);
  } catch {}
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  startClock();
  loadSummary();
  refreshCharts();
  refreshAlertBadge();
  initWebSocket();
  setInterval(loadSummary,        30_000);
  setInterval(refreshAlertBadge,  15_000);
});