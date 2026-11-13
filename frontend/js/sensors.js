/* sensors.js — Sensor page behavior: modals, listing, add sensor, readings */

async function loadSensors() {
  const grid = document.getElementById('sensors-grid');
  if (!grid) return;
  grid.innerHTML = '<div class="loading-spinner">Loading sensors…</div>';
  try {
    const sensors = await SensorAPI.list();
    if (!sensors || sensors.length === 0) {
      grid.innerHTML = '<div class="empty-state">No sensors configured yet.</div>';
      return;
    }
    grid.innerHTML = sensors.map(s => renderSensorCard(s)).join('');
  } catch (err) {
    console.error('Load sensors error', err);
    grid.innerHTML = `<div class="empty-state">Failed to load sensors: ${err.message}</div>`;
  }
}

function renderSensorCard(s) {
  const cardClass = s.status === 'fault' ? 'sensor-card fault-state' : s.status === 'critical' ? 'sensor-card critical-state' : 'sensor-card';
  const statusDot = s.status === 'fault' ? 'sensor-status-dot fault' : s.status === 'critical' ? 'sensor-status-dot critical' : 'sensor-status-dot';
  return `
    <div class="${cardClass}" data-id="${s.id}" onclick="openDetailModal(${s.id})">
      <div class="sensor-header">
        <div>
          <div class="sensor-name">${escapeHtml(s.name || 'Unnamed')}</div>
          <div class="sensor-type">${escapeHtml(s.sensor_type || '')}</div>
        </div>
        <div>
          <div class="sensor-status"> <span class="${statusDot}"></span></div>
        </div>
      </div>
      <div class="sensor-value-big">${s.latest_value ?? '—'} ${escapeHtml(s.unit || '')}</div>
      <div class="sensor-footer"><div class="sensor-loc">${escapeHtml(s.location || '')}</div><div>id ${s.id}</div></div>
    </div>`;
}

function escapeHtml(text) {
  if (text == null) return '';
  return String(text).replace(/[&"'<>]/g, c => ({'&':'&amp;','"':'&quot;',"'":'&#39;','<':'&lt;','>':'&gt;'}[c]));
}

function openAddModal() {
  const m = document.getElementById('add-modal');
  if (m) m.classList.remove('hidden');
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('hidden');
}

async function addSensor(evt) {
  evt.preventDefault();
  const name = document.getElementById('new-name').value.trim();
  const type = document.getElementById('new-type').value;
  const location = document.getElementById('new-location').value.trim();
  const unit = document.getElementById('new-unit').value.trim();
  try {
    const payload = { name, type, location, unit };
    await SensorAPI.create(payload);
    showToast('Sensor added', 'success');
    closeModal('add-modal');
    setTimeout(loadSensors, 400);
  } catch (err) {
    showToast(err.message || 'Failed to add sensor', 'error');
    console.error('Add sensor error', err);
  }
}

let currentSensorId = null;

async function openDetailModal(id) {
  try {
    const data = await SensorAPI.get(id);
    currentSensorId = id;
    document.getElementById('modal-sensor-name').textContent = data.name || `Sensor ${id}`;
    // populate KPIs
    const kpis = document.getElementById('modal-kpis');
    if (kpis) kpis.innerHTML = `
      <div class="modal-kpi"><div class="modal-kpi-val">${data.latest_value ?? '—'}</div><div class="modal-kpi-label">Last value</div></div>
      <div class="modal-kpi"><div class="modal-kpi-val">${data.total_readings ?? 0}</div><div class="modal-kpi-label">Readings</div></div>
      <div class="modal-kpi"><div class="modal-kpi-val">${data.open_faults ?? 0}</div><div class="modal-kpi-label">Open faults</div></div>`;
    document.getElementById('reading-result').textContent = '';
    document.getElementById('detail-modal').classList.remove('hidden');
    try {
      const readings = await SensorAPI.readings(id, 50);
      renderMiniChart('sensor-chart', readings);
    } catch { /* chart is a bonus, don't block the modal on it */ }
  } catch (err) {
    showToast(err.message || 'Failed to load sensor', 'error');
  }
}

async function submitReading() {
  const valEl = document.getElementById('reading-value');
  if (!valEl) return;
  const val = parseFloat(valEl.value);
  if (isNaN(val)) { showToast('Invalid reading value', 'error'); return; }
  if (!currentSensorId) { showToast('Unknown sensor', 'error'); return; }
  try {
    await SensorAPI.addReading(currentSensorId, val);
    document.getElementById('reading-result').textContent = 'Reading submitted';
    showToast('Reading submitted', 'success');
    valEl.value = '';
    openDetailModal(currentSensorId);
  } catch (err) {
    showToast(err.message || 'Failed to submit reading', 'error');
  }
}

// expose to global
window.openAddModal = openAddModal;
window.closeModal = closeModal;
window.addSensor = addSensor;
window.loadSensors = loadSensors;
window.openDetailModal = openDetailModal;
window.submitReading = submitReading;

document.addEventListener('DOMContentLoaded', () => {
  // Adding sensors is an admin/engineer action (see backend/authz.py) —
  // hide the control for operators rather than let them hit a 403.
  const user = typeof getUser === 'function' ? getUser() : null;
  if (user && user.role === 'operator') {
    const addBtn = document.querySelector('button[onclick="openAddModal()"]');
    if (addBtn) addBtn.remove();
  }
  loadSensors();
});
