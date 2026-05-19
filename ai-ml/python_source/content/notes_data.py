"""
notes_data.py
-------------
Micro-notes for all 14 DDE curriculum units.

DATA SOURCE
───────────
Notes for 10 units are derived directly from python_course_dataset.json
via dataset_loader.py. The remaining 4 units (UNIT4, UNIT6, UNIT9,
UNIT14) are not in the dataset and retain curated hand-written notes.

HOW ALL_NOTES IS BUILT
──────────────────────
1. For each unit that IS in the dataset:
     - One consolidated note per topic is created from the dataset entries,
       grouping concept + code examples into a single searchable document.
     - This gives the RAG engine real, topic-specific content instead of
       the old synthetic "[DRAFT]" placeholders.
2. For units NOT in the dataset:
     - Hand-written notes are used unchanged.
3. The combined list is exported as ALL_NOTES with the same schema the
   RAG engine (rag_engine.py) expects:
       {"id": str, "unit_id": str, "topic": str, "content": str}

HOW THIS FILE IS USED
─────────────────────
The RAG engine imports ALL_NOTES and indexes them into ChromaDB on first
startup. To force a re-index after changes, delete the chroma_db folder:
  rm -rf data/chroma_db
Then restart the server.
"""

from typing import List, Dict

try:
    from python_source.core.dataset_loader import get_dataset
except ImportError:
    try:
        from dataset_loader import get_dataset
    except ImportError:
        get_dataset = None  # type: ignore

# ─────────────────────────────────────────────────────────────────
#  DATASET-DERIVED NOTES BUILDER
# ─────────────────────────────────────────────────────────────────

def _build_note_content(unit_id: str, topic: str, entries: List[Dict]) -> str:
    """
    Combine dataset entries for one (unit, topic) into a single rich
    note document suitable for RAG retrieval.

    Format:
      Topic: <topic>
      ---
      <concept text from entry 1>
      Code Example:
        <code>
      ---
      <concept text from entry 2>  (if different / adds value)
      Code Example:
        <code>
      ...
    """
    lines = [f"Topic: {topic}", ""]

    seen_concepts: set = set()
    seen_codes:    set = set()

    for entry in entries:
        concept     = (entry.get("concept") or "").strip()
        code        = (entry.get("code") or "").strip()
        explanation = (entry.get("explanation") or "").strip()

        # De-duplicate near-identical concept blocks (the dataset
        # has many entries per topic with the same templated concept text)
        concept_key = concept[:80]
        if concept and concept_key not in seen_concepts:
            seen_concepts.add(concept_key)
            lines.append(concept)
            lines.append("")

        # Include code only if it is a real example
        code_key = code[:80]
        if code and code_key not in seen_codes and _has_real_code_str(code):
            seen_codes.add(code_key)
            lines.append("Code Example:")
            for code_line in code.split("\n"):
                lines.append("  " + code_line)
            lines.append("")

        # Include explanation when it adds context beyond the generic phrase
        if (
            explanation
            and "This example demonstrates how" not in explanation
            and explanation not in seen_concepts
        ):
            lines.append(explanation)
            lines.append("")

    return "\n".join(lines).strip()


def _has_real_code_str(code: str) -> bool:
    """Return True for non-trivial code (not just a placeholder print)."""
    if not code:
        return False
    lines = [l.strip() for l in code.strip().split("\n") if l.strip()]
    # Reject: only a comment + a print statement
    if len(lines) <= 2 and all(
        l.startswith("# Example of") or l.startswith("print(") for l in lines
    ):
        return False
    return True


def _notes_from_dataset() -> List[Dict]:
    """Build one note per (unit, topic) from the real dataset."""
    if get_dataset is None:
        return []

    try:
        ds = get_dataset()
    except FileNotFoundError:
        return []

    notes = []
    for unit_id in ds.units_in_dataset():
        for idx, topic in enumerate(ds.topics_for_unit(unit_id), start=1):
            entries = ds.entries_for_topic(unit_id, topic)
            if not entries:
                continue

            content = _build_note_content(unit_id, topic, entries)
            note_id = f"note_{unit_id}_{idx:03d}"

            notes.append({
                "id":      note_id,
                "unit_id": unit_id,
                "topic":   topic,
                "content": content,
            })

    return notes


# ─────────────────────────────────────────────────────────────────
#  HAND-WRITTEN NOTES
#  For the 4 units not covered by python_course_dataset.json:
#  UNIT4_OOPAdvanced, UNIT6_LinkedLists, UNIT9_HashTables,
#  UNIT14_GraphAlgorithms
#
#  Also retains curated notes for dataset units to supplement RAG
#  coverage on topics the dataset handles lightly.
# ─────────────────────────────────────────────────────────────────

_HANDWRITTEN_NOTES: List[Dict] = [

    # ═══════════════════════════════════════════════════════
    #  UNIT4: Advanced OOP  (not in dataset)
    # ═══════════════════════════════════════════════════════
    {
        "id":      "note_UNIT4_001",
        "unit_id": "UNIT4_OOPAdvanced",
        "topic":   "Abstract Classes and ABC",
        "content": """Abstract classes define an interface that subclasses must implement.
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self) -> float:
        pass                        # subclasses MUST override this

    def describe(self):
        return f"I am a shape with area {self.area():.2f}"

class Circle(Shape):
    def __init__(self, r): self.r = r
    def area(self): return 3.14159 * self.r ** 2

# Shape()          → TypeError: Can't instantiate abstract class
c = Circle(5)      # OK — all abstract methods implemented
print(c.describe()) # I am a shape with area 78.54

Rules:
  - A class with at least one @abstractmethod cannot be instantiated.
  - Subclass must implement ALL abstract methods or itself becomes abstract.
  - Use ABC for strict interface contracts across a class hierarchy.""",
    },
    {
        "id":      "note_UNIT4_002",
        "unit_id": "UNIT4_OOPAdvanced",
        "topic":   "Decorators",
        "content": """A decorator is a higher-order function that wraps another function
to add behaviour without modifying its source code.

def timer(func):
    import time
    def wrapper(*args, **kwargs):
        start  = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__} took {time.perf_counter()-start:.4f}s")
        return result
    return wrapper

@timer
def slow_add(a, b):
    import time; time.sleep(0.1)
    return a + b

slow_add(2, 3)   # prints: slow_add took 0.1002s

Built-in decorators:
  @staticmethod  — no self or cls; plain function scoped in class
  @classmethod   — receives cls; can access/modify class state
  @property      — getter accessed as attribute (no parentheses)

functools.wraps: always use @functools.wraps(func) inside wrapper
to preserve the original function's __name__ and __doc__.""",
    },
    {
        "id":      "note_UNIT4_003",
        "unit_id": "UNIT4_OOPAdvanced",
        "topic":   "Dunder Methods",
        "content": """Dunder (double-underscore) methods let you define how objects
respond to Python operators and built-in functions.

class Vector:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __repr__(self):              # repr(v) — developer-facing
        return f"Vector({self.x}, {self.y})"

    def __str__(self):               # str(v) — user-facing
        return f"({self.x}, {self.y})"

    def __add__(self, other):        # v1 + v2
        return Vector(self.x + other.x, self.y + other.y)

    def __len__(self):               # len(v)
        return 2

    def __eq__(self, other):         # v1 == v2
        return self.x == other.x and self.y == other.y

v1, v2 = Vector(1, 2), Vector(3, 4)
print(v1 + v2)    # (4, 6)
print(len(v1))    # 2
print(v1 == v2)   # False

Key dunders: __init__, __repr__, __str__, __add__, __sub__,
__mul__, __len__, __getitem__, __iter__, __contains__, __eq__, __lt__""",
    },

    # ═══════════════════════════════════════════════════════
    #  UNIT6: Linked Lists  (not in dataset)
    # ═══════════════════════════════════════════════════════
    {
        "id":      "note_UNIT6_001",
        "unit_id": "UNIT6_LinkedLists",
        "topic":   "Singly Linked List",
        "content": """A singly linked list is a chain of nodes where each node holds
data and a pointer (next) to the following node.

class Node:
    def __init__(self, data):
        self.data = data
        self.next = None   # points to next node

class LinkedList:
    def __init__(self):
        self.head = None

    def append(self, data):        # O(n) — must reach the tail
        new = Node(data)
        if not self.head:
            self.head = new; return
        cur = self.head
        while cur.next:            # traverse to last node
            cur = cur.next
        cur.next = new

    def prepend(self, data):       # O(1) — just update head
        new = Node(data)
        new.next = self.head
        self.head = new

    def delete(self, data):        # O(n) search + O(1) removal
        cur = self.head
        if cur and cur.data == data:
            self.head = cur.next; return
        while cur and cur.next:
            if cur.next.data == data:
                cur.next = cur.next.next; return
            cur = cur.next

Complexity:
  Access / Search : O(n)  — no random access, must traverse
  Insert at head  : O(1)
  Insert at tail  : O(n)  (O(1) if tail pointer maintained)
  Delete          : O(n) search + O(1) relink""",
    },
    {
        "id":      "note_UNIT6_002",
        "unit_id": "UNIT6_LinkedLists",
        "topic":   "Floyd Cycle Detection",
        "content": """Floyd's algorithm (tortoise and hare) detects cycles in a linked list
using two pointers that move at different speeds.

def has_cycle(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next          # moves 1 step
        fast = fast.next.next     # moves 2 steps
        if slow is fast:          # they meet inside the cycle
            return True
    return False                  # fast reached None → no cycle

Why it works:
  - If no cycle: fast reaches None in O(n/2) steps.
  - If cycle exists: fast laps slow inside the loop.
    The gap closes by 1 each iteration → they must meet.

Finding cycle start (extension):
  After detection, reset slow to head.
  Advance both one step at a time → they meet at cycle start.

Time  : O(n)  — at most 2 full traversals
Space : O(1)  — only two pointers, no hash set""",
    },

    # ═══════════════════════════════════════════════════════
    #  UNIT9: Hash Tables  (not in dataset)
    # ═══════════════════════════════════════════════════════
    {
        "id":      "note_UNIT9_001",
        "unit_id": "UNIT9_HashTables",
        "topic":   "Hashing and Collision Resolution",
        "content": """A hash table maps keys to values using a hash function.
h(key) → index in an underlying array.

Python dict is a hash table — O(1) average for get/set/delete.

Collision: two different keys produce the same index.

Resolution strategies:
1. Chaining — each bucket holds a linked list of (key, value) pairs.
   Lookup: hash(key) → bucket → scan list for key.  O(1) avg, O(n) worst.

2. Open Addressing — find the next empty slot.
   Linear probing: check index+1, index+2, …
   Quadratic probing: check index+1², index+2², …
   Double hashing: use a second hash function for step size.

Load factor α = n / capacity
  When α exceeds ~0.7 (Python uses 2/3), the table is REHASHED:
    - New array of ~2× size allocated
    - All entries re-inserted  (O(n) one-time cost)
  This keeps α low and maintains O(1) amortised performance.

Why lists can't be dict keys:
  Keys must be hashable (immutable). Lists are mutable — their
  contents (and thus hash) could change, breaking the table.""",
    },
    {
        "id":      "note_UNIT9_002",
        "unit_id": "UNIT9_HashTables",
        "topic":   "Python dict and set Patterns",
        "content": """Common hash-table patterns in Python:

# Frequency counter
from collections import Counter
freq = Counter("abracadabra")   # Counter({'a': 5, 'b': 2, 'r': 2, 'c': 1, 'd': 1})

# defaultdict avoids KeyError on missing keys
from collections import defaultdict
graph = defaultdict(list)
graph["A"].append("B")          # no need to initialise graph["A"] first

# Two-sum in O(n) using a dict
def two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        complement = target - n
        if complement in seen:
            return [seen[complement], i]
        seen[n] = i

# Caching / memoisation with dict
memo = {}
def fib(n):
    if n in memo: return memo[n]
    if n <= 1:    return n
    memo[n] = fib(n-1) + fib(n-2)
    return memo[n]

set operations — also hash-based, O(1) membership:
  s = {1, 2, 3}
  3 in s          # O(1)
  s1 & s2         # intersection
  s1 | s2         # union
  s1 - s2         # difference""",
    },

    # ═══════════════════════════════════════════════════════
    #  UNIT14: Graph Algorithms  (not in dataset)
    # ═══════════════════════════════════════════════════════
    {
        "id":      "note_UNIT14_001",
        "unit_id": "UNIT14_GraphAlgorithms",
        "topic":   "BFS and DFS",
        "content": """Graph traversal visits every reachable vertex exactly once.

BFS — Breadth-First Search  (uses a queue)
  Explores all neighbours at depth d before depth d+1.
  Finds shortest path (fewest edges) in unweighted graphs.

from collections import deque

def bfs(graph, start):
    visited = set()
    queue   = deque([start])
    visited.add(start)
    order   = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbour in graph[node]:
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)
    return order

DFS — Depth-First Search  (uses a stack / recursion)
  Goes deep along one path before backtracking.
  Used for: cycle detection, topological sort, connected components.

def dfs(graph, node, visited=None):
    if visited is None: visited = set()
    visited.add(node)
    for neighbour in graph[node]:
        if neighbour not in visited:
            dfs(graph, neighbour, visited)
    return visited

Complexity (both):
  Time  : O(V + E)  — each vertex and edge visited once
  Space : O(V)      — visited set + queue/stack""",
    },
    {
        "id":      "note_UNIT14_002",
        "unit_id": "UNIT14_GraphAlgorithms",
        "topic":   "Shortest Paths and Topological Sort",
        "content": """Dijkstra's Algorithm — shortest path in weighted graphs (non-negative edges)

import heapq

def dijkstra(graph, start):
    # graph: {node: [(weight, neighbour), ...]}
    dist = {node: float('inf') for node in graph}
    dist[start] = 0
    pq = [(0, start)]                # (distance, node)
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]: continue     # stale entry
        for w, v in graph[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heapq.heappush(pq, (dist[v], v))
    return dist

Time: O((V + E) log V) with a min-heap.
Cannot handle negative edges — use Bellman-Ford for those.

Topological Sort — linear ordering of a DAG
  Every directed edge u → v means u comes before v.
  Used for: build systems, task scheduling, course prerequisites.

from collections import deque

def topo_sort(graph, in_degree):   # Kahn's BFS algorithm
    queue = deque(n for n in graph if in_degree[n] == 0)
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in graph[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
    return order if len(order) == len(graph) else []  # [] = cycle detected""",
    },

    # ═══════════════════════════════════════════════════════
    #  SUPPLEMENTAL — dataset units with extra curated notes
    #  on topics not well-covered by the templated dataset.
    # ═══════════════════════════════════════════════════════

    # UNIT1 supplement — control flow (not a topic in dataset)
    {
        "id":      "note_UNIT1_supp_001",
        "unit_id": "UNIT1_PythonBasics",
        "topic":   "Control Flow",
        "content": """Control flow determines which code runs and when.

if / elif / else:
  Python evaluates conditions top to bottom, runs the first True branch.
  x = 10
  if x > 5:    print("A")   # runs — x=10 > 5
  elif x > 8:  print("B")   # skipped — first branch already matched
  else:         print("C")

for loops — iterate over any iterable:
  for i in range(5):         # i = 0,1,2,3,4
  for item in my_list:       # iterates elements
  for k, v in my_dict.items(): # key-value pairs

while loops — run while condition is True:
  n = 10
  while n > 0:
      n -= 1                 # ensure termination

Loop controls:
  break    — exit the loop immediately
  continue — skip to next iteration
  pass     — valid no-op placeholder

Ternary expression:
  result = "pass" if score >= 40 else "fail"

List comprehension (compact for-loop):
  evens = [x for x in range(10) if x % 2 == 0]   # [0,2,4,6,8]""",
    },

    # UNIT2 supplement — scope (not in dataset)
    {
        "id":      "note_UNIT2_supp_001",
        "unit_id": "UNIT2_PythonFunctions",
        "topic":   "Scope and LEGB",
        "content": """Python resolves names using the LEGB rule (searched in order):
  L — Local      : variables inside the current function
  E — Enclosing  : variables in outer function (for nested functions)
  G — Global     : module-level variables
  B — Built-in   : Python built-ins (len, range, print, …)

x = "global"

def outer():
    x = "enclosing"
    def inner():
        # x not defined locally → finds "enclosing" in outer's scope
        print(x)          # enclosing
    inner()

Modifying outer scopes:
  global x      — allows writing to the module-level x inside a function
  nonlocal x    — allows writing to x in the immediately enclosing function

Closures:
  A nested function that captures variables from its enclosing scope.
  def make_counter():
      count = 0
      def counter():
          nonlocal count
          count += 1
          return count
      return counter

  c = make_counter()
  c()  # 1
  c()  # 2   (count persists in closure)""",
    },

    # UNIT3 supplement — super() and MRO (not in dataset)
    {
        "id":      "note_UNIT3_supp_001",
        "unit_id": "UNIT3_OOP",
        "topic":   "Inheritance and MRO",
        "content": """Python uses C3 linearisation to determine Method Resolution Order (MRO) —
the order in which base classes are searched when a method is called.

class A:
    def hello(self): print("A")

class B(A):
    def hello(self): print("B")

class C(A):
    def hello(self): print("C")

class D(B, C):          # multiple inheritance
    pass

D().hello()             # prints "B"
print(D.__mro__)        # (<class 'D'>, <class 'B'>, <class 'C'>, <class 'A'>, <class 'object'>)

super() follows the MRO — it doesn't call the direct parent, it calls
the NEXT class in the MRO chain. This is critical in cooperative
multiple inheritance.

class B(A):
    def __init__(self):
        super().__init__()  # calls C.__init__ next (via MRO), then A.__init__
        print("B init")""",
    },

    # UNIT12 supplement — call stack (not explicit in dataset)
    {
        "id":      "note_UNIT12_supp_001",
        "unit_id": "UNIT12_Recursion",
        "topic":   "Call Stack and Tail Recursion",
        "content": """Each recursive call adds a stack frame to the call stack.
Python's default recursion limit is 1000 (sys.getrecursionlimit()).

Stack frame holds: local variables, parameters, return address.
For factorial(5): 6 frames stacked before any unwinding.

Space complexity of recursion = O(depth of call tree).

Tail recursion:
  A recursive call is "tail" when it is the LAST operation.
  factorial(n, acc=1):
    if n == 0: return acc
    return factorial(n-1, n * acc)   ← tail call

  Python does NOT optimise tail calls (unlike Haskell, Scala).
  Tail-recursive functions still consume O(n) stack space in Python.
  Convert to iteration for large inputs.

When to use iteration instead:
  - Input size > ~900 (to avoid hitting recursion limit)
  - Performance-critical code (function call overhead)
  - sys.setrecursionlimit() raises the limit but not the OS stack size""",
    },
]


# ─────────────────────────────────────────────────────────────────
#  ASSEMBLE ALL_NOTES
#  Dataset-derived notes first, then hand-written supplements.
#  De-duplicate by id (dataset entries take precedence).
# ─────────────────────────────────────────────────────────────────

def _build_all_notes() -> List[Dict]:
    dataset_notes = _notes_from_dataset()

    # Index by id so we can de-duplicate
    by_id: Dict[str, Dict] = {n["id"]: n for n in dataset_notes}

    # Hand-written notes: add if id not already present (dataset wins)
    for note in _HANDWRITTEN_NOTES:
        if note["id"] not in by_id:
            by_id[note["id"]] = note

    return list(by_id.values())


ALL_NOTES: List[Dict] = _build_all_notes()
