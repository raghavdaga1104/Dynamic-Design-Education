"""
mistake_tracker.py
------------------
Tracks incorrect quiz answers and generates weakness insights.

Architecture
────────────
Two layers:

1. MistakeLog (raw events)
   Every wrong answer is appended as an immutable event.
   Never modified after writing — used for historical analysis
   and future ML training data.

2. ConceptIndex (running aggregate)
   {concept_tag: {correct, wrong, last_wrong_ts, last_correct_ts}}
   Updated in-place on every quiz answer.
   Used for fast insight generation without scanning the full log.

Insight generation uses weighted frequency scoring with recency decay:
  weakness_score(concept) = Σ wrong_events × e^(-λ × days_since_event)
  λ = 0.1 → halves weight every ~7 days

This means recent mistakes matter more than old ones.
A concept you mastered last week but struggled with today scores high.
A concept you struggled with 3 weeks ago but now get right scores low.

ML upgrade path
───────────────
When you have 500+ mistake events per user, replace weakness_score
with a trained logistic regression:
  features: [wrong_rate, recency_score, avg_difficulty, attempts_since_last_wrong]
  target:   P(wrong on next attempt)
The schema here is designed to support that transition directly.
"""

import math
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────

# Recency decay constant
# λ = 0.1 → e^(-0.1 × 7) ≈ 0.50 → 7-day-old mistakes count at 50%
# λ = 0.1 → e^(-0.1 × 14) ≈ 0.25 → 14-day-old mistakes count at 25%
LAMBDA_DECAY = 0.1

# Minimum weakness score to be reported as a weakness
WEAKNESS_THRESHOLD = 0.8

# Minimum attempts before a concept can be called a weakness
# (avoids reporting a concept as weak after just 1 attempt)
MIN_ATTEMPTS_FOR_INSIGHT = 2

# Difficulty label → numeric weight for scoring
DIFFICULTY_WEIGHT = {"easy": 1.0, "medium": 1.5, "hard": 2.0}

# ─────────────────────────────────────────────────────────────────
#  MISTAKE EVENT
# ─────────────────────────────────────────────────────────────────

def make_mistake_event(
    question_id:  str,
    unit_id:      str,
    topic:        str,
    concept_tags: List[str],
    difficulty:   str,
    irt_b:        float = 0.5,
    timestamp:    Optional[float] = None,
    attempt_num:  int = 1,
    was_correct:  bool = False,
) -> Dict:
    """
    Create a standardised mistake/attempt event dict.
    Both correct and incorrect answers are logged —
    correct answers are needed to compute wrong_rate accurately.
    """
    return {
        "question_id":  question_id,
        "unit_id":      unit_id,
        "topic":        topic,
        "concept_tags": concept_tags,
        "difficulty":   difficulty,
        "irt_b":        round(irt_b, 3),
        "timestamp":    timestamp or round(time.time(), 3),
        "attempt_num":  attempt_num,
        "was_correct":  was_correct,
    }


# ─────────────────────────────────────────────────────────────────
#  CONCEPT INDEX — running aggregate
# ─────────────────────────────────────────────────────────────────

def update_concept_index(
    index:        Dict,
    concept_tags: List[str],
    was_correct:  bool,
    difficulty:   str,
    timestamp:    float,
) -> Dict:
    """
    Update the running concept aggregate with one quiz answer.

    index structure:
    {
      "concept_tag": {
        "correct":          int,
        "wrong":            int,
        "last_wrong_ts":    float | None,
        "last_correct_ts":  float | None,
        "difficulty_wrong_counts": {"easy": int, "medium": int, "hard": int}
      }
    }
    """
    for tag in concept_tags:
        if tag not in index:
            index[tag] = {
                "correct":          0,
                "wrong":            0,
                "last_wrong_ts":    None,
                "last_correct_ts":  None,
                "difficulty_wrong_counts": {"easy": 0, "medium": 0, "hard": 0},
            }

        entry = index[tag]
        if was_correct:
            entry["correct"]         += 1
            entry["last_correct_ts"]  = timestamp
        else:
            entry["wrong"]           += 1
            entry["last_wrong_ts"]    = timestamp
            diff_key = difficulty if difficulty in entry["difficulty_wrong_counts"] else "medium"
            entry["difficulty_wrong_counts"][diff_key] += 1

    return index


# ─────────────────────────────────────────────────────────────────
#  RECENCY-WEIGHTED WEAKNESS SCORING
# ─────────────────────────────────────────────────────────────────

def compute_weakness_score(
    mistake_log:  List[Dict],
    concept_tag:  str,
    now:          Optional[float] = None,
) -> float:
    """
    Compute the recency-weighted weakness score for one concept.

    weakness_score = Σ difficulty_weight × e^(-λ × days_since_mistake)

    Only incorrect answers contribute to the score.
    Higher score = more recent and more frequent mistakes on this concept.
    """
    if now is None:
        now = time.time()

    score = 0.0
    for event in mistake_log:
        if event.get("was_correct", True):
            continue
        if concept_tag not in event.get("concept_tags", []):
            continue

        days_ago = (now - event["timestamp"]) / 86400
        decay    = math.exp(-LAMBDA_DECAY * days_ago)
        weight   = DIFFICULTY_WEIGHT.get(event.get("difficulty", "medium"), 1.5)
        score   += weight * decay

    return round(score, 4)


def rank_weaknesses(
    mistake_log:    List[Dict],
    concept_index:  Dict,
    now:            Optional[float] = None,
    top_n:          int = 5,
) -> List[Dict]:
    """
    Rank all tracked concepts by weakness score.
    Filters out concepts with too few attempts to be meaningful.

    Returns top_n weakest concepts sorted by score descending.
    """
    if now is None:
        now = time.time()

    ranked = []
    for tag, entry in concept_index.items():
        total_attempts = entry["correct"] + entry["wrong"]
        if total_attempts < MIN_ATTEMPTS_FOR_INSIGHT:
            continue
        if entry["wrong"] == 0:
            continue

        score     = compute_weakness_score(mistake_log, tag, now)
        wrong_rate = entry["wrong"] / total_attempts

        ranked.append({
            "concept":       tag,
            "weakness_score": score,
            "wrong_rate":    round(wrong_rate, 3),
            "wrong_count":   entry["wrong"],
            "correct_count": entry["correct"],
            "total_attempts": total_attempts,
            "last_wrong_ts": entry["last_wrong_ts"],
            "difficulty_breakdown": entry["difficulty_wrong_counts"],
        })

    ranked.sort(key=lambda x: -x["weakness_score"])
    return ranked[:top_n]



# ─────────────────────────────────────────────────────────────────
#  MCTS INTEGRATION — Skill-level weakness map
# ─────────────────────────────────────────────────────────────────

def build_skill_weakness_map(
    concept_index: Dict,
    mistake_log:   List[Dict],
    now:           Optional[float] = None,
) -> Dict[str, float]:
    """
    NEW — Convert concept-tag weakness scores into skill-level scores
    that MCTS can consume directly.

    Why this function is needed
    ───────────────────────────
    mistake_tracker operates on concept tags (e.g. "space complexity",
    "call stack", "LIFO") which come from the quiz question tags field.

    MCTS operates on skill names (e.g. "recursion", "python basics")
    which come from the KnowledgeGraph skills_taught field.

    These are different namespaces. This function bridges them by
    matching concept tags to skills using substring containment:
      concept tag "call stack"  → matches skill "recursion" (call stack is a recursion concept)
      concept tag "LIFO"        → matches skill "stacks and queues"
      concept tag "recursion"   → matches skill "recursion" directly

    Parameters
    ----------
    concept_index : {concept_tag: {correct, wrong, last_wrong_ts, ...}}
                    from session.concept_index
    mistake_log   : raw event log from session.mistake_log
    now           : current timestamp (uses time.time() if None)

    Returns
    -------
    Dict[str, float] — {skill_name: weakness_score (0-1 normalised)}

    The scores are normalised to [0,1] so MCTS weight (W_WEAKNESS=0.15)
    produces a consistent bonus regardless of mistake volume.
    """
    if now is None:
        now = time.time()

    if not concept_index or not mistake_log:
        return {}

    # Step 1: compute raw weakness score per concept tag
    raw_scores: Dict[str, float] = {}
    for tag in concept_index:
        score = compute_weakness_score(mistake_log, tag, now)
        if score > 0:
            raw_scores[tag] = score

    if not raw_scores:
        return {}

    # Step 2: build skill → weakness score by matching concept tags to skills.
    # A concept tag matches a skill if either:
    #   a) concept tag is a substring of the skill name, or
    #   b) skill name is a substring of the concept tag.
    # This handles:
    #   "recursion" ↔ "recursion" (exact)
    #   "space complexity" ↔ "recursion" (via concept tag in question tags)
    #   "LIFO" ↔ "stacks and queues" — no match (intentionally — unrelated strings)
    # For concept tags that don't match any skill directly, we use a fallback:
    # match to the most recently failed unit's skill.
    skill_scores: Dict[str, float] = {}

    for tag, score in raw_scores.items():
        matched = False

        for event in mistake_log:
            if tag not in event.get("concept_tags", []):
                continue
            # FIX: always use the 'topic' field which is set to skills[0]
            # in main.py. Old code had a domain fallback (e.g. "algorithms")
            # that never matched any skill name in MCTS, silently killing
            # the weakness bonus for those units. topic is always a skill name.
            unit_skill = event.get("topic", "").strip()
            if unit_skill:
                current = skill_scores.get(unit_skill, 0.0)
                skill_scores[unit_skill] = max(current, score)
                matched = True

        if not matched:
            tag_lower = tag.lower()
            skill_scores[tag_lower] = max(skill_scores.get(tag_lower, 0.0), score)

    if not skill_scores:
        return {}

    # Step 3: normalise to [0,1] — max score becomes 1.0
    max_score = max(skill_scores.values())
    if max_score == 0:
        return {}

    return {
        skill: round(score / max_score, 4)
        for skill, score in skill_scores.items()
    }


# ─────────────────────────────────────────────────────────────────
#  INSIGHT GENERATION
# ─────────────────────────────────────────────────────────────────

def generate_insights(
    mistake_log:   List[Dict],
    concept_index: Dict,
    now:           Optional[float] = None,
) -> Dict:
    """
    Generate human-readable weakness insights from the mistake data.

    Returns a structured dict with:
      weekly_insights  : list of specific insight strings for the week
      top_weaknesses   : ranked concept weakness list
      strong_areas     : concepts the user is reliably correct on
      improvement_tips : actionable study suggestions per weakness
      summary          : one-line overall status
    """
    if now is None:
        now = time.time()

    # ── Weekly window (last 7 days) ──────────────────────────────
    week_ago      = now - (7 * 86400)
    week_mistakes = [e for e in mistake_log if e["timestamp"] >= week_ago and not e.get("was_correct", True)]
    week_correct  = [e for e in mistake_log if e["timestamp"] >= week_ago and e.get("was_correct", True)]

    # ── Rank weaknesses ──────────────────────────────────────────
    weaknesses = rank_weaknesses(mistake_log, concept_index, now, top_n=5)

    # ── Strong areas ─────────────────────────────────────────────
    strong = []
    for tag, entry in concept_index.items():
        total = entry["correct"] + entry["wrong"]
        if total >= MIN_ATTEMPTS_FOR_INSIGHT and entry["correct"] / total >= 0.80:
            strong.append({
                "concept":      tag,
                "correct_rate": round(entry["correct"] / total, 3),
                "total":        total,
            })
    strong.sort(key=lambda x: -x["correct_rate"])

    # ── Generate insight strings ──────────────────────────────────
    insights = []

    # Weekly volume insight
    if week_mistakes:
        topics = _extract_topics(week_mistakes)
        if topics:
            top_topic = max(topics, key=topics.get)
            insights.append(
                f"This week you made {len(week_mistakes)} mistake(s). "
                f"Most mistakes were in '{top_topic}' ({topics[top_topic]} wrong answers)."
            )
    else:
        insights.append("No mistakes this week. Keep it up!")

    # Concept-level weakness insights
    for w in weaknesses[:3]:
        concept   = w["concept"]
        score     = w["weakness_score"]
        wrong_pct = round(w["wrong_rate"] * 100)
        diff      = _dominant_difficulty(w["difficulty_breakdown"])

        if score >= 3.0:
            severity = "consistently struggling with"
        elif score >= 1.5:
            severity = "finding difficulty with"
        else:
            severity = "occasionally missing"

        insights.append(
            f"You are {severity} '{concept}' — "
            f"{wrong_pct}% wrong rate, mostly on {diff} questions."
        )

    # Difficulty pattern insight
    diff_counts = _aggregate_difficulty(week_mistakes)
    if diff_counts:
        worst_diff = max(diff_counts, key=diff_counts.get)
        insights.append(
            f"You struggle most with {worst_diff} difficulty questions "
            f"({diff_counts[worst_diff]} wrong this week)."
        )

    # Improvement tips per weakness
    tips = _generate_tips(weaknesses[:3])

    # Summary
    total_events = len(mistake_log)
    if total_events == 0:
        summary = "No quiz data yet. Complete some quizzes to see your pattern."
    elif weaknesses:
        summary = (
            f"Your biggest area to improve is '{weaknesses[0]['concept']}' "
            f"with a weakness score of {weaknesses[0]['weakness_score']}."
        )
    else:
        summary = "No significant weakness patterns detected yet. Keep practising."

    return {
        "generated_at":    round(now, 3),
        "weekly_insights": insights,
        "top_weaknesses":  weaknesses,
        "strong_areas":    strong[:3],
        "improvement_tips": tips,
        "summary":         summary,
        "stats": {
            "week_mistakes":  len(week_mistakes),
            "week_correct":   len(week_correct),
            "total_mistakes": sum(1 for e in mistake_log if not e.get("was_correct", True)),
            "total_correct":  sum(1 for e in mistake_log if e.get("was_correct", True)),
            "concepts_tracked": len(concept_index),
        },
    }


# ─────────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────

def _extract_topics(events: List[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for e in events:
        counts[e.get("topic", "unknown")] += 1
    return dict(counts)


def _aggregate_difficulty(events: List[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for e in events:
        counts[e.get("difficulty", "medium")] += 1
    return dict(counts)


def _dominant_difficulty(diff_breakdown: Dict) -> str:
    if not any(diff_breakdown.values()):
        return "medium"
    return max(diff_breakdown, key=diff_breakdown.get)


def _generate_tips(weaknesses: List[Dict]) -> List[Dict]:
    """Generate one actionable improvement tip per weakness concept."""
    tip_templates = {
        # Time complexity concepts
        "complexity":    "Practice deriving time complexity from code by counting loop iterations. Start with single loops → nested loops → recursive calls.",
        "space complexity": "Draw the call stack on paper for recursive functions. Count how many frames exist at peak depth.",
        "call stack":    "Trace through a small recursive example (factorial(4)) manually, drawing each stack frame.",

        # Data structure concepts
        "LIFO":          "Implement a stack from scratch using a Python list. Practice push/pop 10 times without looking at notes.",
        "FIFO":          "Implement a queue using collections.deque. Time the difference between list.pop(0) and deque.popleft().",
        "BST":           "Draw a BST insertion sequence on paper for [5,3,7,1,4,6,8]. Trace inorder traversal to verify sorted output.",
        "cycle":         "Re-read Floyd's algorithm. Trace fast/slow pointers on a list with 6 nodes and a cycle at node 3.",
        "hashing":       "Work through a hash collision example manually using chaining. Draw the linked lists at each bucket.",

        # Algorithm concepts
        "recursion":     "Write factorial and fibonacci without looking at notes. Then trace the call tree for n=4 on paper.",
        "backtracking":  "Solve the N-Queens problem for N=4 manually on paper before coding it. Identify where you backtrack.",
        "memoisation":   "Convert a recursive fibonacci to memoised version. Count how many function calls each makes for n=10.",
        "BFS":           "Trace BFS on a 6-node graph by hand. Write the queue state after each dequeue step.",
        "Dijkstra":      "Run Dijkstra on a 5-node weighted graph manually. Write the distance table after each step.",
        "sorting":       "Write merge sort from memory. If you can't, focus on the merge step — that is where most mistakes are.",

        # Default
        "default":       "Re-read the unit notes. Then close them and try to write a 3-sentence explanation in your own words.",
    }

    tips = []
    for w in weaknesses:
        concept = w["concept"]
        # Find a matching tip — check if any key is in the concept string
        tip_text = tip_templates.get(
            concept,
            next(
                (v for k, v in tip_templates.items() if k in concept.lower()),
                tip_templates["default"]
            )
        )
        tips.append({
            "concept":     concept,
            "tip":         tip_text,
            "wrong_count": w["wrong_count"],
            "priority":    "high" if w["weakness_score"] >= 3.0 else "medium" if w["weakness_score"] >= 1.5 else "low",
        })
    return tips
