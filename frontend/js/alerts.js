function alertSeverityClass(severity) {
  return {
    critical: "critical",
    high:     "high",
    medium:   "medium",
  }[severity] || "normal";
}

function formatTimestamp(ts) {
  return new Date(ts).toLocaleString();
}

window.alertSeverityClass = alertSeverityClass;
window.formatTimestamp = formatTimestamp;
