"""
main.py - starts the whole app.

Run it from the project root with:
    uvicorn backend.main:app --reload
then open http://localhost:8000/docs to see and try the API.

It does four things:
1. Creates the database tables on startup (if they are missing).
2. Includes my routes (auth.py, flats_and_users.py).
3. Includes Person 2's routes (staff.py, entries.py) if those files exist yet.
4. Serves the uploads/ folder at /uploads and the frontend/ folder at /.
"""

import os
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# --- make imports work from either the project root or the backend/ folder ---
# When you run "uvicorn backend.main:app", Python starts in the project root,
# so plain "import auth" would fail. Adding backend/ to the search path lets
# all backend files import each other with simple names.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import init_db  # noqa: E402  (import after the sys.path fix)
from auth import router as auth_router  # noqa: E402
from flats_and_users import router as flats_and_users_router  # noqa: E402

app = FastAPI(title="Society Gate App")


@app.on_event("startup")
def on_startup():
    """Runs once when the server starts."""
    init_db()
    # uploads/ holds visitor photos and staff photos. Create it if missing.
    os.makedirs(os.path.join(PROJECT_ROOT, "uploads"), exist_ok=True)


# My routes.
app.include_router(auth_router)
app.include_router(flats_and_users_router)

# Person 2's routes. Those files may not exist yet, so a missing file must not
# stop the app from starting - the app just serves fewer endpoints for now.
try:
    from staff import router as staff_router

    app.include_router(staff_router)
except ImportError:
    pass

try:
    from entries import router as entries_router

    app.include_router(entries_router)
except ImportError:
    pass

# Photos: entry.photo_url / staff.photo_url are "/uploads/<file>".
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# The plain HTML pages. Mounted last (at "/") so it cannot hide the /api routes.
# If frontend/ does not exist yet, the API still works.
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
