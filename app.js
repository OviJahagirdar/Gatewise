// ============================================================
// Shared helpers for every guard page. Load with:
//   <script src="app.js"></script>
// ============================================================

// STEP 1: keep this true while the backend isn't ready (uses the FAKE DATA at the bottom).
// STEP 2: when P1 + P2's endpoints are live, change it to false. Nothing else changes.
const USE_FAKE_DATA = true;

// ---------- login state (keys come from the team contract) ----------
function getToken() { return localStorage.getItem("gate_token"); }

function getUser() {
  try { return JSON.parse(localStorage.getItem("gate_user")) || {}; } catch (e) { return {}; }
}

function logout() {
  localStorage.clear();
  location.href = "login.html";
}

// Call at the top of every page except login.html
function requireLogin() {
  if (!getToken()) location.href = "login.html";
}

// ---------- talking to the server ----------
// Paths are written WITHOUT "/api": callApi adds it.
//   const flats = await callApi("/flats");
//   await callApi("/entries", { method: "POST", body: JSON.stringify({...}) });
async function callApi(path, options = {}) {
  if (USE_FAKE_DATA) return fakeApi(path, options);

  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  const res = await fetch("/api" + path, { ...options, headers });

  // Server says "not logged in" -> clear everything and go back to login
  // (a wrong password on the login page is also a 401, so skip that one)
  if (res.status === 401 && path !== "/login") {
    logout();
    throw new Error("Please log in again");
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // Errors are always { "detail": "message" } (a list if the input was malformed)
    const msg = data && typeof data.detail === "string" ? data.detail : "Something went wrong. Check the details and try again.";
    throw new Error(msg);
  }
  return data;
}

// ---------- small display helpers ----------
// Always run text from the server/user through esc() before putting it in innerHTML
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Entry shape: { flat: {label: "A-101"} | null, staff: {name} | null, visitor_name, ... }
function flatLabel(e) {
  return e.flat ? e.flat.label : "No flat";
}

function entryTitle(e) {
  if (e.entry_type === "staff") return e.staff ? e.staff.name : "Staff";
  return e.visitor_name || (e.entry_type === "delivery" ? "Delivery" : "Visitor");
}

function timeLabel(iso) {
  if (!iso) return "";
  const d = new Date(String(iso).replace(" ", "T")); // Safari needs the "T"
  return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function showMsg(el, text, kind) {
  el.textContent = text;
  el.className = "msg " + (kind || "");
}

// ============================================================
// FAKE DATA - remove once backend is ready
// Pretends to be the server so the pages work today. Shapes match the
// contract exactly. Data lives in localStorage; to reset, run
//   localStorage.removeItem("fake_db")
// in the browser console. Delete this whole section at the end.
// ============================================================
function fakeFlat(id, wing, number) { return { id, wing, number, label: wing + "-" + number }; }

function fakeLoad() {
  let db = JSON.parse(localStorage.getItem("fake_db") || "null");
  if (!db) {
    db = {
      nextId: 2,
      flats: [fakeFlat(1, "A", "101"), fakeFlat(2, "A", "102"), fakeFlat(3, "A", "201"),
              fakeFlat(4, "B", "101"), fakeFlat(5, "B", "102"), fakeFlat(6, "B", "301")],
      staff: [
        { id: 1, name: "Sunita", role: "maid", verification_status: "verified" },
        { id: 2, name: "Ramesh", role: "driver", verification_status: "verified" },
        { id: 3, name: "Geeta", role: "cook", verification_status: "pending" },
        { id: 4, name: "Mohan", role: "cook", verification_status: "not_done" },
      ],
      entries: [
        { id: 1, entry_type: "visitor", flat_id: 1, staff_id: null, visitor_name: "Rahul", entry_time: new Date().toISOString(), exit_time: null },
        { id: 2, entry_type: "delivery", flat_id: 4, staff_id: null, visitor_name: "Amazon", entry_time: new Date().toISOString(), exit_time: null },
      ],
    };
    fakeSave(db);
  }
  return db;
}
function fakeSave(db) { localStorage.setItem("fake_db", JSON.stringify(db)); }

// Turn a stored row into the Entry shape from the contract
function fakeEntry(db, e) {
  return {
    id: e.id, entry_type: e.entry_type,
    flat: db.flats.find((f) => f.id === e.flat_id) || null,
    staff: db.staff.find((s) => s.id === e.staff_id) || null,
    visitor_name: e.visitor_name, visitor_phone: e.visitor_phone || null, note: e.note || null,
    photo_url: null, source: "guard", logged_by: "Demo Guard",
    entry_time: e.entry_time, exit_time: e.exit_time,
  };
}

async function fakeApi(path, options) {
  await new Promise((r) => setTimeout(r, 150)); // pretend the network is slow
  const method = options.method || "GET";
  const body = options.body ? JSON.parse(options.body) : {};
  const url = new URL(path, location.origin);
  const p = url.pathname;
  const db = fakeLoad();

  if (p === "/login" && method === "POST") {
    if (!body.username || !body.password) throw new Error("Wrong username or password");
    return { token: "fake-token", user: { id: 2, username: body.username, full_name: "Demo Guard", role: "guard", society_id: 1 } };
  }
  if (p === "/flats") return db.flats;
  if (p === "/staff") {
    const q = (url.searchParams.get("search") || "").toLowerCase();
    return db.staff.filter((s) => s.name.toLowerCase().includes(q));
  }
  if (p === "/entries/inside") {
    return db.entries.filter((e) => !e.exit_time).map((e) => fakeEntry(db, e));
  }
  if (p === "/entries" && method === "POST") {
    const e = {
      id: ++db.nextId, entry_type: body.entry_type, flat_id: body.flat_id || null,
      staff_id: body.staff_id || null, visitor_name: body.visitor_name || "",
      visitor_phone: body.visitor_phone || "", note: body.note || "",
      entry_time: new Date().toISOString(), exit_time: null,
    };
    db.entries.push(e); fakeSave(db);
    return fakeEntry(db, e);
  }
  const m = p.match(/^\/entries\/(\d+)\/exit$/);
  if (m && method === "POST") {
    const e = db.entries.find((x) => x.id === Number(m[1]));
    if (e) e.exit_time = new Date().toISOString();
    fakeSave(db);
    return fakeEntry(db, e);
  }
  throw new Error("Fake API doesn't know " + p);
}
