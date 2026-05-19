"""
state_manager.py
----------------
Persists learner state to JSON files on disk.

FIXES APPLIED (Review §3 Bug #3 / §8.1):
  1. File locking  — per-user threading.Lock prevents concurrent requests
     from the same user_id from corrupting the JSON file.
  2. Atomic writes — write to a .tmp file first, then os.replace() which
     is atomic on POSIX systems. If the process crashes mid-write the
     original file is never touched.
  3. user_id length guard — prevents OS filename-length errors from
     excessively long IDs (max 64 chars).

In production this would write to MongoDB.
For the Python microservice demo and development, JSON files work
perfectly and mean the system remembers learner progress between runs.

File layout:  data/learner_states/{user_id}.json
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from python_source.core.knowledge_graph  import KnowledgeGraph
from python_source.core.learner_session  import LearnerSession
from python_source.core.analytics_logger import AnalyticsLogger

logger = logging.getLogger(__name__)

# Per-user locks — created on first access, never deleted during process lifetime
_LOCKS: dict = {}
_LOCKS_MUTEX = threading.Lock()   # protects _LOCKS dict itself

# Default storage directory relative to the service root
DEFAULT_STATE_DIR = Path(__file__).parent.parent / "data" / "learner_states"

# Max user_id length — prevents OS filename-length errors
MAX_USER_ID_LENGTH = 64


class StateManager:

    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = state_dir or DEFAULT_STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────
    #  Save / Load
    # ──────────────────────────────────────────

    def save(self, session: LearnerSession) -> None:
        """
        Serialise and atomically persist a learner session to disk.

        Uses:
          1. Per-user threading.Lock  — only one save runs at a time per user
          2. Write to .tmp first      — original untouched until write succeeds
          3. os.replace()             — atomic rename on POSIX (Linux/Mac)
        """
        path = self._path(session.user_id)
        tmp  = path.with_suffix(".tmp")

        with self._lock(session.user_id):
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(session.to_dict(), f, indent=2)
                os.replace(tmp, path)          # atomic on Linux/Mac
                logger.debug("Saved session for user %s", session.user_id)
            except Exception:
                # If write failed, remove the partial .tmp so it doesn't
                # confuse future reads
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
                raise

    def load(
        self,
        user_id: str,
        kg:      KnowledgeGraph,
        logger_: Optional[AnalyticsLogger] = None,
    ) -> LearnerSession:
        """
        Load a learner session from disk.
        If no saved state exists, returns a fresh session for the user.
        """
        path = self._path(user_id)

        with self._lock(user_id):
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    return LearnerSession.from_dict(data, kg, logger_)
                except (json.JSONDecodeError, KeyError) as exc:
                    # Corrupted file — log and start fresh rather than crashing
                    logger.error(
                        "Corrupted state file for user %s (%s). Starting fresh.",
                        user_id, exc,
                    )
                    # Rename corrupted file so it is not lost
                    path.rename(path.with_suffix(".corrupted"))

        # First time or recovery — create a fresh session
        return LearnerSession(user_id=user_id, kg=kg, logger=logger_)

    def exists(self, user_id: str) -> bool:
        """Return True if a saved state exists for this user."""
        return self._path(user_id).exists()

    def delete(self, user_id: str) -> None:
        """Delete a user's saved state (reset)."""
        path = self._path(user_id)
        with self._lock(user_id):
            if path.exists():
                path.unlink()
        logger.info("Reset state for user %s", user_id)

    def list_users(self) -> list:
        """Return user_ids for all stored sessions."""
        return [p.stem for p in self.state_dir.glob("*.json")]

    # ──────────────────────────────────────────
    #  Internal
    # ──────────────────────────────────────────

    def _path(self, user_id: str) -> Path:
        """
        Sanitise the user_id to avoid path traversal and OS filename issues.
        Keeps only alphanumerics, hyphens, and underscores. Max 64 chars.
        """
        safe_id = "".join(c for c in user_id if c.isalnum() or c in "-_")
        if not safe_id:
            safe_id = "unknown_user"
        safe_id = safe_id[:MAX_USER_ID_LENGTH]
        return self.state_dir / f"{safe_id}.json"

    def _lock(self, user_id: str) -> threading.Lock:
        """
        Return (and create if needed) the per-user threading.Lock.
        Thread-safe creation via a global mutex.
        """
        safe_id = "".join(c for c in user_id if c.isalnum() or c in "-_")[:MAX_USER_ID_LENGTH]
        with _LOCKS_MUTEX:
            if safe_id not in _LOCKS:
                _LOCKS[safe_id] = threading.Lock()
        return _LOCKS[safe_id]
