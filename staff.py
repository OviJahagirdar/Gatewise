"""
staff.py 

Routes for the domestic staff registry (maids, cooks, drivers, ...).

What this file does, in plain words:
  - register a new staff member
  - list / search staff
  - get one staff member
  - update a staff member (admin only), e.g. change verification status
  - upload a staff photo
"""
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from database import get_db                      # Person 1's file
from auth import get_current_user, require_admin  # Person 1's file

# A "router" is a group of routes. main.py plugs it into the app.
# The prefix means every route below starts with /api.
router = APIRouter(prefix="/api")

# Photos are saved in the "uploads" folder at the top of the project.
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"

VERIFICATION_STATUSES = ("not_done", "pending", "verified")
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------
# Request bodies. Pydantic checks incoming JSON has these fields.
# ---------------------------------------------------------------
class StaffCreate(BaseModel):
    name: str
    role: str
    flat_ids: List[int] = []
    verification_status: str = "not_done"
    verification_date: Optional[str] = None  # e.g. "2026-08-10"


class StaffUpdate(BaseModel):
    # Everything is optional: send only the fields you want to change.
    name: Optional[str] = None
    role: Optional[str] = None
    flat_ids: Optional[List[int]] = None
    verification_status: Optional[str] = None
    verification_date: Optional[str] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------
def flat_label(wing, number):
    """'A' + '101' -> 'A-101'. If there is no wing, just '101'."""
    return f"{wing}-{number}" if wing else number


def get_staff_flats(db, staff_id):
    """Return the list of flats this staff member works in."""
    rows = db.execute(
        """SELECT f.id, f.wing, f.number
           FROM flats f
           JOIN staff_flats sf ON sf.flat_id = f.id
           WHERE sf.staff_id = ?
           ORDER BY f.wing, f.number""",
        (staff_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "wing": r["wing"] or "",
            "number": r["number"],
            "label": flat_label(r["wing"], r["number"]),
        }
        for r in rows
    ]


def staff_to_dict(db, row):
    """Turn a database row into the Staff JSON shape from the contract."""
    return {
        "id": row["id"],
        "name": row["name"],
        "role": row["role"],
        "photo_url": ("/uploads/" + row["photo_path"]) if row["photo_path"] else None,
        "verification_status": row["verification_status"],
        "verification_date": row["verification_date"],
        "qr_code": row["qr_code"],
        "is_active": bool(row["is_active"]),
        "flats": get_staff_flats(db, row["id"]),
    }


def find_staff(db, staff_id, society_id):
    """Get one staff row. 404 if it doesn't exist OR belongs to another society."""
    row = db.execute(
        "SELECT * FROM staff WHERE id = ? AND society_id = ?",
        (staff_id, society_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return row


def check_flat_ids(db, society_id, flat_ids):
    """Make sure every flat id belongs to the logged-in user's society."""
    unique_ids = list(set(flat_ids))
    if not unique_ids:
        return
    placeholders = ",".join("?" for _ in unique_ids)
    rows = db.execute(
        f"SELECT id FROM flats WHERE society_id = ? AND id IN ({placeholders})",
        [society_id] + unique_ids,
    ).fetchall()
    if len(rows) != len(unique_ids):
        raise HTTPException(status_code=422, detail="One or more flats do not belong to your society")


def set_staff_flats(db, staff_id, flat_ids):
    """Replace the staff member's flats with the given list."""
    db.execute("DELETE FROM staff_flats WHERE staff_id = ?", (staff_id,))
    for flat_id in set(flat_ids):
        db.execute(
            "INSERT INTO staff_flats (staff_id, flat_id) VALUES (?, ?)",
            (staff_id, flat_id),
        )


# ---------------------------------------------------------------
# Routes
# ---------------------------------------------------------------
@router.post("/staff", status_code=201)
def create_staff(body: StaffCreate, request: Request):
    """Register a new staff member. Guards and admins can do this."""
    user = get_current_user(request)

    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Name is required")
    if body.verification_status not in VERIFICATION_STATUSES:
        raise HTTPException(status_code=422, detail="verification_status must be not_done, pending or verified")

    db = get_db()
    try:
        check_flat_ids(db, user["society_id"], body.flat_ids)

        cursor = db.execute(
            """INSERT INTO staff
               (society_id, name, role, verification_status, verification_date, qr_code, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (
                user["society_id"],
                body.name.strip(),
                body.role,
                body.verification_status,
                body.verification_date,
                str(uuid.uuid4()),  # unique code for this person's QR badge
            ),
        )
        staff_id = cursor.lastrowid
        set_staff_flats(db, staff_id, body.flat_ids)
        db.commit()

        row = find_staff(db, staff_id, user["society_id"])
        return staff_to_dict(db, row)
    finally:
        db.close()


@router.get("/staff")
def list_staff(request: Request, search: Optional[str] = None, active: bool = True):
    """
    List staff in the logged-in user's society.
      ?search=sun   -> name contains "sun" (not case sensitive)
      ?active=false -> also include staff who were deactivated
    """
    user = get_current_user(request)

    sql = "SELECT * FROM staff WHERE society_id = ?"
    params = [user["society_id"]]
    if active:
        sql += " AND is_active = 1"
    if search:
        sql += " AND name LIKE ?"
        params.append(f"%{search}%")
    sql += " ORDER BY name"

    db = get_db()
    try:
        rows = db.execute(sql, params).fetchall()
        return [staff_to_dict(db, row) for row in rows]
    finally:
        db.close()


@router.get("/staff/{staff_id}")
def get_staff(staff_id: int, request: Request):
    """Get one staff member."""
    user = get_current_user(request)
    db = get_db()
    try:
        row = find_staff(db, staff_id, user["society_id"])
        return staff_to_dict(db, row)
    finally:
        db.close()


@router.patch("/staff/{staff_id}")
def update_staff(staff_id: int, body: StaffUpdate, request: Request):
    """Update a staff member. Admin only. Only the fields you send are changed."""
    user = require_admin(request)
    changes = body.dict(exclude_unset=True)  # only fields the client actually sent

    if "verification_status" in changes and changes["verification_status"] not in VERIFICATION_STATUSES:
        raise HTTPException(status_code=422, detail="verification_status must be not_done, pending or verified")
    if "name" in changes and not (changes["name"] or "").strip():
        raise HTTPException(status_code=422, detail="Name cannot be empty")

    db = get_db()
    try:
        find_staff(db, staff_id, user["society_id"])  # 404 if not ours

        # Update simple columns (these names are fixed by us, so it is safe)
        for column in ("name", "role", "verification_status", "verification_date"):
            if column in changes:
                db.execute(
                    f"UPDATE staff SET {column} = ? WHERE id = ?",
                    (changes[column], staff_id),
                )
        if "is_active" in changes:
            db.execute(
                "UPDATE staff SET is_active = ? WHERE id = ?",
                (1 if changes["is_active"] else 0, staff_id),
            )
        if changes.get("flat_ids") is not None:
            check_flat_ids(db, user["society_id"], changes["flat_ids"])
            set_staff_flats(db, staff_id, changes["flat_ids"])

        db.commit()
        row = find_staff(db, staff_id, user["society_id"])
        return staff_to_dict(db, row)
    finally:
        db.close()


@router.post("/staff/{staff_id}/photo")
def upload_staff_photo(staff_id: int, request: Request, file: UploadFile = File(...)):
    """Upload a photo (jpg or png, max 5 MB) for a staff member."""
    user = get_current_user(request)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=422, detail="Photo must be a JPG or PNG image")
    contents = file.file.read()
    if len(contents) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=422, detail="Photo is too big (max 5 MB)")

    db = get_db()
    try:
        row = find_staff(db, staff_id, user["society_id"])

        # Save the file with a random name so nobody can guess it
        UPLOADS_DIR.mkdir(exist_ok=True)
        filename = str(uuid.uuid4()) + ALLOWED_IMAGE_TYPES[file.content_type]
        (UPLOADS_DIR / filename).write_bytes(contents)

        # Delete the old photo file, if there was one
        if row["photo_path"]:
            old_file = UPLOADS_DIR / row["photo_path"]
            if old_file.exists():
                old_file.unlink()

        db.execute("UPDATE staff SET photo_path = ? WHERE id = ?", (filename, staff_id))
        db.commit()

        row = find_staff(db, staff_id, user["society_id"])
        return staff_to_dict(db, row)
    finally:
        db.close()