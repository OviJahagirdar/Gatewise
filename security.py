"""
security.py - passwords and login tokens.

Only two ideas live here:

1. Passwords are never stored as typed. hash_password() turns a password into
   a fixed-length scrambled string, and verify_password() compares hashes.
2. A login token is just a long random string. It is saved in the `sessions`
   table and sent back by the browser as "Authorization: Bearer <token>".
"""

import hashlib
import secrets
from datetime import datetime

from app.core.config import PASSWORD_SALT, SESSION_TOKEN_BYTES


def hash_password(password: str) -> str:
    """Turn a plain password into a scrambled string (SHA-256 + salt)."""
    return hashlib.sha256((PASSWORD_SALT + password).encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """
    True when the typed password matches the stored hash.

    compare_digest takes the same time for every input, so an attacker cannot
    learn anything from how long the check took.
    """
    return secrets.compare_digest(hash_password(password), password_hash or "")


def new_session_token() -> str:
    """A fresh, unguessable token for one login."""
    return secrets.token_hex(SESSION_TOKEN_BYTES)


def new_qr_token() -> str:
    """A fresh token that a society's check-in QR code points at."""
    return secrets.token_urlsafe(16)


def now_iso() -> str:
    """Current local time as text, e.g. '2026-10-05T09:30:00'."""
    return datetime.now().replace(microsecond=0).isoformat()
