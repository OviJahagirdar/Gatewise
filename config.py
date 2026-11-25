"""
config.py - all settings in one place.

Every value can be overridden with an environment variable (or a ".env" file
in the project root, copied from .env.example). No other file reads
os.environ directly, so there is exactly one place to look when a setting
needs to change.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# This file lives in backend/app/core/, so going up three folders lands on
# the project root (the folder that holds .env, app.db and uploads/).
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Load ".env" if it exists. Real environment variables win over the file.
load_dotenv(PROJECT_ROOT / ".env")

APP_TITLE = os.environ.get("APP_TITLE", "Society Gate App")

# Used when SOCIETY_DB_PATH is not set.
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "app.db"
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "uploads"

# A fixed "salt" mixed into every password before hashing. Real apps use a
# random salt per user; one shared salt is enough for a student project.
PASSWORD_SALT = os.environ.get("PASSWORD_SALT", "society-gate-salt-v1")

# How many random bytes make up a login token.
SESSION_TOKEN_BYTES = 16

# New societies keep gate entries for this many days (Person 2 uses it).
DEFAULT_RETENTION_DAYS = 90


def _resolve(raw: str) -> Path:
    """Turn a configured path into a full path, relative to the project root."""
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def database_path() -> str:
    """
    Full path of the SQLite file.

    This is a function instead of a constant on purpose: the tests point
    SOCIETY_DB_PATH at a temporary file, and reading the variable on every
    call means each request uses the right database.
    """
    raw = os.environ.get("SOCIETY_DB_PATH")
    if not raw:
        return str(DEFAULT_DATABASE_PATH)
    return str(_resolve(raw))


def upload_dir() -> Path:
    """Folder where visitor and staff photos are stored."""
    raw = os.environ.get("SOCIETY_UPLOAD_DIR")
    if not raw:
        return DEFAULT_UPLOAD_DIR
    return _resolve(raw)
