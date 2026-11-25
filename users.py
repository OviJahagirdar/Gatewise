"""
users.py - the shapes for logins that can be created and listed.

UserOut never contains password_hash, so it is safe to send to the browser.
"""

from pydantic import BaseModel

from app.schemas.common import RowModel


class UserCreate(BaseModel):
    """Body of POST /api/users."""

    username: str
    password: str
    full_name: str
    role: str  # 'admin' or 'guard'


class UserOut(RowModel):
    """One login, as the API returns it."""

    id: int
    username: str
    full_name: str | None = None
    role: str
    society_id: int
