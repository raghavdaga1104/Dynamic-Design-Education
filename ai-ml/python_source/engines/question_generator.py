"""
question_generator.py
---------------------
On-demand AI question generation for the DDE quiz system.

HOW IT WORKS
────────────
When a student clicks "Take Quiz", the questions endpoint calls
get_or_generate_questions(user_id, unit_id).

1. CACHE HIT (quiz taken in last 6 hrs):
   - Returns cached questions immediately
   - Returns locked_until so the frontend can show the countdown

2. CACHE MISS (first time or 24 hrs elapsed):
   - Calls Groq to generate a fresh set of questions for this unit
   - Saves them to  data/quiz_cache/{user_id}_{unit_id}.json
   - Sets locked_until = now + 6 hours
   - Registers the questions into quiz_bank's live QUESTIONS list
     so check_answer and submit-irt can look them up

3. GROQ UNAVAILABLE (no key, network error, rate limit):
   - Falls back to handcrafted questions from quiz_bank
   - No lock is set — student can retry immediately

CACHE FILE STRUCTURE (mirrors notes.json style)
───────────────────────────────────────────────
data/quiz_cache/{user_id}_{unit_id}.json
{
  "user_id":      "alice",
  "unit_id":      "UNIT1_PythonBasics",
  "generated_at": 1716200000.0,
  "locked_until": 1716286400.0,   ← generated_at + 86400s
  "questions": [ { question dict }, ... ]
}
"""

import os
import re
import json
import time
import logging
import httpx
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Groq credentials (same as rag_engine.py) ──────────────────────────────────
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL    = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

# ── Cache directory ────────────────────────────────────────────────────────────
_CACHE_DIR = Path(__file__).parent.parent / "data" / "quiz_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Lock duration ──────────────────────────────────────────────────────────────
LOCK_SECONDS = 21600   # 6 hours

# ── Questions per difficulty per on-demand call ────────────────────────────────
# 5 per tier = 15 total — fits comfortably in one Groq response
QUESTIONS_PER_DIFFICULTY = 5

# ── Unit metadata for prompts ─────────────────────────────────────────────────
# Self-contained copy so this module has no dependency on curriculum.py
_UNIT_META: Dict[str, Dict] = {
    "UNIT1_PythonBasics":        {"title": "Python Basics",           "topics": ["variables", "data types", "control flow", "loops", "list comprehensions", "operators", "type conversion"]},
    "UNIT2_PythonFunctions":     {"title": "Functions & Scope",       "topics": ["function definition", "LEGB scope", "closures", "lambda", "map/filter/reduce", "default arguments", "recursion basics"]},
    "UNIT3_OOP":                 {"title": "OOP Concepts",            "topics": ["classes", "objects", "self", "inheritance", "encapsulation", "polymorphism", "MRO", "super()"]},
    "UNIT4_OOPAdvanced":         {"title": "Advanced OOP",            "topics": ["@property", "abc module", "@staticmethod vs @classmethod", "abstract classes", "decorators", "dunder methods"]},
    "UNIT5_Arrays":              {"title": "Arrays & Lists",          "topics": ["indexing", "slicing", "insert/delete complexity", "list methods", "nested lists", "two-pointer technique"]},
    "UNIT6_LinkedLists":         {"title": "Linked Lists",            "topics": ["singly linked list", "doubly linked list", "traversal", "insertion", "deletion", "Floyd's cycle detection"]},
    "UNIT7_StacksQueues":        {"title": "Stacks & Queues",         "topics": ["stack operations", "queue operations", "deque", "monotonic stack", "BFS with queue", "balanced parentheses"]},
    "UNIT8_Trees":               {"title": "Trees & BST",             "topics": ["binary tree", "BST search/insert/delete", "inorder", "preorder", "postorder", "level-order BFS", "tree height"]},
    "UNIT9_HashTables":          {"title": "Hash Tables",             "topics": ["hash function", "collision resolution", "chaining vs open addressing", "load factor", "Python dict", "hashable types"]},
    "UNIT10_Sorting":            {"title": "Sorting Algorithms",      "topics": ["bubble sort", "selection sort", "insertion sort", "merge sort", "quicksort", "Timsort", "stability"]},
    "UNIT11_Searching":          {"title": "Searching Algorithms",    "topics": ["linear search", "binary search", "bisect module", "search on BST", "two-pointer search"]},
    "UNIT12_Recursion":          {"title": "Recursion & Backtracking","topics": ["base case", "recursive case", "call stack depth", "memoisation", "backtracking pattern", "permutations"]},
    "UNIT13_DynamicProgramming": {"title": "Dynamic Programming",     "topics": ["overlapping subproblems", "optimal substructure", "top-down memoisation", "bottom-up tabulation", "coin change", "0/1 knapsack"]},
    "UNIT14_GraphAlgorithms":    {"title": "Graph Algorithms",        "topics": ["adjacency list vs matrix", "BFS", "DFS", "Dijkstra", "topological sort", "cycle detection"]},
}


# ─────────────────────────────────────────────────────────────────────────────
#  CACHE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _cache_path(user_id: str, unit_id: str) -> Path:
    safe_uid  = re.sub(r"[^\w\-]", "_", user_id)
    safe_unit = re.sub(r"[^\w\-]", "_", unit_id)
    return _CACHE_DIR / f"{safe_uid}_{safe_unit}.json"


def _load_cache(user_id: str, unit_id: str) -> Optional[Dict]:
    path = _cache_path(user_id, unit_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_question_cache(user_id: str, unit_id: str, questions: List[Dict]) -> Dict:
    """
    Save generated questions to cache WITHOUT setting a lock.
    The lock is set separately by _save_lock() when the student submits.
    This means fetching questions does not lock the quiz.
    """
    now = time.time()
    cache = {
        "user_id":      user_id,
        "unit_id":      unit_id,
        "generated_at": now,
        "locked_until": None,   # no lock yet — only set on submit
        "questions":    questions,
    }
    path = _cache_path(user_id, unit_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    return cache


def _save_cache(user_id: str, unit_id: str, questions: List[Dict]) -> Dict:
    """
    Alias kept for backward compatibility with the submit-irt endpoint
    which calls _save_cache(user_id, unit_id, []) to set a lock-only entry.
    When questions is empty this sets the lock with no question data.
    When questions is non-empty this is called from submit path.
    """
    now = time.time()
    # Load existing cache to preserve questions if present
    existing = _load_cache(user_id, unit_id) or {}
    cache = {
        "user_id":      user_id,
        "unit_id":      unit_id,
        "generated_at": existing.get("generated_at", now),
        "locked_until": now + LOCK_SECONDS,
        "questions":    questions if questions else existing.get("questions", []),
    }
    path = _cache_path(user_id, unit_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    return cache


def get_lock_status(user_id: str, unit_id: str) -> Dict:
    """
    Returns the current lock status for a user+unit combination.
    Used by the submit-irt endpoint to enforce the 6hr cooldown.
    """
    cache = _load_cache(user_id, unit_id)
    if not cache:
        return {"locked": False, "locked_until": None, "seconds_remaining": 0}
    locked_until = cache.get("locked_until") or 0   # None means not yet locked
    remaining    = max(0, locked_until - time.time())
    return {
        "locked":            remaining > 0,
        "locked_until":      locked_until,
        "seconds_remaining": int(remaining),
    }


def clear_lock(user_id: str, unit_id: str) -> None:
    """
    Clear the lock for a user+unit after a failed attempt, so they can
    retry immediately.  We KEEP the cached questions so the scorer uses
    the same question set that was shown to the student.  Only the
    locked_until timestamp is reset to None.
    """
    path = _cache_path(user_id, unit_id)
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        cache["locked_until"] = None   # unlock without deleting questions
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("clear_lock: could not update cache for %s/%s: %s", user_id, unit_id, e)
        # Last resort: delete so next fetch regenerates cleanly
        path.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
#  PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

_DIFFICULTY_GUIDE = {
    "easy":   "Straightforward recall or single-step code trace. A student who read the notes once should answer correctly.",
    "medium": "Requires understanding, not just recall. May involve a short code snippet, a trade-off, or applying a rule.",
    "hard":   "Requires deep understanding: complexity analysis, edge cases, algorithm decisions, or multi-step reasoning.",
}

_STYLE_EXAMPLES = """\
STYLE EXAMPLES — match this format exactly:

Easy:
{"difficulty":"easy","text":"Which keyword defines a function in Python?","options":["function","define","def","func"],"correct_idx":2,"explanation":"Python uses 'def' to define functions. 'function' and 'func' are not Python keywords.","tags":["syntax"]}

Medium:
{"difficulty":"medium","text":"What prints?\\n\\nx = 10\\nif x > 5:\\n    print('A')\\nelif x > 8:\\n    print('B')\\nelse:\\n    print('C')","options":["A","B","C","AB"],"correct_idx":0,"explanation":"The first condition x>5 is True so 'A' prints immediately. Python stops at the first True branch.","tags":["control flow"]}

Hard:
{"difficulty":"hard","text":"Why can't Dijkstra's algorithm handle negative edge weights?","options":["Its priority queue doesn't support negatives","Its greedy assumption breaks — a negative edge can invalidate an already-settled node","Negative weights cause integer overflow","It only works on trees"],"correct_idx":1,"explanation":"Dijkstra greedily finalises the closest node. A later negative edge could shorten an already-settled path, which Dijkstra never revisits.","tags":["Dijkstra","greedy"]}"""


def _build_prompt(unit_id: str, n: int) -> str:
    meta   = _UNIT_META.get(unit_id, {"title": unit_id, "topics": []})
    topics = ", ".join(meta["topics"])
    total  = n * 3

    return f"""You are writing quiz questions for a university Python and Data Structures course.

Generate exactly {total} multiple-choice questions for:
UNIT: {meta['title']}
TOPICS: {topics}

Generate {n} EASY, {n} MEDIUM, and {n} HARD questions.

DIFFICULTY GUIDE:
- easy   : {_DIFFICULTY_GUIDE['easy']}
- medium : {_DIFFICULTY_GUIDE['medium']}
- hard   : {_DIFFICULTY_GUIDE['hard']}

{_STYLE_EXAMPLES}

RULES:
- Exactly 4 options per question — all plausible, no obviously wrong distractors
- correct_idx must be 0, 1, 2, or 3 — vary across questions
- explanation must say WHY the answer is correct, not just restate it
- Use \\n for line breaks inside code snippets in the "text" field
- Tags must be short lowercase strings (e.g. "complexity", "BST", "lambda")
- Every question must test something DIFFERENT

Respond with ONLY a raw JSON array. No markdown fences, no explanation, no extra text.
Each item: {{"difficulty":"easy|medium|hard","text":"...","options":["A","B","C","D"],"correct_idx":0,"explanation":"...","tags":["tag"]}}"""


# ─────────────────────────────────────────────────────────────────────────────
#  GROQ CALLER
# ─────────────────────────────────────────────────────────────────────────────

def _call_groq(prompt: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    Returns (questions_list, error_string).
    questions_list is None on any failure.
    """
    if not GROQ_API_KEY:
        return None, "GROQ_API_KEY not set"
    try:
        resp = httpx.post(
            GROQ_BASE_URL,
            json={
                "model":       GROQ_MODEL,
                "messages":    [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens":  3000,
            },
            timeout=45,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
        )
        if resp.status_code == 401:
            return None, "Invalid GROQ_API_KEY"
        if resp.status_code == 429:
            return None, "Groq rate limited"
        if resp.status_code != 200:
            return None, f"Groq HTTP {resp.status_code}"

        raw = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if model added them despite instructions
        clean = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        clean = re.sub(r"\s*```\s*$",        "", clean, flags=re.MULTILINE).strip()

        questions = json.loads(clean)
        if not isinstance(questions, list):
            return None, "Response was not a JSON array"
        return questions, None

    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"
    except httpx.TimeoutException:
        return None, "Groq request timed out"
    except Exception as e:
        return None, f"Unexpected error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
#  VALIDATOR + ID ASSIGNER
# ─────────────────────────────────────────────────────────────────────────────

def _validate(q: Dict) -> bool:
    try:
        assert isinstance(q.get("text"), str)       and len(q["text"].strip()) >= 10
        assert isinstance(q.get("options"), list)   and len(q["options"]) == 4
        assert all(isinstance(o, str) and o.strip() for o in q["options"])
        assert q.get("correct_idx") in (0, 1, 2, 3)
        assert isinstance(q.get("explanation"), str) and len(q["explanation"].strip()) >= 10
        assert isinstance(q.get("tags"), list)       and len(q["tags"]) > 0
        assert q.get("difficulty") in ("easy", "medium", "hard")
        return True
    except AssertionError:
        return False


def _assign_ids(questions: List[Dict], unit_id: str, user_id: str) -> List[Dict]:
    """
    Assign question IDs scoped to this user + unit so they never collide
    with handcrafted IDs or other users' generated IDs.
    Format: Q_{unit_code}_U_{user_hash}_{difficulty_prefix}_{idx:03d}
    """
    code      = re.search(r"UNIT(\d+)", unit_id)
    ucode     = code.group(1) if code else "X"
    uhash     = abs(hash(user_id)) % 10000   # 4-digit user hash
    prefix    = {"easy": "E", "medium": "M", "hard": "H"}
    counters  = {"easy": 1, "medium": 1, "hard": 1}
    result    = []
    for q in questions:
        diff = q["difficulty"]
        idx  = counters[diff]
        counters[diff] += 1
        result.append({
            "question_id": f"Q_UNIT{ucode}_GEN_{uhash}_{prefix[diff]}_{idx:03d}",
            "unit_id":     unit_id,
            "source":      "ai_generated",
            **q,
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  QUIZ_BANK REGISTRATION
#  Generated questions are injected into quiz_bank's live QUESTIONS list
#  and _QUESTION_MAP so check_answer and submit-irt can look them up.
# ─────────────────────────────────────────────────────────────────────────────

def _register_in_quiz_bank(questions: List[Dict]) -> None:
    """
    Inject questions into quiz_bank's module-level QUESTIONS and _QUESTION_MAP.
    This is safe — we only add questions that don't already exist (by question_id).
    Called whenever questions are loaded from cache OR freshly generated.
    """
    try:
        import python_source.content.quiz_bank as qb
        for q in questions:
            qid = q["question_id"]
            if qid not in qb._QUESTION_MAP:
                qb.QUESTIONS.append(q)
                qb._QUESTION_MAP[qid] = q
    except Exception as e:
        logger.warning("Could not register questions in quiz_bank: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def get_or_generate_questions(
    user_id: str,
    unit_id: str,
    n_per_difficulty: int = QUESTIONS_PER_DIFFICULTY,
) -> Dict:
    """
    Main entry point called by the /curriculum/{unit_id}/questions endpoint.

    Returns:
    {
      "questions":        [ list of question dicts (correct_idx stripped) ],
      "locked_until":     float unix timestamp or None,
      "seconds_remaining": int,
      "source":           "cache" | "generated" | "fallback",
      "generated_at":     float or None,
    }
    """
    # ── 1. Check cache ─────────────────────────────────────────────────────
    cache = _load_cache(user_id, unit_id)
    if cache:
        locked_until = cache.get("locked_until") or 0
        remaining    = max(0, locked_until - time.time())
        if remaining > 0:
            questions = cache.get("questions", [])
            if questions:
                _register_in_quiz_bank(questions)
            logger.info("Quiz cache hit (locked) for %s / %s — %.0fh remaining",
                        user_id, unit_id, remaining / 3600)
            return {
                "questions":         _strip_answers(questions),
                "locked_until":      locked_until,
                "seconds_remaining": int(remaining),
                "source":            "locked",
                "generated_at":      cache.get("generated_at"),
            }

        # Cache exists but lock has expired or was never set (questions cached,
        # not yet submitted this cycle). Serve the cached questions directly.
        questions = cache.get("questions", [])
        if questions:
            _register_in_quiz_bank(questions)
            logger.info("Serving cached (unlocked) questions for %s / %s",
                        user_id, unit_id)
            return {
                "questions":         _strip_answers(questions),
                "locked_until":      None,
                "seconds_remaining": 0,
                "source":            "cache",
                "generated_at":      cache.get("generated_at"),
            }

    # ── 2. Generate fresh questions via Groq ───────────────────────────────
    prompt    = _build_prompt(unit_id, n_per_difficulty)
    raw_qs, err = _call_groq(prompt)

    if err:
        logger.warning("Groq generation failed for %s / %s: %s — using fallback",
                       user_id, unit_id, err)
        return _fallback(unit_id)

    # Validate and filter
    valid = [q for q in raw_qs if _validate(q)]
    if len(valid) < n_per_difficulty:   # need at least 1 per difficulty tier
        logger.warning("Too few valid questions (%d/%d) for %s — using fallback",
                       len(valid), len(raw_qs), unit_id)
        return _fallback(unit_id)

    # Assign IDs and cap to n_per_difficulty per difficulty
    by_diff: Dict[str, List] = {"easy": [], "medium": [], "hard": []}
    for q in valid:
        diff = q["difficulty"]
        if len(by_diff[diff]) < n_per_difficulty:
            by_diff[diff].append(q)

    final_qs_raw = by_diff["easy"] + by_diff["medium"] + by_diff["hard"]
    if not final_qs_raw:
        return _fallback(unit_id)

    questions = _assign_ids(final_qs_raw, unit_id, user_id)

    # ── 3. Save questions to cache (NO lock yet — lock is set on submit) ─────
    cache = _save_question_cache(user_id, unit_id, questions)
    _register_in_quiz_bank(questions)

    logger.info("Generated %d questions for %s / %s — serving now, lock set on submit",
                len(questions), user_id, unit_id)

    return {
        "questions":         _strip_answers(questions),
        "locked_until":      None,   # no lock until submitted
        "seconds_remaining": 0,
        "source":            "generated",
        "generated_at":      cache["generated_at"],
    }


def _fallback(unit_id: str) -> Dict:
    """Return handcrafted questions with no lock when Groq is unavailable."""
    try:
        import random
        from python_source.content.quiz_bank import get_questions_for_unit
        # FIX: Cap fallback questions to QUESTIONS_PER_DIFFICULTY * 3
        # so the frontend and scorer always agree on the total count.
        cap = QUESTIONS_PER_DIFFICULTY * 3  # e.g. 5*3 = 15
        questions = get_questions_for_unit(unit_id)[:cap]   # already shuffled
        logger.info("Fallback to %d handcrafted questions (capped) for %s", len(questions), unit_id)
    except Exception:
        questions = []
    return {
        "questions":         _strip_answers(questions),
        "locked_until":      None,
        "seconds_remaining": 0,
        "source":            "fallback",
        "generated_at":      None,
    }


def _strip_answers(questions: List[Dict]) -> List[Dict]:
    """Remove correct_idx and explanation before sending to frontend."""
    return [
        {
            "question_id": q["question_id"],
            "text":        q["text"],
            "options":     q["options"],
            "difficulty":  q["difficulty"],
            "tags":        q.get("tags", []),
        }
        for q in questions
    ]