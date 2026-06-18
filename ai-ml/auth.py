"""
auth.py
-------
Authentication module for DDE.

Provides:
  - SQLite-backed user storage  (data/dde_auth.db)
  - Email + password auth       (bcrypt hashing)
  - Google OAuth                (ID token verification)
  - JWT session tokens          (HS256, 30-day expiry)
  - Legacy migration            (links old learner state files to new accounts)

DATABASE SCHEMA
───────────────
users table:
  id               INTEGER PRIMARY KEY AUTOINCREMENT
  email            TEXT UNIQUE NOT NULL
  display_name     TEXT NOT NULL
  hashed_password  TEXT                  -- NULL for Google-only accounts
  google_id        TEXT UNIQUE           -- NULL for email accounts
  learner_state_id TEXT UNIQUE NOT NULL  -- maps to STATE_MANAGER file key
  created_at       TEXT NOT NULL

ENVIRONMENT VARIABLES (add to .env)
────────────────────────────────────
  JWT_SECRET_KEY        -- required, any long random string
  GOOGLE_CLIENT_ID      -- required for Google OAuth
  JWT_EXPIRE_DAYS       -- optional, default 30

ADD TO REQUIREMENTS.TXT
────────────────────────
  python-jose[cryptography]==3.3.0
  passlib[bcrypt]==1.7.4
"""

import os
import sqlite3
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY  = os.environ.get("JWT_SECRET_KEY", "dde-change-this-secret-in-production")
JWT_ALGORITHM   = "HS256"
JWT_EXPIRE_DAYS = int(os.environ.get("JWT_EXPIRE_DAYS", "30"))
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

# Warn loudly if using the default secret
if JWT_SECRET_KEY == "dde-change-this-secret-in-production":
    logger.warning(
        "JWT_SECRET_KEY is using the default value. "
        "Set a strong secret in .env before deploying."
    )

# ── Lazy imports (so server starts even if packages not yet installed) ─────────
def _get_pwd_context():
    from passlib.context import CryptContext
    return CryptContext(schemes=["bcrypt"], deprecated="auto")

def _get_jose():
    from jose import jwt, JWTError
    return jwt, JWTError

# ── Database setup ─────────────────────────────────────────────────────────────
_DB_PATH = Path(__file__).parent / "python_source" / "data" / "dde_auth.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Create tables if they don't exist. Called at server startup."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                email            TEXT UNIQUE NOT NULL,
                display_name     TEXT NOT NULL,
                hashed_password  TEXT,
                google_id        TEXT UNIQUE,
                learner_state_id TEXT UNIQUE NOT NULL,
                created_at       TEXT NOT NULL
            )
        """)
        conn.commit()
    logger.info("Auth DB initialised at %s", _DB_PATH)


# ── Password helpers ───────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return _get_pwd_context().hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return _get_pwd_context().verify(plain, hashed)


# ── JWT helpers ────────────────────────────────────────────────────────────────
def create_token(user_id: int, learner_state_id: str, email: str, display_name: str) -> str:
    jwt, _ = _get_jose()
    payload = {
        "sub":               str(user_id),
        "learner_state_id":  learner_state_id,
        "email":             email,
        "display_name":      display_name,
        "exp":               datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> Optional[Dict]:
    """Returns payload dict or None if invalid/expired."""
    jwt, JWTError = _get_jose()
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# ── User DB operations ─────────────────────────────────────────────────────────
def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()

def get_user_by_google_id(google_id: str) -> Optional[sqlite3.Row]:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone()

def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()

def create_user(
    email: str,
    display_name: str,
    hashed_password: Optional[str] = None,
    google_id: Optional[str] = None,
    legacy_state_id: Optional[str] = None,  # for migration of existing learner files
) -> sqlite3.Row:
    """
    Create a new user. Returns the created row.
    legacy_state_id: pass an existing learner state filename (e.g. 'testuser_01')
                     to link the new account to existing progress.
    """
    learner_state_id = legacy_state_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO users
               (email, display_name, hashed_password, google_id, learner_state_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (email.lower().strip(), display_name, hashed_password, google_id, learner_state_id, now),
        )
        conn.commit()
    return get_user_by_email(email)

def link_google_to_existing(user_id: int, google_id: str) -> None:
    """Link a Google account to an existing email account."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET google_id = ? WHERE id = ?", (google_id, user_id)
        )
        conn.commit()


# ── Google ID token verification ───────────────────────────────────────────────
def verify_google_token(id_token: str) -> Optional[Dict]:
    """
    Verify a Google ID token and return the payload.
    Returns None if verification fails.

    Requires GOOGLE_CLIENT_ID to be set in .env.
    Install: pip install google-auth
    """
    if not GOOGLE_CLIENT_ID:
        logger.error("GOOGLE_CLIENT_ID not set in .env — Google OAuth unavailable")
        return None
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        payload = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        return payload
    except Exception as e:
        logger.warning("Google token verification failed: %s", e)
        return None


# ── FastAPI dependency ─────────────────────────────────────────────────────────
def get_current_user_from_header(authorization: str) -> Optional[Dict]:
    """
    Extract and validate JWT from Authorization: Bearer <token> header.
    Returns decoded payload or None.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    return decode_token(token)
