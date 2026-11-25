"""
society.py - the `societies` table.

One row per housing society using the app. `retention_days` is how long gate
entries are kept, and `qr_token` is what the society's check-in QR code
points at.
"""

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS societies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    city TEXT,
    retention_days INTEGER DEFAULT 90,
    qr_token TEXT UNIQUE
)
"""


def create_table(conn) -> None:
    conn.execute(CREATE_SQL)
