# Demo script — Society Gate

A 10-minute walkthrough for the final presentation, plus the setup and fallbacks
so it does not fall apart in front of the examiner. Owner: Person 4.

**The story we tell:** "Every society has a paper register at the gate. It gets
lost, it is unreadable, and nobody can search it. We replaced it with one page a
guard can use in 15 seconds, a laptop view the committee can filter and export,
and a QR code for visitors when no guard is around."

---

## 0. Ten minutes before the demo

- [ ] `source .venv/Scripts/activate` (Windows) and `pip install -r requirements.txt`.
- [ ] `python -m backend.seed` — demo society, admin login, guard login, flats.
- [ ] `uvicorn backend.main:app --reload` — check the terminal for the "Uvicorn running" line.
- [ ] Open these tabs, in this order, and leave them open:
  1. `http://localhost:8000/committee/index.html` (logged out)
  2. `http://localhost:8000/committee/logs.html` (after logging in as admin)
  3. `http://localhost:8000/guard/login.html`
  4. `http://localhost:8000/committee/settings.html` (for the QR link)
- [ ] A second browser profile (or incognito window) ready for the guard login.
- [ ] Phone on the same WiFi, with the QR link already typed once so it loads fast.
- [ ] `flats.csv` on the Desktop with two new rows, e.g. `wing,number` + `C,201` + `C,202`.
- [ ] `pytest backend/tests -v` run once: all green, so you know the story will work.
- [ ] Close every other app so notifications do not pop up on the projector.

**Cast:** speaker (P4), "guard" (P3), "committee member" (P1 or P2). Two people
clicking is more convincing than one person switching tabs.

---

## 1. The problem — 30 seconds (no clicking)

> "Our society's gate register is one notebook. Entries are illegible, the
> notebook gets lost, and if you want 'every delivery last Tuesday' you flip
> pages. We built a website that replaces it. Same gate, same guard, no new
> hardware — the guard's phone and a laptop."

## 2. Create a society — 1 minute (P4, committee tab)

1. Open `/committee/index.html`, click **Create a new society**.
2. Fill in: `Green Valley`, `Pune`, your name, username `demo_admin`, password `demo1234`.
3. Click **Create society and log in** → you land on **Gate logs**, logged in.

> "Onboarding is one form: the society, and the first committee login. No install,
> no licence, no server of our own."

## 3. Add flats and a guard — 1 minute

1. **Flats** → add `B` / `202` → it appears in the table.
2. Click **Choose file**, pick `flats.csv` → "2 created, 0 skipped".
3. **Users** → add `Ramu Guard`, username `ramu`, password `ramu123`, role **Guard**.

> "Flats can be typed one by one or uploaded once from a CSV, which is what a
> committee would actually do — they already have the list in Excel."

## 4. Register domestic staff — 1 minute

1. **Staff** → name `Sunita`, role `maid`, verification `pending`, pick flat `B-202`.
2. Click the new row → change verification to **verified**, set today's date, **Save changes**.
3. Upload a photo (any image) → it appears.

> "Maids, cooks and drivers get one record, checked once, with a photo and which
> flats they serve. The guard never types their name again."

## 5. The guard logs a visitor — 1 minute 30 (P3, incognito tab, phone-size window)

1. `/guard/login.html` → `ramu` / `ramu123`.
2. **Visitor** → pick `B-202` → name `Rahul` → Save.
3. Show the "inside now" list, then tap **Exit** on Rahul.

> "Fifteen seconds, two taps and a name. That is the whole point: the guard is
> standing at a gate, not sitting at a desk."

## 6. Committee sees it — 1 minute (P4, logs tab)

1. Refresh **Logs**: the Rahul row is there — time, type, name, flat, source `guard`, exit time.
2. Filter: type `Visitor`, search `Rahul` → one row.
3. Click **Download CSV** → open the file → the same row is there.

> "This is the part the paper register cannot do: filter last week's deliveries,
> or hand the committee a spreadsheet at the monthly meeting."

## 7. QR self check-in — 2 minutes (phone)

1. **Settings** → show the big QR link.
2. Open the link on the phone (no login) → society name, name, phone, flat, Visitor/Delivery.
3. Submit → "✓ Check-in recorded, please wait at the gate."
4. Back on the laptop, refresh **Logs** → the new row with source `qr`.

> "When there is no guard — a Sunday, a late courier — the visitor scans the code
> taped at the gate and logs themselves. Same log, marked as self check-in."

## 8. Retention and clean-up — 45 seconds

1. **Settings** → retention `90` days → Save.
2. **Purge old entries** → "0 old entries removed" (correct: everything is new).
3. Type `DELETE` in the box, point out the button only then becomes clickable.

> "Old logs get cleared on a schedule, and wiping everything needs the word DELETE
> typed out — we do not ship a one-click delete."

## 9. Close — 30 seconds

> "One Python server, one database file, plain HTML and JavaScript — four students,
> one month, no frameworks. It runs on the society's laptop today, and the same
> code can be hosted later without a rewrite."

---

## Fallbacks if something breaks

| Problem | What to do, in front of the examiner |
|---|---|
| A page shows a red error | Read the message out loud — it comes from the server, so it is a real error, not a mystery. Switch to your prepared backup. |
| Server crashed / terminal closed | Restart `uvicorn backend.main:app --reload`. Data is still in `app.db`. |
| Login fails | You are probably in the wrong browser profile; the token lives per profile. Log in again in the same window. |
| CSV download does nothing | Show the file you downloaded during rehearsal and explain the fetch+Blob approach. |
| QR page says Invalid QR code | The `?t=` token was copied with a missing character — open it from Settings → **Copy link**. |
| Phone cannot reach localhost | Run uvicorn with `--host 0.0.0.0` and use `http://<laptop-ip>:8000`; if the WiFi blocks it, present the phone steps as screenshots. |
| Automated tests fail mid-demo | Do not debug live. Say "our test suite covers this journey; let me show you the manual run" and continue. |

## Questions we should be ready for

- **"Where is the data stored?"** One SQLite file, `app.db`, next to the code. No
  separate database server to install.
- **"Is one society able to see another's data?"** No. Every route takes
  `society_id` from the logged-in user's row, never from the browser, and every
  query filters on it. There is a test for exactly this.
- **"How is the login secured?"** Passwords are hashed, and a random token in the
  `sessions` table acts as the ticket. It is deliberately simple for an MVP; token
  expiry and password reset are listed as future work.
- **"What about no internet?"** Out of scope this month; the app runs on a local
  network only. Noted in the README's limitations.
- **"Could this work for a real society?"** It is Phase 1: register replacement.
  Hosting and a resident app are the next phases.

## After the demo

1. **Settings** → type `DELETE` → **Delete everything** to clear the demo log,
   or delete `app.db` and run `python -m backend.seed` again.
2. Keep the successful `pytest backend/tests -v` output — useful in the report.
