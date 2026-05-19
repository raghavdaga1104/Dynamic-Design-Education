"""
quiz_bank.py
------------
Quiz questions for all 14 DDE curriculum units.

DATA SOURCE STRATEGY
────────────────────
The original quiz bank used hand-crafted MCQs (conceptual questions).
python_course_dataset.json provides real code examples that can serve
as additional "code-reading" questions.

After auditing the dataset (5000 entries, 10 units):
  - The dataset has 5 distinct real code snippets reused 167× each.
  - Concept text is templated and near-identical across entries.
  - Dataset code snippets are genuine and complement the conceptual MCQs.

Integration approach:
  1. All original hand-crafted MCQs are RETAINED — they test conceptual
     understanding which the dataset does not provide.
  2. Dataset code snippets are used to create additional "What does this
     code do?" questions for the 5 topics that have real examples:
       UNIT1  / Variables           (x = 10; y = 'Hello')
       UNIT2  / Functions           (def add(a, b): return a + b)
       UNIT2  / Recursion           (def fact(n): ...)
       UNIT7  / Stack               (stack = []; stack.append(10)...)
       UNIT7  / Queue               (from collections import deque...)
  3. The dataset is also used to tag questions with dataset entry IDs
     for traceability (field: "dataset_ids").
  4. All existing public API functions are unchanged.

ADDING NEW QUESTIONS
────────────────────
  - Hand-crafted: add a dict to QUESTIONS below following the schema.
  - Dataset-derived: add to _DATASET_QUESTIONS below. These are merged
    into QUESTIONS at module load time.
  - No changes to algorithm code are required.
"""

from typing import List, Dict, Optional

DIFFICULTY_TO_IRT = {"easy": 0.30, "medium": 0.60, "hard": 0.90}

# ─────────────────────────────────────────────────────────────────
#  HAND-CRAFTED MCQ QUESTIONS
#  Conceptual questions retained from original quiz bank.
# ─────────────────────────────────────────────────────────────────

_HANDCRAFTED_QUESTIONS: List[Dict] = [
    # ── UNIT1 — Python Basics ───────────────────────────────────────────────
    {
        "question_id": "Q_UNIT1_001", "unit_id": "UNIT1_PythonBasics",
        "text": "What is the output of: type(3.14)?",
        "options": ["<class 'int'>", "<class 'float'>", "<class 'str'>", "<class 'double'>"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "3.14 is a float literal. type() returns <class 'float'>.",
        "tags": ["data types"],
    },
    {
        "question_id": "Q_UNIT1_002", "unit_id": "UNIT1_PythonBasics",
        "text": "Which keyword defines a function in Python?",
        "options": ["function", "define", "def", "func"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "Python uses 'def' to define a function.",
        "tags": ["syntax"],
    },
    {
        "question_id": "Q_UNIT1_003", "unit_id": "UNIT1_PythonBasics",
        "text": "What prints?\n\nx = 10\nif x > 5:\n    print('A')\nelif x > 8:\n    print('B')\nelse:\n    print('C')",
        "options": ["A", "B", "C", "AB"],
        "correct_idx": 0, "difficulty": "medium",
        "explanation": "First condition (x>5) is True so 'A' prints. Python stops at first True branch.",
        "tags": ["control flow"],
    },
    {
        "question_id": "Q_UNIT1_004", "unit_id": "UNIT1_PythonBasics",
        "text": "Difference between '==' and 'is'?",
        "options": [
            "Same — both check value",
            "'==' checks value; 'is' checks identity (same object in memory)",
            "'is' checks value; '==' checks identity",
            "Both check identity",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "== compares values. is compares object identity (memory address).",
        "tags": ["operators"],
    },
    {
        "question_id": "Q_UNIT1_005", "unit_id": "UNIT1_PythonBasics",
        "text": "Time complexity of index access in a Python list?",
        "options": ["O(n)", "O(log n)", "O(1)", "O(n²)"],
        "correct_idx": 2, "difficulty": "hard",
        "explanation": "Lists are dynamic arrays. Index access is O(1) — address computed directly.",
        "tags": ["complexity"],
    },
    {
        "question_id": "Q_UNIT1_006", "unit_id": "UNIT1_PythonBasics",
        "text": "What does [x for x in range(10) if x % 2 == 0] produce?",
        "options": ["[1,3,5,7,9]", "[0,2,4,6,8]", "[0..9]", "[2,4,6,8,10]"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "range(10) gives 0-9. x%2==0 keeps evens: 0,2,4,6,8.",
        "tags": ["list comprehension"],
    },
    {
        "question_id": "Q_UNIT1_007", "unit_id": "UNIT1_PythonBasics",
        "text": "Output of: print(type([]) == type({}))?",
        "options": ["True", "False", "TypeError", "None"],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "type([]) is list; type({}) is dict. Different types so False.",
        "tags": ["data types"],
    },
    {
        "question_id": "Q_UNIT1_008", "unit_id": "UNIT1_PythonBasics",
        "text": "Which correctly swaps a and b in Python?",
        "options": ["temp=a;a=b;b=temp", "a,b=b,a", "Both A and B", "a=b;b=a"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "Both work. a,b=b,a is Pythonic. The temp method is classic.",
        "tags": ["swap"],
    },

    # ── UNIT2 — Functions & Scope ───────────────────────────────────────────
    {
        "question_id": "Q_UNIT2_001", "unit_id": "UNIT2_PythonFunctions",
        "text": "What does LEGB stand for in Python scope resolution?",
        "options": [
            "Local,External,Global,Built-in",
            "Local,Enclosing,Global,Built-in",
            "Loop,Exception,Global,Block",
            "Local,Enclosing,General,Base",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "LEGB: Local → Enclosing → Global → Built-in. Python searches in this order.",
        "tags": ["scope"],
    },
    {
        "question_id": "Q_UNIT2_002", "unit_id": "UNIT2_PythonFunctions",
        "text": "Output of this code?\n\ndef outer():\n    x = 10\n    def inner():\n        print(x)\n    inner()\n\nouter()",
        "options": ["10", "Error: x not defined", "None", "0"],
        "correct_idx": 0, "difficulty": "medium",
        "explanation": "inner() finds x in the enclosing scope (outer's local scope). This is a closure.",
        "tags": ["closures"],
    },
    {
        "question_id": "Q_UNIT2_003", "unit_id": "UNIT2_PythonFunctions",
        "text": "What does lambda x, y: x + y create?",
        "options": [
            "Named function that adds x and y",
            "Anonymous function that returns x+y",
            "Declares variables x and y",
            "Calls a function with x and y",
        ],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "lambda creates anonymous functions. lambda x,y: x+y equals def f(x,y): return x+y.",
        "tags": ["lambda"],
    },
    {
        "question_id": "Q_UNIT2_004", "unit_id": "UNIT2_PythonFunctions",
        "text": "Result of list(map(lambda x: x**2, [1,2,3,4]))?",
        "options": ["[1,4,9,16]", "[2,4,6,8]", "[1,2,3,4]", "Error"],
        "correct_idx": 0, "difficulty": "easy",
        "explanation": "map applies the lambda: 1²=1, 2²=4, 3²=9, 4²=16.",
        "tags": ["map", "lambda"],
    },
    {
        "question_id": "Q_UNIT2_005", "unit_id": "UNIT2_PythonFunctions",
        "text": "What does a Python function return without an explicit return statement?",
        "options": ["Raises SyntaxError", "Returns 0", "Returns None implicitly", "Returns empty string"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "A function that ends without return implicitly returns None.",
        "tags": ["return", "None"],
    },

    # ── UNIT3 — OOP ─────────────────────────────────────────────────────────
    {
        "question_id": "Q_UNIT3_001", "unit_id": "UNIT3_OOP",
        "text": "What is a class in Python?",
        "options": [
            "A built-in function",
            "A blueprint for creating objects with shared attributes and methods",
            "A module to import",
            "A loop structure",
        ],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "A class is a blueprint. Objects are instances of it.",
        "tags": ["classes"],
    },
    {
        "question_id": "Q_UNIT3_002", "unit_id": "UNIT3_OOP",
        "text": "What does 'self' refer to in a class method?",
        "options": ["The class itself", "The parent class", "The specific instance calling the method", "A global variable"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "self = the specific object instance calling the method.",
        "tags": ["self"],
    },
    {
        "question_id": "Q_UNIT3_003", "unit_id": "UNIT3_OOP",
        "text": "What is method overriding?",
        "options": [
            "Two methods with same name different params",
            "Child class providing its own implementation of an inherited method",
            "Importing a method",
            "Calling parent method from child",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Overriding: subclass redefines a parent method. The child's version takes precedence.",
        "tags": ["inheritance"],
    },
    {
        "question_id": "Q_UNIT3_004", "unit_id": "UNIT3_OOP",
        "text": "Which demonstrates encapsulation?",
        "options": [
            "Class inheriting another",
            "Making an attribute private with __ prefix and providing getters/setters",
            "Recursive function",
            "Importing a class",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Encapsulation hides state. __ makes attribute private in Python.",
        "tags": ["encapsulation"],
    },
    {
        "question_id": "Q_UNIT3_005", "unit_id": "UNIT3_OOP",
        "text": "What is MRO (Method Resolution Order)?",
        "options": [
            "Order Python searches for a method in the class hierarchy",
            "Order methods are defined",
            "Sequence in recursive calls",
            "Priority of built-ins over user methods",
        ],
        "correct_idx": 0, "difficulty": "hard",
        "explanation": "MRO = order to search in multiple inheritance. Python uses C3 linearisation.",
        "tags": ["MRO"],
    },
    {
        "question_id": "Q_UNIT3_006", "unit_id": "UNIT3_OOP",
        "text": "What does super().__init__() do inside a child class?",
        "options": [
            "Creates a new parent object",
            "Calls parent's constructor to initialise inherited attributes",
            "Deletes the parent",
            "Overrides all parent methods",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "super().__init__() runs the parent's constructor so inherited attributes are set up.",
        "tags": ["super"],
    },
    {
        "question_id": "Q_UNIT3_007", "unit_id": "UNIT3_OOP",
        "text": "Difference between class attribute and instance attribute?",
        "options": [
            "No difference",
            "Class attributes shared across all instances; instance attributes belong to specific objects",
            "Instance attributes are shared",
            "Class attributes hold only numbers",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Class attrs in class body, shared. Instance attrs via self in __init__, per-object.",
        "tags": ["attributes"],
    },

    # ── UNIT4 — Advanced OOP ────────────────────────────────────────────────
    {
        "question_id": "Q_UNIT4_001", "unit_id": "UNIT4_OOPAdvanced",
        "text": "What does @property do?",
        "options": [
            "Makes method static",
            "Turns method into read-only attribute accessed without parentheses",
            "Makes method private",
            "Turns class abstract",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "@property: obj.name instead of obj.name(). Controls attribute access.",
        "tags": ["property"],
    },
    {
        "question_id": "Q_UNIT4_002", "unit_id": "UNIT4_OOPAdvanced",
        "text": "What module creates abstract classes in Python?",
        "options": ["abstract", "interface", "abc", "meta"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "from abc import ABC, abstractmethod. abc = Abstract Base Classes.",
        "tags": ["abc"],
    },
    {
        "question_id": "Q_UNIT4_003", "unit_id": "UNIT4_OOPAdvanced",
        "text": "Key difference between @staticmethod and @classmethod?",
        "options": [
            "staticmethod receives cls; classmethod receives self",
            "classmethod receives cls (the class); staticmethod receives neither",
            "They are identical",
            "staticmethod for private; classmethod for public",
        ],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "@classmethod gets cls (class state access). @staticmethod is a plain function in the class.",
        "tags": ["staticmethod", "classmethod"],
    },
    {
        "question_id": "Q_UNIT4_004", "unit_id": "UNIT4_OOPAdvanced",
        "text": "Can you instantiate an abstract class directly?",
        "options": [
            "Yes always",
            "Yes if it has concrete methods",
            "No — TypeError; must subclass and implement abstract methods",
            "No — SyntaxError",
        ],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "Abstract classes can't be instantiated directly. Must subclass and implement all abstract methods.",
        "tags": ["abstract classes"],
    },
    {
        "question_id": "Q_UNIT4_005", "unit_id": "UNIT4_OOPAdvanced",
        "text": "What does a decorator fundamentally do?",
        "options": [
            "Renames a function",
            "Wraps a function to add behaviour without modifying the original",
            "Deletes function after one run",
            "Compiles to machine code",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Decorator = higher-order function that wraps another function with extra behaviour.",
        "tags": ["decorators"],
    },

    # ── UNIT5 — Arrays ──────────────────────────────────────────────────────
    {
        "question_id": "Q_UNIT5_001", "unit_id": "UNIT5_Arrays",
        "text": "Time complexity of inserting at the beginning of a Python list?",
        "options": ["O(1)", "O(log n)", "O(n)", "O(n²)"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "Insert at 0 shifts all n elements right. O(n).",
        "tags": ["complexity"],
    },
    {
        "question_id": "Q_UNIT5_002", "unit_id": "UNIT5_Arrays",
        "text": "What does lst[-1] return?",
        "options": ["First element", "IndexError", "Last element", "Empty list"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "Negative indexing: -1 = last element, -2 = second to last.",
        "tags": ["indexing"],
    },
    {
        "question_id": "Q_UNIT5_003", "unit_id": "UNIT5_Arrays",
        "text": "What does lst[1:4] return for [10,20,30,40,50]?",
        "options": ["[10,20,30]", "[20,30,40]", "[20,30,40,50]", "[10,20,30,40]"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "Slicing: start-inclusive, end-exclusive. Indices 1,2,3 = [20,30,40].",
        "tags": ["slicing"],
    },
    {
        "question_id": "Q_UNIT5_004", "unit_id": "UNIT5_Arrays",
        "text": "Which removes and returns the last element of a list?",
        "options": ["remove()", "delete()", "pop()", "discard()"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "pop() removes and returns last element in O(1). pop(i) removes at index i in O(n).",
        "tags": ["list methods"],
    },
    {
        "question_id": "Q_UNIT5_005", "unit_id": "UNIT5_Arrays",
        "text": "Time complexity of Python's list.sort()?",
        "options": ["O(n)", "O(n log n)", "O(n²)", "O(log n)"],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Python uses Timsort: O(n log n) average/worst, O(n) for already-sorted.",
        "tags": ["sorting"],
    },
    {
        "question_id": "Q_UNIT5_006", "unit_id": "UNIT5_Arrays",
        "text": "Difference between list.append() and list.extend()?",
        "options": [
            "No difference",
            "append() adds single element; extend() adds all elements from an iterable",
            "extend() adds single element; append() adds all",
            "append() creates new list; extend() modifies in place",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "append([1,2]) adds list as one element. extend([1,2]) adds 1 and 2 separately.",
        "tags": ["list methods"],
    },

    # ── UNIT6 — Linked Lists ────────────────────────────────────────────────
    {
        "question_id": "Q_UNIT6_001", "unit_id": "UNIT6_LinkedLists",
        "text": "Time complexity of accessing nth element in a singly linked list?",
        "options": ["O(1)", "O(log n)", "O(n)", "O(n²)"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "Must traverse from head to reach any node. No random access. O(n).",
        "tags": ["complexity"],
    },
    {
        "question_id": "Q_UNIT6_002", "unit_id": "UNIT6_LinkedLists",
        "text": "Main advantage of linked list over array for insertions?",
        "options": [
            "Supports random access",
            "Inserting at a known node is O(1) — no element shifting",
            "Uses less memory",
            "Faster to search",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "With pointer to node, insertion is O(1) — just relink. Arrays need O(n) shifting.",
        "tags": ["insertion"],
    },
    {
        "question_id": "Q_UNIT6_003", "unit_id": "UNIT6_LinkedLists",
        "text": "How does Floyd's cycle detection work?",
        "options": [
            "Hash set to track visited nodes",
            "Two pointers — fast (2 steps) and slow (1 step); if they meet, a cycle exists",
            "Reverse and compare",
            "Count nodes and check for repeats",
        ],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "Fast/slow pointers. If cycle exists, fast laps slow and they meet.",
        "tags": ["Floyd", "cycle"],
    },
    {
        "question_id": "Q_UNIT6_004", "unit_id": "UNIT6_LinkedLists",
        "text": "Extra pointer in a doubly linked list vs singly?",
        "options": ["Pointer to tail", "Pointer to previous node", "Pointer to head", "Pointer to random node"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "Doubly linked: data + next + prev. Enables backward traversal.",
        "tags": ["doubly linked"],
    },
    {
        "question_id": "Q_UNIT6_005", "unit_id": "UNIT6_LinkedLists",
        "text": "Time complexity of deleting a node when you already have a pointer to it (doubly linked)?",
        "options": ["O(1)", "O(log n)", "O(n)", "O(n²)"],
        "correct_idx": 0, "difficulty": "hard",
        "explanation": "With prev pointer available, deletion = just relink pointers = O(1).",
        "tags": ["deletion"],
    },

    # ── UNIT7 — Stacks & Queues ─────────────────────────────────────────────
    {
        "question_id": "Q_UNIT7_001", "unit_id": "UNIT7_StacksQueues",
        "text": "Which follows LIFO?",
        "options": ["Queue", "Stack", "Linked List", "Heap"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "Stack = Last-In-First-Out. Like a stack of plates.",
        "tags": ["stack", "LIFO"],
    },
    {
        "question_id": "Q_UNIT7_002", "unit_id": "UNIT7_StacksQueues",
        "text": "Which models a Queue?",
        "options": ["Browser back button", "Function call stack", "People waiting in line", "Undo in text editor"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "Queue = FIFO. First person to arrive is first served.",
        "tags": ["queue", "FIFO"],
    },
    {
        "question_id": "Q_UNIT7_003", "unit_id": "UNIT7_StacksQueues",
        "text": "Time complexity of push() and pop() on a stack?",
        "options": ["O(n) both", "O(log n) both", "O(1) both", "O(1) push O(n) pop"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "Both operate on top only — no traversal. Both O(1).",
        "tags": ["complexity"],
    },
    {
        "question_id": "Q_UNIT7_004", "unit_id": "UNIT7_StacksQueues",
        "text": "Implement Queue using two Stacks?",
        "options": [
            "Not possible",
            "Push to stack1; dequeue: if stack2 empty transfer from stack1 to stack2 then pop stack2",
            "Always same stack",
            "Alternate enqueue/dequeue stacks",
        ],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "Transferring stack1 to stack2 reverses order giving FIFO. Amortised O(1).",
        "tags": ["interview"],
    },
    {
        "question_id": "Q_UNIT7_005", "unit_id": "UNIT7_StacksQueues",
        "text": "Why use collections.deque instead of list for a queue?",
        "options": [
            "deque is slower but memory efficient",
            "deque gives O(1) popleft(); list.pop(0) is O(n)",
            "They are equal",
            "deque supports negative indexing",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "deque.popleft() is O(1). list.pop(0) shifts all elements = O(n).",
        "tags": ["deque"],
    },
    {
        "question_id": "Q_UNIT7_006", "unit_id": "UNIT7_StacksQueues",
        "text": "Which traversal uses a queue?",
        "options": ["DFS", "Inorder traversal", "BFS", "Postorder"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "BFS uses a queue to process nodes level by level.",
        "tags": ["BFS"],
    },

    # ── UNIT8 — Trees ───────────────────────────────────────────────────────
    {
        "question_id": "Q_UNIT8_001", "unit_id": "UNIT8_Trees",
        "text": "Inorder traversal of a BST visits nodes in what order?",
        "options": ["Random", "Descending", "Ascending (sorted)", "Level by level"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "Inorder (left,root,right) on BST = ascending order. Key BST property.",
        "tags": ["inorder", "BST"],
    },
    {
        "question_id": "Q_UNIT8_002", "unit_id": "UNIT8_Trees",
        "text": "Time complexity of search in a balanced BST?",
        "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Each comparison halves the remaining tree. O(log n) balanced, O(n) skewed.",
        "tags": ["BST", "complexity"],
    },
    {
        "question_id": "Q_UNIT8_003", "unit_id": "UNIT8_Trees",
        "text": "Which traversal visits root BEFORE left and right?",
        "options": ["Inorder", "Postorder", "Preorder", "Level-order"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "Preorder = root, left, right. Used to copy or serialise a tree.",
        "tags": ["preorder"],
    },
    {
        "question_id": "Q_UNIT8_004", "unit_id": "UNIT8_Trees",
        "text": "How does BST insertion work?",
        "options": [
            "Always leftmost",
            "Always becomes root",
            "Go left if smaller, right if larger, insert at null position",
            "Appended to end",
        ],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "BST property: traverse left if smaller, right if larger. Insert where you'd find null.",
        "tags": ["BST insert"],
    },
    {
        "question_id": "Q_UNIT8_005", "unit_id": "UNIT8_Trees",
        "text": "Height of complete binary tree with n nodes?",
        "options": ["O(n)", "O(n²)", "O(log n)", "O(1)"],
        "correct_idx": 2, "difficulty": "hard",
        "explanation": "Complete tree fills levels left to right. height = floor(log₂(n)). O(log n).",
        "tags": ["height"],
    },
    {
        "question_id": "Q_UNIT8_006", "unit_id": "UNIT8_Trees",
        "text": "Data structure for level-order tree traversal?",
        "options": ["Stack", "Array", "Queue", "Set"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "Level-order uses queue. Enqueue root, dequeue, enqueue children, repeat.",
        "tags": ["BFS", "level-order"],
    },

    # ── UNIT9 — Hash Tables ─────────────────────────────────────────────────
    {
        "question_id": "Q_UNIT9_001", "unit_id": "UNIT9_HashTables",
        "text": "Average time for search/insert/delete in a hash table?",
        "options": ["O(n)", "O(log n)", "O(1)", "O(n log n)"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "Hash tables give O(1) average via direct addressing using hash function.",
        "tags": ["complexity"],
    },
    {
        "question_id": "Q_UNIT9_002", "unit_id": "UNIT9_HashTables",
        "text": "What is a collision?",
        "options": [
            "Two identical keys",
            "Two different keys hash to the same index",
            "Table becomes full",
            "A key is deleted",
        ],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "Collision = two different keys map to same bucket. Resolved by chaining or open addressing.",
        "tags": ["collision"],
    },
    {
        "question_id": "Q_UNIT9_003", "unit_id": "UNIT9_HashTables",
        "text": "Which Python type implements a hash table?",
        "options": ["list", "tuple", "dict", "set but not dict"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "dict is a hash table. set is also hash-based. list is a dynamic array.",
        "tags": ["Python dict"],
    },
    {
        "question_id": "Q_UNIT9_004", "unit_id": "UNIT9_HashTables",
        "text": "Why can't you use a list as a dict key?",
        "options": [
            "Lists are too large",
            "Python reserves lists for values",
            "Lists are mutable (unhashable) — their hash would change",
            "No other reason",
        ],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "Keys must be hashable (immutable). Mutable objects' hash could change breaking the dict.",
        "tags": ["hashable"],
    },
    {
        "question_id": "Q_UNIT9_005", "unit_id": "UNIT9_HashTables",
        "text": "What is the load factor and why does it matter?",
        "options": [
            "Number of buckets",
            "elements/capacity — exceeding ~0.7 triggers rehash to maintain O(1)",
            "Hash function complexity",
            "Number of collisions",
        ],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "High load factor = more collisions = worse performance. Rehashing keeps it low.",
        "tags": ["load factor"],
    },

    # ── UNIT10 — Sorting ────────────────────────────────────────────────────
    {
        "question_id": "Q_UNIT10_001", "unit_id": "UNIT10_Sorting",
        "text": "Average-case time complexity of QuickSort?",
        "options": ["O(n)", "O(n log n)", "O(n²)", "O(log n)"],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Partitioning O(n), recursion depth O(log n), total O(n log n) average.",
        "tags": ["quicksort"],
    },
    {
        "question_id": "Q_UNIT10_002", "unit_id": "UNIT10_Sorting",
        "text": "Which sorting algorithm is stable AND guarantees O(n log n) worst case?",
        "options": ["QuickSort", "HeapSort", "MergeSort", "SelectionSort"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "MergeSort: stable, always O(n log n). QuickSort: O(n²) worst. HeapSort: not stable.",
        "tags": ["mergesort"],
    },
    {
        "question_id": "Q_UNIT10_003", "unit_id": "UNIT10_Sorting",
        "text": "When is Insertion Sort preferred over MergeSort?",
        "options": ["Always", "n > 10000", "Small or nearly sorted arrays", "When memory is tight"],
        "correct_idx": 2, "difficulty": "hard",
        "explanation": "For small or nearly-sorted data, insertion sort's low overhead beats merge sort in practice.",
        "tags": ["insertion sort"],
    },
    {
        "question_id": "Q_UNIT10_004", "unit_id": "UNIT10_Sorting",
        "text": "Worst case of QuickSort and its cause?",
        "options": [
            "O(n log n) always",
            "O(n²) — pivot always smallest or largest causing unbalanced partitions",
            "O(n²) — all elements equal",
            "O(n³) for reverse sorted",
        ],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "QuickSort degrades to O(n²) with consistently bad pivot (e.g., sorted array + first-element pivot).",
        "tags": ["quicksort", "worst case"],
    },
    {
        "question_id": "Q_UNIT10_005", "unit_id": "UNIT10_Sorting",
        "text": "What does 'stable' mean for sorting?",
        "options": [
            "Always O(n log n)",
            "Uses O(1) space",
            "Equal elements maintain original relative order",
            "Works on all input types",
        ],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "Stable: equal elements appear in same relative order in input and output.",
        "tags": ["stable sort"],
    },
    {
        "question_id": "Q_UNIT10_006", "unit_id": "UNIT10_Sorting",
        "text": "What sort does Python's built-in sort() use?",
        "options": ["QuickSort", "MergeSort", "Timsort", "HeapSort"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "Python uses Timsort — hybrid of Merge+Insertion. Stable, O(n log n), adaptive.",
        "tags": ["Timsort"],
    },

    # ── UNIT11 — Searching ──────────────────────────────────────────────────
    {
        "question_id": "Q_UNIT11_001", "unit_id": "UNIT11_Searching",
        "text": "Prerequisite for binary search?",
        "options": ["Only integers", "Array must be sorted", "Odd number of elements", "No duplicates"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "Binary search requires sorted array to eliminate half the space each step.",
        "tags": ["binary search"],
    },
    {
        "question_id": "Q_UNIT11_002", "unit_id": "UNIT11_Searching",
        "text": "Time complexity of binary search?",
        "options": ["O(n)", "O(log n)", "O(n log n)", "O(1)"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "Each step halves search space. After log₂(n) steps, 1 element remains. O(log n).",
        "tags": ["complexity"],
    },
    {
        "question_id": "Q_UNIT11_003", "unit_id": "UNIT11_Searching",
        "text": "Why is mid = left+(right-left)//2 safer than (left+right)//2?",
        "options": [
            "Different result",
            "Avoids integer overflow for large indices (Java/C++)",
            "Faster",
            "Handles negatives",
        ],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "In C++/Java, left+right can overflow int. Python has unlimited ints but good practice.",
        "tags": ["overflow"],
    },
    {
        "question_id": "Q_UNIT11_004", "unit_id": "UNIT11_Searching",
        "text": "Which Python module has built-in binary search?",
        "options": ["search", "heapq", "bisect", "itertools"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "bisect: bisect_left(), bisect_right() do binary search. insort() inserts maintaining sort.",
        "tags": ["bisect"],
    },
    {
        "question_id": "Q_UNIT11_005", "unit_id": "UNIT11_Searching",
        "text": "Sorted array, frequent searches — which is best?",
        "options": [
            "Linear O(n)",
            "Binary O(log n)",
            "Build hash table O(1) per query",
            "Sort then linear",
        ],
        "correct_idx": 2, "difficulty": "hard",
        "explanation": "Build hash table once O(n), then O(1) per query. Beats binary O(log n) for repeated lookups.",
        "tags": ["strategy"],
    },

    # ── UNIT12 — Recursion ──────────────────────────────────────────────────
    {
        "question_id": "Q_UNIT12_001", "unit_id": "UNIT12_Recursion",
        "text": "Two essential components of recursion?",
        "options": [
            "Loop and counter",
            "Base case and recursive case",
            "Return and parameter",
            "If and while",
        ],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "Base case stops recursion. Recursive case reduces problem and calls itself.",
        "tags": ["recursion"],
    },
    {
        "question_id": "Q_UNIT12_002", "unit_id": "UNIT12_Recursion",
        "text": "What if a recursive function has no base case?",
        "options": ["Returns None", "SyntaxError", "Infinite recursion → RecursionError", "Runs once and stops"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "Without base case: infinite recursion until Python's recursion limit is hit.",
        "tags": ["base case"],
    },
    {
        "question_id": "Q_UNIT12_003", "unit_id": "UNIT12_Recursion",
        "text": "Space complexity of recursive factorial(n)?",
        "options": ["O(1)", "O(n)", "O(n²)", "O(log n)"],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "Each call adds stack frame. n+1 frames simultaneously. O(n) space.",
        "tags": ["space complexity", "call stack"],
    },
    {
        "question_id": "Q_UNIT12_004", "unit_id": "UNIT12_Recursion",
        "text": "Key step distinguishing backtracking from regular recursion?",
        "options": [
            "Uses a queue",
            "Undoes last choice before trying next option",
            "Always finds optimal solution",
            "Avoids repeating subproblems",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Backtracking: try choice, recurse, UNDO choice before next option. The undo is the key.",
        "tags": ["backtracking"],
    },
    {
        "question_id": "Q_UNIT12_005", "unit_id": "UNIT12_Recursion",
        "text": "Why is naive recursive Fibonacci O(2^n)?",
        "options": [
            "Fibonacci numbers grow exponentially",
            "Recomputes same subproblems repeatedly",
            "Python function calls are slow",
            "Recursion depth is n",
        ],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "fib(n) calls fib(n-1) and fib(n-2), each branching again. Exponential overlap.",
        "tags": ["fibonacci"],
    },
    {
        "question_id": "Q_UNIT12_006", "unit_id": "UNIT12_Recursion",
        "text": "What reduces recursive Fibonacci from O(2^n) to O(n)?",
        "options": ["Backtracking", "Memoisation (caching results)", "Sorting inputs", "While loop"],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Memoisation stores computed fib(k). Return cached result instead of recomputing.",
        "tags": ["memoisation"],
    },

    # ── UNIT13 — Dynamic Programming ────────────────────────────────────────
    {
        "question_id": "Q_UNIT13_001", "unit_id": "UNIT13_DynamicProgramming",
        "text": "Two key properties for DP?",
        "options": [
            "Sorted input and unique elements",
            "Overlapping subproblems and optimal substructure",
            "Greedy choice and monotonicity",
            "Polynomial time and linear space",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Overlapping subproblems: same subproblem recomputed. Optimal substructure: optimal built from optimal sub-solutions.",
        "tags": ["DP properties"],
    },
    {
        "question_id": "Q_UNIT13_002", "unit_id": "UNIT13_DynamicProgramming",
        "text": "Difference between memoisation and tabulation?",
        "options": [
            "Memo is bottom-up; tab is top-down",
            "Memoisation is top-down with cache; tabulation is bottom-up iterative",
            "They are identical",
            "Memo uses arrays; tab uses dicts",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Memoisation: add cache to recursion. Tabulation: fill table from smallest subproblems up.",
        "tags": ["memoisation", "tabulation"],
    },
    {
        "question_id": "Q_UNIT13_003", "unit_id": "UNIT13_DynamicProgramming",
        "text": "Time complexity of DP coin change (amount n, k coin types)?",
        "options": ["O(n)", "O(k)", "O(n*k)", "O(2^n)"],
        "correct_idx": 2, "difficulty": "hard",
        "explanation": "For each of n amounts, try k coins. dp[i] = min(dp[i-coin]+1). Total O(n*k).",
        "tags": ["coin change"],
    },
    {
        "question_id": "Q_UNIT13_004", "unit_id": "UNIT13_DynamicProgramming",
        "text": "How to identify a DP problem?",
        "options": [
            "Involves sorting",
            "Asks for optimal value AND brute force has repeated subproblems",
            "Has graph structure",
            "Input is always an array",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Start with recursion. Draw the tree. Repeated calls = signal to apply DP.",
        "tags": ["identification"],
    },
    {
        "question_id": "Q_UNIT13_005", "unit_id": "UNIT13_DynamicProgramming",
        "text": "In 0/1 Knapsack, what does dp[i][w] represent?",
        "options": [
            "Weight of item i",
            "Max value using first i items with capacity exactly w",
            "Max value using first i items with capacity at most w",
            "Whether item i fits in weight w",
        ],
        "correct_idx": 2, "difficulty": "hard",
        "explanation": "dp[i][w] = max value using items 1..i with total weight ≤ w. Include or exclude item i.",
        "tags": ["knapsack"],
    },

    # ── UNIT14 — Graph Algorithms ───────────────────────────────────────────
    {
        "question_id": "Q_UNIT14_001", "unit_id": "UNIT14_GraphAlgorithms",
        "text": "Data structure BFS uses?",
        "options": ["Stack", "Queue", "Heap", "Array"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "BFS uses queue (FIFO). Enqueue start, dequeue, process, enqueue unvisited neighbours.",
        "tags": ["BFS"],
    },
    {
        "question_id": "Q_UNIT14_002", "unit_id": "UNIT14_GraphAlgorithms",
        "text": "Time complexity of BFS and DFS on graph with V vertices E edges?",
        "options": ["O(V)", "O(E)", "O(V+E)", "O(V*E)"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "Visit each vertex once O(V) and each edge once O(E). Total O(V+E).",
        "tags": ["complexity"],
    },
    {
        "question_id": "Q_UNIT14_003", "unit_id": "UNIT14_GraphAlgorithms",
        "text": "Which finds shortest path in an unweighted graph?",
        "options": ["Dijkstra", "Bellman-Ford", "DFS", "BFS"],
        "correct_idx": 3, "difficulty": "medium",
        "explanation": "BFS explores level by level. First time it reaches a node = shortest path (fewest edges).",
        "tags": ["shortest path"],
    },
    {
        "question_id": "Q_UNIT14_004", "unit_id": "UNIT14_GraphAlgorithms",
        "text": "What is topological sort?",
        "options": [
            "Sort vertices by degree",
            "Linear ordering of DAG where every edge u→v has u before v — for dependency resolution",
            "Sort edges by weight",
            "Sort by DFS visit time",
        ],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "Topological sort orders nodes of a DAG so all edges point forward. Used for dependencies.",
        "tags": ["topological sort"],
    },
    {
        "question_id": "Q_UNIT14_005", "unit_id": "UNIT14_GraphAlgorithms",
        "text": "Why can't Dijkstra handle negative edge weights?",
        "options": [
            "It can",
            "Greedy assumption breaks: negative edge can invalidate an already-settled node's distance",
            "Negative weights overflow",
            "Priority queue doesn't support negatives",
        ],
        "correct_idx": 1, "difficulty": "hard",
        "explanation": "Dijkstra greedily finalises closest node. A later negative edge could shorten an already-finalised path.",
        "tags": ["Dijkstra"],
    },
]


# ─────────────────────────────────────────────────────────────────
#  DATASET-DERIVED CODE-READING QUESTIONS
#  One question per real code example extracted from the dataset.
#  Uses "What does this code do?" format to test code comprehension.
#
#  dataset_ids field links to the source entry IDs for traceability.
# ─────────────────────────────────────────────────────────────────

_DATASET_QUESTIONS: List[Dict] = [

    # ── UNIT1 — Variables (dataset code: x = 10; y = 'Hello') ──────────────
    {
        "question_id": "Q_UNIT1_DS_001", "unit_id": "UNIT1_PythonBasics",
        "text": "What are the data types of x and y after running:\n\nx = 10\ny = 'Hello'",
        "options": [
            "x is str, y is int",
            "x is int, y is str",
            "Both are str",
            "Both are int",
        ],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": (
            "10 is an integer literal → x is int. "
            "'Hello' is a string literal → y is str. "
            "Python infers types dynamically at assignment."
        ),
        "tags": ["variables", "data types", "code reading"],
        "dataset_ids": ["py_1"],
        "source": "python_course_dataset.json",
    },
    {
        "question_id": "Q_UNIT1_DS_002", "unit_id": "UNIT1_PythonBasics",
        "text": "After executing:\n\nx = 10\ny = 'Hello'\n\nWhat does print(type(x)) output?",
        "options": [
            "<class 'str'>",
            "<class 'float'>",
            "<class 'int'>",
            "10",
        ],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "x = 10 assigns an integer. type(x) returns the class object <class 'int'>.",
        "tags": ["variables", "type()", "code reading"],
        "dataset_ids": ["py_1"],
        "source": "python_course_dataset.json",
    },

    # ── UNIT2 — Functions (dataset code: def add(a, b): return a + b) ───────
    {
        "question_id": "Q_UNIT2_DS_001", "unit_id": "UNIT2_PythonFunctions",
        "text": "What does this function return when called as add(3, 4)?\n\ndef add(a, b):\n    return a + b",
        "options": ["'34'", "7", "None", "TypeError"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "add(3, 4) evaluates a + b = 3 + 4 = 7. The + operator on ints returns their sum.",
        "tags": ["functions", "return", "code reading"],
        "dataset_ids": ["py_6"],
        "source": "python_course_dataset.json",
    },
    {
        "question_id": "Q_UNIT2_DS_002", "unit_id": "UNIT2_PythonFunctions",
        "text": "What happens when add('Hello', ' World') is called?\n\ndef add(a, b):\n    return a + b",
        "options": [
            "TypeError — can't add strings",
            "'Hello World' — + concatenates strings",
            "None",
            "SyntaxError",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "Python's + operator is polymorphic. On strings it concatenates, returning 'Hello World'.",
        "tags": ["functions", "polymorphism", "string concat", "code reading"],
        "dataset_ids": ["py_6"],
        "source": "python_course_dataset.json",
    },

    # ── UNIT2 — Recursion (dataset code: def fact(n): ...) ──────────────────
    {
        "question_id": "Q_UNIT2_DS_003", "unit_id": "UNIT2_PythonFunctions",
        "text": "What is the output of fact(5)?\n\ndef fact(n): return 1 if n==0 else n*fact(n-1)",
        "options": ["5", "15", "120", "RecursionError"],
        "correct_idx": 2, "difficulty": "medium",
        "explanation": "fact(5) = 5×4×3×2×1 = 120. The base case returns 1 when n==0.",
        "tags": ["recursion", "factorial", "code reading"],
        "dataset_ids": ["py_8"],
        "source": "python_course_dataset.json",
    },
    {
        "question_id": "Q_UNIT2_DS_004", "unit_id": "UNIT2_PythonFunctions",
        "text": "What is the base case in this factorial function?\n\ndef fact(n): return 1 if n==0 else n*fact(n-1)",
        "options": [
            "n == 1",
            "n == 0, which returns 1",
            "n*fact(n-1)",
            "There is no base case",
        ],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "The condition n==0 is the base case. It returns 1 and stops the recursion.",
        "tags": ["recursion", "base case", "code reading"],
        "dataset_ids": ["py_8"],
        "source": "python_course_dataset.json",
    },

    # ── UNIT7 — Stack (dataset code: stack=[]; stack.append(10); stack.pop()) ─
    {
        "question_id": "Q_UNIT7_DS_001", "unit_id": "UNIT7_StacksQueues",
        "text": "What is the state of 'stack' after this code?\n\nstack = []\nstack.append(10)\nstack.pop()",
        "options": [
            "[10]",
            "[]  — the appended 10 was popped off",
            "[10, 10]",
            "None",
        ],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "append(10) adds 10; pop() removes and returns the last element (10). Stack is empty again.",
        "tags": ["stack", "append", "pop", "code reading"],
        "dataset_ids": ["py_18"],
        "source": "python_course_dataset.json",
    },
    {
        "question_id": "Q_UNIT7_DS_002", "unit_id": "UNIT7_StacksQueues",
        "text": "What value does stack.pop() return in this code?\n\nstack = []\nstack.append(10)\nstack.pop()",
        "options": ["None", "0", "10", "[]"],
        "correct_idx": 2, "difficulty": "easy",
        "explanation": "pop() removes AND returns the last element. stack.append(10) placed 10 on top, so pop() returns 10.",
        "tags": ["stack", "pop", "return value", "code reading"],
        "dataset_ids": ["py_18"],
        "source": "python_course_dataset.json",
    },

    # ── UNIT7 — Queue (dataset code: deque, popleft) ────────────────────────
    {
        "question_id": "Q_UNIT7_DS_003", "unit_id": "UNIT7_StacksQueues",
        "text": "What does popleft() return in this code?\n\nfrom collections import deque\nq = deque([1, 2])\nq.popleft()",
        "options": ["2", "1", "deque([1, 2])", "None"],
        "correct_idx": 1, "difficulty": "easy",
        "explanation": "deque([1, 2]) has 1 at the front. popleft() removes and returns the leftmost element: 1.",
        "tags": ["queue", "deque", "popleft", "code reading"],
        "dataset_ids": ["py_19"],
        "source": "python_course_dataset.json",
    },
    {
        "question_id": "Q_UNIT7_DS_004", "unit_id": "UNIT7_StacksQueues",
        "text": "After popleft() completes, what is the state of q?\n\nfrom collections import deque\nq = deque([1, 2])\nq.popleft()",
        "options": [
            "deque([1, 2])  — unchanged",
            "deque([2])     — 1 was removed from front",
            "deque([1])     — 2 was removed from back",
            "deque([])",
        ],
        "correct_idx": 1, "difficulty": "medium",
        "explanation": "popleft() removes the first element (1) from the front. q becomes deque([2]).",
        "tags": ["queue", "deque", "state", "code reading"],
        "dataset_ids": ["py_19"],
        "source": "python_course_dataset.json",
    },
]


# ─────────────────────────────────────────────────────────────────
#  MERGE: combine hand-crafted + dataset questions
#  De-duplicate by question_id (hand-crafted takes precedence).
# ─────────────────────────────────────────────────────────────────

def _merge_questions() -> List[Dict]:
    by_id: Dict[str, Dict] = {q["question_id"]: q for q in _HANDCRAFTED_QUESTIONS}
    for q in _DATASET_QUESTIONS:
        if q["question_id"] not in by_id:
            by_id[q["question_id"]] = q
    return list(by_id.values())


QUESTIONS: List[Dict] = _merge_questions()

# ─────────────────────────────────────────────────────────────────
#  O(1) LOOKUP  (built once at module load)
# ─────────────────────────────────────────────────────────────────

_QUESTION_MAP: Dict[str, Dict] = {q["question_id"]: q for q in QUESTIONS}


# ─────────────────────────────────────────────────────────────────
#  PUBLIC API  (unchanged — all callers remain compatible)
# ─────────────────────────────────────────────────────────────────

def get_questions_for_unit(unit_id: str) -> List[Dict]:
    return [q for q in QUESTIONS if q["unit_id"] == unit_id]


def get_question_by_id(question_id: str) -> Optional[Dict]:
    return _QUESTION_MAP.get(question_id)


def get_questions_by_difficulty(unit_id: str, difficulty: str) -> List[Dict]:
    return [
        q for q in QUESTIONS
        if q["unit_id"] == unit_id and q["difficulty"] == difficulty
    ]


def get_question_irt_difficulty(question: Dict) -> float:
    return DIFFICULTY_TO_IRT.get(question.get("difficulty", "medium"), 0.60)


_IRT_PARAM_MAP = {
    "easy":   {"irt_b": 0.30, "irt_a": 1.20},
    "medium": {"irt_b": 0.60, "irt_a": 1.00},
    "hard":   {"irt_b": 0.90, "irt_a": 0.80},
}


def get_irt_params(question: Dict) -> Dict:
    if "irt_b" in question and "irt_a" in question:
        return {"irt_b": float(question["irt_b"]), "irt_a": float(question["irt_a"])}
    difficulty = question.get("difficulty", "medium")
    return _IRT_PARAM_MAP.get(difficulty, _IRT_PARAM_MAP["medium"])


def enrich_with_irt(questions: List[Dict]) -> List[Dict]:
    enriched = []
    for q in questions:
        params = get_irt_params(q)
        enriched.append({
            **q,
            "irt_difficulty": get_question_irt_difficulty(q),
            "irt_b":          params["irt_b"],
            "irt_a":          params["irt_a"],
        })
    return enriched


def get_dataset_questions(unit_id: Optional[str] = None) -> List[Dict]:
    """
    Return only questions derived from python_course_dataset.json.
    Useful for reporting what real-data coverage looks like.
    """
    ds_qs = [q for q in QUESTIONS if q.get("source") == "python_course_dataset.json"]
    if unit_id:
        ds_qs = [q for q in ds_qs if q["unit_id"] == unit_id]
    return ds_qs
