"""
entries.py 

Everything about logging who comes in and out:
  - guard logs a visitor / delivery / staff entry
  - guard marks an exit
  - "who is inside right now" list
  - committee search/filter + CSV download
  - public QR self check-in (no login)
  - admin cleanup: purge old logs, delete everything
"""
import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from database import get_db                      # Person 1's file
from auth import get_current_user, require_admin  # Person 1's file

router = APIRouter(prefix="/api")

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
ENTRY_TYPES = ("visitor", "delivery", "staff")


# ---------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------
class EntryCreate(BaseModel):
    entry_type: str                      # "visitor", "delivery" or "staff"
    flat_id: Optional[int] = None        # required for visitor / delivery
    staff_id: Optional[int] = None       # required for staff
    visitor_name: Optional[str] = None
    visitor_phone: Optional[str] = None
    note: Optional[str] = None


class CheckinForm(BaseModel):
    visitor_name: str
    flat_id: int
    entry_type: str = "visitor"          # "visitor" or "delivery"
    visitor_phone: Optional[str] = None
    note: Optional[str] = None


class DeleteEverythingRequest(BaseModel):
    confirm: str


# ---------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------
def now_iso():
    """Current time (UTC) like 2026-10-05T09:30:00"""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat()


def flat_label(wing, number):
    return f"{wing}-{number}" if wing else number


# One query that gets an entry together with its flat, staff and guard name.
# LEFT JOIN = "include the entry even if there is no flat / staff / guard".
ENTRY_SELECT = """
SELECT e.*,
       f.wing AS f_wing, f.number AS f_number,
       s.name AS s_name, s.role AS s_role, s.verification_status AS s_verification,
       u.full_name AS logged_by_name
FROM entries e
LEFT JOIN flats f ON f.id = e.flat_id
LEFT JOIN staff s ON s.id = e.staff_id
LEFT JOIN users u ON u.id = e.logged_by_user_id
"""


def fetch_entries(db, where_sql, params, limit=None):
    """Run the big SELECT above with a WHERE clause. Newest entries first."""
    sql = ENTRY_SELECT + " WHERE " + where_sql + " ORDER BY e.entry_time DESC, e.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return db.execute(sql, params).fetchall()


def entry_to_dict(row):
    """Turn a database row into the Entry JSON shape from the contract."""
    flat = None
    if row["flat_id"] is not None and row["f_number"] is not None:
        flat = {
            "id": row["flat_id"],
            "wing": row["f_wing"] or "",
            "number": row["f_number"],
            "label": flat_label(row["f_wing"], row["f_number"]),
        }

    staff = None
    if row["staff_id"] is not None and row["s_name"] is not None:
        staff = {
            "id": row["staff_id"],
            "name": row["s_name"],
            "role": row["s_role"],
            "verification_status": row["s_verification"],
        }

    return {
        "id": row["id"],
        "entry_type": row["entry_type"],
        "flat": flat,
        "staff": staff,
        "visitor_name": row["visitor_name"],
        "visitor_phone": row["visitor_phone"],
        "note": row["note"],
        "photo_url": ("/uploads/" + row["photo_path"]) if row["photo_path"] else None,
        "source": row["source"],
        "logged_by": row["logged_by_name"],
        "entry_time": row["entry_time"],
        "exit_time": row["exit_time"],
    }


def get_entry_or_404(db, entry_id, society_id):
    rows = fetch_entries(db, "e.id = ? AND e.society_id = ?", (entry_id, society_id))
    if not rows:
        raise HTTPException(status_code=404, detail="Entry not found")
    return rows[0]


def build_filters(society_id, date_from, date_to, entry_type, flat_id, search):
    """
    Build the WHERE part of the query for the logs list and the CSV export.
    The society_id condition is ALWAYS included - this keeps societies separate.
    Dates are compared as UTC dates (YYYY-MM-DD).
    """
    where = "e.society_id = ?"
    params = [society_id]

    if date_from:
        where += " AND date(e.entry_time) >= ?"
        params.append(date_from)
    if date_to:
        where += " AND date(e.entry_time) <= ?"
        params.append(date_to)
    if entry_type:
        where += " AND e.entry_type = ?"
        params.append(entry_type)
    if flat_id:
        where += " AND e.flat_id = ?"
        params.append(flat_id)
    if search:
        where += " AND (e.visitor_name LIKE ? OR e.visitor_phone LIKE ? OR s.name LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])

    return where, params


def delete_photo_file(photo_path):
    """Delete a photo file from the uploads folder, if it exists."""
    if photo_path:
        path = UPLOADS_DIR / photo_path
        if path.exists():
            path.unlink()


# ---------------------------------------------------------------
# Guard routes: log entries
# ---------------------------------------------------------------
@router.post("/entries", status_code=201)
def create_entry(body: EntryCreate, request: Request):
    """Log a visitor / delivery / staff entry."""
    user = get_current_user(request)

    if body.entry_type not in ENTRY_TYPES:
        raise HTTPException(status_code=422, detail="entry_type must be visitor, delivery or staff")

    db = get_db()
    try:
        flat_id = None
        staff_id = None

        if body.entry_type in ("visitor", "delivery"):
            if body.flat_id is None:
                raise HTTPException(status_code=422, detail="flat_id is required for visitors and deliveries")
            flat = db.execute(
                "SELECT id FROM flats WHERE id = ? AND society_id = ?",
                (body.flat_id, user["society_id"]),
            ).fetchone()
            if flat is None:
                raise HTTPException(status_code=404, detail="Flat not found")
            flat_id = body.flat_id

        else:  # staff
            if body.staff_id is None:
                raise HTTPException(status_code=422, detail="staff_id is required for staff entries")
            staff = db.execute(
                "SELECT id FROM staff WHERE id = ? AND society_id = ? AND is_active = 1",
                (body.staff_id, user["society_id"]),
            ).fetchone()
            if staff is None:
                raise HTTPException(status_code=404, detail="Staff member not found")
            already_inside = db.execute(
                "SELECT id FROM entries WHERE society_id = ? AND staff_id = ? AND exit_time IS NULL",
                (user["society_id"], body.staff_id),
            ).fetchone()
            if already_inside:
                raise HTTPException(status_code=409, detail="This staff member is already inside")
            staff_id = body.staff_id

        cursor = db.execute(
            """INSERT INTO entries
               (society_id, entry_type, flat_id, staff_id, visitor_name, visitor_phone,
                note, source, logged_by_user_id, entry_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'guard', ?, ?)""",
            (
                user["society_id"], body.entry_type, flat_id, staff_id,
                body.visitor_name, body.visitor_phone, body.note,
                user["id"], now_iso(),
            ),
        )
        db.commit()
        return entry_to_dict(get_entry_or_404(db, cursor.lastrowid, user["society_id"]))
    finally:
        db.close()


@router.post("/entries/{entry_id}/exit")
def mark_exit(entry_id: int, request: Request):
    """Mark that the person has left."""
    user = get_current_user(request)
    db = get_db()
    try:
        entry = get_entry_or_404(db, entry_id, user["society_id"])
        if entry["exit_time"] is not None:
            raise HTTPException(status_code=409, detail="This entry already has an exit time")

        db.execute("UPDATE entries SET exit_time = ? WHERE id = ?", (now_iso(), entry_id))
        db.commit()
        return entry_to_dict(get_entry_or_404(db, entry_id, user["society_id"]))
    finally:
        db.close()


@router.get("/entries/inside")
def entries_inside(request: Request):
    """Everyone who has entered but not exited yet. Newest first."""
    user = get_current_user(request)
    db = get_db()
    try:
        rows = fetch_entries(db, "e.society_id = ? AND e.exit_time IS NULL", (user["society_id"],))
        return [entry_to_dict(row) for row in rows]
    finally:
        db.close()


# ---------------------------------------------------------------
# Committee routes: search, filter, export
# ---------------------------------------------------------------
@router.get("/entries")
def list_entries(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    entry_type: Optional[str] = None,
    flat_id: Optional[int] = None,
    search: Optional[str] = None,
):
    """Filtered list of entries. Admin only. All filters are optional."""
    user = require_admin(request)
    where, params = build_filters(user["society_id"], date_from, date_to, entry_type, flat_id, search)
    db = get_db()
    try:
        rows = fetch_entries(db, where, params, limit=500)  # 500 newest rows is plenty for the MVP
        return [entry_to_dict(row) for row in rows]
    finally:
        db.close()


@router.get("/entries/export-csv")
def export_entries_csv(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    entry_type: Optional[str] = None,
    flat_id: Optional[int] = None,
    search: Optional[str] = None,
):
    """Same filters as the list above, but returns a CSV file. Admin only."""
    user = require_admin(request)
    where, params = build_filters(user["society_id"], date_from, date_to, entry_type, flat_id, search)
    db = get_db()
    try:
        rows = fetch_entries(db, where, params)
    finally:
        db.close()

    # Write the CSV into memory (a text buffer), then send it as a download
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "entry_type", "visitor_name", "flat", "staff_name",
                     "note", "source", "entry_time", "exit_time"])
    for row in rows:
        flat = flat_label(row["f_wing"], row["f_number"]) if row["f_number"] else ""
        writer.writerow([
            row["id"], row["entry_type"], row["visitor_name"] or "", flat,
            row["s_name"] or "", row["note"] or "", row["source"],
            row["entry_time"], row["exit_time"] or "",
        ])

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="entries.csv"'},
    )


# ---------------------------------------------------------------
# Public QR check-in (NO login needed - the society is found from the qr_token)
# ---------------------------------------------------------------
def find_society_by_qr(db, qr_token):
    society = db.execute("SELECT * FROM societies WHERE qr_token = ?", (qr_token,)).fetchone()
    if society is None:
        raise HTTPException(status_code=404, detail="Invalid QR code")
    return society


@router.get("/checkin/{qr_token}")
def checkin_info(qr_token: str):
    """Society name + flat list, so the visitor's form can show a flat dropdown."""
    db = get_db()
    try:
        society = find_society_by_qr(db, qr_token)
        rows = db.execute(
            "SELECT id, wing, number FROM flats WHERE society_id = ? ORDER BY wing, number",
            (society["id"],),
        ).fetchall()
        flats = [
            {"id": r["id"], "wing": r["wing"] or "", "number": r["number"],
             "label": flat_label(r["wing"], r["number"])}
            for r in rows
        ]
        return {"society_name": society["name"], "flats": flats}
    finally:
        db.close()


@router.post("/checkin/{qr_token}", status_code=201)
def checkin_submit(qr_token: str, body: CheckinForm):
    """A visitor checks themselves in."""
    if not body.visitor_name.strip():
        raise HTTPException(status_code=422, detail="Name is required")
    if body.entry_type not in ("visitor", "delivery"):
        raise HTTPException(status_code=422, detail="entry_type must be visitor or delivery")

    db = get_db()
    try:
        society = find_society_by_qr(db, qr_token)
        flat = db.execute(
            "SELECT id FROM flats WHERE id = ? AND society_id = ?",
            (body.flat_id, society["id"]),
        ).fetchone()
        if flat is None:
            raise HTTPException(status_code=404, detail="Flat not found")

        cursor = db.execute(
            """INSERT INTO entries
               (society_id, entry_type, flat_id, visitor_name, visitor_phone,
                note, source, logged_by_user_id, entry_time)
               VALUES (?, ?, ?, ?, ?, ?, 'qr', NULL, ?)""",
            (society["id"], body.entry_type, body.flat_id, body.visitor_name.strip(),
             body.visitor_phone, body.note, now_iso()),
        )
        db.commit()
        return {"entry_id": cursor.lastrowid, "message": "Check-in recorded"}
    finally:
        db.close()


# ---------------------------------------------------------------
# Admin cleanup routes
# ---------------------------------------------------------------
@router.post("/admin/purge-old")
def purge_old(request: Request):
    """
    Delete visitor/delivery entries older than the society's retention_days.
    Staff entries are never deleted here.
    """
    user = require_admin(request)
    db = get_db()
    try:
        society = db.execute(
            "SELECT retention_days FROM societies WHERE id = ?", (user["society_id"],)
        ).fetchone()
        days = (society["retention_days"] if society else None) or 90
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)).isoformat()

        where = "society_id = ? AND entry_type IN ('visitor', 'delivery') AND entry_time < ?"
        old_rows = db.execute(f"SELECT photo_path FROM entries WHERE {where}",
                              (user["society_id"], cutoff)).fetchall()
        for r in old_rows:
            delete_photo_file(r["photo_path"])

        cursor = db.execute(f"DELETE FROM entries WHERE {where}", (user["society_id"], cutoff))
        db.commit()
        return {"deleted": cursor.rowcount}
    finally:
        db.close()


@router.post("/admin/delete-everything")
def delete_everything(body: DeleteEverythingRequest, request: Request):
    """Delete ALL entries and ALL staff of this society. Needs {"confirm": "DELETE"}."""
    user = require_admin(request)
    if body.confirm != "DELETE":
        raise HTTPException(status_code=422, detail='Send {"confirm": "DELETE"} to confirm')

    society_id = user["society_id"]
    db = get_db()
    try:
        # Remove photo files first
        for r in db.execute("SELECT photo_path FROM entries WHERE society_id = ?", (society_id,)).fetchall():
            delete_photo_file(r["photo_path"])
        for r in db.execute("SELECT photo_path FROM staff WHERE society_id = ?", (society_id,)).fetchall():
            delete_photo_file(r["photo_path"])

        deleted_entries = db.execute("DELETE FROM entries WHERE society_id = ?", (society_id,)).rowcount
        db.execute("DELETE FROM staff_flats WHERE staff_id IN (SELECT id FROM staff WHERE society_id = ?)",
                   (society_id,))
        deleted_staff = db.execute("DELETE FROM staff WHERE society_id = ?", (society_id,)).rowcount
        db.commit()
        return {"deleted_entries": deleted_entries, "deleted_staff": deleted_staff}
    finally:
        db.close()