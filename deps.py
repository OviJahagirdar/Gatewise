"""
deps.py - dependencies the routers share.

A "dependency" is something FastAPI builds for a route automatically. Here we
build the logged-in user:

    Authorization: Bearer <token>
                    ^ the token /api/login gave the browser

The token is looked up in the `sessions` table, so the browser can never
choose a user id or a society id - they always come from that table.
"""

import sqlite3

from fastapi import Depends, Header, HTTPException

from app.core.database import get_db
from app.schemas.users import UserOut


def get_current_user(
    conn: sqlite3.Connection = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> UserOut:
    """
    Return the user who owns the token in the Authorization header.

    Raises 401 when the header is missing, or when the token is not in the
    sessions table (logged out / made up token).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not logged in")

    token = authorization[len("bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")

    # JOIN: find the row in sessions by token, then the user that owns it.
    row = conn.execute(
        """
        SELECT users.*
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ?
        """,
        (token,),
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=401, detail="Not logged in")

    return UserOut.from_row(row)


def require_admin(user: UserOut = Depends(get_current_user)) -> UserOut:
    """Like get_current_user, but also raises 403 unless the role is admin."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return user
