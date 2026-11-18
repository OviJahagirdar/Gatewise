# Society Gate — Blueprint

The one-page technical picture of the project: what the pieces are, who owns each
one, how a click in the browser travels to the database and back, and which
assumptions still need confirming. Written and maintained by Person 4.

---

## 1. What we are building (and not building)

A website that replaces a society's paper gate register. Three users, three jobs:

| User | Device | Job |
|---|---|---|
| Guard | phone browser | Log a visitor / delivery / staff member in a few taps, mark exits |
| Committee member (admin) | laptop browser | See, filter and export the log; manage flats, logins and staff; QR link; retention |
| Visitor | own phone | Scan the QR at the gate and check themselves in |

Phase 1 only: no resident app, no approvals, no push notifications, no payments,
no offline mode, no translations, no deployment. Running on one laptop is enough.

## 2. Architecture

```
Phone / laptop browser        FastAPI (Python)              SQLite
  plain HTML + CSS + JS  -->  backend/*.py routes      -->  app.db (one file)
  fetch('/api/...')           plain sqlite3, no ORM         7 tables
```

- No React/Vue, no npm, no bundler, no build step.
- No ORM, no Alembic, no services layer. Raw SQL strings through `sqlite3`.
- Login is a random token in the `sessions` table, sent as
  `Authorization: Bearer <token>` (the "coat-check ticket" model).

## 3. Files and owners

```
society-gate/
├─ README.md                              P4
├─ docs/BLUEPRINT.md  docs/DEMO_SCRIPT.md P4
├─ requirements.txt  .gitignore           P1
├─ backend/
│  ├─ main.py database.py auth.py
│  │  flats_and_users.py seed.py          P1
│  ├─ staff.py  entries.py                P2
│  └─ tests/test_integration_flow.py
│     tests/test_isolation.py             P4
└─ frontend/
   ├─ guard/   login.html home.html entry.html staff.html app.js   P3
   ├─ committee/
   │  ├─ index.html onboard.html logs.html flats.html
   │  │  users.html staff.html settings.html                       P4
   │  ├─ css/committee.css                                         P4
   │  └─ js/api.js  js/common.js                                   P4
   └─ checkin/ index.html  js/checkin.js                           P4
```

Rule: nobody edits another person's files. Need a change there? Ask that person.

## 4. How one action travels (log a visitor)

1. The guard taps **Save** on the guard page (P3), which calls
   `callApi("/api/entries", {method: "POST", body: …})`.
2. `callApi` attaches `Authorization: Bearer <token>` from `localStorage`.
3. FastAPI's `/api/entries` route (P2) calls `get_current_user(request)` (P1),
   which looks the token up in `sessions` and returns the user row — **including
   `society_id`**.
4. The route inserts one row into `entries` with that `society_id`.
5. It answers with the exact JSON shape from the contract, including the nested
   `flat` object.
6. That entry later appears on the committee's `logs.html` through
   `GET /api/entries?date_from=…`, and in the CSV export.

Anything that fails answers `{"detail": "message"}`, which the pages show in a
red message box.

## 5. The isolation rule (most important thing in the backend)

Every route except `POST /api/societies`, `POST /api/login`,
`GET /api/checkin/{t}` and `POST /api/checkin/{t}`:

- gets `society_id` from `get_current_user(request)`, **never** from the request;
- filters every SQL query with `WHERE society_id = ?`.

`backend/tests/test_isolation.py` is the proof: two societies are created and the
test asserts neither can list, read or edit the other's flats, staff or entries,
that a spoofed `society_id` in a request body is ignored, that QR check-ins land
in the right society, and that `delete-everything` only empties its own log.

## 6. Data model (7 tables, all created in `backend/database.py`)

| Table | Columns that matter |
|---|---|
| `societies` | id, name, city, retention_days, **qr_token** (used by the public QR link) |
| `users` | id, society_id, username (unique), password_hash, full_name, role (`admin`/`guard`) |
| `sessions` | token (PK), user_id, created_at |
| `flats` | id, society_id, wing, number |
| `staff` | id, society_id, name, role, photo_path, verification_status (`not_done`/`pending`/`verified`), verification_date, qr_code, is_active |
| `staff_flats` | staff_id, flat_id |
| `entries` | id, society_id, entry_type, flat_id, staff_id, visitor_name, visitor_phone, note, photo_path, source (`guard`/`qr`), logged_by_user_id, entry_time, exit_time |

JSON shapes (exact, from the team contract): `User`, `Society`, `Flat`
(`{id, wing, number, label}`), `Staff` (with `photo_url`, `flats[]`,
`is_active`), `Entry` (with nested `flat`, `staff`, `photo_url`, `logged_by`).

## 7. Page ↔ endpoint map

| Page (P4) | Endpoints it calls |
|---|---|
| `committee/index.html` (login) | `POST /api/login` |
| `committee/onboard.html` | `POST /api/societies`, `POST /api/login` |
| `committee/logs.html` | `GET /api/entries`, `GET /api/entries/export-csv` |
| `committee/flats.html` | `GET /api/flats`, `POST /api/flats`, `POST /api/flats/upload-csv` |
| `committee/users.html` | `GET /api/users`, `POST /api/users` |
| `committee/staff.html` | `GET /api/staff`, `POST /api/staff`, `GET /api/staff/{id}`, `PATCH /api/staff/{id}`, `POST /api/staff/{id}/photo`, `GET /api/flats` |
| `committee/settings.html` | `POST /api/admin/purge-old`, `POST /api/admin/delete-everything`, `PATCH /api/society`*, `GET /api/society`* |
| `checkin/index.html` | `GET /api/checkin/{t}`, `POST /api/checkin/{t}` |
| every page except login/onboard | `GET /api/me` (the `requireAdmin()` guard) |

\* not in the contract yet — see §9.

## 8. Frontend conventions (P4's pages)

- `js/api.js` — `callApi()`, `getToken()`, `saveLogin()`, `logout()`,
  `LOGIN_PAGE`. All requests go through `callApi`, which adds the token, turns a
  401 into a redirect to `index.html`, and throws the server's `detail` message.
- `js/common.js` — `requireAdmin()` (calls `GET /api/me`, rejects guard logins),
  `renderNav()`, `escapeHtml()`, `formatDateTime()`, `flatLabel()`,
  `showMessage()` / `clearMessage()`.
- `css/committee.css` — the only stylesheet; desktop layout, one file.
- Page scripts run inside `(async function start() { … })()` — check the admin
  login first, then draw the nav, then load data.
- Responses are accepted as either a plain list or `{entries: […]}` /
  `{flats: […]}` / `{staff: […]}` / `{users: […]}`, so the backend can pick either.
- The CSV button uses `fetch` + `Blob` + a temporary `<a download>` because a
  plain `<a href>` cannot carry the Authorization header.
- Delete-everything stays disabled until the exact word `DELETE` is typed.

## 9. Assumptions that still need a thumbs-up

The contract fixes URLs and response shapes but not every request body, so the
frontend sends the obvious version. If the backend differs, change one
`JSON.stringify({...})` in that page.

| Call | Body sent |
|---|---|
| `POST /api/societies` | `{name, city, full_name, username, password}` |
| `POST /api/flats` | `{wing, number}` |
| `POST /api/flats/upload-csv` | multipart, file field `file` |
| `POST /api/users` | `{full_name, username, password, role}` |
| `POST /api/staff` | `{name, role, verification_status, flat_ids: [id,…]}` |
| `PATCH /api/staff/{id}` | `{name, role, verification_status, verification_date, is_active, flat_ids}` |
| `POST /api/staff/{id}/photo` | multipart, file field `file` |
| `POST /api/entries` | `{entry_type, flat_id, staff_id, visitor_name, visitor_phone, note}` |
| `POST /api/checkin/{t}` | `{visitor_name, visitor_phone, flat_id, entry_type}` |

Missing endpoints, needed by `settings.html`:

1. `PATCH /api/society` `{retention_days}` — otherwise the retention field can
   only be displayed.
2. `GET /api/society` — otherwise the page falls back to the society row cached
   in `localStorage` at login/onboarding, which must contain `retention_days`
   and `qr_token`.

## 10. Testing strategy

| Layer | What | Where |
|---|---|---|
| Integration | The full journey: society → flat → guard → staff → visitor → exit → filtered log → CSV → QR check-in → purge → delete-everything; plus guard-cannot-wipe and anonymous-requests-refused | `backend/tests/test_integration_flow.py` |
| Isolation | Two societies cannot see or change each other's data; spoofed `society_id` ignored | `backend/tests/test_isolation.py` |
| Manual | The click-through checklist in `README.md` §4, on the laptop plus one phone pass | `README.md` |

Run the automated ones with `pip install pytest httpx` then
`pytest backend/tests -v` from the `society-gate` folder. Each test creates its
own society, so the tests never wipe demo data. Until P1/P2's backend exists the
test files skip themselves with a clear message.

## 11. Risks and how we handle them

| Risk | Mitigation |
|---|---|
| Endpoint/JSON mismatch between people | Everyone works from the same contract; pages tolerate list-or-wrapped responses; this document lists every request body |
| One society seeing another's data | Isolation test fails loudly before a demo |
| CSV download "not logged in" | Token is sent via `fetch`, never a bare link |
| Accidental data wipe | Typed `DELETE` confirmation, and a guard gets a 403 |
| No internet at the demo venue | Pico-style CDN CSS is not used; all CSS is local, no external requests |
| Backend still unfinished late | Pages show the backend's error message instead of a blank screen; the test suite tells you exactly which endpoint is missing |

## 12. Out of scope for this month

Translations, offline mode, camera QR scanning, resident/approval flows, push
notifications, password resets, token expiry, deployment.
