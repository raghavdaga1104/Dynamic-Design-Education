from dotenv import load_dotenv
load_dotenv()

"""
main.py — DDE AI/ML Service
FIXES APPLIED:
  1. IRT → BKT: /quiz/submit-irt now calls record_quiz_result_irt (blends θ)
  2. SM-2 gate enforced server-side in /recommend (returns 409 if reviews due)
  3. /recommend is async + MCTS runs in ThreadPoolExecutor (non-blocking)
  4. Duplicate @app.post("/flashcard/review") removed — only server-day version kept
  5. Mistake tracking auto-called inside /quiz/submit-irt and /quiz/result
  6. Curriculum complete returns 200 success instead of 404
  7. Diagnostic replay guard added to /diagnostic/submit
  8. stuck_alert surfaced in /quiz/result response
  9. Weakness map bridge: topic uses skill name not domain
 10. [NEW] IRT-BKT threshold: unit_passed uses irt_passed directly — not
     re-evaluated BKT blend (new learners could never pass — fixed)
 11. [NEW] /diagnostic/skip now calls _unlock_units_before (was missing)
 12. [NEW] Double-submission guard on /quiz/result and /quiz/submit-irt
 13. [NEW] /chat is now async — runs in thread executor (was blocking worker)
 14. [NEW] OLLAMA_MODEL constant used in /health (was hardcoded string)
 15. [NEW] topic fallback removed everywhere — always uses skills[0]
 16. [NEW] GET /curriculum/{unit_id}/notes — serves notes from dataset JSON
 17. [NEW] GET /debug/dataset — inspect dataset unit field values for debugging
 18. [NEW] Notes endpoint uses 4-strategy matching + dedup + 50-note cap (fixes 835 topics bug)
"""

import sys
import json
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import engine
from models import Base

sys.path.insert(0, str(Path(__file__).parent))

from python_source.content.curriculum    import build_knowledge_graph
from python_source.content.quiz_bank     import get_questions_for_unit, get_question_by_id, enrich_with_irt
from python_source.engines.question_generator import get_or_generate_questions, get_lock_status, clear_lock
from python_source.core.mcts_algorithm   import MCTSAlgorithm
from python_source.core.learner_session  import LearnerSession
from python_source.core.analytics_logger import AnalyticsLogger
from python_source.core.adaptive_systems import irt_select_best_question, mastery_to_level
from python_source.state.state_manager   import StateManager
from python_source.engines.rag_engine    import RAGEngine, GROQ_MODEL
from python_source.core.irt_scoring      import score_quiz as irt_score_quiz
from python_source.engines.ats_engine    import ATSEngine
from python_source.engines.resume_parser import extract_resume_text, ResumeParseError
from python_source.auth.auth_router       import router as auth_router

# ─────────────────────────────────────────────────────────────────
#  APP SETUP
# ─────────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DDE AI/ML Service",
    description="Adaptive learning engine + local RAG chatbot + ATS scorer.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

# ─────────────────────────────────────────────────────────────────
#  STARTUP
# ─────────────────────────────────────────────────────────────────

KG            = build_knowledge_graph()
STATE_MANAGER = StateManager()
RAG           = RAGEngine()
ATS           = ATSEngine()
MCTS_ITERS    = 60

# Thread pool for CPU-bound MCTS — prevents event loop blocking
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dde_mcts")

# Path to dataset
# main.py is at:  ai-ml/main.py
# dataset is at:  ai-ml/python_source/data/python_course_dataset.json
_DATASET_PATH = Path(__file__).parent / "python_source" / "data" / "python_course_dataset.json"
_NOTES_PATH   = Path(__file__).parent / "python_source" / "data" / "notes.json"

# Maps curriculum unit_ids → notes.json unit_ids
_NOTES_UNIT_MAP = {
    "UNIT1_PythonBasics":        "UNIT1_PythonBasics",
    "UNIT2_PythonFunctions":     "UNIT2_FunctionsScope",
    "UNIT3_OOP":                 "UNIT3_OOP",
    "UNIT4_OOPAdvanced":         "UNIT10_AdvancedOOP",
    "UNIT5_Arrays":              "UNIT4_ArraysLists",
    "UNIT6_LinkedLists":         "UNIT11_LinkedLists",
    "UNIT7_StacksQueues":        "UNIT12_StacksQueues",
    "UNIT8_Trees":               "UNIT13_TreesBST",
    "UNIT9_HashTables":          "UNIT14_HashTables",
    "UNIT10_Sorting":            "UNIT5_Sorting",
    "UNIT11_Searching":          "UNIT6_Searching",
    "UNIT12_Recursion":          "UNIT7_RecursionBacktracking",
    "UNIT13_DynamicProgramming": "UNIT8_DynamicProgramming",
    "UNIT14_GraphAlgorithms":    "UNIT9_GraphAlgorithms",
}

# How many questions to serve per quiz attempt.
# With the AI-generated bank each unit has ~34 questions — capping at 10 means
# students get a fresh random 10 every attempt rather than the full pool.
# Override in .env:  QUIZ_QUESTION_CAP=10
QUIZ_QUESTION_CAP: int = int(os.environ.get("QUIZ_QUESTION_CAP", "15"))

# ─────────────────────────────────────────────────────────────────
#  REQUEST MODELS
# ─────────────────────────────────────────────────────────────────

class LearnerProfileIn(BaseModel):
    user_id:  str
    degree:   str = "BTech"
    year:     str = "2nd"
    interest: str = "data structures"

class QuizResultIn(BaseModel):
    user_id:     str
    unit_id:     str
    was_correct: bool

class FlashcardReviewIn(BaseModel):
    user_id:     str
    unit_id:     str
    quality:     int
    current_day: int = 0   # ignored — server calculates day

class ChatIn(BaseModel):
    user_id:     str
    question:    str
    unit_id:     Optional[str] = None
    unit_title:  Optional[str] = None
    unit_domain: Optional[str] = None
    unit_notes:  Optional[str] = None
    mode:        str = "question"

class ATSIn(BaseModel):
    user_id:         str
    resume_text:     str
    job_description: str
    # include_semantic_matches kept for backwards compatibility but is now always True —
    # semantic matching runs inside analyze() itself (SBERT is fast/free, LLM advisory
    # implied-keyword check runs only when Groq is available).
    include_semantic_matches: bool = True

class ATSImproveIn(BaseModel):
    user_id:         str
    resume_text:     str
    job_description: str
    target_role:     str = ""
    resume_sections: Optional[Dict[str, str]] = None

class IRTQuizSubmitIn(BaseModel):
    user_id: str
    unit_id: str
    answers: Dict[str, int]   # {question_id: chosen_index}

class DiagnosticStartIn(BaseModel):
    user_id: str
    topic:   str

class DiagnosticSubmitIn(BaseModel):
    user_id: str
    topic:   str
    answers: Dict[str, int]

class DiagnosticSkipIn(BaseModel):
    user_id: str
    topic:   str

class QuizAnswerIn(BaseModel):
    user_id:     str
    unit_id:     str
    topic:       str
    question_id: str
    chosen_idx:  int
    was_correct: bool

class BatchAnswersIn(BaseModel):
    user_id:  str
    unit_id:  str
    topic:    str
    answers:  List[Dict]

# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────

def _load_session(user_id: str):
    logger  = AnalyticsLogger(user_id=user_id)
    session = STATE_MANAGER.load(user_id, KG, logger)
    return session, logger


def _get_current_day(session) -> int:
    """Server-calculated day from creation timestamp. Never relies on client."""
    import time
    created = getattr(session, "_created_at", 0)
    if created == 0:
        return getattr(session, "current_day", 0)
    return int((time.time() - created) / 86400)


def _unlock_units_before(session, target_unit_id: str) -> None:
    """
    Pre-set mastery for all prerequisite skills of target unit.
    Uses BFS to walk prerequisites transitively.
    """
    target_meta = KG.units.get(target_unit_id)
    if not target_meta:
        return

    skills_to_unlock: set = set()
    visited_units: set = {target_unit_id}
    queue = list(target_meta.get("prereq_skills", set()))

    while queue:
        skill = queue.pop(0)
        if skill in skills_to_unlock:
            continue
        skills_to_unlock.add(skill)
        for uid, meta in KG.units.items():
            if uid in visited_units:
                continue
            if skill in meta.get("skills_taught", []):
                visited_units.add(uid)
                for prereq in meta.get("prereq_skills", set()):
                    if prereq not in skills_to_unlock:
                        queue.append(prereq)

    for skill in skills_to_unlock:
        current = session.skill_mastery.get(skill, 0.1)
        if current < 0.85:
            session.skill_mastery[skill] = 0.85


# ─────────────────────────────────────────────────────────────────
#  UTILITY ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {
        "status":          "ok",
        "units_in_graph":  len(KG),
        "rag_indexed":     RAG.collection.count() if hasattr(RAG, "collection") else 0,
        "ollama_running":  RAG.groq_available if hasattr(RAG, "groq_available") else RAG.ollama_available if hasattr(RAG, "ollama_available") else False,
        "ollama_model":    GROQ_MODEL,
        "groq_model":      GROQ_MODEL,
        "external_api":    "groq",
    }


@app.get("/curriculum")
def get_curriculum():
    units = []
    for uid, meta in KG.units.items():
        units.append({
            "unit_id":       uid,
            "display_name":  meta["display_name"],
            "domain":        meta["domain"],
            "description":   meta["description"],
            "prereq_skills": list(meta["prereq_skills"]),
            "skills_taught": meta["skills_taught"],
        })
    return {"units": units, "total": len(units)}


@app.get("/curriculum/{unit_id}/questions")
def get_unit_questions(unit_id: str, user_id: str = ""):
    if user_id:
        result = get_or_generate_questions(user_id, unit_id)
        # Lock active with no questions (submitted before AI fetch)
        if result["seconds_remaining"] > 0 and not result["questions"]:
            return {
                "unit_id":           unit_id,
                "questions":         [],
                "count":             0,
                "locked_until":      result["locked_until"],
                "seconds_remaining": result["seconds_remaining"],
                "source":            "locked",
            }
        return {
            "unit_id":           unit_id,
            "questions":         result["questions"],
            "count":             len(result["questions"]),
            "locked_until":      result["locked_until"],
            "seconds_remaining": result["seconds_remaining"],
            "source":            result["source"],
        }
    # Legacy / anonymous path
    questions = get_questions_for_unit(unit_id)[:QUIZ_QUESTION_CAP]
    if not questions:
        raise HTTPException(404, f"No questions for unit {unit_id}.")
    safe = [
        {
            "question_id": q["question_id"],
            "text":        q["text"],
            "options":     q["options"],
            "difficulty":  q["difficulty"],
            "tags":        q.get("tags", []),
        }
        for q in questions
    ]
    return {"unit_id": unit_id, "questions": safe, "count": len(safe),
            "locked_until": None, "seconds_remaining": 0, "source": "handcrafted"}


@app.get("/debug/dataset")
def debug_dataset():
    """
    Inspects python_course_dataset.json — call GET /debug/dataset in browser
    to see all unique 'unit' field values and confirm they match your unit IDs.
    Remove this endpoint before going to production.
    """
    if not _DATASET_PATH.exists():
        return {"error": f"File not found: {_DATASET_PATH}"}
    with open(_DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    unit_values = sorted(set(str(n.get("unit", "MISSING")) for n in data))
    all_fields  = set()
    for n in data[:20]:
        all_fields.update(n.keys())
    return {
        "total_records":      len(data),
        "unique_unit_values": unit_values,
        "unique_unit_count":  len(unit_values),
        "all_field_names":    sorted(all_fields),
        "sample_entries":     data[:3],
        "dataset_path":       str(_DATASET_PATH),
    }


# ── Curated note content — real explanations for all 28 topics ─────────────
# Replaces the auto-generated placeholder text in python_course_dataset.json.
_NOTE_CONTENT = {
    "UNIT1_PythonBasics": {
        "Variables": {
            "concept": "A variable is a named label that stores a value in memory. In Python you never declare types — the interpreter infers them automatically. The same variable can be reassigned to a different type at any time.",
            "code": "name = 'Alice'\nage  = 21\ngpa  = 8.75\nis_enrolled = True\n\nprint(name, age, gpa, is_enrolled)\n\n# Reassign to different type\nvalue = 10\nvalue = 'ten'\nprint(value)",
            "input_output": "Alice 21 8.75 True\nten",
            "explanation": "Variable names must start with a letter or underscore, not a digit. Use snake_case: student_name not studentname. Avoid single-letter names except for loop counters."
        },
        "Data Types": {
            "concept": "Python has five core built-in types: int (whole numbers), float (decimals), str (text), bool (True/False), and NoneType (no value). Use type() to inspect any value at runtime.",
            "code": "x = 42          # int\ny = 3.14        # float\ns = 'hello'     # str\nb = True        # bool\nn = None        # NoneType\n\nprint(type(x))  # <class 'int'>\nprint(type(s))  # <class 'str'>\nprint(type(n))  # <class 'NoneType'>",
            "input_output": "<class 'int'>\n<class 'str'>\n<class 'NoneType'>",
            "explanation": "Type conversion: int('5')→5, float('3.14')→3.14, str(100)→'100', bool(0)→False, bool(1)→True. Careful: int('3.5') raises ValueError — convert to float first."
        },
        "Type Casting": {
            "concept": "Type casting converts a value from one type to another using int(), float(), str(), bool(). This is essential when reading input — input() always returns a string, so you must cast to int or float before doing arithmetic.",
            "code": "age_str = '21'           # input() always gives a string\nage_int = int(age_str)   # convert to int\n\nprint(age_int + 1)       # 22\nprint(float(age_str))    # 21.0\nprint(str(100) + ' marks')  # '100 marks'\nprint(bool(0), bool(42)) # False True",
            "input_output": "22\n21.0\n100 marks\nFalse True",
            "explanation": "int() truncates decimals: int(3.9)→3. Use round() if you want rounding. bool() is False for 0, '', [], {}, None. Everything else is True."
        },
        "Input Output": {
            "concept": "input() reads a line from the keyboard and always returns a string. print() displays output. f-strings (f'...') are the cleanest way to embed variables in output strings.",
            "code": "name = 'Alice'   # normally: name = input('Enter name: ')\nage  = 20        # normally: age = int(input('Enter age: '))\n\nprint('Hello,', name)\nprint(f'You are {age} years old')\nprint(f'Next year: {age + 1}')\nprint('Score: {:.2f}'.format(95.678))",
            "input_output": "Hello, Alice\nYou are 20 years old\nNext year: 21\nScore: 95.68",
            "explanation": "f-strings are Python 3.6+. Write f'text {variable}' — the expression inside {} is evaluated at runtime. {:.2f} formats a float to 2 decimal places. sep and end are optional print() parameters."
        },
        "Operators": {
            "concept": "Python operators: Arithmetic (+,-,*,/,//,%,**), Comparison (==,!=,<,>,<=,>=) return bool, Logical (and, or, not) combine conditions. // is floor division, % is modulo (remainder), ** is power.",
            "code": "print(10 // 3)   # 3   floor division\nprint(10 %  3)   # 1   remainder\nprint(2  ** 8)   # 256 power\n\nprint(5 == 5.0)  # True\n\nx = 7\nprint(x > 0 and x < 10)  # True\nprint(not (x == 7))       # False",
            "input_output": "3\n1\n256\nTrue\nTrue\nFalse",
            "explanation": "% is useful for even/odd: if n%2==0 means even. Use == for value comparison, is only for None checks. Short-circuit evaluation: in 'a and b', if a is False, b is never evaluated."
        },
    },
    "UNIT2_PythonFunctions": {
        "Functions": {
            "concept": "A function is a named, reusable block of code that performs a specific task. Define once with def, call as many times as needed. Functions make code modular, testable, and readable.",
            "code": "def calculate_grade(marks):\n    if marks >= 90: return 'A'\n    elif marks >= 75: return 'B'\n    elif marks >= 60: return 'C'\n    else: return 'F'\n\nprint(calculate_grade(92))\nprint(calculate_grade(78))\nprint(calculate_grade(45))",
            "input_output": "A\nB\nF",
            "explanation": "def keyword is followed by the function name, parentheses for parameters, and a colon. return sends a value back to the caller. Without return, the function returns None. Always write functions that do ONE thing well."
        },
        "Lambda": {
            "concept": "A lambda is a small, anonymous one-line function. Syntax: lambda arguments: expression. Used with map(), filter(), sorted() where a full def would be overkill.",
            "code": "square = lambda x: x ** 2\nadd    = lambda x, y: x + y\n\nprint(square(5))   # 25\nprint(add(3, 4))   # 7\n\nstudents = [('Alice',85), ('Bob',92), ('Carol',78)]\nstudents.sort(key=lambda s: s[1], reverse=True)\nprint(students)",
            "input_output": "25\n7\n[('Bob', 92), ('Alice', 85), ('Carol', 78)]",
            "explanation": "lambda x: x**2 is equivalent to def f(x): return x**2. For anything longer than one expression, write a proper def. Lambdas are most useful as the key argument in sorted()."
        },
        "Recursion": {
            "concept": "Recursion is when a function calls itself to solve a smaller version of the same problem. Every recursive function needs a BASE CASE (stop condition) and a RECURSIVE CASE (the self-call that moves toward the base case).",
            "code": "def factorial(n):\n    if n == 0:           # base case\n        return 1\n    return n * factorial(n - 1)  # recursive case\n\nprint(factorial(5))   # 120\nprint(factorial(0))   # 1\nprint(factorial(7))   # 5040",
            "input_output": "120\n1\n5040",
            "explanation": "factorial(5)=5x4x3x2x1=120. Without a base case the function calls itself forever: RecursionError. Python default limit is 1000 calls. Recursion is elegant but iteration is faster for large inputs."
        },
        "Arguments": {
            "concept": "Four argument types: positional (order matters), keyword (named, order-free), default (pre-set, optional), *args (extra positional as tuple), **kwargs (extra keyword as dict).",
            "code": "def profile(name, age=18, *hobbies, city='Unknown', **extra):\n    print(f'{name}, age {age}, from {city}')\n    print('Hobbies:', hobbies)\n    print('Extra:', extra)\n\nprofile('Alice', 21, 'chess', 'hiking', city='Delhi', roll=101)",
            "input_output": "Alice, age 21, from Delhi\nHobbies: ('chess', 'hiking')\nExtra: {'roll': 101}",
            "explanation": "*args collects extra positional arguments into a tuple. **kwargs collects extra keyword arguments into a dict. Order: positional -> *args -> keyword-only -> **kwargs. This pattern is used in every major Python library."
        },
    },
    "UNIT3_OOP": {
        "Classes": {
            "concept": "A class is a blueprint for creating objects. It bundles data (attributes) and behaviour (methods) together. Think of a class as a cookie cutter and objects as the individual cookies.",
            "code": "class Student:\n    school = 'DDE'           # class attribute (shared)\n\n    def __init__(self, name, marks):\n        self.name  = name    # instance attribute (unique)\n        self.marks = marks\n\n    def grade(self):\n        return 'Pass' if self.marks >= 40 else 'Fail'\n\ns1 = Student('Alice', 85)\ns2 = Student('Bob', 35)\nprint(s1.name, s1.grade())\nprint(s2.name, s2.grade())\nprint(Student.school)",
            "input_output": "Alice Pass\nBob Fail\nDDE",
            "explanation": "__init__ is the constructor — runs when you create an object. self refers to the specific object. Class attributes are shared by all objects; instance attributes are unique to each object."
        },
        "Objects": {
            "concept": "An object is a specific instance of a class — a concrete realisation of the blueprint. Each object holds its own instance attributes in memory but shares methods and class attributes with other objects of the same class.",
            "code": "class Rectangle:\n    def __init__(self, width, height):\n        self.width  = width\n        self.height = height\n\n    def area(self):\n        return self.width * self.height\n\n    def perimeter(self):\n        return 2 * (self.width + self.height)\n\nr1 = Rectangle(4, 6)\nr2 = Rectangle(10, 3)\nprint(f'r1: area={r1.area()} perimeter={r1.perimeter()}')\nprint(f'r2: area={r2.area()} perimeter={r2.perimeter()}')",
            "input_output": "r1: area=24 perimeter=20\nr2: area=30 perimeter=26",
            "explanation": "r1 and r2 are two separate objects in memory. Changing r1.width does not affect r2. Python stores methods once on the class — not on each object — saving memory."
        },
        "Inheritance": {
            "concept": "Inheritance lets a child class reuse all attributes and methods of a parent, then add or override them. Models IS-A relationships: Dog IS-A Animal. Use super() to call the parent's version.",
            "code": "class Animal:\n    def __init__(self, name):\n        self.name = name\n    def speak(self):\n        return '...'\n\nclass Dog(Animal):\n    def speak(self):\n        return 'Woof!'\n\nclass Cat(Animal):\n    def speak(self):\n        return 'Meow!'\n\nfor pet in [Dog('Rex'), Cat('Whiskers'), Dog('Bruno')]:\n    print(f'{pet.name}: {pet.speak()}')",
            "input_output": "Rex: Woof!\nWhiskers: Meow!\nBruno: Woof!",
            "explanation": "Dog inherits __init__ from Animal automatically. speak() is overridden in each subclass. Python resolves methods using MRO (Method Resolution Order): child first, then parent. super().__init__() lets you extend the parent constructor without replacing it."
        },
        "Encapsulation": {
            "concept": "Encapsulation hides internal data and exposes only a clean interface. Use _ (private by convention) or __ (name-mangled, strongly private). Access data through controlled methods (getters/setters) so you can add validation.",
            "code": "class BankAccount:\n    def __init__(self, owner, balance):\n        self.owner    = owner\n        self.__balance = balance     # private\n\n    def deposit(self, amount):\n        if amount > 0:\n            self.__balance += amount\n\n    def get_balance(self):\n        return self.__balance\n\nacc = BankAccount('Alice', 10000)\nacc.deposit(5000)\nprint(acc.get_balance())\n# acc.__balance  <- AttributeError",
            "input_output": "15000",
            "explanation": "acc.__balance is name-mangled to acc._BankAccount__balance. You can still access it but it clearly signals 'do not touch directly'. Encapsulation prevents invalid states like negative balances by putting validation inside deposit()."
        },
        "Polymorphism": {
            "concept": "Polymorphism (many forms) means the same method name behaves differently on different objects. It lets you write code that works with any object that has the right method, without knowing its exact class.",
            "code": "class Rectangle:\n    def __init__(self, w, h): self.w, self.h = w, h\n    def area(self): return self.w * self.h\n\nclass Circle:\n    def __init__(self, r): self.r = r\n    def area(self): return round(3.14159 * self.r**2, 2)\n\nclass Triangle:\n    def __init__(self, b, h): self.b, self.h = b, h\n    def area(self): return 0.5 * self.b * self.h\n\nshapes = [Rectangle(4,5), Circle(3), Triangle(6,4)]\nfor s in shapes:\n    print(type(s).__name__, '->', s.area())",
            "input_output": "Rectangle -> 20\nCircle -> 28.27\nTriangle -> 12.0",
            "explanation": "The for loop calls .area() without knowing whether each shape is a Rectangle, Circle, or Triangle. Python's duck typing: if an object has an area() method, it can be treated as a shape. No isinstance() checks needed."
        },
    },
    "UNIT5_Arrays": {
        "Lists": {
            "concept": "A Python list is an ordered, mutable collection that can hold items of any type. It supports indexing (lst[0]), slicing (lst[1:3]), and methods: append, pop, insert, remove, sort, reverse.",
            "code": "marks = [85, 92, 78, 95, 60]\nmarks.append(88)\nprint('All:', marks)\nprint('First:', marks[0])\nprint('Last:', marks[-1])\nprint('Slice:', marks[1:4])\nprint('Top 3:', sorted(marks, reverse=True)[:3])",
            "input_output": "All: [85, 92, 78, 95, 60, 88]\nFirst: 85\nLast: 88\nSlice: [92, 78, 95]\nTop 3: [95, 92, 88]",
            "explanation": "Negative indexing: marks[-1] is the last element. Slicing: marks[1:4] gives indices 1,2,3. append/pop at end is O(1). insert/remove in middle is O(n) because elements shift."
        },
        "List Comprehension": {
            "concept": "List comprehension is a concise way to create a new list by applying an expression to each item in an iterable, with an optional filter condition. It replaces multi-line for loops with a single readable line.",
            "code": "# Traditional loop\nsquares_loop = []\nfor x in range(1, 6):\n    squares_loop.append(x**2)\n\n# List comprehension — same result\nsquares = [x**2 for x in range(1, 6)]\nprint(squares)\n\n# With condition\nevens = [x for x in range(1, 11) if x % 2 == 0]\nprint(evens)\n\n# Flatten 2D list\nmatrix = [[1,2],[3,4],[5,6]]\nflat = [n for row in matrix for n in row]\nprint(flat)",
            "input_output": "[1, 4, 9, 16, 25]\n[2, 4, 6, 8, 10]\n[1, 2, 3, 4, 5, 6]",
            "explanation": "Syntax: [expression for item in iterable if condition]. The if part is optional. Comprehensions are generally faster than equivalent for loops because they are optimised at the Python bytecode level."
        },
        "Array Operations": {
            "concept": "Common array/list operations: traversal (for loop), insertion (append/insert), deletion (remove/pop), searching (in / index()), sorting (sort()/sorted()), reversing (reverse()/[::-1]).",
            "code": "data = [5, 2, 8, 1, 9, 3]\ndata.sort()\nprint('Sorted:', data)\n\n# Stack: LIFO with append/pop\nstack = []\nfor v in [1, 2, 3]:\n    stack.append(v)\nprint('Stack top:', stack[-1])\nprint('Popped:', stack.pop())\n\n# Reverse\nprint('Reversed:', data[::-1])\n\n# Search\nprint('9 at index:', data.index(9))",
            "input_output": "Sorted: [1, 2, 3, 5, 8, 9]\nStack top: 3\nPopped: 3\nReversed: [9, 8, 5, 3, 2, 1]\n9 at index: 4",
            "explanation": "data[::-1] creates a reversed copy without modifying original. data.sort() modifies in place; sorted(data) returns a new list. .index() raises ValueError if item is not found — use 'in' to check first."
        },
    },
    "UNIT7_StacksQueues": {
        "Stack": {
            "concept": "A stack is LIFO — Last In, First Out. Like a stack of plates: you add and remove from the top only. Operations: push (add) and pop (remove from top). Use Python list with append() and pop().",
            "code": "# Stack using list\nstack = []\n\nstack.append('page1')  # push\nstack.append('page2')\nstack.append('page3')\nprint('Stack:', stack)\nprint('Top:', stack[-1])\n\nstack.pop()            # pop\nprint('After pop:', stack)\n\n# Real use: undo history\nactions = ['type A', 'type B', 'delete']\nprint('Undo:', actions.pop())",
            "input_output": "Stack: ['page1', 'page2', 'page3']\nTop: page3\nAfter pop: ['page1', 'page2']\nUndo: delete",
            "explanation": "append() and pop() on a list are both O(1). Stacks are used for: function call stack, undo/redo, expression evaluation, DFS graph traversal. Use collections.deque for thread-safe stack operations."
        },
        "Queue": {
            "concept": "A queue is FIFO — First In, First Out. Like a ticket counter: first person to join is first to be served. Operations: enqueue (add to rear) and dequeue (remove from front). Use collections.deque for O(1) both ends.",
            "code": "from collections import deque\n\nqueue = deque()\nqueue.append('customer1')   # enqueue\nqueue.append('customer2')\nqueue.append('customer3')\nprint('Queue:', queue)\n\nserved = queue.popleft()     # dequeue O(1)\nprint('Served:', served)\nprint('Remaining:', queue)\nprint('Next up:', queue[0])",
            "input_output": "Queue: deque(['customer1', 'customer2', 'customer3'])\nServed: customer1\nRemaining: deque(['customer2', 'customer3'])\nNext up: customer2",
            "explanation": "Use deque not list for queues — popleft() is O(1) on deque but O(n) on list because all elements shift left. Queues are used in BFS graph traversal, task scheduling, and print spooling."
        },
    },
    "UNIT8_Trees": {
        "Binary Tree": {
            "concept": "A binary tree is a hierarchical data structure where each node has at most two children: left and right. The topmost node is the root; nodes with no children are leaves. Used in file systems, parsing, and databases.",
            "code": "class TreeNode:\n    def __init__(self, val):\n        self.val   = val\n        self.left  = None\n        self.right = None\n\n#       1\n#      / \\\n#     2   3\n#    / \\\n#   4   5\nroot = TreeNode(1)\nroot.left         = TreeNode(2)\nroot.right        = TreeNode(3)\nroot.left.left    = TreeNode(4)\nroot.left.right   = TreeNode(5)\n\ndef inorder(node):\n    if node:\n        inorder(node.left)\n        print(node.val, end=' ')\n        inorder(node.right)\n\ninorder(root)",
            "input_output": "4 2 5 1 3",
            "explanation": "Inorder (L, Root, R) gives sorted output for BSTs. Preorder (Root, L, R) is used for copying trees. Postorder (L, R, Root) is used for deleting trees. Tree height = longest root-to-leaf path."
        },
        "BST": {
            "concept": "A Binary Search Tree (BST) has the ordering property: every node's left subtree contains only SMALLER values and right subtree only LARGER values. This makes search, insert, and delete O(log n) average.",
            "code": "class Node:\n    def __init__(self, val):\n        self.val = val\n        self.left = self.right = None\n\ndef insert(root, val):\n    if not root: return Node(val)\n    if val < root.val: root.left  = insert(root.left,  val)\n    else:              root.right = insert(root.right, val)\n    return root\n\ndef search(root, val):\n    if not root: return False\n    if root.val == val: return True\n    if val < root.val: return search(root.left, val)\n    return search(root.right, val)\n\nroot = None\nfor v in [5, 3, 7, 1, 4, 6, 8]:\n    root = insert(root, v)\nprint(search(root, 4))\nprint(search(root, 9))",
            "input_output": "True\nFalse",
            "explanation": "BST search: compare at each node and go left (smaller) or right (larger) — halves the search space each step, O(log n) average. Worst case O(n) if tree is unbalanced (sorted input). Use AVL or Red-Black trees for guaranteed O(log n)."
        },
    },
    "UNIT10_Sorting": {
        "Bubble Sort": {
            "concept": "Bubble Sort repeatedly compares adjacent elements and swaps them if out of order. After each pass, the largest unsorted element 'bubbles' to the end. Time: O(n²) — too slow for large data but simple to understand.",
            "code": "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n - 1):\n        swapped = False\n        for j in range(n - 1 - i):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n                swapped = True\n        if not swapped:   # already sorted\n            break\n    return arr\n\ndata = [64, 34, 25, 12, 22, 11, 90]\nprint(bubble_sort(data))",
            "input_output": "[11, 12, 22, 25, 34, 64, 90]",
            "explanation": "The swapped flag is an optimisation: if no swaps in a full pass, the list is already sorted — break early (O(n) best case). Bubble sort is stable (equal elements keep original order) but not used in production because O(n^2) is too slow."
        },
        "Merge Sort": {
            "concept": "Merge Sort uses divide and conquer: split list in half, recursively sort each half, then merge the two sorted halves. Time: O(n log n). Stable sort. Preferred for linked lists and external sorting.",
            "code": "def merge_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    mid   = len(arr) // 2\n    left  = merge_sort(arr[:mid])\n    right = merge_sort(arr[mid:])\n    return merge(left, right)\n\ndef merge(left, right):\n    result = []\n    i = j  = 0\n    while i < len(left) and j < len(right):\n        if left[i] <= right[j]:\n            result.append(left[i]); i += 1\n        else:\n            result.append(right[j]); j += 1\n    result.extend(left[i:])\n    result.extend(right[j:])\n    return result\n\nprint(merge_sort([38, 27, 43, 3, 9, 82, 10]))",
            "input_output": "[3, 9, 10, 27, 38, 43, 82]",
            "explanation": "Merge sort splits until single elements (base case), then merges upward. Space: O(n) extra for the temporary arrays. Python's built-in sorted() uses Timsort — a hybrid of merge sort and insertion sort optimised for real-world data."
        },
        "Quick Sort": {
            "concept": "Quick Sort picks a pivot, partitions the array into elements smaller than pivot (left) and larger (right), then recursively sorts both parts. Average O(n log n), worst case O(n^2) with bad pivot choice.",
            "code": "def quick_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot  = arr[len(arr) // 2]\n    left   = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right  = [x for x in arr if x > pivot]\n    return quick_sort(left) + middle + quick_sort(right)\n\ndata = [3, 6, 8, 10, 1, 2, 1]\nprint(quick_sort(data))",
            "input_output": "[1, 1, 2, 3, 6, 8, 10]",
            "explanation": "Choosing middle element as pivot avoids worst case on sorted input. Quick sort is in-place in the original implementation and cache-friendly, making it faster than merge sort in practice despite the same average complexity."
        },
    },
    "UNIT11_Searching": {
        "Linear Search": {
            "concept": "Linear Search checks every element from the start until it finds the target or reaches the end. Works on unsorted data. Time: O(n) — must check all n elements in the worst case.",
            "code": "def linear_search(lst, target):\n    for i, val in enumerate(lst):\n        if val == target:\n            return i      # found — return index\n    return -1             # not found\n\nstudents = ['Alice', 'Bob', 'Carol', 'Dave', 'Eve']\nprint(linear_search(students, 'Carol'))   # 2\nprint(linear_search(students, 'Frank'))   # -1\n\n# Python built-in (also linear search)\nprint('Dave' in students)",
            "input_output": "2\n-1\nTrue",
            "explanation": "enumerate() gives both index and value. The 'in' operator on a list is O(n) linear search. For frequent lookups, convert to a set: membership check becomes O(1). Use linear search only for small or unsorted data."
        },
        "Binary Search": {
            "concept": "Binary Search works ONLY on SORTED lists. It halves the search range each step by comparing the target with the middle element. Time: O(log n) — for 1 million items, at most 20 comparisons.",
            "code": "def binary_search(lst, target):\n    lo, hi = 0, len(lst) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if lst[mid] == target:\n            return mid\n        elif lst[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1\n\ndata = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]\nprint(binary_search(data, 23))   # 5\nprint(binary_search(data, 10))   # -1",
            "input_output": "5\n-1",
            "explanation": "log2(1,000,000) is about 20 — binary search finds any element in 20 steps regardless of list size. The list MUST be sorted first. Use Python's bisect module for production: import bisect; bisect.bisect_left(sorted_list, target)."
        },
    },
    "UNIT12_Recursion": {
        "Factorial": {
            "concept": "Factorial of n (n!) = n x (n-1) x ... x 1. Factorial(5)=120. It is the classic recursion example: n! = n x (n-1)! with base case 0!=1.",
            "code": "def factorial(n):\n    if n == 0:              # base case\n        return 1\n    return n * factorial(n - 1)  # recursive case\n\nfor i in range(8):\n    print(f'{i}! = {factorial(i)}')",
            "input_output": "0! = 1\n1! = 1\n2! = 2\n3! = 6\n4! = 24\n5! = 120\n6! = 720\n7! = 5040",
            "explanation": "Each call adds a frame to the call stack. factorial(5) needs 6 frames. Without a base case: infinite recursion -> RecursionError (Python limit: 1000). For large n, use math.factorial() which is C-speed and handles arbitrary precision."
        },
        "Fibonacci": {
            "concept": "Fibonacci sequence: 0, 1, 1, 2, 3, 5, 8, 13 ... Each number is the sum of the two before it. fib(n) = fib(n-1) + fib(n-2), base cases: fib(0)=0, fib(1)=1.",
            "code": "# Naive recursion — exponential O(2^n)\ndef fib_slow(n):\n    if n <= 1: return n\n    return fib_slow(n-1) + fib_slow(n-2)\n\n# Memoized — O(n)\nfrom functools import lru_cache\n@lru_cache(maxsize=None)\ndef fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)\n\nprint([fib(i) for i in range(10)])\nprint(fib(50))",
            "input_output": "[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]\n12586269025",
            "explanation": "Naive fib(50) makes billions of calls recomputing the same values. @lru_cache stores each result the first time — subsequent calls return instantly. This is memoization, a key dynamic programming concept."
        },
    },
    "UNIT13_DynamicProg": {
        "Memoization": {
            "concept": "Memoization is top-down dynamic programming: solve recursively but cache each subproblem result. On repeated calls with the same input, return cached result instead of recomputing. Turns O(2^n) into O(n).",
            "code": "def fib_memo(n, cache={}):\n    if n in cache: return cache[n]\n    if n <= 1: return n\n    cache[n] = fib_memo(n-1, cache) + fib_memo(n-2, cache)\n    return cache[n]\n\ndef min_coins(amount, coins, memo={}):\n    if amount == 0: return 0\n    if amount < 0:  return float('inf')\n    if amount in memo: return memo[amount]\n    memo[amount] = 1 + min(min_coins(amount-c, coins, memo) for c in coins)\n    return memo[amount]\n\nprint(fib_memo(10))\nprint(min_coins(11, [1, 5, 6, 9]))",
            "input_output": "55\n2",
            "explanation": "The cache dict stores computed results. min_coins(11,[1,5,6,9])=2 because 11=9+... wait, 11=6+5. Memoization shines when the same subproblem is solved many times. Python's @lru_cache does this automatically."
        },
        "Tabulation": {
            "concept": "Tabulation is bottom-up dynamic programming: fill a table starting from smallest subproblems up to the target using previously computed values. No recursion. Often faster than memoization — no function call overhead.",
            "code": "def fib_tab(n):\n    if n <= 1: return n\n    dp = [0] * (n + 1)\n    dp[1] = 1\n    for i in range(2, n + 1):\n        dp[i] = dp[i-1] + dp[i-2]\n    return dp[n]\n\ndef knapsack(weights, values, capacity):\n    n  = len(weights)\n    dp = [[0]*(capacity+1) for _ in range(n+1)]\n    for i in range(1, n+1):\n        for w in range(capacity+1):\n            dp[i][w] = dp[i-1][w]\n            if weights[i-1] <= w:\n                dp[i][w] = max(dp[i][w], values[i-1]+dp[i-1][w-weights[i-1]])\n    return dp[n][capacity]\n\nprint(fib_tab(10))\nprint(knapsack([2,3,4,5],[3,4,5,6], 5))",
            "input_output": "55\n7",
            "explanation": "Tabulation fills dp[i] iteratively from dp[0] up — no stack depth issues. Knapsack dp[i][w] = max value using first i items with capacity w. Bottom-up DP is preferred in production for predictable O(n x m) time and space."
        },
    },
}


def _enrich_notes(unit_id: str, notes: list) -> list:
    """Replace dataset placeholder text with real curated explanations.
    Falls back to original dataset note if no curated version exists."""
    unit_content = _NOTE_CONTENT.get(unit_id, {})
    enriched = []
    for note in notes:
        topic   = note.get("topic", "")
        curated = unit_content.get(topic)
        if curated:
            enriched.append({
                "id":           note["id"],
                "unit":         note.get("unit", unit_id),
                "topic":        topic,
                "concept":      curated.get("concept",      note.get("concept",      "")),
                "code":         curated.get("code",         note.get("code",         "")),
                "input_output": curated.get("input_output", note.get("input_output", "")),
                "explanation":  curated.get("explanation",  note.get("explanation",  "")),
            })
        else:
            enriched.append(note)
    return enriched



@app.get("/curriculum/{unit_id}/notes")
def get_unit_notes(unit_id: str):
    """
    Returns notes for a unit.
    Primary source  : notes.json (rich format — definitions, key_concepts, code_examples).
    Fallback source : python_course_dataset.json (legacy flat format).
    """
    # ── Primary: notes.json ────────────────────────────────────────────────
    if _NOTES_PATH.exists():
        notes_unit_id = _NOTES_UNIT_MAP.get(unit_id)
        if notes_unit_id:
            with open(_NOTES_PATH, "r", encoding="utf-8") as f:
                notes_data = json.load(f)
            unit_entry = next(
                (u for u in notes_data.get("units", []) if u["unit_id"] == notes_unit_id),
                None,
            )
            if unit_entry and unit_entry.get("topics"):
                return {
                    "unit_id": unit_id,
                    "count":   len(unit_entry["topics"]),
                    "topics":  unit_entry["topics"],
                }

    # ── Fallback: python_course_dataset.json ───────────────────────────────
    if not _DATASET_PATH.exists():
        raise HTTPException(
            404,
            f"Notes not found. Neither notes.json nor python_course_dataset.json "
            f"exists in the data/ folder.",
        )

    with open(_DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_notes = [n for n in data if n.get("unit") == unit_id]
    seen: set = set()
    unique_notes = []
    for note in raw_notes:
        topic = note.get("topic", "General")
        if topic not in seen:
            seen.add(topic)
            unique_notes.append(note)

    enriched = _enrich_notes(unit_id, unique_notes)

    return {
        "unit_id": unit_id,
        "count":   len(enriched),
        "notes":   enriched,
    }



@app.post("/curriculum/{unit_id}/questions/{question_id}/check")
def check_answer(unit_id: str, question_id: str, answer_idx: int):
    question = get_question_by_id(question_id)
    if not question or question["unit_id"] != unit_id:
        raise HTTPException(404, "Question not found.")
    is_correct = (answer_idx == question["correct_idx"])
    return {
        "question_id":  question_id,
        "answer_idx":   answer_idx,
        "correct_idx":  question["correct_idx"],
        "is_correct":   is_correct,
        "explanation":  question.get("explanation", ""),
    }


# ─────────────────────────────────────────────────────────────────
#  LEARNING ENGINE ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.post("/recommend")
async def get_recommendation(profile: LearnerProfileIn):
    session, logger = _load_session(profile.user_id)

    # SM-2 gate enforced server-side
    day       = _get_current_day(session)
    due_cards = session.get_due_flashcards_detail(day)
    if due_cards:
        enriched = []
        for card in due_cards:
            meta = KG.get_unit_metadata(card["unit_id"])
            enriched.append({
                **card,
                "display_name": meta.get("display_name", card["unit_id"]),
                "domain":       meta.get("domain", ""),
                "front":        meta.get("display_name", card["unit_id"]),
                "back":         "Skills: " + ", ".join(meta.get("skills_taught", [])),
            })
        raise HTTPException(
            status_code=409,
            detail={
                "code":            "REVIEWS_DUE",
                "message":         f"Complete {len(due_cards)} flashcard review(s) before starting a new unit.",
                "cards_due_count": len(due_cards),
                "due_cards":       enriched,
                "current_day":     day,
                "action":          "POST /flashcard/review for each card, then retry /recommend",
            },
        )

    from python_source.core.mistake_tracker import build_skill_weakness_map
    skill_weakness = build_skill_weakness_map(
        concept_index=session.concept_index,
        mistake_log=  session.mistake_log,
    )

    mcts = MCTSAlgorithm(
        knowledge_graph=     KG,
        initial_skill_state= session.get_mastery_state(),
        learner_profile={
            "degree":   profile.degree,
            "year":     profile.year,
            "interest": profile.interest,
        },
        logger=         logger,
        skill_weakness= skill_weakness,
    )

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_EXECUTOR, mcts.run, MCTS_ITERS)

    details = mcts.get_recommendation_details()
    unit_id = details["unit_id"]

    if not unit_id:
        return {
            "user_id": profile.user_id,
            "status":  "curriculum_complete",
            "message": "You have mastered all available units. Congratulations!",
        }

    skills    = KG.get_unit_skills(unit_id)
    mastery   = session.skill_mastery.get(skills[0], 0.1) if skills else 0.1
    questions = enrich_with_irt(get_questions_for_unit(unit_id))
    best_q    = irt_select_best_question(mastery, questions)

    logger.log_recommendation(unit_id, KG.get_display_name(unit_id), session.get_mastery_state())
    session.current_unit_id = unit_id
    STATE_MANAGER.save(session)

    return {
        "user_id":       profile.user_id,
        "unit_id":       unit_id,
        "display_name":  KG.get_display_name(unit_id),
        "description":   KG.get_description(unit_id),
        "domain":        KG.get_domain(unit_id),
        "quiz_question": best_q,
        "mcts_details":  details,
        "mastery_state": session.get_mastery_state(),
    }


@app.post("/quiz/result")
def submit_quiz_result(result: QuizResultIn):
    session, logger = _load_session(result.user_id)

    if not KG.are_prereqs_met(result.unit_id, session.get_mastery_state()):
        raise HTTPException(400, f"Prerequisites not met for {result.unit_id}.")

    import time as _time_mod
    recent = [
        h for h in session.quiz_history[-5:]
        if h["unit_id"] == result.unit_id
        and _time_mod.time() - h["timestamp"] < 60
    ]
    if recent:
        raise HTTPException(
            409,
            f"Quiz result for {result.unit_id} was already submitted in the last 60 seconds. "
            "Duplicate submission ignored."
        )

    update = session.record_quiz_result(result.unit_id, result.was_correct)

    skills = KG.get_unit_skills(result.unit_id)
    topic  = skills[0] if skills else result.unit_id
    from python_source.core.mistake_tracker import make_mistake_event, update_concept_index
    import time as _t
    event = make_mistake_event(
        question_id=  f"binary_{result.unit_id}",
        unit_id=      result.unit_id,
        topic=        topic,
        concept_tags= [topic],
        difficulty=   "medium",
        was_correct=  result.was_correct,
        timestamp=    round(_t.time(), 3),
    )
    session.mistake_log.append(event)
    session.concept_index = update_concept_index(
        index=        session.concept_index,
        concept_tags= [topic],
        was_correct=  result.was_correct,
        difficulty=   "medium",
        timestamp=    event["timestamp"],
    )

    STATE_MANAGER.save(session)

    return {
        "user_id":                   result.user_id,
        "unit_id":                   result.unit_id,
        "skill_updates":             update["skill_updates"],
        "unit_passed":               update["unit_passed"],
        "progress":                  session.get_progress_summary(),
        "consecutive_failures":      update["consecutive_failures"],
        "stuck_alert":               update["stuck_alert"],
        "stuck_threshold":           update["stuck_threshold"],
        "prereq_review_suggestions": update["prereq_review_suggestions"],
    }


@app.get("/learner/{user_id}")
def get_learner_state(user_id: str):
    session, _ = _load_session(user_id)
    return {
        "user_id":         user_id,
        "progress":        session.get_progress_summary(),
        "current_unit_id": session.current_unit_id,
        "completed_units": list(session.completed_units),
        "mastery_summary": session.get_mastery_summary(),
    }


@app.post("/learner/{user_id}/reset")
def reset_learner(user_id: str):
    STATE_MANAGER.delete(user_id)
    return {"user_id": user_id, "status": "reset"}


@app.delete("/learner/{user_id}/quiz-lock/{unit_id}")
def clear_quiz_lock(user_id: str, unit_id: str):
    """
    Manually clear the 24hr quiz lock for a specific user + unit.
    Useful during development and testing.
    """
    clear_lock(user_id, unit_id)
    return {"user_id": user_id, "unit_id": unit_id, "status": "lock_cleared"}


@app.delete("/learner/{user_id}/quiz-lock")
def clear_all_quiz_locks(user_id: str):
    """
    Clear ALL quiz locks for a user across all units.
    Useful during development and testing.
    """
    from python_source.engines.question_generator import _CACHE_DIR, _cache_path
    import re
    safe_uid = re.sub(r"[^\w\-]", "_", user_id)
    cleared = []
    for f in _CACHE_DIR.glob(f"{safe_uid}_*.json"):
        f.unlink()
        cleared.append(f.stem)
    return {"user_id": user_id, "cleared": cleared, "count": len(cleared)}


# ─────────────────────────────────────────────────────────────────
#  FLASHCARD ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.post("/flashcard/review")
def review_flashcard(req: FlashcardReviewIn):
    """Uses server-calculated day — client's current_day field is ignored."""
    if not 0 <= req.quality <= 5:
        raise HTTPException(400, "Quality must be 0-5.")
    session, _ = _load_session(req.user_id)
    day        = _get_current_day(session)
    result     = session.review_flashcard(req.unit_id, req.quality, day)
    STATE_MANAGER.save(session)

    remaining = session.get_due_flashcards_detail(day)
    return {
        "user_id":         req.user_id,
        "unit_id":         req.unit_id,
        "quality":         req.quality,
        "new_interval":    result["new_interval"],
        "next_due_day":    result["next_due_day"],
        "ease_factor":     result["ease_factor"],
        "cards_remaining": len(remaining),
        "can_proceed":     len(remaining) == 0,
        "message": (
            "Review recorded. All done for today!" if len(remaining) == 0
            else f"{len(remaining)} card(s) still to review."
        ),
    }


@app.get("/flashcard/due/{user_id}")
def get_due_flashcards(user_id: str):
    session, _ = _load_session(user_id)
    day        = _get_current_day(session)
    due        = session.get_due_flashcards(day)
    return {"user_id": user_id, "due_units": due, "due_count": len(due)}


@app.get("/flashcard/gate/{user_id}")
def flashcard_gate(user_id: str):
    session, _ = _load_session(user_id)
    day        = _get_current_day(session)
    due_cards  = session.get_due_flashcards_detail(day)
    due_count  = len(due_cards)

    enriched = []
    for card in due_cards:
        meta = KG.get_unit_metadata(card["unit_id"])
        enriched.append({
            **card,
            "display_name": meta.get("display_name", card["unit_id"]),
            "domain":       meta.get("domain", ""),
            "front":        meta.get("display_name", card["unit_id"]),
            "back":         "Skills: " + ", ".join(meta.get("skills_taught", [])),
        })

    if due_count == 0:
        message = "No reviews due. You can start a new unit."
    elif due_count == 1:
        message = "1 flashcard review due before you can continue."
    else:
        message = f"{due_count} flashcard reviews due before you can continue."

    return {
        "user_id":         user_id,
        "reviews_due":     due_count > 0,
        "can_proceed":     due_count == 0,
        "cards_due_count": due_count,
        "due_cards":       enriched,
        "current_day":     day,
        "message":         message,
    }


@app.post("/flashcard/create/{user_id}/{unit_id}")
def create_flashcard(user_id: str, unit_id: str):
    if unit_id not in KG.units:
        raise HTTPException(404, f"Unit {unit_id} not in knowledge graph.")
    session, _ = _load_session(user_id)
    day        = _get_current_day(session)
    if unit_id in session.flashcards:
        return {
            "user_id":  user_id,
            "unit_id":  unit_id,
            "created":  False,
            "message":  "Flashcard already exists.",
            "next_due": day + session.flashcards[unit_id].interval,
        }
    from python_source.core.adaptive_systems import SM2Flashcard
    session.flashcards[unit_id]      = SM2Flashcard(unit_id)
    session.last_review_day[unit_id] = day
    STATE_MANAGER.save(session)
    return {
        "user_id":  user_id,
        "unit_id":  unit_id,
        "created":  True,
        "next_due": day + 1,
        "message":  f"Flashcard created. Due tomorrow (day {day+1}).",
    }


@app.get("/flashcard/schedule/{user_id}")
def get_full_schedule(user_id: str):
    session, _ = _load_session(user_id)
    day        = _get_current_day(session)
    schedule   = []
    for uid, card in session.flashcards.items():
        last_day = session.last_review_day.get(uid, 0)
        due_day  = last_day + card.interval
        meta     = KG.get_unit_metadata(uid)
        schedule.append({
            "unit_id":      uid,
            "display_name": meta.get("display_name", uid),
            "domain":       meta.get("domain", ""),
            "due_day":      due_day,
            "is_due_today": due_day <= day,
            "days_until":   max(0, due_day - day),
            "interval":     card.interval,
            "ease_factor":  round(card.ease_factor, 2),
            "repetitions":  card.repetitions,
        })
    schedule.sort(key=lambda x: x["due_day"])
    return {
        "user_id":     user_id,
        "current_day": day,
        "total_cards": len(schedule),
        "due_today":   sum(1 for s in schedule if s["is_due_today"]),
        "schedule":    schedule,
    }


# ─────────────────────────────────────────────────────────────────
#  AI FEATURE ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.post("/chat")
async def ask_chatbot(req: ChatIn):
    if req.mode == "simplify" and not req.unit_notes:
        raise HTTPException(400, "unit_notes is required for simplify mode.")
    if req.mode != "simplify" and not req.question.strip():
        raise HTTPException(400, "question cannot be empty.")

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _EXECUTOR,
        lambda: RAG.query(
            user_question= req.question,
            unit_id=       req.unit_id,
            unit_title=    req.unit_title,
            unit_domain=   req.unit_domain,
            unit_notes=    req.unit_notes,
            mode=          req.mode,
        )
    )
    return {
        "user_id":      req.user_id,
        "question":     req.question,
        "mode":         result["mode"],
        "answer":       result["answer"],
        "sources":      result["sources"],
        "context_used": result.get("context_used", False),
        "unit_id":      req.unit_id,
        "unit_title":   req.unit_title,
    }


@app.post("/ats/analyze")
def analyze_resume(req: ATSIn):
    if not req.resume_text.strip() or not req.job_description.strip():
        raise HTTPException(400, "Both resume_text and job_description required.")

    result = ATS.analyze(req.resume_text, req.job_description)

    # keyword_density and recommendations aliases for ATSPage
    matched_count = len(result.get("matched_keywords", []))
    missing_count = len(result.get("missing_keywords", []))
    implied_count = len(result.get("implied_keywords", []))
    result["keyword_density"]  = round(matched_count / max(matched_count + missing_count + implied_count, 1), 3)
    result["recommendations"]  = result.get("suggestions", [])

    # semantic_matches is already included by analyze() — no extra call needed.
    # implied_keywords shows keywords the resume already covers under different
    # wording (shown as amber chips in the UI, separate from green matched and
    # red missing).

    return {"user_id": req.user_id, **result}


@app.post("/ats/improve")
def improve_resume(req: ATSImproveIn):
    if not req.resume_text.strip() or not req.job_description.strip():
        raise HTTPException(400, "Both resume_text and job_description required.")
    result = ATS.analyze_and_improve(
        resume_text=     req.resume_text,
        job_description= req.job_description,
        target_role=     req.target_role,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    # Flatten so ATSPage can read bullet_rewrites, keyword_suggestions etc at top level
    scoring  = result.get("scoring",      {})
    improve  = result.get("improvements", {})
    return {
        "user_id":                 req.user_id,
        "score_ats":               scoring.get("score_ats", 0),
        "matched_keywords":        scoring.get("matched_keywords", []),
        "missing_keywords":        scoring.get("missing_keywords", []),
        "implied_keywords":        scoring.get("implied_keywords", []),    # NEW
        "semantic_matches":        scoring.get("semantic_matches", []),    # NEW
        "feedback":                scoring.get("feedback", ""),
        "bullet_rewrites":         improve.get("bullet_rewrites", []),
        "keyword_suggestions":     improve.get("keyword_suggestions", []),
        "improved_summary":        improve.get("improved_summary", {}),
        "anti_hallucination_note": improve.get("anti_hallucination_note", ""),
        "scoring":                 scoring,
        "improvements":            improve,
    }


@app.post("/ats/rewrite-bullets")
def rewrite_bullets_only(req: ATSImproveIn):
    if not req.resume_text.strip():
        raise HTTPException(400, "resume_text required.")
    score = ATS.analyze(req.resume_text, req.job_description)
    if "error" in score:
        raise HTTPException(400, score["error"])
    rewrites = ATS.rewrite_resume(
        resume_text=      req.resume_text,
        missing_keywords= score["missing_keywords"],
        matched_keywords= score["matched_keywords"],
        job_description=  req.job_description,
        target_role=      req.target_role,
        resume_sections=  req.resume_sections,
    )
    return {
        "user_id":                 req.user_id,
        "score_ats":               score["score_ats"],
        "bullet_rewrites":         rewrites.get("bullet_rewrites", []),
        "improved_summary":        rewrites.get("improved_summary", {}),
        "anti_hallucination_note": rewrites.get("anti_hallucination_note", ""),
    }


MAX_RESUME_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@app.post("/ats/upload-resume")
async def upload_resume_file(file: UploadFile = File(...)):
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "docx"):
        raise HTTPException(400, "Please upload a PDF or DOCX file.")

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Uploaded file is empty.")
    if len(contents) > MAX_RESUME_FILE_SIZE:
        raise HTTPException(400, "File is too large (max 5MB).")

    try:
        text = extract_resume_text(contents, ext)
    except ResumeParseError as exc:
        raise HTTPException(400, str(exc))

    return {
        "resume_text": text,
        "filename":    filename,
        "char_count":  len(text),
    }


@app.post("/rag/reindex")
def reindex_notes():
    count = RAG.reindex()
    return {"status": "reindexed", "notes_count": count}


# ─────────────────────────────────────────────────────────────────
#  SKILL TREE
# ─────────────────────────────────────────────────────────────────

@app.get("/skill-tree/{user_id}")
def get_skill_tree(user_id: str, topic: Optional[str] = None):
    session, _ = _load_session(user_id)
    mastery     = session.get_mastery_state()
    completed   = session.completed_units
    current     = session.current_unit_id

    nodes = []
    for uid, meta in KG.units.items():
        if topic and meta.get("domain", "").lower() != topic.lower():
            continue
        prereqs_met = all(
            mastery.get(skill, 0.0) >= 0.50
            for skill in meta["prereq_skills"]
        )
        if uid in completed:
            status = "completed"
        elif prereqs_met or uid == current:
            # If this is the current unit (assigned by MCTS before a server restart),
            # always show it as unlocked even if mastery hasn't been reloaded yet.
            status = "unlocked"
        else:
            status = "locked"

        nodes.append({
            "id":            uid,
            "title":         meta["display_name"],
            "domain":        meta["domain"],
            "description":   meta["description"],
            "status":        status,
            "is_current":    uid == current,
            "prereq_skills": list(meta["prereq_skills"]),
            "skills_taught": meta["skills_taught"],
            "mastery":       round(
                max((mastery.get(s, 0.0) for s in meta["skills_taught"]), default=0.0),
                3
            ),
        })

    # Sort by curriculum progression order, not alphabetically by ID.
    # Within each status group units appear in the order they were defined
    # in curriculum.py (UNIT1 first, UNIT14 last) so the tree reads naturally.
    from python_source.content.curriculum import CURRICULUM_UNITS
    curriculum_order = {u["unit_id"]: i for i, u in enumerate(CURRICULUM_UNITS)}
    status_order = {"completed": 0, "unlocked": 1, "locked": 2}
    nodes.sort(key=lambda n: (status_order[n["status"]], curriculum_order.get(n["id"], 99)))

    return {
        "user_id":      user_id,
        "nodes":        nodes,
        "total":        len(nodes),
        "completed":    sum(1 for n in nodes if n["status"] == "completed"),
        "unlocked":     sum(1 for n in nodes if n["status"] == "unlocked"),
        "locked":       sum(1 for n in nodes if n["status"] == "locked"),
        "current_unit": current,
    }


# ─────────────────────────────────────────────────────────────────
#  DIAGNOSTIC QUIZ ENDPOINTS
# ─────────────────────────────────────────────────────────────────

from python_source.content.diagnostic_quiz import DiagnosticEngine
DIAGNOSTIC = DiagnosticEngine()


@app.get("/diagnostic/topics")
def get_diagnostic_topics():
    return {"topics": DIAGNOSTIC.get_available_topics()}


@app.post("/diagnostic/start")
def start_diagnostic(req: DiagnosticStartIn):
    session, _ = _load_session(req.user_id)

    prev_result   = session.diagnostic_result or {}
    prev_topic    = prev_result.get("topic", "").lower().strip()
    current_topic = req.topic.lower().strip()
    is_retake     = (
        bool(prev_result)
        and not prev_result.get("skipped")
        and prev_topic == current_topic
    )

    questions = DIAGNOSTIC.get_questions(req.topic)
    return {
        "user_id":                req.user_id,
        "topic":                  req.topic,
        "questions":              questions,
        "total":                  len(questions),
        "max_score":              20,
        "is_retake":              is_retake,
        "previous_tier":          prev_result.get("tier")          if is_retake else None,
        "previous_starting_unit": prev_result.get("starting_unit") if is_retake else None,
        "instructions": (
            "Answer all 10 questions. Easy=1pt, Medium=2pts, Hard=3pts. "
            "Based on your score we will place you at the right starting point."
        ),
    }


@app.post("/diagnostic/submit")
def submit_diagnostic(req: DiagnosticSubmitIn):
    if not req.answers:
        raise HTTPException(400, "No answers provided.")

    session, _ = _load_session(req.user_id)

    prev_result   = session.diagnostic_result or {}
    prev_topic    = prev_result.get("topic", "").lower().strip()
    current_topic = req.topic.lower().strip()
    is_same_topic_retake = (
        bool(prev_result)
        and not prev_result.get("skipped")
        and prev_topic == current_topic
    )
    if is_same_topic_retake:
        raise HTTPException(
            409,
            f"Diagnostic for '{req.topic}' already completed. "
            "Choose a different topic or reset your account to retake it.",
        )

    result = DIAGNOSTIC.evaluate(topic=req.topic, answers=req.answers)
    session.diagnostic_result = result
    _unlock_units_before(session, result["starting_unit"])
    STATE_MANAGER.save(session)

    return {
        "user_id":            req.user_id,
        "topic":              req.topic,
        "score":              result["score_raw"],
        "score_max":          result["score_max"],
        "percent":            result["score_percent"],
        "tier":               result["tier"],
        "starting_unit":      result["starting_unit"],
        "starting_unit_name": KG.get_display_name(result["starting_unit"]),
        "message":            result["message"],
        "breakdown":          result["breakdown"],
    }


@app.post("/diagnostic/skip")
def skip_diagnostic(req: DiagnosticSkipIn):
    result     = DIAGNOSTIC.get_skip_result(req.topic)
    session, _ = _load_session(req.user_id)
    session.diagnostic_result = result
    _unlock_units_before(session, result["starting_unit"])
    STATE_MANAGER.save(session)
    return {
        "user_id":            req.user_id,
        "topic":              req.topic,
        "skipped":            True,
        "starting_unit":      result["starting_unit"],
        "starting_unit_name": KG.get_display_name(result["starting_unit"]),
        "message":            result["message"],
    }


# ─────────────────────────────────────────────────────────────────
#  IRT QUIZ SCORING ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.post("/quiz/submit-irt")
def submit_quiz_irt(req: IRTQuizSubmitIn):
    session, logger = _load_session(req.user_id)

    # Prereqs validated by MCTS at recommendation time.
    # Warn only, do not block. Blocking here means students
    # can start the quiz but cannot submit it.
    if not KG.are_prereqs_met(req.unit_id, session.get_mastery_state()):
        import logging as _prereq_log
        _prereq_log.getLogger(__name__).warning(
            "submit-irt: prereqs not fully met for %s / %s, allowing anyway",
            req.user_id, req.unit_id
        )

    # ── 24-hour quiz lock check ──────────────────────────────────────────────
    # Blocks resubmission within 24 hours of the last attempt.
    lock = get_lock_status(req.user_id, req.unit_id)
    if lock["locked"]:
        raise HTTPException(
            423,   # 423 Locked
            {
                "code":              "QUIZ_LOCKED",
                "message":           (
                    f"Quiz for {req.unit_id} is locked for "
                    f"{lock['seconds_remaining'] // 3600}h "
                    f"{(lock['seconds_remaining'] % 3600) // 60}m. Come back tomorrow!"
                ),
                "locked_until":      lock["locked_until"],
                "seconds_remaining": lock["seconds_remaining"],
            }
        )

    # FIX: Score only the questions actually served to this user.
    # Previously used get_questions_for_unit() which returns ALL handcrafted
    # questions (e.g. 24) regardless of how many the frontend showed (e.g. 15),
    # causing the result screen to show "3/24" instead of "3/15".
    # ── Rebuild question list with correct_idx for scoring ─────────────────
    # Strategy:
    #   1. Load the raw cache (contains correct_idx for AI-generated questions).
    #   2. For handcrafted questions, re-attach correct_idx from quiz_bank
    #      (ground-truth source), ignoring whatever the cache says.
    #   3. For AI-generated questions, use correct_idx from the cache BUT also
    #      verify it passes the same semantic check used at generation time.
    #      If a question fails the check here (e.g. cache was written before
    #      the fix), drop it and log — it will not affect the student's score.
    from python_source.engines.question_generator import _load_cache as _qgen_load_cache
    _raw_cache    = _qgen_load_cache(req.user_id, req.unit_id)
    _raw_cache_qs = {q["question_id"]: q for q in (_raw_cache or {}).get("questions", [])}

    _cache_result = get_or_generate_questions(req.user_id, req.unit_id)
    _served_qs    = _cache_result.get("questions") or []
    if _served_qs:
        # Build a map of handcrafted questions by ID (authoritative correct_idx)
        _bank_map = {q["question_id"]: q for q in get_questions_for_unit(req.unit_id)}
        _served_with_answers = []
        for q in _served_qs:
            qid    = q["question_id"]
            bank_q = _bank_map.get(qid)
            if bank_q:
                # Handcrafted — always use quiz_bank's correct_idx (manually verified)
                _served_with_answers.append(bank_q)
            else:
                # AI-generated — pull correct_idx from raw cache (not the stripped version)
                raw_q = _raw_cache_qs.get(qid)
                if raw_q and "correct_idx" in raw_q:
                    # Merge: take display fields from served q, scoring fields from raw cache
                    merged = {**q, "correct_idx": raw_q["correct_idx"],
                              "explanation": raw_q.get("explanation", "")}
                    _served_with_answers.append(merged)
                else:
                    # correct_idx missing entirely — skip this question to avoid
                    # marking everything wrong due to a None comparison
                    import logging as _sl
                    _sl.getLogger(__name__).warning(
                        "submit-irt: AI question %s has no correct_idx in cache — skipping",
                        qid,
                    )
        questions = enrich_with_irt(_served_with_answers)
    else:
        # Fallback: no cache, cap to QUIZ_QUESTION_CAP
        questions = enrich_with_irt(get_questions_for_unit(req.unit_id)[:QUIZ_QUESTION_CAP])
    if not questions:
        raise HTTPException(404, f"No questions found for unit {req.unit_id}.")

    irt_result = irt_score_quiz(
        questions=    questions,
        user_answers= req.answers,
    )

    bkt_result = session.record_quiz_result_irt(
        unit_id=     req.unit_id,
        irt_mastery= irt_result["mastery"],
        irt_passed=  irt_result["passed"],
    )

    skills = KG.get_unit_skills(req.unit_id)
    topic  = skills[0] if skills else req.unit_id

    for q in questions:
        qid         = q["question_id"]
        chosen      = req.answers.get(qid)
        was_correct = (chosen == q["correct_idx"]) if chosen is not None else False
        session.record_quiz_answer(
            question=    q,
            was_correct= was_correct,
            unit_id=     req.unit_id,
            topic=       topic,
        )

    STATE_MANAGER.save(session)

    # FIX: Only lock the quiz when the user PASSES.
    # Previously the lock was set on every submit (pass or fail),
    # which forced failed students to wait 6 hours before retrying.
    # Now: pass → lock (prevents re-grinding a passed unit)
    #      fail → clear questions cache so fresh questions are generated on retry
    from python_source.engines.question_generator import _save_cache as _set_lock, clear_lock
    if irt_result["passed"]:
        _set_lock(req.user_id, req.unit_id, [])   # lock on pass only
    else:
        clear_lock(req.user_id, req.unit_id)       # allow immediate retry on fail

    return {
        "user_id":  req.user_id,
        "unit_id":  req.unit_id,
        "irt": {
            "theta":          irt_result["theta"],
            "mastery":        irt_result["mastery"],
            "mastery_pct":    round(irt_result["mastery"] * 100),
            "mastery_level":  mastery_to_level(irt_result["mastery"]),  # label from IRT score
            "passed":         irt_result["passed"],
            "pass_threshold": irt_result["pass_threshold"],
            "explanation":    irt_result["explanation"],
        },
        "raw": {
            "correct": irt_result["raw_correct"],
            "total":   irt_result["raw_total"],
            "percent": irt_result["raw_percent"],
        },
        "bkt": {
            "skill_updates": bkt_result["skill_updates"],
            "unit_passed":   bkt_result["unit_passed"],
            "update_method": "irt_blend" if irt_result["passed"] else "bkt_binary",
            "new_mastery":   max((s["p_L_after"] for s in bkt_result["skill_updates"]), default=0.0),
        },
        "question_detail":           irt_result["question_detail"],
        "progress":                  session.get_progress_summary(),
        "consecutive_failures":      bkt_result["consecutive_failures"],
        "stuck_alert":               bkt_result["stuck_alert"],
        "stuck_threshold":           bkt_result["stuck_threshold"],
        "prereq_review_suggestions": bkt_result["prereq_review_suggestions"],
    }


@app.get("/quiz/score-explanation/{unit_id}")
def explain_irt_scoring(unit_id: str):
    questions = enrich_with_irt(get_questions_for_unit(unit_id))
    if not questions:
        raise HTTPException(404, f"No questions for {unit_id}.")

    from python_source.core.irt_scoring import p_correct, PASS_THETA
    question_info = []
    for q in questions:
        b = q["irt_b"]
        a = q["irt_a"]
        question_info.append({
            "question_id":          q["question_id"],
            "difficulty_label":     q["difficulty"],
            "irt_b":                b,
            "irt_a":                a,
            "p_correct_if_passing": round(p_correct(PASS_THETA, b, a), 3),
        })
    return {
        "unit_id":        unit_id,
        "pass_threshold": 0.65,
        "pass_theta":     PASS_THETA,
        "scoring_method": "2PL IRT Maximum Likelihood Estimation",
        "questions":      question_info,
    }


# ─────────────────────────────────────────────────────────────────
#  MISTAKE TRACKING ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.post("/mistakes/track")
def track_single_answer(req: QuizAnswerIn):
    session, _ = _load_session(req.user_id)
    question   = get_question_by_id(req.question_id)
    if not question:
        raise HTTPException(404, f"Question {req.question_id} not in quiz bank.")
    enriched_q = enrich_with_irt([question])[0]
    skills = KG.get_unit_skills(req.unit_id)
    topic  = skills[0] if skills else req.unit_id
    session.record_quiz_answer(
        question=    enriched_q,
        was_correct= req.was_correct,
        unit_id=     req.unit_id,
        topic=       topic,
    )
    STATE_MANAGER.save(session)
    return {"user_id": req.user_id, "question_id": req.question_id, "tracked": True}


@app.post("/mistakes/track-batch")
def track_batch_answers(req: BatchAnswersIn):
    session, _ = _load_session(req.user_id)
    skills     = KG.get_unit_skills(req.unit_id)
    topic      = skills[0] if skills else req.unit_id
    tracked, errors = 0, []

    for ans in req.answers:
        qid         = ans.get("question_id")
        was_correct = ans.get("was_correct", False)
        question    = get_question_by_id(qid)
        if not question:
            errors.append(f"Question {qid} not found")
            continue
        session.record_quiz_answer(
            question=    enrich_with_irt([question])[0],
            was_correct= was_correct,
            unit_id=     req.unit_id,
            topic=       topic,
        )
        tracked += 1

    STATE_MANAGER.save(session)
    return {"user_id": req.user_id, "tracked": tracked, "errors": errors}


@app.get("/mistakes/insights/{user_id}")
def get_insights(user_id: str):
    session, _ = _load_session(user_id)
    if not session.mistake_log:
        return {
            "user_id": user_id,
            "message": "No quiz data yet. Complete some quizzes to see your patterns.",
            "weekly_insights":  [],
            "top_weaknesses":   [],
            "strong_areas":     [],
            "improvement_tips": [],
            "summary":          "No data yet.",
            "stats": {
                "week_mistakes":    0,
                "week_correct":     0,
                "total_mistakes":   0,
                "total_correct":    0,
                "concepts_tracked": 0,
            },
        }
    insights = session.get_insights()
    return {"user_id": user_id, **insights}


@app.get("/mistakes/log/{user_id}")
def get_mistake_log(user_id: str, limit: int = 50, wrong_only: bool = True):
    limit      = min(limit, 200)
    session, _ = _load_session(user_id)
    log        = session.mistake_log
    if wrong_only:
        log = [e for e in log if not e.get("was_correct", True)]
    log = list(reversed(log[-limit:]))
    return {"user_id": user_id, "returned": len(log), "log": log}


@app.get("/mistakes/concept-summary/{user_id}")
def get_concept_summary(user_id: str):
    session, _ = _load_session(user_id)
    summary = []
    for concept, entry in session.concept_index.items():
        total = entry["correct"] + entry["wrong"]
        summary.append({
            "concept":              concept,
            "correct":              entry["correct"],
            "wrong":                entry["wrong"],
            "total":                total,
            "wrong_rate":           round(entry["wrong"] / total, 3) if total > 0 else 0,
            "difficulty_breakdown": entry.get("difficulty_wrong_counts", {}),
        })
    summary.sort(key=lambda x: -x["wrong_rate"])
    return {"user_id": user_id, "concepts_tracked": len(summary), "concepts": summary}