"""
auth.py - passwords, login sessions, and "who is calling?" helpers.

What this file does:
1. hash_password()      -> scrambles a password before we store it.
2. POST /api/societies  -> creates a new society plus its first admin login.
3. POST /api/login      -> checks username + password, gives back a token.
4. GET  /api/me         -> tells the browser who it is logged in as.
5. get_current_user()   -> the function every other backend file imports.
6. require_admin()      -> same, but only lets admins through.

How the login system works (the "coat-check ticket" idea):
- On login we make a random string (the token) and save it in the `sessions`
  table next to the user's id.
- The browser stores that token and sends it on every request as:
      Authorization: Bearer <token>
- The server looks the token up in `sessions` to find out which user it is.
  So the browser never has to send a password again, and we never trust a
  user id / society id that the browser makes up.
"""

import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database import get_db

router = APIRouter()

# A fixed "salt" mixed into every password before hashing.
# Real apps use a random salt per user; one fixed salt is good enough for a
# student project. Hashing means even if someone opens app.db they cannot
# read the real passwords back.
SALT = "society-gate-salt-v1"


def now_iso() -> str:
    """Current local time as text, e.g. '2026-10-05T09:30:00'."""
    return datetime.now().replace(microsecond=0).isoformat()


def hash_password(password: str) -> str:
    """Turn a plain password into a fixed-length scrambled string."""
    return hashlib.sha256((SALT + password).encode()).hexdigest()


def user_to_dict(row) -> dict:
    """
    Convert a `users` row into the exact JSON shape from the contract.
    We never include password_hash in a response.
    """
    return {
        "id": row["id"],
        "username": row["username"],
        "full_name": row["full_name"],
        "role": row["role"],
        "society_id": row["society_id"],
    }


def society_to_dict(row) -> dict:
    """Convert a `societies` row into the JSON shape from the contract."""
    return {
        "id": row["id"],
        "name": row["name"],
        "city": row["city"],
        "retention_days": row["retention_days"],
        "qr_token": row["qr_token"],
    }


# ---------- request bodies (kept in this file, next to the routes) ----------


class SocietyCreate(BaseModel):
    society_name: str
    city: str | None = None
    admin_full_name: str
    admin_username: str
    admin_password: str


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------- the two helpers the rest of the backend imports ----------


def get_current_user(request: Request) -> dict:
    """
    Read the 'Authorization: Bearer <token>' header and return the matching
    user as a dict. Raises 401 if the header is missing or the token is not
    in the sessions table.
    """
    header = request.headers.get("Authorization") or ""
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not logged in")

    token = header[len("bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")

    conn = get_db()
    try:
        # JOIN: find the session by token, then the user that owns it.
        row = conn.execute(
            """
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=401, detail="Not logged in")

    return user_to_dict(row)


def require_admin(request: Request) -> dict:
    """Like get_current_user, but also raises 403 unless role is 'admin'."""
    user = get_current_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return user


# ---------- routes ----------


@router.post("/api/societies")
def create_society(body: SocietyCreate):
    """
    Onboard a brand new society and its first committee (admin) login.
    This is the one route that does not need a login, because nobody has a
    login for that society yet.
    """
    conn = get_db()
    try:
        # Usernames are unique across the whole database, so check first and
        # give a clear 409 instead of a database crash.
        taken = conn.execute(
            "SELECT id FROM users WHERE username = ?", (body.admin_username,)
        ).fetchone()
        if taken is not None:
            raise HTTPException(status_code=409, detail="Username already taken")

        # qr_token is what the check-in QR code points at for this society.
        qr_token = secrets.token_urlsafe(16)
        cursor = conn.execute(
            """
            INSERT INTO societies (name, city, retention_days, qr_token)
            VALUES (?, ?, ?, ?)
            """,
            (body.society_name, body.city, 90, qr_token),
        )
        society_id = cursor.lastrowid

        cursor = conn.execute(
            """
            INSERT INTO users (society_id, username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, 'admin')
            """,
            (
                society_id,
                body.admin_username,
                hash_password(body.admin_password),
                body.admin_full_name,
            ),
        )
        user_id = cursor.lastrowid
        conn.commit()

        society_row = conn.execute(
            "SELECT * FROM societies WHERE id = ?", (society_id,)
        ).fetchone()
        user_row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    return {"society": society_to_dict(society_row), "user": user_to_dict(user_row)}


@router.post("/api/login")
def login(body: LoginRequest):
    """
    Check username + password, then hand back a fresh session token.
    The browser keeps the token and sends it as 'Authorization: Bearer ...'.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (body.username,)
        ).fetchone()

        # Same message for "no such user" and "wrong password" on purpose, so
        # nobody can guess which usernames exist.
        if row is None or row["password_hash"] != hash_password(body.password):
            raise HTTPException(
                status_code=401, detail="Incorrect username or password"
            )

        token = secrets.token_hex(16)
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, row["id"], now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

    return {"token": token, "user": user_to_dict(row)}


@router.get("/api/me")
def me(request: Request):
    """Return the user who owns the token in the Authorization header."""
    return get_current_user(request)
