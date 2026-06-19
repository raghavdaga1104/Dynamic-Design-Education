"""
state_manager.py
----------------
Persists learner state to PostgreSQL via SQLAlchemy.

Previously stored state as JSON files in data/learner_states/{user_id}.json.
Now stores the same JSON blob in the learner_states table (state_data column),
so progress survives Railway redeployments.

The LearnerSession interface is unchanged — only the save/load/exists/delete
methods changed internally. Everything that calls StateManager works as before.
"""

import json
import logging
import threading
from typing import Optional

from python_source.core.knowledge_graph  import KnowledgeGraph
from python_source.core.learner_session  import LearnerSession
from python_source.core.analytics_logger import AnalyticsLogger

from database import SessionLocal
from models import LearnerState

logger = logging.getLogger(__name__)

# Per-user locks — prevent concurrent requests from racing on the same user
_LOCKS: dict = {}
_LOCKS_MUTEX = threading.Lock()

MAX_USER_ID_LENGTH = 64


class StateManager:

    def __init__(self, state_dir=None):
        # state_dir kept for signature compatibility — no longer used
        pass

    # ──────────────────────────────────────────
    #  Save / Load
    # ──────────────────────────────────────────

    def save(self, session: LearnerSession) -> None:
        """Serialise and persist a learner session to PostgreSQL."""
        user_id    = self._safe_id(session.user_id)
        state_json = json.dumps(session.to_dict())

        with self._lock(user_id):
            db = SessionLocal()
            try:
                row = db.query(LearnerState).filter(
                    LearnerState.user_id == user_id
                ).first()

                if row:
                    row.state_data = state_json
                else:
                    db.add(LearnerState(user_id=user_id, state_data=state_json))

                db.commit()
                logger.debug("Saved session for user %s", user_id)
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def load(
        self,
        user_id: str,
        kg:      KnowledgeGraph,
        logger_: Optional[AnalyticsLogger] = None,
    ) -> LearnerSession:
        """Load a learner session from PostgreSQL. Returns a fresh session if none exists."""
        user_id = self._safe_id(user_id)

        with self._lock(user_id):
            db = SessionLocal()
            try:
                row = db.query(LearnerState).filter(
                    LearnerState.user_id == user_id
                ).first()

                if row:
                    try:
                        data = json.loads(row.state_data)
                        return LearnerSession.from_dict(data, kg, logger_)
                    except (json.JSONDecodeError, KeyError) as exc:
                        logger.error(
                            "Corrupted state for user %s (%s). Starting fresh.",
                            user_id, exc,
                        )
                        # Delete corrupted row so next save starts clean
                        db.delete(row)
                        db.commit()
            finally:
                db.close()

        # First time or recovery — fresh session
        return LearnerSession(user_id=user_id, kg=kg, logger=logger_)

    def exists(self, user_id: str) -> bool:
        """Return True if a saved state exists for this user."""
        user_id = self._safe_id(user_id)
        db = SessionLocal()
        try:
            return db.query(LearnerState).filter(
                LearnerState.user_id == user_id
            ).first() is not None
        finally:
            db.close()

    def delete(self, user_id: str) -> None:
        """Delete a user's saved state (reset)."""
        user_id = self._safe_id(user_id)
        with self._lock(user_id):
            db = SessionLocal()
            try:
                row = db.query(LearnerState).filter(
                    LearnerState.user_id == user_id
                ).first()
                if row:
                    db.delete(row)
                    db.commit()
            finally:
                db.close()
        logger.info("Reset state for user %s", user_id)

    def list_users(self) -> list:
        """Return user_ids for all stored sessions."""
        db = SessionLocal()
        try:
            return [row.user_id for row in db.query(LearnerState).all()]
        finally:
            db.close()

    # ──────────────────────────────────────────
    #  Internal
    # ──────────────────────────────────────────

    def _safe_id(self, user_id: str) -> str:
        safe = "".join(c for c in user_id if c.isalnum() or c in "-_")
        return (safe or "unknown_user")[:MAX_USER_ID_LENGTH]

    def _lock(self, user_id: str) -> threading.Lock:
        with _LOCKS_MUTEX:
            if user_id not in _LOCKS:
                _LOCKS[user_id] = threading.Lock()
        return _LOCKS[user_id]