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
    msgEl.textContent = 'Password updated';
    showToast('Password updated', 'success');
    document.getElementById('old-pass').value = '';
    document.getElementById('new-pass').value = '';
    document.getElementById('conf-pass').value = '';
  } catch (err) {
    msgEl.textContent = err.message || 'Failed to update password';
    showToast(err.message || 'Failed to update password', 'error');
  }
}

async function resendVerification(btn) {
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = 'Sending…';
  try {
    const data = await AuthAPI.resendVerification();
    showToast(data.message, 'success');
  } catch (err) {
    showToast(err.message || 'Failed to send verification email', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = original;
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

// Plausible normal-operating ranges per sensor type, mirroring the demo
// data generator in routes/api.py, so training data looks like real baseline
// readings rather than noise.
const TRAIN_RANGES = {
  temperature: [60, 95],
  vibration:   [5, 40],
  pressure:    [80, 180],
  current:     [20, 90],
  voltage:     [210, 255],
  humidity:    [30, 95],
};

function generateBaselineSamples(type, count) {
  const [lo, hi] = TRAIN_RANGES[type] || [0, 100];
  const mid = (lo + hi) / 2;
  const spread = (hi - lo) / 6; // keep samples clustered so the model learns a tight "normal" band
  const values = [];
  for (let i = 0; i < count; i++) {
    const noise = (Math.random() + Math.random() + Math.random() - 1.5) * spread; // approx normal via sum of uniforms
    values.push(Math.round((mid + noise) * 100) / 100);
  }
  return values;
}

async function trainModel() {
  const type = document.getElementById('train-type').value;
  const count = parseInt(document.getElementById('train-count').value || '0', 10);
  const resultEl = document.getElementById('train-result');
  resultEl.textContent = '';
  if (isNaN(count) || count < 20) { resultEl.textContent = 'Sample count must be at least 20'; return; }
  const btn = document.querySelector('button[onclick="trainModel()"]');
  try {
    if (btn) { btn.disabled = true; btn.textContent = 'Training…'; }
    resultEl.classList.add('visible');
    resultEl.textContent = 'Training… this may take a moment';
    const values = generateBaselineSamples(type, count);
    const result = await MLAPI.train(type, values);
    if (result && result.success === false) {
      throw new Error(result.error || 'Training failed');
    }
    resultEl.textContent = `Training completed. ${result.n_samples} samples, mean ${result.mean}, std ${result.std}.`;
    showToast('Model trained', 'success');
  } catch (err) {
    resultEl.textContent = err.message || 'Training failed';
    showToast(err.message || 'Training failed', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Train model'; }
  }
}

// Initialize settings UI state
document.addEventListener('DOMContentLoaded', () => {
  // populate user UI if available (auth.js provides this)
  if (typeof populateUserUI === 'function') populateUserUI();

  // Training is an admin/engineer action (see backend/authz.py) — swap the
  // controls for a note rather than let an operator hit a 403.
  const user = typeof getUser === 'function' ? getUser() : null;
  if (user && user.role === 'operator') {
    const controls = document.getElementById('training-controls');
    if (controls) {
      controls.outerHTML = '<p style="color:var(--text-tertiary);font-size:0.9rem">' +
        'Training requires an engineer or admin role.</p>';
    }
  }

  // Fetch fresh (not the possibly-stale cached copy) so a session that
  // started before email verification existed still gets an accurate banner.
  AuthAPI.me().then(fresh => {
    document.getElementById('verify-banner').classList.toggle('hidden', fresh.email_verified !== false);
  }).catch(() => {});

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
window.resendVerification = resendVerification;
