/* settings.js — handlers for the Settings page */

async function changePassword(e) {
  e.preventDefault();
  const oldP = document.getElementById('old-pass').value;
  const newP = document.getElementById('new-pass').value;
  const conf = document.getElementById('conf-pass').value;
  const msgEl = document.getElementById('pass-msg');
  msgEl.textContent = '';
  if (newP !== conf) { msgEl.textContent = 'Passwords do not match'; return; }
  try {
    await AuthAPI.changePassword(oldP, newP);
    msgEl.textContent = 'Password updated ✓';
    showToast('Password updated', 'success');
    document.getElementById('old-pass').value = '';
    document.getElementById('new-pass').value = '';
    document.getElementById('conf-pass').value = '';
  } catch (err) {
    msgEl.textContent = err.message || 'Failed to update password';
    showToast(err.message || 'Failed to update password', 'error');
  }
}

function toggleDarkMode(checkbox) {
  const enabled = checkbox.checked;
  if (!enabled) {
    document.body.classList.add('light');
    localStorage.setItem('dark_mode', 'false');
  } else {
    document.body.classList.remove('light');
    localStorage.setItem('dark_mode', 'true');
  }
}

function savePref(key, value) {
  localStorage.setItem(key, value ? 'true' : 'false');
  // apply immediate effects for a few preferences
  if (key === 'sidebar_collapsed') {
    if (value) document.body.classList.add('sidebar-collapsed'); else document.body.classList.remove('sidebar-collapsed');
  }
  if (key === 'dark_mode') {
    if (value === 'false' || value === false) document.body.classList.add('light'); else document.body.classList.remove('light');
  }
  showToast('Preference saved', 'info');
}

async function toggleNotifications(checkbox) {
  const enabled = checkbox.checked;
  if (enabled) {
    if (!('Notification' in window)) {
      showToast('Notifications not supported in this browser', 'error');
      checkbox.checked = false;
      return;
    }
    try {
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        showToast('Notifications blocked by user', 'error');
        checkbox.checked = false;
        return;
      }
    } catch (e) {
      showToast('Notification permission failed', 'error');
      checkbox.checked = false;
      return;
    }
  }
  savePref('browser_notifications', enabled);
}

async function trainModel() {
  const type = document.getElementById('train-type').value;
  const count = parseInt(document.getElementById('train-count').value || '0', 10);
  const resultEl = document.getElementById('train-result');
  resultEl.textContent = '';
  if (isNaN(count) || count < 20) { resultEl.textContent = 'Sample count must be at least 20'; return; }
  try {
    const btn = document.querySelector('button[onclick="trainModel()"]');
    if (btn) { btn.disabled = true; btn.textContent = 'Training…'; }
    resultEl.classList.add('visible');
    resultEl.textContent = 'Training… this may take a moment';
    // backend expects a POST to /api/train/{type}?count={count}
    await apiFetch(`/api/train/${encodeURIComponent(type)}?count=${count}`, { method: 'POST', body: JSON.stringify({}) });
    resultEl.textContent = 'Training completed ✓';
    showToast('Model trained', 'success');
    if (btn) { btn.disabled = false; btn.textContent = '🤖 Train Model'; }
  } catch (err) {
    resultEl.textContent = err.message || 'Training failed';
    showToast(err.message || 'Training failed', 'error');
    const btn = document.querySelector('button[onclick="trainModel()"]');
    if (btn) { btn.disabled = false; btn.textContent = '🤖 Train Model'; }
  }
}

// Initialize settings UI state
document.addEventListener('DOMContentLoaded', () => {
  // populate user UI if available (auth.js provides this)
  if (typeof populateUserUI === 'function') populateUserUI();

  // dark mode toggle
  const darkToggle = document.getElementById('dark-mode-toggle');
  if (darkToggle) {
    const dm = localStorage.getItem('dark_mode');
    // default to true if not set
    darkToggle.checked = (dm !== 'false');
  }

  // sidebar pref
  const sb = document.getElementById('sidebar-pref');
  if (sb) sb.checked = (localStorage.getItem('sidebar_collapsed') === 'true');

  // notifications
  const nt = document.getElementById('notif-toggle');
  if (nt) nt.checked = (localStorage.getItem('browser_notifications') === 'true');

  // sound alerts
  const sd = document.getElementById('sound-toggle');
  if (sd) sd.checked = (localStorage.getItem('sound_alerts') === 'true');
});

// expose for inline handlers
window.changePassword = changePassword;
window.toggleDarkMode = toggleDarkMode;
window.savePref = savePref;
window.toggleNotifications = toggleNotifications;
window.trainModel = trainModel;
