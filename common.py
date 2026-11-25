"""
common.py - pieces more than one schema file needs.

RowModel is the base class for "this is a database row turned into JSON".
The database rows carry every column (including password_hash); extra fields
are dropped automatically, so a hash can never leak into a response.
"""

from pydantic import BaseModel, ConfigDict


class RowModel(BaseModel):
    """Base class for schemas that are built from an sqlite3.Row."""

    # Ignore columns we did not declare instead of failing.
    model_config = ConfigDict(extra="ignore")

    @classmethod
    def from_row(cls, row):
        """Build this schema from a row returned by sqlite3."""
        return cls(**dict(row))


class Message(BaseModel):
    """The shape FastAPI uses for every error: {"detail": "..."}."""

    detail: str
