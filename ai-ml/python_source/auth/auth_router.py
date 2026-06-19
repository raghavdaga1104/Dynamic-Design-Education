"""
auth_router.py
──────────────
FastAPI router for /auth endpoints.

Storage
-------
  Users are persisted in PostgreSQL (Railway) via SQLAlchemy.
  Falls back to SQLite locally when DATABASE_URL is not set.
  No more users.json — all reads/writes go through the User model.

Endpoints
---------
  POST /auth/signup   — register a new user
  POST /auth/login    — authenticate, return user_id + profile
  POST /auth/logout   — stateless, signals the client to clear its token
  GET  /auth/me       — return profile for a logged-in user_id

Security
--------
  • PBKDF2-HMAC-SHA256, 260 000 iterations (NIST 2024 recommendation)
  • Random 16-byte salt per user
  • Passwords never stored in plaintext
"""

import hashlib
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, LearnerState

logger = logging.getLogger(__name__)

PBKDF2_ITERS = 260_000
PBKDF2_HASH  = "sha256"


# ── DB session dependency ─────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Password helpers ──────────────────────────────────────────────

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
    user_id:     str
    name:        str
    profile:     dict
    is_new_user: bool = False


# ── Router ────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user. Returns user_id and profile on success."""
    email_lower = req.email.lower()

    existing = db.query(User).filter(User.email == email_lower).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    salt          = secrets.token_hex(16)
    password_hash = _hash_password(req.password, salt)
    user_id       = "u_" + secrets.token_hex(8)

    new_user = User(
        user_id       = user_id,
        name          = req.name,
        email         = email_lower,
        password_hash = password_hash,
        salt          = salt,
        degree        = req.degree,
        year          = req.year,
        interest      = req.interest,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info("New user registered: %s (%s)", user_id, email_lower)

    return AuthResponse(
        user_id     = user_id,
        name        = req.name,
        profile     = {"degree": req.degree, "year": req.year, "interest": req.interest},
        is_new_user = True,
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user. Returns user_id and profile on success."""
    email_lower = req.email.lower()
    user = db.query(User).filter(User.email == email_lower).first()

    if not user or not _verify_password(req.password, user.salt, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    logger.info("User logged in: %s", user.user_id)

    # Check PostgreSQL for existing learner state — not the file system
    has_state = db.query(LearnerState).filter(
        LearnerState.user_id == user.user_id
    ).first() is not None

    return AuthResponse(
        user_id     = user.user_id,
        name        = user.name,
        profile     = {"degree": user.degree, "year": user.year, "interest": user.interest},
        is_new_user = not has_state,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout():
    """Stateless logout — the client clears its own localStorage."""
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=AuthResponse)
def me(user_id: str, db: Session = Depends(get_db)):
    """
    Return profile for an existing user_id.
    Used on app reload to re-hydrate the frontend context.
    """
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return AuthResponse(
        user_id = user.user_id,
        name    = user.name,
        profile = {"degree": user.degree, "year": user.year, "interest": user.interest},
    )