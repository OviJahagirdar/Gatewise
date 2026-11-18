// ---------------------------------------------------------------------------
// frontend/committee/app.js
// Shared helpers for every committee (admin) page. Each page in this folder
// loads this file at the bottom of <body>, before its own <script>.
// Owner: Person 4.
//
// What lives here:
//   getToken() / saveLogin() / logout()   - the login token in localStorage
//   callApi(path, options)                - fetch() + the Authorization header
//   requireAdmin()                        - "is an admin logged in?" guard
//   renderNav(activePage)                 - the top navigation bar
//   small formatting helpers used by pages
// ---------------------------------------------------------------------------

// The backend login route gives us a token; we keep it in localStorage under
// this key and send it back as "Authorization: Bearer <token>".
const TOKEN_KEY = "gate_token";
const USER_KEY = "gate_user";
const SOCIETY_KEY = "gate_society"; // cached society row (name, retention_days, qr_token)

// ---- Login token helpers ---------------------------------------------------

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

// Saves whatever the login/onboard response contained and returns the token.
// The backend sends {token: "...", user: {...}}; we also accept {access_token}.
function saveLogin(data) {
  const token = data.token || data.access_token;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  if (data.user) localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  if (data.society) localStorage.setItem(SOCIETY_KEY, JSON.stringify(data.society));
  return token;
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  // The society cache is not a secret and is handy to keep for the QR link.
  window.location.href = "login.html";
}

// ---- The one function every page uses to talk to the backend --------------

// callApi("/api/flats") or callApi("/api/flats", { method: "POST", body: ... })
// - adds the saved token to every request
// - sends the user back to login.html if the server answers 401 (not logged in)
// - throws an Error with the server's {"detail": "..."} message when it fails
async function callApi(path, options) {
  const settings = options || {};
  const headers = Object.assign({}, settings.headers || {});

  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  // A string body is JSON; a FormData body (file uploads) must NOT get a
  // Content-Type, because the browser adds the right one with the boundary.
  if (typeof settings.body === "string" && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, Object.assign({}, settings, { headers: headers }));

  if (response.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.location.href = "login.html";
    throw new Error("You are not logged in.");
  }

  if (!response.ok) {
    let message = "Request failed (" + response.status + ")";
    try {
      const problem = await response.json();
      if (problem && problem.detail) message = problem.detail;
    } catch (ignored) {
      // Some errors have no JSON body; the status-code message is enough.
    }
    throw new Error(message);
  }

  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  if (contentType.indexOf("application/json") !== -1) return response.json();
  return response.text();
}

// ---- "Only admins allowed" guard -----------------------------------------

// Call this at the top of every page except login.html and onboard.html:
//   const me = await requireAdmin();
//   if (!me) return;
// It asks GET /api/me who is logged in, and kicks out anyone who is not an
// admin (a guard login, for example, belongs on the guard pages instead).
async function requireAdmin() {
  let me;
  try {
    me = await callApi("/api/me");
  } catch (error) {
    // callApi already sent us to login.html if it was a 401.
    return null;
  }

  if (!me || me.role !== "admin") {
    document.body.innerHTML =
      '<main><div class="card" style="max-width:520px;margin:60px auto">' +
      '<p class="message error">This page is for committee (admin) logins only. ' +
      "Taking you back to the login page…</p></div></main>";
    setTimeout(function () {
      window.location.href = "login.html";
    }, 2500);
    return null;
  }

  localStorage.setItem(USER_KEY, JSON.stringify(me));
  return me;
}

// ---- Navigation bar ------------------------------------------------------

// renderNav("logs.html") draws the dark bar at the top of the page and marks
// the current page as active.
function renderNav(activePage) {
  const pages = [
    ["logs.html", "Logs"],
    ["flats.html", "Flats"],
    ["users.html", "Users"],
    ["staff.html", "Staff"],
    ["settings.html", "Settings"],
  ];

  const bar = document.createElement("header");
  bar.className = "topbar";

  let links = "";
  for (const page of pages) {
    const isActive = page[0] === activePage ? ' class="active"' : "";
    links += '<a href="' + page[0] + '"' + isActive + ">" + page[1] + "</a>";
  }
  links += '<a href="#" id="nav-logout">Logout</a>';

  bar.innerHTML = '<span class="brand">Society Gate</span><nav class="nav">' + links + "</nav>";
  document.body.prepend(bar);

  bar.querySelector("#nav-logout").addEventListener("click", function (event) {
    event.preventDefault();
    logout();
  });
}

// ---- Small formatting helpers --------------------------------------------

// Stops text from the database (a visitor name, say) from breaking the page.
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// "2026-10-05T09:30:00" -> "05 Oct 2026, 09:30"
function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (isNaN(date.getTime())) return String(value);
  return date.toLocaleString([], {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Flats come from the backend as {id, wing, number, label}; be forgiving if
// label is missing.
function flatLabel(flat) {
  if (!flat) return "—";
  return flat.label || flat.wing + "-" + flat.number;
}

// Shows a green/red message in an element like <p id="message" hidden>.
function showMessage(elementId, text, isError) {
  const element = document.getElementById(elementId);
  if (!element) return;
  element.textContent = text;
  element.className = "message " + (isError ? "error" : "ok");
  element.hidden = false;
}

function clearMessage(elementId) {
  const element = document.getElementById(elementId);
  if (!element) return;
  element.textContent = "";
  element.hidden = true;
}

// ---- Shared look and feel ------------------------------------------------

// Injected from here so each page file stays short and readable.
const SHARED_CSS = `
:root { --ink:#1f2933; --muted:#64748b; --line:#e2e8f0; --brand:#1d4ed8; --bg:#f6f7f9; }
* { box-sizing: border-box; }
body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
       background: var(--bg); color: var(--ink); font-size:15px; }
.topbar { display:flex; align-items:center; gap:24px; padding:0 24px; height:56px;
          background:#0f172a; color:#fff; }
.topbar .brand { font-weight:700; }
.topbar .nav { display:flex; gap:4px; margin-left:auto; }
.topbar .nav a { color:#cbd5e1; text-decoration:none; padding:8px 12px; border-radius:6px; font-size:14px; }
.topbar .nav a:hover { background:#1e293b; color:#fff; }
.topbar .nav a.active { background:var(--brand); color:#fff; }
main { max-width:1100px; margin:0 auto; padding:24px; }
.card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:20px; margin-bottom:20px; }
h1 { font-size:22px; margin:0 0 6px; }
h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:0 0 12px; }
.hint { color:var(--muted); font-size:13px; margin:0 0 14px; }
label { display:block; font-size:13px; font-weight:600; margin-bottom:4px; }
input, select { width:100%; padding:8px 10px; border:1px solid #cbd5e1; border-radius:6px;
                font:inherit; background:#fff; }
select[multiple] { height:auto; padding:4px; }
input[type=checkbox] { width:auto; }
.row { display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; }
.row > .field { flex:1 1 150px; min-width:130px; }
button { font:inherit; padding:9px 16px; border-radius:6px; border:1px solid transparent;
         background:var(--brand); color:#fff; cursor:pointer; font-weight:600; }
button:hover { filter:brightness(1.08); }
button.secondary { background:#fff; color:var(--ink); border-color:#cbd5e1; }
button.danger { background:#b91c1c; }
button:disabled { opacity:.45; cursor:not-allowed; filter:none; }
table { width:100%; border-collapse:collapse; font-size:14px; }
th, td { text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); background:#f8fafc; }
tbody tr:hover { background:#f8fafc; }
tbody tr.clickable { cursor:pointer; }
tbody tr.selected { background:#eff6ff; }
.badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:600;
         background:#e2e8f0; color:#334155; }
.badge.verified { background:#dcfce7; color:#166534; }
.badge.pending { background:#fef3c7; color:#92400e; }
.badge.not_done { background:#e2e8f0; color:#475569; }
.message { padding:10px 12px; border-radius:6px; font-size:14px; margin:12px 0; }
.message.ok { background:#dcfce7; color:#166534; }
.message.error { background:#fee2e2; color:#991b1b; }
.auth-card { max-width:420px; margin:60px auto; }
.field-gap { margin-top:12px; }
a { color:var(--brand); }
`;

(function injectSharedStyles() {
  const style = document.createElement("style");
  style.textContent = SHARED_CSS;
  document.head.appendChild(style);
})();
