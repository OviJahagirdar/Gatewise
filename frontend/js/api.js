// ---------------------------------------------------------------------------
// frontend/committee/js/api.js
// The network + login-token layer shared by every committee page.
// Owner: Person 4.
//
//   getToken()             - the saved login token, or null
//   saveLogin(data)        - stores whatever POST /api/login returned
//   logout()               - forgets the login and goes to index.html
//   callApi(path, options) - fetch() with the Authorization header added
//
// Load order on every page:  js/api.js  ->  js/common.js  ->  page script.
// ---------------------------------------------------------------------------

// The backend's login route gives us a random token string. We keep it in
// localStorage and send it back as "Authorization: Bearer <token>".
const TOKEN_KEY = "gate_token";
const USER_KEY = "gate_user";
const SOCIETY_KEY = "gate_society"; // cached society row: name, retention_days, qr_token

// Where pages go when there is no valid login. index.html is the login page.
const LOGIN_PAGE = "index.html";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

// Saves whatever the login / onboard / me response contained and returns token.
// The backend sends {token: "...", user: {...}}; {access_token} is accepted too.
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
  // The society cache is not a secret and is handy for the QR link later.
  window.location.href = LOGIN_PAGE;
}

// callApi("/api/flats") or callApi("/api/flats", { method: "POST", body: ... })
// - adds the saved token to every request
// - sends the user back to the login page when the server answers 401
// - throws an Error carrying the server's {"detail": "..."} message otherwise
async function callApi(path, options) {
  const settings = options || {};
  const headers = Object.assign({}, settings.headers || {});

  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  // A string body is JSON. A FormData body (file uploads) must NOT get a
  // Content-Type: the browser sets it, including the multipart boundary.
  if (typeof settings.body === "string" && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, Object.assign({}, settings, { headers: headers }));

  if (response.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.location.href = LOGIN_PAGE;
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
