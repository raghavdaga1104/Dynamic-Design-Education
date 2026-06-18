"""
auth_router.py
──────────────
FastAPI router for /auth endpoints.

Endpoints
---------
  POST /auth/signup   — register a new user
  POST /auth/login    — authenticate, return user_id + profile
  POST /auth/logout   — stateless, just signals the client to clear its token
  GET  /auth/me       — return profile for a logged-in user_id

Storage
-------
  Users are stored in:
    ai-ml/python_source/data/users.json

  Each record:
  {
    "user_id":      "u_<8-hex>",
    "name":         "Arjun Sharma",
    "email":        "arjun@example.com",     ← lowercased at write time
    "password_hash": "<pbkdf2_sha256 hex>",
    "salt":         "<16-byte hex salt>",
    "profile": {
      "degree":   "BTech",
      "year":     "2nd",
      "interest": "python"
    },
    "created_at": "2026-05-30T13:00:00"
  }

Security
--------
  • PBKDF2-HMAC-SHA256, 260 000 iterations (NIST 2024 recommendation)
  • Random 16-byte salt per user
  • Passwords never stored in plaintext
  • Atomic JSON writes (tmp → os.replace)
  • Thread-safe via a module-level Lock

No JWT / sessions: the frontend keeps user_id in localStorage exactly as
it did with the old Onboarding flow.  Add JWT later by wrapping user_id
in a signed token — the frontend only needs to swap localStorage key.
"""

import hashlib
import json
import logging
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

# Learner state dir — used to detect returning users
_LEARNER_STATE_DIR = Path(__file__).parent.parent / "data" / "learner_states"
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator

logger = logging.getLogger(__name__)

# ── Storage ───────────────────────────────────────────────────────
_USERS_PATH  = Path(__file__).parent.parent / "data" / "users.json"
_WRITE_LOCK  = threading.Lock()

PBKDF2_ITERS = 260_000
PBKDF2_HASH  = "sha256"


# ── Helpers ───────────────────────────────────────────────────────

def _load_users() -> list:
    if not _USERS_PATH.exists():
        return []
    try:
        with open(_USERS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.error("users.json corrupted — returning empty list")
        return []


def _save_users(users: list) -> None:
    _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _USERS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)
    os.replace(tmp, _USERS_PATH)


def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        PBKDF2_HASH,
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERS,
    )
    return dk.hex()


def _verify_password(password: str, salt: str, stored_hash: str) -> bool:
    return secrets.compare_digest(_hash_password(password, salt), stored_hash)


def _find_by_email(users: list, email: str) -> Optional[dict]:
    email_lower = email.lower()
    return next((u for u in users if u["email"] == email_lower), None)


def _find_by_id(users: list, user_id: str) -> Optional[dict]:
    return next((u for u in users if u["user_id"] == user_id), None)


# ── Pydantic models ───────────────────────────────────────────────

class SignupRequest(BaseModel):
    name:     str
    email:    EmailStr
    password: str
    degree:   str = "BTech"
    year:     str = "2nd"
    interest: str = "python"

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty.")
        return v.strip()


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id:      str
    name:         str
    profile:      dict
    is_new_user:  bool = False  # True only on first signup


# ── Router ────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest):
    """Register a new user. Returns user_id and profile on success."""
    with _WRITE_LOCK:
        users = _load_users()

        # Duplicate email check
        if _find_by_email(users, req.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        salt        = secrets.token_hex(16)
        password_hash = _hash_password(req.password, salt)
        user_id     = "u_" + secrets.token_hex(8)

        new_user = {
            "user_id":       user_id,
            "name":          req.name,
            "email":         req.email.lower(),
            "password_hash": password_hash,
            "salt":          salt,
            "profile": {
                "degree":   req.degree,
                "year":     req.year,
                "interest": req.interest,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        users.append(new_user)
        _save_users(users)

    logger.info("New user registered: %s (%s)", user_id, req.email)

    return AuthResponse(
        user_id=user_id,
        name=req.name,
        profile=new_user["profile"],
        is_new_user=True,
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    """Authenticate a user. Returns user_id and profile on success."""
    users = _load_users()
    user  = _find_by_email(users, req.email)

    if not user or not _verify_password(req.password, user["salt"], user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    logger.info("User logged in: %s", user["user_id"])

    # If no learner state file exists yet, treat as new user → send to diagnostic
    safe_id = "".join(c for c in user["user_id"] if c.isalnum() or c in "-_")
    has_state = (_LEARNER_STATE_DIR / f"{safe_id}.json").exists()

    return AuthResponse(
        user_id=user["user_id"],
        name=user["name"],
        profile=user["profile"],
        is_new_user=not has_state,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout():
    """
    Stateless logout — the client clears its own localStorage.
    Included so the frontend has a real endpoint to call.
    """
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=AuthResponse)
def me(user_id: str):
    """
    Return profile for an existing user_id.
    Used on app reload to re-hydrate the frontend context.
    """
    users = _load_users()
    user  = _find_by_id(users, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return AuthResponse(
        user_id=user["user_id"],
        name=user["name"],
        profile=user["profile"],
    )