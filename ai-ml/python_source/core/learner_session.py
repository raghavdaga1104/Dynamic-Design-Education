"""
learner_session.py
------------------
Central learner state object.

FIXES APPLIED (Review §3 Bug #1):
  CRITICAL — Orphaned method body in _update_streak / _get_prereq_suggestions.
  The body of _get_prereq_suggestions was accidentally indented inside
  _update_streak, making it completely unreachable. The stuck_alert feature
  — which fires after 3 consecutive failures — was silently doing nothing.
  Fixed by correctly separating the two methods at the right indentation.

Other fixes already present (retained from previous version):
  - record_quiz_result_irt() blends IRT mastery into BKT state
  - stuck_alert surfaced in record_quiz_result return dict
  - _auto_create_flashcard uses _created_at correctly
  - concept_index pruned to prevent unbounded growth
  - streak_days actually updated (was always 0 before)
  - IRT pass/fail uses IRT's own decision (not BKT re-evaluation)
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Set

from python_source.core.adaptive_systems  import bkt_update, SM2Flashcard, mastery_to_level
from python_source.core.mistake_tracker   import (
    make_mistake_event,
    update_concept_index,
    generate_insights,
)
from python_source.core.knowledge_graph  import KnowledgeGraph
from python_source.core.analytics_logger import AnalyticsLogger

logger = logging.getLogger(__name__)

PASS_THRESHOLD  = 0.70
STUCK_THRESHOLD = 3
IRT_BLEND_ALPHA = 0.7   # weight given to IRT mastery estimate on quiz pass


class LearnerSession:

    def __init__(
        self,
        user_id:             str,
        kg:                  KnowledgeGraph,
        initial_skill_state: Optional[Dict[str, float]] = None,
        bkt_params:          Optional[Dict[str, Dict[str, float]]] = None,
        logger:              Optional[AnalyticsLogger] = None,
    ):
        self.user_id      = user_id
        self.kg           = kg
        self.bkt_params   = bkt_params or {}
        self.logger       = logger

        all_skills             = kg.get_all_skills()
        default_state          = {s: 0.1 for s in all_skills}
        if initial_skill_state:
            default_state.update(initial_skill_state)
        self.skill_mastery: Dict[str, float] = default_state

        self.completed_units: Set[str]        = set()
        self.current_unit_id: Optional[str]   = None
        self.session_start:   float           = time.time()

        self.flashcards:      Dict[str, SM2Flashcard] = {}
        self.last_review_day: Dict[str, int]          = {}

        self.quiz_history: List[Dict] = []
        self.streak_days:  int        = 0

        self.diagnostic_result: Optional[Dict] = None

        self._created_at: float = time.time()
        self.current_day: int   = 0

        self.mistake_log:   List[Dict] = []
        self.concept_index: Dict       = {}

        self.consecutive_failures: Dict[str, int] = {}

    # ──────────────────────────────────────────
    #  BKT quiz result (binary signal)
    # ──────────────────────────────────────────

    def record_quiz_result(
        self,
        unit_id:     str,
        was_correct: bool,
    ) -> Dict:
        """
        Process a single binary quiz answer through BKT.
        Used by /quiz/result (simple binary endpoint).
        """
        skills = self.kg.get_unit_skills(unit_id)
        if not skills:
            return {"error": f"No skills registered for unit {unit_id}"}

        skill_updates: List[Dict] = []

        for skill in skills:
            p_before = self.skill_mastery.get(skill, 0.1)
            params   = self._bkt_params(skill)
            p_after  = bkt_update(
                p_before, was_correct,
                params["p_guess"], params["p_slip"], params["p_trans"],
            )
            self.skill_mastery[skill] = p_after

            if self.logger:
                self.logger.log_bkt_update(skill, p_before, p_after, was_correct)

            skill_updates.append({
                "skill":         skill,
                "p_L_before":    round(p_before, 3),
                "p_L_after":     round(p_after,  3),
                "mastery_level": mastery_to_level(p_after),
                "update_method": "bkt_binary",
            })

        self.quiz_history.append({
            "unit_id":     unit_id,
            "was_correct": was_correct,
            "timestamp":   round(time.time(), 3),
        })

        self._update_streak(was_correct)

        if was_correct:
            self.consecutive_failures[unit_id] = 0
        else:
            self.consecutive_failures[unit_id] = (
                self.consecutive_failures.get(unit_id, 0) + 1
            )
        failure_streak = self.consecutive_failures[unit_id]

        unit_passed = all(
            self.skill_mastery.get(s, 0.0) >= PASS_THRESHOLD
            for s in skills
        )
        if unit_passed and unit_id not in self.completed_units:
            self.completed_units.add(unit_id)
            if self.logger:
                self.logger.log_unit_completed(
                    unit_id, skills[0], self.skill_mastery.get(skills[0], 0.0)
                )
            self._auto_create_flashcard(unit_id)

        stuck_alert        = (not was_correct) and (failure_streak >= STUCK_THRESHOLD)
        prereq_suggestions = self._get_prereq_suggestions(unit_id) if stuck_alert else []

        return {
            "unit_id":                   unit_id,
            "was_correct":               was_correct,
            "skill_updates":             skill_updates,
            "unit_passed":               unit_passed,
            "consecutive_failures":      failure_streak,
            "stuck_alert":               stuck_alert,
            "stuck_threshold":           STUCK_THRESHOLD,
            "prereq_review_suggestions": prereq_suggestions,
        }

    # ──────────────────────────────────────────
    #  IRT-aware quiz result
    # ──────────────────────────────────────────

    def record_quiz_result_irt(
        self,
        unit_id:     str,
        irt_mastery: float,
        irt_passed:  bool,
    ) -> Dict:
        """
        Process a full quiz result using the IRT mastery estimate.

        When passed: blends IRT mastery estimate into BKT state.
            new = IRT_BLEND_ALPHA * irt_mastery + (1 - IRT_BLEND_ALPHA) * bkt_prior
        When failed: fall back to standard BKT binary update (was_correct=False).

        unit_passed uses IRT's own pass/fail decision directly —
        not a re-evaluation of the blended BKT value, which would make
        it impossible for new learners (prior=0.1) to pass.
        """
        skills = self.kg.get_unit_skills(unit_id)
        if not skills:
            return {"error": f"No skills registered for unit {unit_id}"}

        skill_updates: List[Dict] = []

        for skill in skills:
            p_before = self.skill_mastery.get(skill, 0.1)

            if irt_passed:
                p_after = IRT_BLEND_ALPHA * irt_mastery + (1 - IRT_BLEND_ALPHA) * p_before
                p_after = float(min(1.0, max(0.0, p_after)))
                update_method = "irt_blend"
            else:
                params  = self._bkt_params(skill)
                p_after = bkt_update(
                    p_before, False,
                    params["p_guess"], params["p_slip"], params["p_trans"],
                )
                update_method = "bkt_binary"

            self.skill_mastery[skill] = p_after

            if self.logger:
                self.logger.log_bkt_update(skill, p_before, p_after, irt_passed)

            skill_updates.append({
                "skill":         skill,
                "p_L_before":    round(p_before, 3),
                "p_L_after":     round(p_after,  3),
                "mastery_level": mastery_to_level(p_after),
                "update_method": update_method,
            })

        self.quiz_history.append({
            "unit_id":     unit_id,
            "was_correct": irt_passed,
            "irt_mastery": round(irt_mastery, 4),
            "timestamp":   round(time.time(), 3),
        })

        self._update_streak(irt_passed)

        if irt_passed:
            self.consecutive_failures[unit_id] = 0
        else:
            self.consecutive_failures[unit_id] = (
                self.consecutive_failures.get(unit_id, 0) + 1
            )
        failure_streak = self.consecutive_failures[unit_id]

        # Use IRT's pass/fail directly — do NOT re-evaluate blended BKT mastery
        unit_passed = irt_passed
        if unit_passed and unit_id not in self.completed_units:
            self.completed_units.add(unit_id)
            if self.logger:
                self.logger.log_unit_completed(
                    unit_id, skills[0], self.skill_mastery.get(skills[0], 0.0)
                )
            self._auto_create_flashcard(unit_id)

        stuck_alert        = (not irt_passed) and (failure_streak >= STUCK_THRESHOLD)
        prereq_suggestions = self._get_prereq_suggestions(unit_id) if stuck_alert else []

        return {
            "unit_id":                   unit_id,
            "irt_passed":                irt_passed,
            "irt_mastery":               round(irt_mastery, 4),
            "skill_updates":             skill_updates,
            "unit_passed":               unit_passed,
            "consecutive_failures":      failure_streak,
            "stuck_alert":               stuck_alert,
            "stuck_threshold":           STUCK_THRESHOLD,
            "prereq_review_suggestions": prereq_suggestions,
        }

    # ──────────────────────────────────────────
    #  Mistake tracking
    # ──────────────────────────────────────────

    def record_quiz_answer(
        self,
        question:    Dict,
        was_correct: bool,
        unit_id:     str,
        topic:       str,
    ) -> None:
        """
        Record one quiz answer into mistake_log and concept_index.
        Call for EVERY question answered (correct and incorrect).
        topic should be the skill name (e.g. 'recursion') not the domain.
        """
        qid   = question.get("question_id", "unknown")
        diff  = question.get("difficulty", "medium")
        irt_b = question.get("irt_b", 0.5)
        tags  = question.get("tags") or [topic]

        event = make_mistake_event(
            question_id=  qid,
            unit_id=      unit_id,
            topic=        topic,
            concept_tags= tags,
            difficulty=   diff,
            irt_b=        irt_b,
            timestamp=    round(time.time(), 3),
            attempt_num=  self._get_attempt_num(qid),
            was_correct=  was_correct,
        )

        self.mistake_log.append(event)
        if len(self.mistake_log) > 500:
            self.mistake_log = self.mistake_log[-500:]

        self.concept_index = update_concept_index(
            index=        self.concept_index,
            concept_tags= tags,
            was_correct=  was_correct,
            difficulty=   diff,
            timestamp=    event["timestamp"],
        )

        self._prune_concept_index()

    def get_insights(self) -> Dict:
        return generate_insights(self.mistake_log, self.concept_index)

    def _get_attempt_num(self, question_id: str) -> int:
        return sum(1 for e in self.mistake_log if e.get("question_id") == question_id) + 1

    def _prune_concept_index(self, max_inactive_days: int = 30) -> None:
        """Remove concept_index entries with no activity in max_inactive_days."""
        cutoff    = time.time() - (max_inactive_days * 86400)
        to_remove = [
            tag for tag, entry in self.concept_index.items()
            if max(entry.get("last_correct_ts") or 0.0,
                   entry.get("last_wrong_ts")   or 0.0) < cutoff
        ]
        for tag in to_remove:
            del self.concept_index[tag]

    # ──────────────────────────────────────────
    #  SM-2 flashcard management
    # ──────────────────────────────────────────

    def review_flashcard(
        self,
        unit_id:     str,
        quality:     int,
        current_day: int,
    ) -> Dict:
        if unit_id not in self.flashcards:
            self.flashcards[unit_id] = SM2Flashcard(unit_id)

        card = self.flashcards[unit_id]
        card.update(quality)
        self.last_review_day[unit_id] = current_day

        if self.logger:
            self.logger.log_flashcard_review(unit_id, quality, card.interval)

        return {
            "unit_id":      unit_id,
            "new_interval": card.interval,
            "next_due_day": current_day + card.interval,
            "ease_factor":  round(card.ease_factor, 2),
        }

    def get_due_flashcards(self, current_day: int) -> List[str]:
        return [
            uid for uid, card in self.flashcards.items()
            if card.is_due(current_day, self.last_review_day.get(uid, 0))
        ]

    def _auto_create_flashcard(self, unit_id: str) -> None:
        """
        Create a new SM-2 flashcard for a just-passed unit.
        Sets interval=1 so the card is due tomorrow, not immediately.
        """
        if unit_id not in self.flashcards:
            elapsed = int((time.time() - self._created_at) / 86400)
            card = SM2Flashcard(unit_id)
            card.interval = 1                          # due tomorrow, not today
            self.flashcards[unit_id]      = card
            self.last_review_day[unit_id] = elapsed

    def get_due_flashcards_detail(self, current_day: int) -> List[Dict]:
        due = []
        for unit_id, card in self.flashcards.items():
            if card.is_due(current_day, self.last_review_day.get(unit_id, 0)):
                days_overdue = max(0, current_day
                    - self.last_review_day.get(unit_id, 0)
                    - card.interval)
                due.append({
                    "unit_id":      unit_id,
                    "ease_factor":  round(card.ease_factor, 2),
                    "interval":     card.interval,
                    "repetitions":  card.repetitions,
                    "days_overdue": days_overdue,
                    "_sort_key":    days_overdue,
                })
        due.sort(key=lambda x: -x["_sort_key"])
        for d in due:
            del d["_sort_key"]
        return due

    # ──────────────────────────────────────────
    #  Accessors
    # ──────────────────────────────────────────

    def get_mastery_state(self) -> Dict[str, float]:
        return dict(self.skill_mastery)

    def get_mastery_summary(self) -> List[Dict]:
        return [
            {
                "skill":   skill,
                "mastery": round(p_L, 3),
                "level":   mastery_to_level(p_L),
            }
            for skill, p_L in self.skill_mastery.items()
        ]

    def is_unit_completed(self, unit_id: str) -> bool:
        return unit_id in self.completed_units

    def get_current_day(self) -> int:
        return self.current_day

    def get_progress_summary(self) -> Dict:
        total     = len(self.kg.units)
        completed = len(self.completed_units)
        return {
            "user_id":          self.user_id,
            "units_total":      total,
            "units_completed":  completed,
            "percent_complete": round(completed / total * 100, 1) if total else 0,
            "streak_days":      self.streak_days,
            "mastery_summary":  self.get_mastery_summary(),
        }

    # ──────────────────────────────────────────
    #  Serialisation
    # ──────────────────────────────────────────

    def to_dict(self) -> Dict:
        return {
            "user_id":              self.user_id,
            "skill_mastery":        {k: round(v, 4) for k, v in self.skill_mastery.items()},
            "completed_units":      list(self.completed_units),
            "current_unit_id":      self.current_unit_id,
            "streak_days":          self.streak_days,
            "flashcards":           {uid: card.to_dict() for uid, card in self.flashcards.items()},
            "last_review_day":      self.last_review_day,
            "quiz_history":         self.quiz_history[-50:],
            "diagnostic_result":    self.diagnostic_result,
            "current_day":          self.current_day,
            "_created_at":          self._created_at,
            "mistake_log":          self.mistake_log[-500:],
            "concept_index":        self.concept_index,
            "consecutive_failures": self.consecutive_failures,
        }

    @classmethod
    def from_dict(
        cls,
        data:   Dict,
        kg:     KnowledgeGraph,
        logger: Optional[AnalyticsLogger] = None,
    ) -> "LearnerSession":
        session = cls(
            user_id=data["user_id"],
            kg=kg,
            initial_skill_state=data.get("skill_mastery", {}),
            logger=logger,
        )
        session.completed_units        = set(data.get("completed_units", []))
        session.current_unit_id        = data.get("current_unit_id")
        session.streak_days            = data.get("streak_days", 0)
        session.diagnostic_result      = data.get("diagnostic_result")
        session.current_day            = data.get("current_day", 0)
        # Migrate legacy sessions that predate _created_at field
        session._created_at            = data.get("_created_at") or time.time()
        session.mistake_log            = data.get("mistake_log", [])
        session.concept_index          = data.get("concept_index", {})
        session.consecutive_failures   = data.get("consecutive_failures", {})
        session.last_review_day        = data.get("last_review_day", {})
        session.quiz_history           = data.get("quiz_history", [])

        for uid, card_data in data.get("flashcards", {}).items():
            session.flashcards[uid] = SM2Flashcard.from_dict(card_data)

        return session

    # ──────────────────────────────────────────
    #  Private helpers
    # ──────────────────────────────────────────

    def _bkt_params(self, skill: str) -> Dict[str, float]:
        overrides = self.bkt_params.get(skill, {})
        return {
            "p_trans": overrides.get("p_trans", 0.15),
            "p_guess": overrides.get("p_guess", 0.20),
            "p_slip":  overrides.get("p_slip",  0.10),
        }

    def _update_streak(self, was_correct: bool) -> None:
        """
        Increment streak on consecutive correct-answer days.
        Resets to 0 on any wrong answer.
        Resets to 1 on a gap of more than one day.
        """
        if not was_correct:
            self.streak_days = 0
            return

        now_day = int(time.time() / 86400)   # days since Unix epoch (UTC)

        if len(self.quiz_history) < 2:
            # First quiz ever — start streak at 1
            self.streak_days = 1
            return

        # quiz_history[-1] is the entry we just appended; [-2] is the previous one
        prev_entry = self.quiz_history[-2]
        prev_day   = int(prev_entry["timestamp"] / 86400)

        if prev_day == now_day - 1:
            self.streak_days += 1       # consecutive day — extend streak
        elif prev_day == now_day:
            pass                        # same day — keep existing streak
        else:
            self.streak_days = 1        # gap — reset to 1 (today counts)

    # ── FIX: _get_prereq_suggestions is now its own correctly-indented method ──
    # Previously the body of this method was accidentally merged inside
    # _update_streak (wrong indentation), making it completely unreachable.
    # The stuck_alert feature was silently doing nothing as a result.

    def _get_prereq_suggestions(self, unit_id: str) -> List[Dict]:
        """
        Return a list of prerequisite skills the learner should review
        when they are stuck (3+ consecutive failures) on a unit.

        Sorted by current mastery ascending — weakest prereq first.
        """
        meta          = self.kg.get_unit_metadata(unit_id)
        prereq_skills = meta.get("prereq_skills", set())

        if not prereq_skills:
            return [{
                "message":  "This unit has no prerequisites. Review the unit notes carefully.",
                "unit_id":  unit_id,
            }]

        suggestions = []
        for skill in prereq_skills:
            current_mastery = self.skill_mastery.get(skill, 0.0)
            teaching_unit   = next(
                (uid for uid, umeta in self.kg.units.items()
                 if skill in umeta.get("skills_taught", [])),
                None,
            )
            suggestions.append({
                "prereq_skill":    skill,
                "current_mastery": round(current_mastery, 3),
                "mastery_level":   mastery_to_level(current_mastery),
                "teaching_unit":   teaching_unit,
                "display_name":    self.kg.get_display_name(teaching_unit) if teaching_unit else skill,
                "needs_review":    current_mastery < 0.70,
                "message": (
                    f"Your mastery of '{skill}' is {current_mastery:.0%}. "
                    f"Review '{self.kg.get_display_name(teaching_unit)}' before retrying."
                    if teaching_unit
                    else f"Review the concept '{skill}' before retrying."
                ),
            })

        suggestions.sort(key=lambda x: x["current_mastery"])
        return suggestions
