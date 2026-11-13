/* charts.js — Chart.js rendering helpers for dashboard & reports */

const CHART_COLORS = {
  accent:   "#0071e3",
  violet:   "#5e5ce6",
  danger:   "#ff3b30",
  warning:  "#ff9500",
  success:  "#30b953",
  purple:   "#af52de",
  muted:    "rgba(110,110,115,0.3)",
};

// Vertical gradient fill under a line, from an opaque-ish top to transparent bottom.
function makeAreaGradient(ctx, topColor, bottomColor = "rgba(255,255,255,0)") {
  const { chartArea } = ctx.chart;
  if (!chartArea) return topColor; // first layout pass, before area is known
  const g = ctx.chart.ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
  g.addColorStop(0, topColor);
  g.addColorStop(1, bottomColor);
  return g;
}

// Diagonal gradient stroke — the brand blue-to-violet signature, used on primary trend lines.
function makeLineGradient(ctx) {
  const { chartArea } = ctx.chart;
  if (!chartArea) return CHART_COLORS.accent;
  const g = ctx.chart.ctx.createLinearGradient(chartArea.left, 0, chartArea.right, 0);
  g.addColorStop(0, CHART_COLORS.accent);
  g.addColorStop(1, CHART_COLORS.violet);
  return g;
}

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 900, easing: "easeOutQuart" },
  plugins: {
    legend: { labels: { color: "#6e6e73", font: { family: "'Inter', -apple-system, sans-serif", size: 12 } } },
    tooltip: {
      backgroundColor: "rgba(29,29,31,0.92)",
      borderColor: "transparent",
      borderWidth: 0,
      titleColor: "#fff",
      titleFont: { family: "'Inter', -apple-system, sans-serif", weight: "600" },
      bodyColor: "rgba(255,255,255,0.85)",
      bodyFont: { family: "'Inter', -apple-system, sans-serif" },
      padding: 11,
      cornerRadius: 10,
      displayColors: true,
      boxPadding: 4,
    },
  },
  scales: {
    x: { ticks: { color: "#86868b" }, grid: { color: "rgba(0,0,0,0.05)" } },
    y: { ticks: { color: "#86868b" }, grid: { color: "rgba(0,0,0,0.05)" }, beginAtZero: true },
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
        borderColor: (c) => makeLineGradient(c),
        backgroundColor: (c) => makeAreaGradient(c, "rgba(0,113,227,0.22)"),
        tension: 0.4,
        fill: true,
        borderWidth: 2.75,
        borderCapStyle: "round",
        borderJoinStyle: "round",
        pointBackgroundColor: CHART_COLORS.accent,
        pointBorderColor: "#fff",
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
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
        borderColor: "#ffffff",
        borderWidth: 3,
        hoverOffset: 10,
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      animation: { duration: 900, easing: "easeOutQuart" },
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#6e6e73", font: { family: "'Inter', -apple-system, sans-serif", size: 12 }, padding: 12 },
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
        backgroundColor: (c) => makeAreaGradient(c, color, color + "cc"),
        borderRadius: 8,
        maxBarThickness: 36,
        hoverBackgroundColor: color,
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

  new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Value",
          data: values,
          borderColor: (c) => makeLineGradient(c),
          backgroundColor: (c) => makeAreaGradient(c, "rgba(0,113,227,0.18)"),
          tension: 0.35,
          fill: true,
          borderWidth: 2.5,
          pointBackgroundColor: readings.map(r =>
            r.is_anomaly ? CHART_COLORS.danger : CHART_COLORS.accent),
          pointBorderColor: "#fff",
          pointBorderWidth: 1.5,
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
