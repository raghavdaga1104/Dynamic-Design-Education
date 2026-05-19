"""
adaptive_systems.py
-------------------
Core adaptive learning algorithms:
  - BKT  : Bayesian Knowledge Tracing  (skill mastery tracking)
  - IRT  : Item Response Theory        (question difficulty modelling)
  - SM-2 : SuperMemo-2                 (spaced repetition scheduling)

FIX APPLIED (Review §3 Bug #2 / §4.1):
  irt_select_best_question previously compared learner_mastery (a [0,1]
  probability) directly to IRT b-parameters. These are on different scales:
    - learner_mastery = P(Learned) from BKT, range [0,1]
    - b parameter     = IRT difficulty, conceptually on logit scale
                        (stored as 0.30 / 0.60 / 0.90 in quiz_bank.py)

  The comparison appeared to work coincidentally because both values sat
  in the same numeric range, but was not mathematically justified. A
  learner with mastery=0.10 (beginner, theta≈−2.2) was being compared
  to b=0.30 as if they were on the same scale. The correct comparison
  is theta vs b.

  Fix: convert mastery → theta via mastery_to_theta (logit) before
  finding the closest question. This is the same conversion used in
  irt_probability_correct and irt_scoring.py — one consistent scale.
"""

import math
import logging
from typing import Dict, List, Tuple, Optional

from python_source.core.irt_scoring import mastery_to_theta

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  BAYESIAN KNOWLEDGE TRACING  (BKT)
# ─────────────────────────────────────────────

def bkt_update(
    p_L: float,
    observed_correct: bool,
    p_guess: float,
    p_slip: float,
    p_trans: float,
) -> float:
    """
    Update a learner's skill mastery probability after one quiz observation.

    BKT models mastery as a Hidden Markov Model:
      Hidden state  : whether the learner truly knows the skill
      Observed state: whether they answered correctly

    Parameters
    ----------
    p_L             : current P(Learned) — probability learner knows the skill
    observed_correct: True if they answered correctly
    p_guess         : P(correct | NOT learned) — lucky guess probability
    p_slip          : P(incorrect | learned)   — careless mistake probability
    p_trans         : P(learns after one opportunity) — learning rate

    Returns
    -------
    Updated P(Learned) after the observation
    """
    p_correct   = p_L * (1 - p_slip) + (1 - p_L) * p_guess
    p_incorrect = 1.0 - p_correct

    if observed_correct:
        posterior = (p_L * (1 - p_slip)) / p_correct   if p_correct   > 0 else 0.0
    else:
        posterior = (p_L * p_slip)        / p_incorrect if p_incorrect > 0 else 0.0

    p_next = posterior + (1 - posterior) * p_trans
    return float(min(1.0, max(0.0, p_next)))


def bkt_expected_update(
    p_L: float,
    p_guess: float,
    p_slip: float,
    p_trans: float,
) -> float:
    """
    Expected mastery after one opportunity (used in MCTS tree expansion).
    Averages the correct and incorrect update paths weighted by their probability.
    Deterministic — keeps the MCTS tree structure stable across iterations.
    """
    p_correct   = p_L * (1 - p_slip) + (1 - p_L) * p_guess
    p_incorrect = 1.0 - p_correct

    posterior_correct   = (p_L * (1 - p_slip)) / p_correct   if p_correct   > 0 else 0.0
    posterior_incorrect = (p_L * p_slip)        / p_incorrect if p_incorrect > 0 else 0.0

    p_next_correct   = posterior_correct   + (1 - posterior_correct)   * p_trans
    p_next_incorrect = posterior_incorrect + (1 - posterior_incorrect) * p_trans

    expected = p_correct * p_next_correct + p_incorrect * p_next_incorrect
    return float(min(1.0, max(0.0, expected)))


def mastery_to_level(p_L: float) -> str:
    """Convert a mastery probability to a human-readable level label."""
    if p_L < 0.3:
        return "Beginner"
    elif p_L < 0.6:
        return "Developing"
    elif p_L < 0.8:
        return "Proficient"
    else:
        return "Mastered"


# ─────────────────────────────────────────────
#  ITEM RESPONSE THEORY  (IRT — 2PL model)
# ─────────────────────────────────────────────

def irt_probability_correct(
    learner_mastery: float,
    item_difficulty: float,
    item_discrimination: float,
) -> float:
    """
    2-Parameter Logistic IRT: probability of a correct response.

    P(correct) = 1 / (1 + exp(-D * a * (theta - b)))

    Parameters
    ----------
    learner_mastery     : BKT P(Learned) on [0,1] — converted to theta via logit
    item_difficulty     : b parameter (stored on [0,1] scale in curriculum.py)
    item_discrimination : a parameter
    """
    D        = 1.702
    theta    = mastery_to_theta(learner_mastery)   # [0,1] → IRT scale
    exponent = max(-500, min(500, -D * item_discrimination * (theta - item_difficulty)))
    return 1.0 / (1.0 + math.exp(exponent))


def irt_select_best_question(
    learner_mastery: float,
    questions: List[Dict],
) -> Optional[Dict]:
    """
    Select the most informative question for the learner's current ability.

    The most informative question is the one whose IRT difficulty (b) is
    closest to the learner's current ability (theta) — it sits at the
    learner's edge, maximising information gain.

    FIX: previously compared learner_mastery directly to b, which conflated
    two different scales. Now converts mastery → theta (logit) first so the
    comparison is on the same IRT scale as the b parameters.

    Parameters
    ----------
    learner_mastery : current BKT mastery probability for the skill, [0,1]
    questions       : list of question dicts, each with 'difficulty' key

    Returns
    -------
    The question dict that best matches the learner's ability
    """
    if not questions:
        return None

    # Convert BKT mastery [0,1] → IRT theta (logit scale) for correct comparison
    theta = mastery_to_theta(learner_mastery)

    def _get_b(q: Dict) -> float:
        """Extract the IRT b parameter from a question dict."""
        if "irt_b" in q:
            return float(q["irt_b"])
        # Fall back to difficulty-label mapping
        d = q.get("difficulty", "medium")
        return {"easy": 0.30, "medium": 0.60, "hard": 0.90}.get(d, 0.60)

    best = min(questions, key=lambda q: abs(_get_b(q) - theta))
    return best


# ─────────────────────────────────────────────
#  SM-2  SPACED REPETITION  (SuperMemo)
# ─────────────────────────────────────────────

class SM2Flashcard:
    """
    Implements the SuperMemo SM-2 spaced repetition algorithm.

    Tracks three state variables per flashcard:
      repetitions : how many consecutive correct reviews
      interval    : days until next review
      ease_factor : controls how fast intervals grow (starts at 2.5)

    Quality grades (q):
      0 = complete blackout
      1 = incorrect, but remembered after hint
      2 = incorrect, but easy to recall
      3 = correct, with serious difficulty
      4 = correct, after hesitation
      5 = perfect response
    """

    def __init__(self, unit_id: str):
        self.unit_id      = unit_id
        self.ease_factor  = 2.5
        self.interval     = 1      # start at 1 (due tomorrow, not today)
        self.repetitions  = 0

    def update(self, quality: int) -> None:
        """Update flashcard schedule based on quality of recall (0-5)."""
        quality = max(0, min(5, quality))

        if quality >= 3:
            if self.repetitions == 0:
                self.interval = 1
            elif self.repetitions == 1:
                self.interval = 6
            else:
                self.interval = math.ceil(self.interval * self.ease_factor)
            self.repetitions += 1
        else:
            self.repetitions = 0
            self.interval    = 1

        # SM-2 ease factor update formula
        self.ease_factor += 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        self.ease_factor  = max(1.3, self.ease_factor)   # floor at 1.3 per spec

    def is_due(self, current_day: int, last_review_day: int) -> bool:
        """Return True if this card is due for review today or overdue."""
        return (last_review_day + self.interval) <= current_day

    def to_dict(self) -> Dict:
        return {
            "unit_id":     self.unit_id,
            "ease_factor": round(self.ease_factor, 4),
            "interval":    self.interval,
            "repetitions": self.repetitions,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SM2Flashcard":
        card             = cls(data["unit_id"])
        card.ease_factor = data.get("ease_factor", 2.5)
        card.interval    = data.get("interval",    1)
        card.repetitions = data.get("repetitions", 0)
        return card
