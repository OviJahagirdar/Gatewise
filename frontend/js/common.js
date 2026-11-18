// ---------------------------------------------------------------------------
// frontend/committee/js/common.js
// Page helpers shared by every committee page. Owner: Person 4.
// Uses callApi()/getToken()/logout() from js/api.js, so load that one first.
//
//   requireAdmin()        - "is an admin logged in?" guard, call it on page start
//   renderNav(page)       - the dark nav bar at the top
//   escapeHtml / formatDateTime / flatLabel
//   showMessage / clearMessage
// ---------------------------------------------------------------------------

// Call at the top of every page except index.html (login) and onboard.html:
//   const me = await requireAdmin();
//   if (!me) return;
// Asks GET /api/me who is logged in, and turns away anyone who is not an admin
// (a guard login belongs on the guard pages, Person 3's screens).
async function requireAdmin() {
  let me;
  try {
    me = await callApi("/api/me");
  } catch (error) {
    // callApi already sent us to the login page if it was a 401.
    return null;
  }

  if (!me || me.role !== "admin") {
    document.body.innerHTML =
      '<main><div class="card" style="max-width:520px;margin:60px auto">' +
      '<p class="message error">This page is for committee (admin) logins only. ' +
      "Taking you back to the login page…</p></div></main>";
    setTimeout(function () {
      window.location.href = LOGIN_PAGE;
    }, 2500);
    return null;
  }

  localStorage.setItem(USER_KEY, JSON.stringify(me));
  return me;
}

// renderNav("logs.html") draws the bar at the top and marks the current page.
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

// Flats arrive as {id, wing, number, label}; be forgiving if label is missing.
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
