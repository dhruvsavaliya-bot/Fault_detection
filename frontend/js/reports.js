async function loadAnalytics() {
  const periodSelect = document.getElementById("period-select");
  const days = Number(periodSelect?.value || 7);

  try {
    const data = await ReportsAPI.analytics(days);

    animateValue(document.getElementById("r-total"),    data.total_faults ?? 0);
    animateValue(document.getElementById("r-critical"), data.by_severity?.critical ?? 0);
    animateValue(document.getElementById("r-high"),     data.by_severity?.high ?? 0);
    document.getElementById("r-rate").textContent     = `${data.resolution_rate ?? 0}%`;

    // Trend (by day) — sort keys chronologically if possible
    const byDay = data.by_day || {};
    let dayLabels = Object.keys(byDay || {});
    try {
      if (dayLabels.length > 1 && !isNaN(Date.parse(dayLabels[0]))) {
        dayLabels = dayLabels.sort((a,b)=>new Date(a) - new Date(b));
      }
    } catch {}
    const dayValues = dayLabels.map(k => byDay[k]);
    renderTrendChart("report-trend-chart", dayLabels, dayValues);

    // By sensor — present in descending order by count for readability
    const bySensor = data.by_sensor || {};
    const sensorEntries = Object.entries(bySensor || {});
    sensorEntries.sort((a,b)=>Number(b[1]||0)-Number(a[1]||0));
    const sensorLabels = sensorEntries.map(e=>e[0]);
    const sensorValues = sensorEntries.map(e=>e[1]);

    renderBarChart(
      "report-sensor-chart",
      sensorLabels,
      sensorValues,
      "Faults",
      CHART_COLORS.accent
    );

    renderSeverityChart("report-severity-chart", data.by_severity || {});
  } catch (err) {
    showToast?.(err.message || "Unable to load analytics", "error");
  }
}

function downloadCSV(blobPromise) {
  return blobPromise.then(({ blob, filename }) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  });
}

function exportFaultsCSV() {
  const days = Number(document.getElementById("period-select")?.value || 30);
  downloadCSV(ReportsAPI.exportFaults(days)).catch(err => {
    showToast?.(err.message || "Unable to download faults report", "error");
  });
}

function exportReadingsCSV() {
  downloadCSV(ReportsAPI.exportReadings()).catch(err => {
    showToast?.(err.message || "Unable to download readings report", "error");
  });
}

window.loadAnalytics = loadAnalytics;
window.exportFaultsCSV = exportFaultsCSV;
window.exportReadingsCSV = exportReadingsCSV;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", loadAnalytics);
} else {
  loadAnalytics();
}
