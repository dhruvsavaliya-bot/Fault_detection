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

// Counts a KPI value up/down from whatever it currently shows, eased — the
// small touch that makes a dashboard feel alive instead of just repainting.
// Shared here (rather than in main.js) because it's used on both the
// Dashboard and Reports pages, which don't share a single page-logic file.
function animateValue(el, target, duration = 650) {
  if (!el) return;
  target = Number(target);
  if (Number.isNaN(target)) { el.textContent = "—"; return; }

  const start = Number(el.textContent.replace(/[^0-9.-]/g, "")) || 0;
  if (start === target) { el.textContent = target; return; }

  const startTime = performance.now();
  function tick(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    el.textContent = Math.round(start + (target - start) * eased);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

window.alertSeverityClass = alertSeverityClass;
window.formatTimestamp = formatTimestamp;
window.animateValue = animateValue;
