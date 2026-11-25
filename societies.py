"""
societies.py - the shapes used when a new society signs up.

Signing up creates two things at once: the society and its first admin login,
so the response contains both.
"""

from pydantic import BaseModel

from app.schemas.common import RowModel
from app.schemas.users import UserOut


class SocietyCreate(BaseModel):
    """Body of POST /api/societies."""

    society_name: str
    city: str | None = None
    admin_full_name: str
    admin_username: str
    admin_password: str


class SocietyOut(RowModel):
    """One society, as the API returns it."""

    id: int
    name: str
    city: str | None = None
    retention_days: int
    qr_token: str


class SocietyCreated(BaseModel):
    """Answer of POST /api/societies."""

    society: SocietyOut
    user: UserOut
