"""
flats_and_users.py - managing flats and the people who can log in.

Routes in this file:
  GET  /api/flats              -> list flats of my society (with ?search=)
  POST /api/flats              -> add one flat (admin only)
  POST /api/flats/upload-csv   -> add many flats from a CSV file (admin only)
  POST /api/users              -> create a guard / committee login (admin only)
  GET  /api/users              -> list logins of my society (admin only)

Every query filters by the logged-in user's society_id, taken from the token.
We never accept a society_id sent by the browser.
"""

import csv
import io

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from auth import get_current_user, hash_password, require_admin, user_to_dict
from database import get_db

router = APIRouter()


def flat_to_dict(row) -> dict:
    """
    Convert a `flats` row into the contract shape, adding the computed
    'label' field: 'A-101', or just '101' when the flat has no wing.
    """
    wing = row["wing"]
    number = row["number"]
    label = f"{wing}-{number}" if wing else number
    return {"id": row["id"], "wing": wing, "number": number, "label": label}


# ---------- request bodies ----------


class FlatCreate(BaseModel):
    wing: str | None = None
    number: str


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str  # 'admin' or 'guard'


# ---------- flats ----------


@router.get("/api/flats")
def list_flats(request: Request, search: str | None = None):
    """All flats of my society, optionally filtered by ?search=."""
    user = get_current_user(request)

    sql = "SELECT * FROM flats WHERE society_id = ?"
    params: list = [user["society_id"]]

    if search:
        # Match either the wing or the flat number (partial match is fine).
        sql += " AND (wing LIKE ? OR number LIKE ?)"
        pattern = f"%{search}%"
        params.extend([pattern, pattern])

    sql += " ORDER BY wing, number"

    conn = get_db()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return [flat_to_dict(row) for row in rows]


@router.post("/api/flats")
def create_flat(body: FlatCreate, request: Request):
    """Admin only: add one flat."""
    user = require_admin(request)

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO flats (society_id, wing, number) VALUES (?, ?, ?)",
            (user["society_id"], body.wing, body.number),
        )
        flat_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM flats WHERE id = ?", (flat_id,)).fetchone()
    finally:
        conn.close()

    return flat_to_dict(row)


@router.post("/api/flats/upload-csv")
async def upload_flats_csv(request: Request, file: UploadFile = File(...)):
    """
    Admin only: upload a CSV whose first row is 'wing,number'.

    Example file:
        wing,number
        A,101
        A,102
        ,301          <- blank wing is allowed

    Flats that already exist in this society are skipped, so uploading the
    same file twice does not create duplicates.
    """
    user = require_admin(request)
    society_id = user["society_id"]

    # Read the uploaded file (it is small, so reading it in one go is fine).
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")  # utf-8-sig also works for plain UTF-8
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be a UTF-8 CSV")

    reader = csv.DictReader(io.StringIO(text))

    conn = get_db()
    try:
        # Existing flats of this society, as (wing, number) pairs.
        existing = {
            ((row["wing"] or "").strip(), (row["number"] or "").strip())
            for row in conn.execute(
                "SELECT wing, number FROM flats WHERE society_id = ?", (society_id,)
            ).fetchall()
        }

        created = 0
        skipped = 0
        for row in reader:
            # Header names may arrive with spaces or capitals, so normalise.
            clean = {
                (key or "").strip().lower(): (value or "").strip()
                for key, value in row.items()
            }
            wing = clean.get("wing", "")
            number = clean.get("number", "")

            if not number:
                skipped += 1  # no flat number means it is not a real row
                continue

            if (wing, number) in existing:
                skipped += 1
                continue

            conn.execute(
                "INSERT INTO flats (society_id, wing, number) VALUES (?, ?, ?)",
                (society_id, wing or None, number),
            )
            existing.add((wing, number))
            created += 1

        conn.commit()
    finally:
        conn.close()

    return {"created": created, "skipped": skipped}


# ---------- users (logins) ----------


@router.post("/api/users")
def create_user(body: UserCreate, request: Request):
    """Admin only: create a guard or another committee login in my society."""
    admin = require_admin(request)

    conn = get_db()
    try:
        taken = conn.execute(
            "SELECT id FROM users WHERE username = ?", (body.username,)
        ).fetchone()
        if taken is not None:
            raise HTTPException(status_code=409, detail="Username already taken")

        cursor = conn.execute(
            """
            INSERT INTO users (society_id, username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                admin["society_id"],
                body.username,
                hash_password(body.password),
                body.full_name,
                body.role,
            ),
        )
        user_id = cursor.lastrowid
        conn.commit()

        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()

    return user_to_dict(row)


@router.get("/api/users")
def list_users(request: Request):
    """Admin only: all logins that belong to my society."""
    admin = require_admin(request)

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM users WHERE society_id = ? ORDER BY id",
            (admin["society_id"],),
        ).fetchall()
    finally:
        conn.close()

    return [user_to_dict(row) for row in rows]
