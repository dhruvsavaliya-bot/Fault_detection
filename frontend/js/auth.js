/* auth.js — Authentication logic: login, register, session guard, logout */

function saveSession(token, user) {
  localStorage.setItem("fd_token", token);
  localStorage.setItem("fd_user",  JSON.stringify(user));
}

function getToken() {
  return localStorage.getItem("fd_token");
}

function getUser() {
  try { return JSON.parse(localStorage.getItem("fd_user")); } catch { return null; }
}

function isLoginPage() {
  const path = window.location.pathname.toLowerCase();
  return path === "/" || path.endsWith("/login.html") || path.includes("login");
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = "/login.html";
    return false;
  }
  return true;
}

function logout() {
  localStorage.removeItem("fd_token");
  localStorage.removeItem("fd_user");
  window.location.href = "/login.html";
}

async function initializeSession() {
  const token = getToken();
  if (!token) return;
  if (getUser()) return;

  try {
    const user = await AuthAPI.me();
    saveSession(token, user);
  } catch (err) {
    console.warn("Session initialization failed:", err);
  }
}

function populateUserUI() {
  const user = getUser();
  if (!user) return;
  ["user-name",     "s-username"].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = user.username; });
  ["user-role",     "s-role"].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = user.role; });
  ["user-avatar",   "settings-avatar"].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = (user.username[0] || "U").toUpperCase(); });
  const emailEl = document.getElementById("s-email");
  if (emailEl) emailEl.textContent = user.email || "";
}

// ── Login Handler ─────────────────────────────────────────────────────────────
async function handleLogin(e) {
  e.preventDefault();
  const btn  = document.getElementById("login-btn");
  const errEl= document.getElementById("login-error");
  const u    = document.getElementById("login-username").value.trim();
  const p    = document.getElementById("login-password").value;

  btn.textContent = "Logging in…";
  btn.disabled    = true;
  errEl.textContent = "";

  try {
    const data = await AuthAPI.login(u, p);
    if (!data || !data.token || !data.user) {
      throw new Error("Login failed. Please check your username and password.");
    }
    saveSession(data.token, data.user);
    window.location.href = "/index.html";
  } catch (err) {
    errEl.textContent = err.message || "Login failed";
    btn.textContent   = "Login";
    btn.disabled      = false;
  }
}

// ── Register Handler ──────────────────────────────────────────────────────────
async function handleRegister(e) {
  e.preventDefault();
  const btn  = document.getElementById("reg-btn");
  const errEl= document.getElementById("reg-error");

  btn.textContent = "Creating…";
  btn.disabled    = true;
  errEl.textContent = "";

  try {
    const data = await AuthAPI.register({
      username: document.getElementById("reg-username").value.trim(),
      email:    document.getElementById("reg-email").value.trim(),
      password: document.getElementById("reg-password").value,
    });
    saveSession(data.token, data.user);
    window.location.href = "/index.html";
  } catch (err) {
    errEl.textContent = err.message || "Registration failed";
    btn.textContent   = "Create Account";
    btn.disabled      = false;
  }
}

// ── Sidebar toggle ────────────────────────────────────────────────────────────
function toggleSidebar() {
  document.body.classList.toggle("sidebar-collapsed");
  localStorage.setItem("sidebar_collapsed",
    document.body.classList.contains("sidebar-collapsed"));
}

function applySavedPrefs() {
  if (localStorage.getItem("dark_mode") === "false")
    document.body.classList.add("light");
}

// ── On every page, manage auth and UI initialization ──────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  if (isLoginPage()) {
    if (getToken()) {
      window.location.href = "/index.html";
    }
    return;
  }

  if (!requireAuth()) {
    return;
  }

  initializeSession().then(() => {
    populateUserUI();
    applySavedPrefs();
  });
});