"""
entry.py - the `entries` table.

The gate register: visitors, deliveries and staff visits. `entry_type` says
what kind of entry it is, and `exit_time` stays NULL until the person leaves.
`source` records how it was logged: 'guard', 'resident' or 'self'.
"""

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id INTEGER,
    entry_type TEXT,
    flat_id INTEGER,
    staff_id INTEGER,
    visitor_name TEXT,
    visitor_phone TEXT,
    note TEXT,
    photo_path TEXT,
    source TEXT,
    logged_by_user_id INTEGER,
    entry_time TEXT,
    exit_time TEXT
)
"""


def create_table(conn) -> None:
    conn.execute(CREATE_SQL)
