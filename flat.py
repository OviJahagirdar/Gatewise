"""
flat.py - the `flats` table.

A flat is a wing + a number inside one society, e.g. wing "A", number "101".
The wing can be empty, so the API shows the label "A-101" or just "101".
"""

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS flats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id INTEGER,
    wing TEXT,
    number TEXT
)
"""


def create_table(conn) -> None:
    conn.execute(CREATE_SQL)
