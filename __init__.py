"""
models/__init__.py - ties the table definitions together.

Each module in this folder owns part of the database:

  society.py -> societies
  user.py    -> users, sessions
  flat.py    -> flats
  staff.py   -> staff, staff_flats
  entry.py   -> entries

A module has one CREATE TABLE statement plus a create_table(conn) function.
Nothing here runs SQL at import time - init_db() in core/database.py calls
create_all_tables() when the app starts.
"""

from app.models import entry, flat, society, staff, user

# The tables have no foreign keys yet, so the order below is only for
# readability: the "parent" tables come first.
TABLE_MODULES = (society, user, flat, staff, entry)


def create_all_tables(conn) -> None:
    """Create every table that does not exist yet."""
    for module in TABLE_MODULES:
        module.create_table(conn)
