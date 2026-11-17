# Society Gate App

A simple website that replaces the paper visitor register of a small residential society (20–150 flats).

- **Guards** log visitors, deliveries and daily staff (maids, cooks, drivers) from a phone browser in a few taps.
- **Committee members** see, search and export every entry, and manage flats, guards and registered staff.
- **Visitors** can self check-in by scanning a QR code when there is no guard at the gate.
- Each society's data is kept separate, and the society can export or delete it.

> College group project (MVP). Built to be understood, not to be production-grade.

---

## Tech stack

| Part | Technology | Why |
|---|---|---|
| Server | Python + FastAPI | Turns Python functions into web endpoints |
| Database | SQLite (plain `sqlite3`, no ORM) | One file, nothing to install |
| Frontend | Plain HTML, CSS, JavaScript | No framework, no build step |
| Login | Random token stored in a `sessions` table | Simple "coat-check ticket" login |

```
Browser (HTML/JS)  →  FastAPI (backend/*.py)  →  SQLite (app.db)
```

---

## Project structure

```
society-gate/
├─ README.md
├─ requirements.txt
├─ .gitignore
├─ backend/
│  ├─ main.py               starts the app, wires everything together
│  ├─ database.py           connects to SQLite, creates the tables
│  ├─ auth.py               login, tokens, get_current_user / require_admin
│  ├─ flats_and_users.py    flats and guard/committee accounts
│  ├─ seed.py               fills in demo data
│  ├─ staff.py              domestic staff registry
│  └─ entries.py            visitor/delivery/staff log, QR check-in, export, cleanup
├─ uploads/                 photos (created automatically, not in Git)
├─ app.db                   the database (created automatically, not in Git)
└─ frontend/
   ├─ guard/                guard phone app
   ├─ committee/            committee web panel
   └─ checkin/              public QR self check-in page
```

---

## Getting started

You need **Python 3.10 or newer** and Git.

```bash
# 1. Get the code
git clone <repo-url>
cd society-gate

# 2. Create and activate a virtual environment (keeps packages isolated)
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
.venv\Scripts\activate             # Windows

# 3. Install packages
pip install -r requirements.txt

# 4. Create demo data (safe to run more than once)
cd backend
python seed.py

# 5. Start the server (still inside backend/)
uvicorn main:app --reload
```

Now open:

| What | URL |
|---|---|
| Guard app | http://localhost:8000/guard/login.html |
| Committee panel | http://localhost:8000/committee/login.html |
| Create a new society | http://localhost:8000/committee/onboard.html |
| QR check-in page | http://localhost:8000/checkin/?t=`<qr_token>` (shown in Committee → Settings) |
| API docs (try endpoints) | http://localhost:8000/docs |

### Demo accounts (created by `seed.py`)

| Role | Username | Password |
|---|---|---|
| Committee admin | `admin` | `admin123` |
| Guard | `guard` | `guard123` |

### Trying it on a real phone
Connect the phone to the same Wi-Fi as your laptop, start the server with `uvicorn main:app --reload --host 0.0.0.0`, and open `http://<your-laptop-ip>:8000/guard/login.html`.

---

## What the app can do (MVP)

- [x] Create a society and its first admin login
- [x] Add flats one by one or upload them from a CSV (`wing,number`)
- [x] Add guard / committee logins
- [x] Register domestic staff (role, flats served, police-verification status and date, photo)
- [x] Guard logs a visitor or delivery by picking a flat
- [x] Guard logs registered staff in/out with one tap
- [x] Guard marks exits; "who is inside now" list
- [x] Committee searches/filters the log and downloads it as CSV
- [x] Visitor self check-in via QR code
- [x] Retention cleanup of old visitor/delivery logs, and delete-all-data

### Not in the MVP
Offline mode, Hindi/Marathi translations, camera scanning of staff QR badges, resident app, approvals, push notifications, payments, password reset, token expiry, online deployment.

---

## API overview

All endpoints start with `/api`. Logged-in requests send the header `Authorization: Bearer <token>` (the token comes from `POST /api/login`). Errors look like `{"detail": "message"}`. Full details are in the team contract; try everything interactively at `/docs`.

| Area | Endpoints |
|---|---|
| Society & login | `POST /societies`, `POST /login`, `GET /me` |
| Flats | `GET /flats`, `POST /flats`, `POST /flats/upload-csv` |
| Users | `GET /users`, `POST /users` |
| Staff | `POST /staff`, `GET /staff`, `GET /staff/{id}`, `PATCH /staff/{id}`, `POST /staff/{id}/photo` |
| Entries | `POST /entries`, `POST /entries/{id}/exit`, `GET /entries/inside`, `GET /entries`, `GET /entries/export-csv` |
| QR check-in (no login) | `GET /checkin/{qr_token}`, `POST /checkin/{qr_token}` |
| Admin | `POST /admin/purge-old`, `POST /admin/delete-everything` |

### Database tables
`societies`, `users`, `sessions`, `flats`, `staff`, `staff_flats`, `entries` — created automatically by `backend/database.py`. Every society-owned row has a `society_id`, and every query filters by the logged-in user's society so societies never see each other's data.

---

## Team and file ownership

Each person edits **only their own files**, which is what avoids Git conflicts.

| Person | Role | Files |
|---|---|---|
| P1 | Database, login, flats, users | `backend/main.py`, `database.py`, `auth.py`, `flats_and_users.py`, `seed.py`, `requirements.txt`, `.gitignore` |
| P2 | Staff and entries | `backend/staff.py`, `backend/entries.py` |
| P3 | Guard app | `frontend/guard/*` |
| P4 | Committee panel, QR page, testing, docs | `frontend/committee/*`, `frontend/checkin/*`, `README.md` |

Need a change in someone else's file, a URL, or a JSON field name? Ask that person first — everyone's code depends on those exact names.

### Daily Git routine
```bash
git pull                       # get everyone's latest work
# ...edit your own files...
git add .
git commit -m "short description of what you did"
git pull                       # again, before pushing
git push
```
If `git pull` reports a conflict: open the file, keep the lines you want, delete the `<<<<<<<`, `=======`, `>>>>>>>` marker lines, then `git add .`, `git commit`, `git push`.

---

## Manual test checklist (run before the demo)

1. Create a society at `/committee/onboard.html` and land on the logs page.
2. Add a flat, then upload a small flats CSV.
3. Add a guard account.
4. Register a staff member with verification status and a photo.
5. Log in to the guard app and log a visitor (target: under 15 seconds).
6. Log the registered staff member in, then out (target: under 5 seconds).
7. Mark the visitor as exited.
8. Open the committee logs: both entries appear; filters work; CSV downloads and opens.
9. Open the QR check-in link in a private window, submit the form, confirm it shows in the logs with source `qr`.
10. Create a second society and confirm it cannot see the first society's data.
11. Try purge-old and delete-everything (the latter must require typing `DELETE`).

---

## Known limitations

- Passwords use simple salted SHA-256 hashing and tokens never expire — fine for a demo, not for production.
- Uploaded photos are served from `/uploads` using random file names, without a login check.
- No automatic tests; verification is the manual checklist above.
- Runs on one machine; no deployment setup.

## Notes

This project is based on a confidential student brief. Do not publish the repo or share the brief outside the team, and check your college's IP policy for student projects.
