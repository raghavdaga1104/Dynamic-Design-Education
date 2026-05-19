"""
irt_scoring.py
--------------
NEW FILE — IRT-based quiz mastery estimation.

Replaces the fixed 80% pass rule with a principled ability estimate.

The system uses the 2-Parameter Logistic (2PL) IRT model with
Maximum Likelihood Estimation to find the learner's ability (θ)
that best explains their observed quiz responses.

This file is self-contained and has no dependencies on other
project files — it can be imported anywhere.

Mathematical background
───────────────────────
2PL IRT model:
  P(correct | θ, b, a) = 1 / (1 + exp(-D * a * (θ - b)))

  θ = learner ability        (what we estimate, range: -3 to +3)
  b = item difficulty        (stored per question, same range)
  a = item discrimination    (stored per question, range: 0.5 to 2.0)
  D = 1.702                  (scaling constant — standard in IRT)

MLE estimation:
  Find θ that maximises:
    L(θ) = Σ [ u_i * log(P_i) + (1-u_i) * log(1-P_i) ]

  where u_i = 1 if correct, 0 if incorrect
  This is solved numerically using gradient ascent (simple, fast).

Mapping θ to mastery (0-1 scale):
  mastery = sigmoid(θ) = 1 / (1 + exp(-θ))
  This maps: θ=-3 → 0.05, θ=0 → 0.50, θ=1 → 0.73, θ=3 → 0.95

Pass threshold:
  θ_pass = 0.619  →  mastery = 0.65  →  65% mastery
  This means the learner can reliably answer medium-difficulty
  questions correctly — equivalent to the BKT 0.70 threshold
  but measured from quiz performance rather than history.
"""

import math
from typing import Dict, List, Tuple, Optional


# ─────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────

D             = 1.702      # IRT scaling constant (standard)
THETA_MIN     = -4.0       # Lower bound for ability estimation
THETA_MAX     =  4.0       # Upper bound
THETA_INIT    =  0.0       # Starting point for MLE search
LEARNING_RATE = 0.1        # Gradient ascent step size
MAX_ITER      = 100        # Iterations for convergence
CONVERGENCE   = 1e-6       # Stop when change is smaller than this

# Pass threshold: θ ≥ 0.619 → mastery ≥ 0.65
# Aligned with existing BKT mastery threshold of 0.70
# (IRT and BKT measure the same latent variable on slightly different scales)
PASS_THETA    = 0.619

# Fallback IRT parameters when not specified in question
# Maps string difficulty labels to (b, a) pairs
DEFAULT_IRT_PARAMS = {
    "easy":   (0.30, 1.20),
    "medium": (0.60, 1.00),
    "hard":   (0.90, 0.80),
}


# ─────────────────────────────────────────────────────────────────
#  CORE IRT FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def p_correct(theta: float, b: float, a: float) -> float:
    """
    2PL IRT: probability of a correct response.

    Parameters
    ----------
    theta : learner ability estimate
    b     : item difficulty
    a     : item discrimination
    """
    exponent = -D * a * (theta - b)
    # Clamp to avoid overflow
    exponent = max(-500, min(500, exponent))
    return 1.0 / (1.0 + math.exp(exponent))


def log_likelihood(theta: float, responses: List[Dict]) -> float:
    """
    Log-likelihood of observing these responses given ability theta.

    Parameters
    ----------
    theta     : ability value to evaluate
    responses : list of dicts with keys: b, a, correct (bool)
    """
    ll = 0.0
    for r in responses:
        p = p_correct(theta, r["b"], r["a"])
        p = max(1e-10, min(1 - 1e-10, p))   # avoid log(0)
        if r["correct"]:
            ll += math.log(p)
        else:
            ll += math.log(1.0 - p)
    return ll


def gradient(theta: float, responses: List[Dict]) -> float:
    """
    Gradient of log-likelihood with respect to theta.
    Used for gradient ascent in MLE.
    """
    grad = 0.0
    for r in responses:
        p    = p_correct(theta, r["b"], r["a"])
        u    = 1.0 if r["correct"] else 0.0
        grad += D * r["a"] * (u - p)
    return grad


def estimate_theta(responses: List[Dict]) -> float:
    """
    Find the MLE estimate of learner ability (θ) given quiz responses.

    Uses gradient ascent with adaptive step size.
    Handles edge cases: all correct → returns high θ,
                        all wrong   → returns low θ.

    Parameters
    ----------
    responses : list of dicts, each with:
        b       : float — IRT difficulty of the question
        a       : float — IRT discrimination
        correct : bool  — whether the learner answered correctly

    Returns
    -------
    float — estimated θ (ability), range approximately -3 to +3
    """
    if not responses:
        return THETA_INIT

    # Edge case: all correct → high ability
    if all(r["correct"] for r in responses):
        return THETA_MAX * 0.8   # 3.2 — high but not maximum

    # Edge case: all wrong → low ability
    if not any(r["correct"] for r in responses):
        return THETA_MIN * 0.8   # -3.2

    # Gradient ascent
    theta = THETA_INIT
    lr    = LEARNING_RATE

    for _ in range(MAX_ITER):
        grad      = gradient(theta, responses)
        theta_new = theta + lr * grad
        theta_new = max(THETA_MIN, min(THETA_MAX, theta_new))

        if abs(theta_new - theta) < CONVERGENCE:
            break

        theta = theta_new

    return round(theta, 4)


def theta_to_mastery(theta: float) -> float:
    """
    Convert θ (unbounded IRT scale) to mastery probability (0-1).
    Uses sigmoid: mastery = 1 / (1 + exp(-θ))

    Reference points:
      θ = -2.0 → mastery = 0.12  (very low)
      θ =  0.0 → mastery = 0.50  (average)
      θ =  0.6 → mastery = 0.65  (pass threshold)
      θ =  1.0 → mastery = 0.73  (proficient)
      θ =  2.0 → mastery = 0.88  (advanced)
    """
    return round(1.0 / (1.0 + math.exp(-theta)), 4)


# NEW — Inverse of theta_to_mastery.
# This is the canonical logit transform used by adaptive_systems.py
# to convert BKT mastery into IRT theta before computing P(correct).
# Defined here (irt_scoring.py) as the single source of truth.
def mastery_to_theta(mastery: float) -> float:
    """
    Convert BKT mastery probability [0,1] → IRT ability θ [-inf, +inf].

    Uses the logit (log-odds) transform — the exact inverse of sigmoid:
      θ = log( p / (1 - p) )

    This is necessary because irt_probability_correct uses theta on the
    standard IRT scale, while BKT tracks mastery on [0,1]. Using mastery
    directly as theta produces errors of up to 0.31 in P(correct).

    Reference points:
      mastery = 0.10 → θ = -2.197
      mastery = 0.30 → θ = -0.847
      mastery = 0.50 → θ =  0.000
      mastery = 0.70 → θ = +0.847
      mastery = 0.90 → θ = +2.197

    Parameters
    ----------
    mastery : BKT P(Learned), must be in (0, 1)

    Returns
    -------
    float — theta on IRT scale
    """
    # Clamp to avoid log(0) at the boundaries
    mastery = max(1e-6, min(1.0 - 1e-6, mastery))
    return math.log(mastery / (1.0 - mastery))


# ─────────────────────────────────────────────────────────────────
#  HIGH-LEVEL QUIZ SCORING API
# ─────────────────────────────────────────────────────────────────

def get_irt_params(question: Dict) -> Tuple[float, float]:
    """
    Extract IRT parameters from a question dict.

    Priority:
    1. Use irt_b and irt_a if explicitly set on the question
    2. Fall back to defaults based on string 'difficulty' label
    3. Fall back to medium defaults if neither is present

    Backward compatible — all existing questions without irt_b/irt_a
    will use their string difficulty label for defaults.
    """
    if "irt_b" in question and "irt_a" in question:
        return float(question["irt_b"]), float(question["irt_a"])

    difficulty = question.get("difficulty", "medium")
    return DEFAULT_IRT_PARAMS.get(difficulty, DEFAULT_IRT_PARAMS["medium"])


def score_quiz(
    questions:   List[Dict],
    user_answers: Dict[str, int],   # {question_id: chosen_index}
) -> Dict:
    """
    Score a quiz using IRT-based mastery estimation.

    Replaces the fixed 80% pass rule.

    Parameters
    ----------
    questions    : list of question dicts from quiz_bank.py
    user_answers : dict mapping question_id → chosen answer index

    Returns
    -------
    dict with:
      theta           : float — estimated ability on IRT scale
      mastery         : float — mastery probability (0-1)
      passed          : bool  — mastery >= PASS_THRESHOLD (0.65)
      raw_correct     : int   — number of correct answers
      raw_total       : int   — total questions answered
      raw_percent     : float — simple percentage (kept for display)
      question_detail : list  — per-question breakdown
      explanation     : str   — human-readable result message
    """
    if not questions:
        return {"error": "No questions provided."}

    question_map = {q["question_id"]: q for q in questions}
    responses    = []
    detail       = []
    raw_correct  = 0

    for q in questions:
        qid       = q["question_id"]
        chosen    = user_answers.get(qid)
        correct   = (chosen == q["correct_idx"]) if chosen is not None else False
        b, a      = get_irt_params(q)

        if correct:
            raw_correct += 1

        responses.append({"b": b, "a": a, "correct": correct})

        detail.append({
            "question_id":  qid,
            "difficulty":   q.get("difficulty", "medium"),
            "irt_b":        b,
            "irt_a":        a,
            "chosen_idx":   chosen,
            "correct_idx":  q["correct_idx"],
            "is_correct":   correct,
            # Contribution: how much this correct answer raises ability
            "p_at_threshold": round(p_correct(PASS_THETA, b, a), 3),
        })

    # Estimate ability
    theta   = estimate_theta(responses)
    mastery = theta_to_mastery(theta)
    passed  = mastery >= 0.65

    # Compute simple percentage for display
    raw_percent = round((raw_correct / len(questions)) * 100, 1)

    explanation = _build_explanation(theta, mastery, passed, raw_correct, len(questions))

    return {
        "theta":           theta,
        "mastery":         mastery,
        "passed":          passed,
        "pass_threshold":  0.65,
        "raw_correct":     raw_correct,
        "raw_total":       len(questions),
        "raw_percent":     raw_percent,
        "question_detail": detail,
        "explanation":     explanation,
    }


def _build_explanation(
    theta: float,
    mastery: float,
    passed: bool,
    correct: int,
    total: int,
) -> str:
    """Human-readable explanation of the IRT result."""
    if passed:
        if mastery >= 0.85:
            level = "Excellent mastery"
        elif mastery >= 0.75:
            level = "Strong mastery"
        else:
            level = "Sufficient mastery"
        return (
            f"{level} demonstrated. "
            f"You answered {correct}/{total} questions correctly. "
            f"Your ability estimate is θ={theta:.2f} (mastery={mastery:.0%}). "
            f"Unit unlocked."
        )
    else:
        gap = round((0.65 - mastery) * 100, 1)
        return (
            f"Not yet at passing level. "
            f"You answered {correct}/{total} questions correctly. "
            f"Your ability estimate is θ={theta:.2f} (mastery={mastery:.0%}). "
            f"You need {gap}% more mastery to pass. "
            f"Review the unit notes and try again."
        )
