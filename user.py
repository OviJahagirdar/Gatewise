"""
user.py - the `users` and `sessions` tables.

users    : people who can log in. role is 'admin' (committee) or 'guard'.
sessions : the login "coat-check tickets". One row per active login:
           token -> user_id. Logging out just deletes the row.
"""

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id INTEGER,
    username TEXT UNIQUE,
    password_hash TEXT,
    full_name TEXT,
    role TEXT
)
"""

CREATE_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER,
    created_at TEXT
)
"""


def create_table(conn) -> None:
    conn.execute(CREATE_SQL)
    conn.execute(CREATE_SESSIONS_SQL)
