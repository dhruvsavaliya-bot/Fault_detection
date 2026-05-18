/* charts.js — Chart.js rendering helpers for dashboard & reports */

const CHART_COLORS = {
  accent:   "#4f8ef7",
  danger:   "#ff4757",
  warning:  "#ffa502",
  success:  "#2ed573",
  purple:   "#a855f7",
  muted:    "rgba(139,144,168,0.3)",
};

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: "#8b90a8", font: { size: 12 } } },
    tooltip: {
      backgroundColor: "#1a1d27",
      borderColor: "#2a2d3e",
      borderWidth: 1,
      titleColor: "#e8eaf0",
      bodyColor: "#8b90a8",
    },
  },
  scales: {
    x: { ticks: { color: "#8b90a8" }, grid: { color: "rgba(42,45,62,0.08)" } },
    y: { ticks: { color: "#8b90a8" }, grid: { color: "rgba(42,45,62,0.08)" }, beginAtZero: true },
  },
};

let trendChartInst    = null;
let severityChartInst = null;

// ── Trend Line Chart ──────────────────────────────────────────────────────────
function renderTrendChart(canvasId, labels, values) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  if (trendChartInst) trendChartInst.destroy();

  labels = Array.isArray(labels) ? labels : [];
  values = Array.isArray(values) ? values : [];
  if (labels.length === 0 || values.length === 0) {
    // nothing to render — leave blank
    return;
  }

  // coerce values to numbers
  const nums = values.map(v => (v === null || v === undefined) ? 0 : Number(v));

  trendChartInst = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Faults",
        data: nums,
        borderColor: CHART_COLORS.accent,
        backgroundColor: "rgba(79,142,247,0.12)",
        tension: 0.4,
        fill: true,
        pointBackgroundColor: CHART_COLORS.accent,
        pointRadius: 4,
      }],
    },
    options: { ...CHART_DEFAULTS, scales: { ...CHART_DEFAULTS.scales, y: { ...CHART_DEFAULTS.scales.y, beginAtZero: true } } },
  });
}

// ── Severity Doughnut ─────────────────────────────────────────────────────────
function renderSeverityChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  if (severityChartInst) severityChartInst.destroy();

  const labels = Object.keys(data);
  const values = Object.values(data);
  const colors = labels.map(l => ({
    critical: CHART_COLORS.danger,
    high:     CHART_COLORS.warning,
    medium:   CHART_COLORS.purple,
    low:      CHART_COLORS.success,
    normal:   CHART_COLORS.accent,
  }[l] || CHART_COLORS.muted));

  severityChartInst = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: "#1a1d27",
        borderWidth: 3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#8b90a8", font: { size: 12 }, padding: 12 },
        },
        tooltip: CHART_DEFAULTS.plugins.tooltip,
      },
    },
  });
}

// ── Bar Chart (by sensor / by day) ────────────────────────────────────────────
function renderBarChart(canvasId, labels, values, label = "Count", color = CHART_COLORS.accent) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const old = Chart.getChart(ctx);
  if (old) old.destroy();

  labels = Array.isArray(labels) ? labels : [];
  values = Array.isArray(values) ? values : [];
  if (labels.length === 0 || values.length === 0) return;

  const nums = values.map(v => (v === null || v === undefined) ? 0 : Number(v));

  new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label,
        data: nums,
        backgroundColor: color + "cc",
        borderColor: color,
        borderWidth: 1,
        borderRadius: 6,
      }],
    },
    options: { ...CHART_DEFAULTS, scales: { ...CHART_DEFAULTS.scales, y: { ...CHART_DEFAULTS.scales.y, beginAtZero: true } } },
  });
}

// ── Sensor Live Mini Chart ────────────────────────────────────────────────────
function renderMiniChart(canvasId, readings) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const old = Chart.getChart(ctx);
  if (old) old.destroy();

  const labels = readings.map(r => new Date(r.timestamp).toLocaleTimeString());
  const values = readings.map(r => r.value);
  const isAnomaly = readings.map(r => r.is_anomaly);

  new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Value",
          data: values,
          borderColor: CHART_COLORS.accent,
          backgroundColor: "rgba(79,142,247,0.08)",
          tension: 0.3,
          fill: true,
          pointBackgroundColor: readings.map(r =>
            r.is_anomaly ? CHART_COLORS.danger : CHART_COLORS.accent),
          pointRadius: readings.map(r => r.is_anomaly ? 6 : 3),
        },
      ],
    },
    options: {
      ...CHART_DEFAULTS,
      plugins: { ...CHART_DEFAULTS.plugins, legend: { display: false } },
    },
  });
}