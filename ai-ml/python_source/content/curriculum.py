"""
curriculum.py
-------------
Defines the complete DDE knowledge graph: all learning units, their
prerequisite chains, skills, IRT parameters, and metadata.

HOW TO ADD A NEW UNIT
─────────────────────
1. Add a new entry to CURRICULUM_UNITS below.
2. Add quiz questions for it in quiz_bank.py.
3. Add micro-notes for it in the notes data file.
4. No algorithm code changes are required — the graph loads automatically.

IRT PARAMETER GUIDE
───────────────────
irt_difficulty   (b parameter):
  0.2 – 0.4  : Easy      (foundational, most learners should pass)
  0.5 – 0.7  : Medium    (requires understanding, not just memory)
  0.8 – 1.0  : Hard      (conceptual depth required)
  1.1 – 1.3  : Very Hard (advanced, expects prior experience)

irt_discrimination  (a parameter):
  0.6 – 0.8  : Low discrimination  (complex topic, many learners partially right)
  0.9 – 1.1  : Normal
  1.2 – 1.5  : High discrimination (clear right/wrong, separates well)

PREREQUISITE LOGIC
──────────────────
A unit is unlocked when ALL of its prereq_skills have mastery >= 0.70.
Design prereq chains so the curriculum flows naturally:
  Python Basics → OOP → Data Structures → Algorithms
"""

from python_source.core.knowledge_graph import KnowledgeGraph

# ─────────────────────────────────────────────────────────────────
#  CURRICULUM DEFINITION
#  Each dict defines one learning unit.
# ─────────────────────────────────────────────────────────────────

CURRICULUM_UNITS = [

    # ── DOMAIN: Python Fundamentals ──────────────────────────────────────────
    {
        "unit_id":            "UNIT1_PythonBasics",
        "display_name":       "Python Basics",
        "domain":             "python",
        "skills_taught":      ["python basics"],
        "prereq_skills":      [],               # no prerequisites — entry point
        "irt_difficulty":     0.30,
        "irt_discrimination": 1.20,
        "description":        "Variables, data types, control flow, and functions in Python.",
    },
    {
        "unit_id":            "UNIT2_PythonFunctions",
        "display_name":       "Functions & Scope",
        "domain":             "python",
        "skills_taught":      ["python functions"],
        "prereq_skills":      ["python basics"],
        "irt_difficulty":     0.45,
        "irt_discrimination": 1.10,
        "description":        "Defining functions, scope rules, recursion, and lambda expressions.",
    },

    # ── DOMAIN: Object-Oriented Programming ──────────────────────────────────
    {
        "unit_id":            "UNIT3_OOP",
        "display_name":       "OOP Concepts",
        "domain":             "oop",
        "skills_taught":      ["oop concepts"],
        "prereq_skills":      ["python basics"],
        "irt_difficulty":     0.65,
        "irt_discrimination": 1.00,
        "description":        "Classes, objects, inheritance, encapsulation, and polymorphism.",
    },
    {
        "unit_id":            "UNIT4_OOPAdvanced",
        "display_name":       "Advanced OOP",
        "domain":             "oop",
        "skills_taught":      ["advanced oop"],
        "prereq_skills":      ["oop concepts"],
        "irt_difficulty":     0.80,
        "irt_discrimination": 0.90,
        "description":        "Abstract classes, decorators, dunder methods, and design patterns.",
    },

    # ── DOMAIN: Data Structures ───────────────────────────────────────────────
    {
        "unit_id":            "UNIT5_Arrays",
        "display_name":       "Arrays & Lists",
        "domain":             "data structures",
        "skills_taught":      ["arrays"],
        "prereq_skills":      ["python basics"],
        "irt_difficulty":     0.40,
        "irt_discrimination": 1.15,
        "description":        "Array operations, list comprehensions, slicing, and complexity.",
    },
    {
        "unit_id":            "UNIT6_LinkedLists",
        "display_name":       "Linked Lists",
        "domain":             "data structures",
        "skills_taught":      ["linked lists"],
        "prereq_skills":      ["python basics", "oop concepts"],
        "irt_difficulty":     0.70,
        "irt_discrimination": 1.00,
        "description":        "Singly and doubly linked lists, traversal, insertion, and deletion.",
    },
    {
        "unit_id":            "UNIT7_StacksQueues",
        "display_name":       "Stacks & Queues",
        "domain":             "data structures",
        "skills_taught":      ["stacks and queues"],
        "prereq_skills":      ["arrays"],
        "irt_difficulty":     0.60,
        "irt_discrimination": 1.05,
        "description":        "LIFO/FIFO, push/pop, enqueue/dequeue, and use-cases.",
    },
    {
        "unit_id":            "UNIT8_Trees",
        "display_name":       "Trees & BST",
        "domain":             "data structures",
        "skills_taught":      ["trees"],
        "prereq_skills":      ["linked lists"],
        "irt_difficulty":     0.85,
        "irt_discrimination": 0.95,
        "description":        "Binary trees, BST operations, tree traversals (inorder, preorder, postorder).",
    },
    {
        "unit_id":            "UNIT9_HashTables",
        "display_name":       "Hash Tables",
        "domain":             "data structures",
        "skills_taught":      ["hash tables"],
        "prereq_skills":      ["arrays"],
        "irt_difficulty":     0.75,
        "irt_discrimination": 1.00,
        "description":        "Hashing, collision resolution, dictionaries, and time complexity.",
    },

    # ── DOMAIN: Algorithms ───────────────────────────────────────────────────
    {
        "unit_id":            "UNIT10_Sorting",
        "display_name":       "Sorting Algorithms",
        "domain":             "algorithms",
        "skills_taught":      ["sorting"],
        "prereq_skills":      ["arrays"],
        "irt_difficulty":     0.70,
        "irt_discrimination": 1.00,
        "description":        "Bubble, selection, insertion, merge, and quicksort with complexity analysis.",
    },
    {
        "unit_id":            "UNIT11_Searching",
        "display_name":       "Searching Algorithms",
        "domain":             "algorithms",
        "skills_taught":      ["searching"],
        "prereq_skills":      ["arrays", "sorting"],
        "irt_difficulty":     0.65,
        "irt_discrimination": 1.05,
        "description":        "Linear search, binary search, and search on data structures.",
    },
    {
        "unit_id":            "UNIT12_Recursion",
        "display_name":       "Recursion & Backtracking",
        "domain":             "algorithms",
        "skills_taught":      ["recursion"],
        "prereq_skills":      ["python functions"],
        "irt_difficulty":     0.80,
        "irt_discrimination": 0.90,
        "description":        "Recursive thinking, base cases, call stack, and backtracking problems.",
    },
    {
        "unit_id":            "UNIT13_DynamicProgramming",
        "display_name":       "Dynamic Programming",
        "domain":             "algorithms",
        "skills_taught":      ["dynamic programming"],
        "prereq_skills":      ["recursion", "arrays"],
        "irt_difficulty":     1.10,
        "irt_discrimination": 0.80,
        "description":        "Memoisation, tabulation, overlapping subproblems, and optimal substructure.",
    },
    {
        "unit_id":            "UNIT14_GraphAlgorithms",
        "display_name":       "Graph Algorithms",
        "domain":             "algorithms",
        "skills_taught":      ["graph algorithms"],
        "prereq_skills":      ["trees", "recursion"],
        "irt_difficulty":     1.15,
        "irt_discrimination": 0.75,
        "description":        "BFS, DFS, shortest paths, and graph representations.",
    },
]


# ─────────────────────────────────────────────────────────────────
#  FACTORY: build and return a populated KnowledgeGraph
# ─────────────────────────────────────────────────────────────────

def build_knowledge_graph() -> KnowledgeGraph:
    """
    Instantiate a KnowledgeGraph and populate it from CURRICULUM_UNITS.
    Call this once at application startup.
    """
    kg = KnowledgeGraph()
    for unit in CURRICULUM_UNITS:
        kg.add_unit(
            unit_id=            unit["unit_id"],
            skills_taught=      unit["skills_taught"],
            prereq_skills=      set(unit.get("prereq_skills", [])),
            display_name=       unit["display_name"],
            domain=             unit["domain"],
            irt_difficulty=     unit["irt_difficulty"],
            irt_discrimination= unit["irt_discrimination"],
            description=        unit["description"],
        )
    return kg
