"""
seed.py - put demo data in the database so the team can log in on day 1.

Run it from the project root:
    python backend/seed.py

It creates:
  society : Demo Heights (Pune), qr_token for the check-in page
  admin   : admin / admin123  (full name "Asha K")
  guard   : guard / guard123  (full name "Ramu Guard")
  flats   : A-101, A-102, B-201, B-202, C-301

Safe to run twice: if "Demo Heights" already exists it does nothing.
"""

import os
import secrets
import sys

# Make "import database" work no matter where we are started from.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import get_db, init_db  # noqa: E402
from auth import hash_password  # noqa: E402

DEMO_SOCIETY_NAME = "Demo Heights"

DEMO_USERS = [
    # (username, password, full name, role)
    ("admin", "admin123", "Asha K", "admin"),
    ("guard", "guard123", "Ramu Guard", "guard"),
]

DEMO_FLATS = [
    # (wing, number)
    ("A", "101"),
    ("A", "102"),
    ("B", "201"),
    ("B", "202"),
    ("C", "301"),
]


def seed():
    # Create the tables first, in case the database file is brand new.
    init_db()

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM societies WHERE name = ?", (DEMO_SOCIETY_NAME,)
        ).fetchone()

        if existing is not None:
            print("Demo society already exists - nothing to do.")
            print("Admin login: admin / admin123")
            print("Guard login: guard / guard123")
            return

        cursor = conn.execute(
            """
            INSERT INTO societies (name, city, retention_days, qr_token)
            VALUES (?, ?, ?, ?)
            """,
            (DEMO_SOCIETY_NAME, "Pune", 90, secrets.token_urlsafe(16)),
        )
        society_id = cursor.lastrowid

        for username, password, full_name, role in DEMO_USERS:
            conn.execute(
                """
                INSERT INTO users (society_id, username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (society_id, username, hash_password(password), full_name, role),
            )

        for wing, number in DEMO_FLATS:
            conn.execute(
                "INSERT INTO flats (society_id, wing, number) VALUES (?, ?, ?)",
                (society_id, wing, number),
            )

        conn.commit()

        print("Demo data created.")
        print("  Society: Demo Heights, Pune")
        print("  Admin login: admin / admin123")
        print("  Guard login: guard / guard123")
        print("  Flats: A-101, A-102, B-201, B-202, C-301")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
