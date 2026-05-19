"""
analytics_logger.py
--------------------
Lightweight event logger for the AI/ML layer.

In the full architecture this would publish events to a Kafka topic.
For now it stores everything in memory and provides a structured
export that the FastAPI layer can return or forward to a real stream.

Event types:
  - MCTS_Action         : MCTS selected and scored a node
  - BKT_Update          : learner mastery changed after a quiz
  - Recommendation_Made : final unit recommendation sent to learner
  - Unit_Completed      : learner passed a unit (mastery crossed threshold)
  - Session_Started     : new learning session began
  - Flashcard_Reviewed  : SM-2 flashcard reviewed
"""

import time
from typing import Dict, Any, List, Optional


class AnalyticsLogger:

    def __init__(self, user_id: Optional[str] = None):
        self.user_id: Optional[str] = user_id
        self.log_entries: List[Dict[str, Any]] = []

    # ──────────────────────────────────────────
    #  Logging methods
    # ──────────────────────────────────────────

    def log_mcts_action(
        self,
        iteration: int,
        unit_id: str,
        reward: float,
        c_value: float,
    ) -> None:
        self._append({
            "event":            "MCTS_Action",
            "iteration":        iteration,
            "unit_id":          unit_id,
            "reward":           round(reward, 4),
            "c_value":          round(c_value, 3),
        })

    def log_bkt_update(
        self,
        skill_id: str,
        p_L_before: float,
        p_L_after: float,
        was_correct: bool,
    ) -> None:
        self._append({
            "event":        "BKT_Update",
            "skill":        skill_id,
            "p_L_before":   round(p_L_before, 4),
            "p_L_after":    round(p_L_after,  4),
            "delta":        round(p_L_after - p_L_before, 4),
            "was_correct":  was_correct,
        })

    def log_recommendation(
        self,
        unit_id: str,
        display_name: str,
        mastery_state: Dict[str, float],
    ) -> None:
        self._append({
            "event":        "Recommendation_Made",
            "unit_id":      unit_id,
            "display_name": display_name,
            "mastery_snapshot": {k: round(v, 3) for k, v in mastery_state.items()},
        })

    def log_unit_completed(
        self,
        unit_id: str,
        skill: str,
        final_mastery: float,
    ) -> None:
        self._append({
            "event":         "Unit_Completed",
            "unit_id":       unit_id,
            "skill":         skill,
            "final_mastery": round(final_mastery, 4),
        })

    def log_session_start(self, user_id: str) -> None:
        self._append({
            "event":   "Session_Started",
            "user_id": user_id,
        })

    def log_flashcard_review(
        self,
        unit_id: str,
        quality: int,
        new_interval: int,
    ) -> None:
        self._append({
            "event":        "Flashcard_Reviewed",
            "unit_id":      unit_id,
            "quality":      quality,
            "new_interval": new_interval,
        })

    # ──────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────

    def _append(self, payload: Dict) -> None:
        entry = {
            "timestamp": round(time.time(), 3),
            "user_id":   self.user_id,
        }
        entry.update(payload)
        self.log_entries.append(entry)

    # ──────────────────────────────────────────
    #  Export
    # ──────────────────────────────────────────

    def get_logs(self) -> List[Dict]:
        return self.log_entries

    def get_recent(self, n: int = 20) -> List[Dict]:
        return self.log_entries[-n:]

    def clear(self) -> None:
        self.log_entries.clear()
