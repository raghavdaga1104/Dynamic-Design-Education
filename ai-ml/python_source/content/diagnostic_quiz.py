"""
diagnostic_quiz.py
------------------
NEW FILE — Onboarding diagnostic quiz.

Purpose
-------
When a new user joins, show them a 10-question diagnostic quiz across
their chosen topic. Based on their score, assign a starting unit so
intermediate/advanced learners skip content they already know.

Design decisions
----------------
- Questions are SEPARATE from the main quiz bank (quiz_bank.py).
  Diagnostic questions test prerequisite breadth, not unit depth.
- Each topic has its own 10-question set: 3 easy, 4 medium, 3 hard.
- Score → placement mapping is defined per topic so different topics
  can have different entry points.
- The user can always skip the diagnostic and start from Unit 1.

How it integrates
-----------------
- POST /diagnostic/start  → returns 10 questions for the chosen topic
- POST /diagnostic/submit → accepts answers, calculates score,
                            returns assigned starting unit,
                            saves result into existing LearnerSession
- The starting_unit is then passed to the first /recommend call
  which respects it via the existing prerequisite system.

To add a new topic
------------------
1. Add a DIAGNOSTIC_QUESTIONS entry with key = topic name
2. Add a PLACEMENT_MAP entry mapping score ranges to unit_ids
3. That's it — no algorithm changes needed
"""

from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────
#  DIAGNOSTIC QUESTIONS
#  10 questions per topic: 3 easy, 4 medium, 3 hard
#  These test BREADTH across the topic, not depth of one unit
# ─────────────────────────────────────────────────────────────────

DIAGNOSTIC_QUESTIONS: Dict[str, List[Dict]] = {

    "python": [
        # ── Easy (3) ──────────────────────────────────────────────
        {
            "question_id": "DQ_PY_001",
            "text": "What symbol is used to add a comment in Python?",
            "options": ["//", "#", "/*", "--"],
            "correct_idx": 1,
            "difficulty": "easy",
            "points": 1,
        },
        {
            "question_id": "DQ_PY_002",
            "text": "Which of these is a valid Python variable name?",
            "options": ["2name", "my-name", "my_name", "my name"],
            "correct_idx": 2,
            "difficulty": "easy",
            "points": 1,
        },
        {
            "question_id": "DQ_PY_003",
            "text": "What does len([1, 2, 3]) return?",
            "options": ["2", "3", "4", "Error"],
            "correct_idx": 1,
            "difficulty": "easy",
            "points": 1,
        },
        # ── Medium (4) ────────────────────────────────────────────
        {
            "question_id": "DQ_PY_004",
            "text": "What is the output of: [x**2 for x in range(4)]?",
            "options": [
                "[1, 4, 9, 16]",
                "[0, 1, 4, 9]",
                "[0, 1, 2, 3]",
                "[1, 2, 3, 4]",
            ],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_PY_005",
            "text": "What does *args allow in a function definition?",
            "options": [
                "Keyword arguments only",
                "Variable number of positional arguments",
                "A single required argument",
                "Default parameter values",
            ],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_PY_006",
            "text": "Which method removes and returns the last item from a list?",
            "options": ["remove()", "delete()", "pop()", "discard()"],
            "correct_idx": 2,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_PY_007",
            "text": "What is the difference between a list and a tuple in Python?",
            "options": [
                "Lists are faster; tuples are slower",
                "Lists are mutable; tuples are immutable",
                "Tuples can hold more items",
                "There is no difference",
            ],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        # ── Hard (3) ──────────────────────────────────────────────
        {
            "question_id": "DQ_PY_008",
            "text": "What is the time complexity of searching for an element in a Python dict?",
            "options": ["O(n)", "O(log n)", "O(1) average", "O(n²)"],
            "correct_idx": 2,
            "difficulty": "hard",
            "points": 3,
        },
        {
            "question_id": "DQ_PY_009",
            "text": "What does the @property decorator do?",
            "options": [
                "Makes a method static",
                "Turns a method into a read-only attribute",
                "Makes a class abstract",
                "Registers a class method",
            ],
            "correct_idx": 1,
            "difficulty": "hard",
            "points": 3,
        },
        {
            "question_id": "DQ_PY_010",
            "text": "What is the space complexity of a recursive factorial(n) function?",
            "options": ["O(1)", "O(log n)", "O(n)", "O(n²)"],
            "correct_idx": 2,
            "difficulty": "hard",
            "points": 3,
        },
    ],

    "data structures": [
        # ── Easy (3) ──────────────────────────────────────────────
        {
            "question_id": "DQ_DS_001",
            "text": "Which data structure follows LIFO order?",
            "options": ["Queue", "Stack", "Array", "Linked List"],
            "correct_idx": 1,
            "difficulty": "easy",
            "points": 1,
        },
        {
            "question_id": "DQ_DS_002",
            "text": "What is the time complexity of accessing an element by index in an array?",
            "options": ["O(n)", "O(log n)", "O(1)", "O(n²)"],
            "correct_idx": 2,
            "difficulty": "easy",
            "points": 1,
        },
        {
            "question_id": "DQ_DS_003",
            "text": "Which data structure uses FIFO ordering?",
            "options": ["Stack", "Tree", "Queue", "Graph"],
            "correct_idx": 2,
            "difficulty": "easy",
            "points": 1,
        },
        # ── Medium (4) ────────────────────────────────────────────
        {
            "question_id": "DQ_DS_004",
            "text": "What is the time complexity of inserting at the beginning of a linked list?",
            "options": ["O(n)", "O(log n)", "O(1)", "O(n²)"],
            "correct_idx": 2,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_DS_005",
            "text": "In a BST, where is the smallest element located?",
            "options": ["Root", "Rightmost node", "Leftmost node", "Last level"],
            "correct_idx": 2,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_DS_006",
            "text": "What traversal visits nodes level by level?",
            "options": ["Inorder", "Preorder", "Postorder", "BFS / Level-order"],
            "correct_idx": 3,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_DS_007",
            "text": "What is the average time complexity of search in a hash table?",
            "options": ["O(n)", "O(log n)", "O(1)", "O(n log n)"],
            "correct_idx": 2,
            "difficulty": "medium",
            "points": 2,
        },
        # ── Hard (3) ──────────────────────────────────────────────
        {
            "question_id": "DQ_DS_008",
            "text": "How do you detect a cycle in a linked list efficiently?",
            "options": [
                "Count the nodes and check for repetition",
                "Use Floyd's two-pointer algorithm",
                "Sort the list and check adjacent nodes",
                "Use a recursive approach",
            ],
            "correct_idx": 1,
            "difficulty": "hard",
            "points": 3,
        },
        {
            "question_id": "DQ_DS_009",
            "text": "What is the worst-case height of an unbalanced BST with n nodes?",
            "options": ["O(log n)", "O(√n)", "O(n)", "O(n log n)"],
            "correct_idx": 2,
            "difficulty": "hard",
            "points": 3,
        },
        {
            "question_id": "DQ_DS_010",
            "text": "Which of these problems is best solved using a monotonic stack?",
            "options": [
                "Finding the maximum element in an array",
                "Finding the Next Greater Element for each element",
                "Reversing a string",
                "Checking if a number is prime",
            ],
            "correct_idx": 1,
            "difficulty": "hard",
            "points": 3,
        },
    ],

    # ── FIX: added OOP topic — was missing, caused OOP-interested learners
    #    to get routed to UNIT1_PythonBasics (python fallback) regardless.
    "oop": [
        # ── Easy (3) ──────────────────────────────────────────────
        {
            "question_id": "DQ_OOP_001",
            "text": "What is a class in Python?",
            "options": [
                "A built-in function",
                "A blueprint for creating objects with shared attributes and methods",
                "A module to import",
                "A loop structure",
            ],
            "correct_idx": 1,
            "difficulty": "easy",
            "points": 1,
        },
        {
            "question_id": "DQ_OOP_002",
            "text": "What does 'self' refer to inside a class method?",
            "options": [
                "The class itself",
                "The parent class",
                "The specific instance calling the method",
                "A global variable",
            ],
            "correct_idx": 2,
            "difficulty": "easy",
            "points": 1,
        },
        {
            "question_id": "DQ_OOP_003",
            "text": "How do you create an object from a class called Car?",
            "options": [
                "car = new Car()",
                "car = create Car()",
                "car = Car()",
                "car = object(Car)",
            ],
            "correct_idx": 2,
            "difficulty": "easy",
            "points": 1,
        },
        # ── Medium (4) ────────────────────────────────────────────
        {
            "question_id": "DQ_OOP_004",
            "text": "What is method overriding?",
            "options": [
                "Two methods with the same name but different parameters",
                "A child class providing its own implementation of an inherited method",
                "Importing a method from another module",
                "Calling super() inside a method",
            ],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_OOP_005",
            "text": "What does encapsulation mean in OOP?",
            "options": [
                "Inheriting all parent methods",
                "Hiding internal state and exposing only what is needed",
                "Making all methods static",
                "Overriding parent methods",
            ],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_OOP_006",
            "text": "What does super().__init__() do inside a child class?",
            "options": [
                "Creates a new parent object",
                "Calls the parent constructor to set up inherited attributes",
                "Deletes the parent class",
                "Overrides all parent methods",
            ],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_OOP_007",
            "text": "What is polymorphism?",
            "options": [
                "One class, one method, one behaviour",
                "Different classes responding differently to the same method call",
                "Making all attributes private",
                "Inheriting from multiple classes",
            ],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        # ── Hard (3) ──────────────────────────────────────────────
        {
            "question_id": "DQ_OOP_008",
            "text": "Can you instantiate an abstract class directly in Python?",
            "options": [
                "Yes, always",
                "Yes, if it has at least one concrete method",
                "No — Python raises TypeError",
                "No — Python raises SyntaxError",
            ],
            "correct_idx": 2,
            "difficulty": "hard",
            "points": 3,
        },
        {
            "question_id": "DQ_OOP_009",
            "text": "What does MRO (Method Resolution Order) control?",
            "options": [
                "The order methods are defined inside a class",
                "The sequence in which Python searches classes for a method in multiple inheritance",
                "The order of function return values",
                "The priority of built-ins over user methods",
            ],
            "correct_idx": 1,
            "difficulty": "hard",
            "points": 3,
        },
        {
            "question_id": "DQ_OOP_010",
            "text": "What does a decorator fundamentally do in Python?",
            "options": [
                "Renames a function permanently",
                "Wraps a function to add behaviour without modifying the original source",
                "Deletes a function after one execution",
                "Compiles the function to machine code",
            ],
            "correct_idx": 1,
            "difficulty": "hard",
            "points": 3,
        },
    ],

    "algorithms": [
        # ── Easy (3) ──────────────────────────────────────────────
        {
            "question_id": "DQ_AL_001",
            "text": "What is the time complexity of linear search on an array of n elements?",
            "options": ["O(1)", "O(log n)", "O(n)", "O(n²)"],
            "correct_idx": 2,
            "difficulty": "easy",
            "points": 1,
        },
        {
            "question_id": "DQ_AL_002",
            "text": "Which sorting algorithm has O(n²) worst case AND O(n) best case?",
            "options": ["Merge Sort", "Quick Sort", "Insertion Sort", "Heap Sort"],
            "correct_idx": 2,
            "difficulty": "easy",
            "points": 1,
        },
        {
            "question_id": "DQ_AL_003",
            "text": "What must a recursive function always have?",
            "options": [
                "A loop",
                "A base case",
                "A return type",
                "A global variable",
            ],
            "correct_idx": 1,
            "difficulty": "easy",
            "points": 1,
        },
        # ── Medium (4) ────────────────────────────────────────────
        {
            "question_id": "DQ_AL_004",
            "text": "What is the average time complexity of QuickSort?",
            "options": ["O(n)", "O(n log n)", "O(n²)", "O(log n)"],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_AL_005",
            "text": "Binary search requires the input array to be:",
            "options": [
                "Unsorted",
                "Sorted",
                "Containing only integers",
                "Having even number of elements",
            ],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_AL_006",
            "text": "What are the two required properties for Dynamic Programming to apply?",
            "options": [
                "Sorted input and unique elements",
                "Overlapping subproblems and optimal substructure",
                "Greedy choice and monotonicity",
                "Recursion and memoisation",
            ],
            "correct_idx": 1,
            "difficulty": "medium",
            "points": 2,
        },
        {
            "question_id": "DQ_AL_007",
            "text": "Which graph traversal algorithm finds the shortest path in an unweighted graph?",
            "options": ["DFS", "Dijkstra", "BFS", "Bellman-Ford"],
            "correct_idx": 2,
            "difficulty": "medium",
            "points": 2,
        },
        # ── Hard (3) ──────────────────────────────────────────────
        {
            "question_id": "DQ_AL_008",
            "text": "What is the time complexity of the DP solution to 0/1 Knapsack (n items, capacity W)?",
            "options": ["O(n)", "O(nW)", "O(2^n)", "O(n log n)"],
            "correct_idx": 1,
            "difficulty": "hard",
            "points": 3,
        },
        {
            "question_id": "DQ_AL_009",
            "text": "Why can't Dijkstra's algorithm handle negative edge weights?",
            "options": [
                "It uses a priority queue which doesn't support negatives",
                "Its greedy assumption breaks — a negative edge can invalidate a settled node",
                "Negative weights cause integer overflow",
                "It only works on trees, not graphs",
            ],
            "correct_idx": 1,
            "difficulty": "hard",
            "points": 3,
        },
        {
            "question_id": "DQ_AL_010",
            "text": "What technique reduces the naive O(2^n) recursive Fibonacci to O(n)?",
            "options": [
                "Sorting the inputs first",
                "Using iteration instead of recursion",
                "Memoisation — caching already computed results",
                "Using a stack instead of recursion",
            ],
            "correct_idx": 2,
            "difficulty": "hard",
            "points": 3,
        },
    ],
}

# ─────────────────────────────────────────────────────────────────
#  PLACEMENT MAP
#  Maps (topic, score_percent) → unit_id to start from
#
#  Score is WEIGHTED: easy=1pt, medium=2pts, hard=3pts
#  Max score = 3*1 + 4*2 + 3*3 = 3+8+9 = 20 points
#
#  Placement tiers (same for all topics, adjust unit_ids per topic):
#    0–39%  → Beginner   → first unit of topic
#    40–69% → Developing → first intermediate unit
#    70–89% → Proficient → first advanced unit
#    90+%   → Expert     → last unit (or near-last)
# ─────────────────────────────────────────────────────────────────

PLACEMENT_MAP: Dict[str, Dict[str, str]] = {
    "python": {
        "beginner":   "UNIT1_PythonBasics",
        "developing": "UNIT2_PythonFunctions",
        "proficient": "UNIT3_OOP",
        "expert":     "UNIT4_OOPAdvanced",
    },
    # FIX: added oop topic — was missing from PLACEMENT_MAP causing
    # OOP-interested learners to fall back to python placement silently.
    "oop": {
        "beginner":   "UNIT3_OOP",
        "developing": "UNIT3_OOP",
        "proficient": "UNIT4_OOPAdvanced",
        "expert":     "UNIT4_OOPAdvanced",
    },
    "data structures": {
        "beginner":   "UNIT5_Arrays",
        "developing": "UNIT6_LinkedLists",
        "proficient": "UNIT8_Trees",
        "expert":     "UNIT9_HashTables",
    },
    "algorithms": {
        "beginner":   "UNIT10_Sorting",
        "developing": "UNIT11_Searching",
        "proficient": "UNIT12_Recursion",
        "expert":     "UNIT13_DynamicProgramming",
    },
}

# Maximum weighted score for a 10-question diagnostic
MAX_DIAGNOSTIC_SCORE = 20   # 3×1 + 4×2 + 3×3


# ─────────────────────────────────────────────────────────────────
#  DIAGNOSTIC ENGINE
# ─────────────────────────────────────────────────────────────────

class DiagnosticEngine:
    """
    Handles the onboarding diagnostic quiz flow.

    Usage
    -----
    engine = DiagnosticEngine()

    # Get questions for a topic
    questions = engine.get_questions("python")

    # After user answers, evaluate and get starting unit
    result = engine.evaluate(
        topic="python",
        answers={"DQ_PY_001": 1, "DQ_PY_002": 2, ...}
    )
    # result.starting_unit → the unit_id to begin from
    """

    def get_questions(self, topic: str) -> List[Dict]:
        """
        Return the 10 diagnostic questions for a topic.
        Strips correct_idx and points so the frontend cannot see answers.
        """
        topic_key = topic.lower().strip()
        questions  = DIAGNOSTIC_QUESTIONS.get(topic_key)

        if not questions:
            # Fallback: return python questions for unknown topics
            questions = DIAGNOSTIC_QUESTIONS["python"]

        # Return safe version — no correct answers exposed
        return [
            {
                "question_id": q["question_id"],
                "text":        q["text"],
                "options":     q["options"],
                "difficulty":  q["difficulty"],
            }
            for q in questions
        ]

    def evaluate(
        self,
        topic:   str,
        answers: Dict[str, int],   # {question_id: chosen_index}
    ) -> Dict:
        """
        Score the diagnostic answers and return placement result.

        Parameters
        ----------
        topic   : the topic the user selected (e.g. "python")
        answers : dict mapping question_id → chosen answer index (0-3)

        Returns
        -------
        dict with:
          score_raw      : weighted points earned
          score_max      : maximum possible points (20)
          score_percent  : percentage (0-100)
          tier           : "beginner" | "developing" | "proficient" | "expert"
          starting_unit  : unit_id to start from
          breakdown      : per-question correct/incorrect detail
          message        : friendly explanation for the user
        """
        topic_key  = topic.lower().strip()
        questions  = DIAGNOSTIC_QUESTIONS.get(topic_key, DIAGNOSTIC_QUESTIONS["python"])
        q_map      = {q["question_id"]: q for q in questions}

        score_raw = 0
        breakdown = []

        for q in questions:
            qid      = q["question_id"]
            chosen   = answers.get(qid)
            correct  = q["correct_idx"]
            is_right = (chosen == correct)

            if is_right:
                score_raw += q["points"]

            breakdown.append({
                "question_id":  qid,
                "difficulty":   q["difficulty"],
                "points":       q["points"],
                "chosen_idx":   chosen,
                "correct_idx":  correct,
                "is_correct":   is_right,
                "earned":       q["points"] if is_right else 0,
            })

        score_percent = round((score_raw / MAX_DIAGNOSTIC_SCORE) * 100, 1)

        # Determine placement tier
        tier = self._get_tier(score_percent)

        # Look up starting unit
        placement    = PLACEMENT_MAP.get(topic_key, PLACEMENT_MAP["python"])
        starting_unit = placement.get(tier, placement["beginner"])

        message = self._get_message(tier, score_percent, starting_unit)

        return {
            "topic":          topic,
            "score_raw":      score_raw,
            "score_max":      MAX_DIAGNOSTIC_SCORE,
            "score_percent":  score_percent,
            "tier":           tier,
            "starting_unit":  starting_unit,
            "breakdown":      breakdown,
            "message":        message,
        }

    def get_skip_result(self, topic: str) -> Dict:
        """
        Return beginner placement for users who chose to skip the diagnostic.
        Stored identically to a real result so the system treats it the same way.
        """
        topic_key    = topic.lower().strip()
        placement    = PLACEMENT_MAP.get(topic_key, PLACEMENT_MAP["python"])
        starting_unit = placement["beginner"]

        return {
            "topic":          topic,
            "score_raw":      0,
            "score_max":      MAX_DIAGNOSTIC_SCORE,
            "score_percent":  0.0,
            "tier":           "beginner",
            "starting_unit":  starting_unit,
            "skipped":        True,
            "message":        (
                f"You chose to start from the beginning. "
                f"Your first unit is ready."
            ),
        }

    def get_available_topics(self) -> List[str]:
        """Return all topics that have diagnostic questions."""
        return list(DIAGNOSTIC_QUESTIONS.keys())

    # ──────────────────────────────────────────
    #  Private helpers
    # ──────────────────────────────────────────

    def _get_tier(self, score_percent: float) -> str:
        if score_percent >= 90:
            return "expert"
        elif score_percent >= 70:
            return "proficient"
        elif score_percent >= 40:
            return "developing"
        else:
            return "beginner"

    def _get_message(self, tier: str, score: float, unit: str) -> str:
        messages = {
            "beginner": (
                f"Great start! You scored {score}%. "
                f"We'll begin from the fundamentals to build a solid foundation."
            ),
            "developing": (
                f"Good knowledge! You scored {score}%. "
                f"You already know the basics, so we're skipping ahead "
                f"to save your time."
            ),
            "proficient": (
                f"Strong performance! You scored {score}%. "
                f"You have solid fundamentals. We're placing you at an "
                f"advanced starting point."
            ),
            "expert": (
                f"Excellent! You scored {score}%. "
                f"You already know most of this topic. "
                f"We're starting you at the most advanced level."
            ),
        }
        return messages.get(tier, messages["beginner"])
