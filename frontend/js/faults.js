const FaultsState = {
  data: [],
  filtered: [],
  currentPage: 1,
  pageSize: 15,
  sortKey: null,
  sortDir: "asc",
};

function setFaultsLoading() {
  const tbody = document.getElementById("faults-tbody");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="9" class="loading-row">Loading…</td></tr>';
}

function renderFaultsTable() {
  const tbody = document.getElementById("faults-tbody");
  if (!tbody) return;

  const currentData = FaultsState.filtered.slice(
    (FaultsState.currentPage - 1) * FaultsState.pageSize,
    FaultsState.currentPage * FaultsState.pageSize
  );

  if (currentData.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="loading-row">No faults found.</td></tr>';
    return;
  }

  tbody.innerHTML = currentData.map(f => {
    const sensorLabel = f.sensor_name || `Sensor ${f.sensor_id}`;
    const detected = new Date(f.detected_at).toLocaleString();
    return `
      <tr>
        <td>#${f.id}</td>
        <td>${sensorLabel}</td>
        <td><span class="severity-chip ${f.severity}">${f.severity}</span></td>
        <td>${f.fault_type || "—"}</td>
        <td>${f.value ?? "—"}</td>
        <td>${f.description || "—"}</td>
        <td>${detected}</td>
        <td><span class="status-chip ${f.status}">${f.status}</span></td>
        <td>${f.status === "open" ? `<button class="btn-resolve" onclick="resolveFault(${f.id}, this)">Resolve</button>` : "—"}</td>
      </tr>`;
  }).join("");
}

function renderPagination() {
  const paging = document.getElementById("pagination");
  if (!paging) return;

  const totalPages = Math.ceil(FaultsState.filtered.length / FaultsState.pageSize) || 1;
  if (totalPages <= 1) {
    paging.innerHTML = "";
    return;
  }

  const buttons = [];
  for (let page = 1; page <= totalPages; page += 1) {
    buttons.push(`<button class="btn-sm${page === FaultsState.currentPage ? " active" : ""}" onclick="changeFaultsPage(${page})">${page}</button>`);
  }
  paging.innerHTML = buttons.join("");
}

function changeFaultsPage(page) {
  FaultsState.currentPage = page;
  renderFaultsTable();
  renderPagination();
}

function sortTable(columnIndex) {
  const sortMap = {
    0: "id",
    1: "sensor_id",
    2: "severity",
    6: "detected_at",
  };
  const key = sortMap[columnIndex];
  if (!key) return;

  if (FaultsState.sortKey === key) {
    FaultsState.sortDir = FaultsState.sortDir === "asc" ? "desc" : "asc";
  } else {
    FaultsState.sortKey = key;
    FaultsState.sortDir = "asc";
  }

  FaultsState.filtered.sort((a, b) => {
    const av = a[key] ?? "";
    const bv = b[key] ?? "";
    if (key === "detected_at") {
      return FaultsState.sortDir === "asc"
        ? new Date(av) - new Date(bv)
        : new Date(bv) - new Date(av);
    }
    if (av < bv) return FaultsState.sortDir === "asc" ? -1 : 1;
    if (av > bv) return FaultsState.sortDir === "asc" ? 1 : -1;
    return 0;
  });

  renderFaultsTable();
}

function filterTable() {
  const query = document.getElementById("filter-search").value.trim().toLowerCase();
  if (!query) {
    FaultsState.filtered = [...FaultsState.data];
  } else {
    FaultsState.filtered = FaultsState.data.filter(f => {
      return [
        `${f.id}`,
        f.sensor_name || `Sensor ${f.sensor_id}`,
        f.severity,
        f.fault_type,
        f.description,
        f.status,
      ]
        .filter(Boolean)
        .some(value => value.toLowerCase().includes(query));
    });
  }
  FaultsState.currentPage = 1;
  renderFaultsTable();
  renderPagination();
}

async function loadFaults() {
  setFaultsLoading();
  const severity = document.getElementById("filter-severity")?.value;
  const status = document.getElementById("filter-status")?.value;
  const params = {};
  if (severity) params.severity = severity;
  if (status) params.status = status;

  try {
    const faults = await FaultAPI.list(params);
    FaultsState.data = faults;
    FaultsState.filtered = [...faults];
    FaultsState.currentPage = 1;
    renderFaultsTable();
    renderPagination();
  } catch (err) {
    const tbody = document.getElementById("faults-tbody");
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="9" class="loading-row">Failed to load faults: ${err.message}</td></tr>`;
    }
    showToast(err.message, "error");
  }
}

function exportFaults() {
  ReportsAPI.exportFaults(30).then(({ blob, filename }) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }).catch(err => {
    showToast(err.message || "Unable to export faults", "error");
  });
}

window.loadFaults = loadFaults;
window.sortTable = sortTable;
window.filterTable = filterTable;
window.changeFaultsPage = changeFaultsPage;
window.exportFaults = exportFaults;

document.addEventListener("DOMContentLoaded", () => {
  loadFaults();
});
