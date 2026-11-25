"""
flats.py - the shapes used for flats.

The database stores a wing and a number separately; the API also returns a
combined "label" ("A-101", or "101" when there is no wing) because that is
what people recognise.
"""

from pydantic import BaseModel

from app.schemas.common import RowModel


class FlatCreate(BaseModel):
    """Body of POST /api/flats."""

    wing: str | None = None
    number: str


class FlatOut(RowModel):
    """One flat, as the API returns it."""

    id: int
    wing: str | None = None
    number: str
    label: str

    @classmethod
    def from_row(cls, row) -> "FlatOut":
        """Build a flat and work out its label."""
        data = dict(row)
        wing = data.get("wing")
        number = data.get("number")
        data["label"] = f"{wing}-{number}" if wing else number
        return cls(**data)


class CsvUploadResult(BaseModel):
    """Answer of POST /api/flats/upload-csv."""

    created: int
    skipped: int
