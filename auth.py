"""
Google OAuth authentication, JWT tokens, and SQLite user database for Mnfz.
"""
import os
import sqlite3
import time
import jwt
from jwt import PyJWTError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

# ── Config ────────────────────────────────────────────────────────────────────

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.environ.get("JWT_SECRET", os.environ.get("AZURE_SPEECH_KEY", os.urandom(32).hex()))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mnfz_users.db")

# ── SQLite ────────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id   TEXT UNIQUE NOT NULL,
            email       TEXT NOT NULL,
            name        TEXT NOT NULL,
            picture     TEXT,
            created_at  REAL NOT NULL DEFAULT (unixepoch())
        );

        CREATE TABLE IF NOT EXISTS user_docs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            doc_id      TEXT NOT NULL,
            filename    TEXT NOT NULL,
            page_count  INTEGER NOT NULL DEFAULT 0,
            file_size   INTEGER NOT NULL DEFAULT 0,
            created_at  REAL NOT NULL DEFAULT (unixepoch()),
            UNIQUE(user_id, doc_id)
        );

        CREATE TABLE IF NOT EXISTS reading_progress (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            doc_id          TEXT NOT NULL,
            current_page    INTEGER NOT NULL DEFAULT 1,
            scroll_offset   REAL NOT NULL DEFAULT 0,
            updated_at      REAL NOT NULL DEFAULT (unixepoch()),
            UNIQUE(user_id, doc_id)
        );

        CREATE INDEX IF NOT EXISTS idx_user_docs_user ON user_docs(user_id);
        CREATE INDEX IF NOT EXISTS idx_reading_progress_user ON reading_progress(user_id);

        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            voice      TEXT DEFAULT '',
            engine     TEXT DEFAULT 'piper',
            theme      TEXT DEFAULT 'light',
            lang       TEXT DEFAULT 'ar',
            updated_at REAL NOT NULL DEFAULT (unixepoch())
        );
    """)
    conn.commit()
    conn.close()

# ── Google OAuth ──────────────────────────────────────────────────────────────

def verify_google_token(token: str) -> dict | None:
    """Verify a Google ID token and return the payload or None."""
    if not GOOGLE_CLIENT_ID:
        return None
    try:
        idinfo = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        return idinfo
    except Exception:
        return None

def get_or_create_user(google_payload: dict) -> dict:
    """Find or create a user from Google ID token payload. Returns user row dict."""
    google_id = google_payload["sub"]
    email = google_payload.get("email", "")
    name = google_payload.get("name", email)
    picture = google_payload.get("picture", "")

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone()

        if row is None:
            conn.execute(
                "INSERT INTO users (google_id, email, name, picture) VALUES (?, ?, ?, ?)",
                (google_id, email, name, picture),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM users WHERE google_id = ?", (google_id,)
            ).fetchone()

        return dict(row)
    finally:
        conn.close()

# ── JWT ───────────────────────────────────────────────────────────────────────

def create_app_token(user: dict) -> str:
    """Generate a short-lived app JWT for API calls."""
    now = int(time.time())
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "iat": now,
        "exp": now + (JWT_EXPIRY_HOURS * 3600),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_app_token(token: str) -> dict | None:
    """Verify an app JWT and return the payload or None."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except PyJWTError:
        return None

# ── User Docs & Progress ─────────────────────────────────────────────────────

def save_user_doc(user_id: int, doc_id: str, filename: str,
                  page_count: int = 0, file_size: int = 0):
    conn = get_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO user_docs (user_id, doc_id, filename, page_count, file_size)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, doc_id, filename, page_count, file_size),
        )
        conn.commit()
    finally:
        conn.close()

def get_user_docs(user_id: int) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT d.*, p.current_page, p.scroll_offset
               FROM user_docs d
               LEFT JOIN reading_progress p ON d.user_id = p.user_id AND d.doc_id = p.doc_id
               WHERE d.user_id = ?
               ORDER BY d.created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def delete_user_doc(user_id: int, doc_id: str):
    """Remove a document and its reading progress for a user."""
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM user_docs WHERE user_id = ? AND doc_id = ?",
            (user_id, doc_id),
        )
        conn.execute(
            "DELETE FROM reading_progress WHERE user_id = ? AND doc_id = ?",
            (user_id, doc_id),
        )
        conn.commit()
    finally:
        conn.close()

def save_reading_progress(user_id: int, doc_id: str,
                          current_page: int, scroll_offset: float = 0):
    conn = get_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO reading_progress
               (user_id, doc_id, current_page, scroll_offset, updated_at)
               VALUES (?, ?, ?, ?, unixepoch())""",
            (user_id, doc_id, current_page, scroll_offset),
        )
        conn.commit()
    finally:
        conn.close()

def get_reading_progress(user_id: int, doc_id: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM reading_progress WHERE user_id = ? AND doc_id = ?",
            (user_id, doc_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# ── User Preferences ────────────────────────────────────────────────────────

def save_preferences(user_id: int, voice: str = "", engine: str = "piper",
                     theme: str = "light", lang: str = "ar"):
    conn = get_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO user_preferences
               (user_id, voice, engine, theme, lang, updated_at)
               VALUES (?, ?, ?, ?, ?, unixepoch())""",
            (user_id, voice, engine, theme, lang),
        )
        conn.commit()
    finally:
        conn.close()

def get_preferences(user_id: int) -> dict:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else {"voice": "", "engine": "piper", "theme": "light", "lang": "ar"}
    finally:
        conn.close()
