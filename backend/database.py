"""
database.py - the ONLY file that talks to the SQLite database.

What this file does:
1. get_db()  -> opens a connection to the "app.db" file.
2. init_db() -> creates all 7 tables if they do not already exist.

We use Python's built-in "sqlite3" module directly (raw SQL, no ORM).
"""

import sqlite3

# The database is just a single file called app.db in the project root.
DATABASE_NAME = "app.db"


def get_db():
    """
    Open and return a connection to app.db.

    check_same_thread=False lets FastAPI use the same connection from
    different worker threads, otherwise you get a "SQLite objects created
    in a thread can only be used in that same thread" error.

    row_factory = sqlite3.Row makes a row behave like a dictionary,
    so you can write row["username"] instead of row[2].
    """
    conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Create all 7 tables. "IF NOT EXISTS" means this is safe to run
    again and again - it only creates what is missing.
    """
    conn = get_db()
    cursor = conn.cursor()

    # 1. societies - one row per housing society using the app.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS societies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            city TEXT,
            retention_days INTEGER DEFAULT 90,
            qr_token TEXT UNIQUE
        )
    """)

    # 2. users - people who can log in. role is 'admin' or 'guard'.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            society_id INTEGER,
            username TEXT UNIQUE,
            password_hash TEXT,
            full_name TEXT,
            role TEXT
        )
    """)

    # 3. sessions - the login "coat-check ticket": token -> user.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            created_at TEXT
        )
    """)

    # 4. flats - flats inside a society, e.g. wing "A", number "101".
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            society_id INTEGER,
            wing TEXT,
            number TEXT
        )
    """)

    # 5. staff - maids, drivers, etc. registered with the society.
    # verification_status is 'not_done', 'pending' or 'verified'.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            society_id INTEGER,
            name TEXT,
            role TEXT,
            photo_path TEXT,
            verification_status TEXT DEFAULT 'not_done',
            verification_date TEXT,
            qr_code TEXT UNIQUE,
            is_active INTEGER DEFAULT 1
        )
    """)

    # 6. staff_flats - which flat(s) a staff member works for.
    # One staff row can be linked to many flats, so this is a separate table.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_flats (
            staff_id INTEGER,
            flat_id INTEGER
        )
    """)

    # 7. entries - the gate register: visitors, deliveries and staff visits.
    cursor.execute("""
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
    """)

    # Save the changes to the file. Without commit() nothing is written.
    conn.commit()
    conn.close()


# Running "python backend/database.py" by hand creates the database too.
# This is only a convenience for testing this file on its own.
if __name__ == "__main__":
    init_db()
    print("Database initialised successfully.")
