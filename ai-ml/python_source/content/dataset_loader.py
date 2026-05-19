"""
dataset_loader.py
-----------------
Single source of truth for python_course_dataset.json.

Loads the real course dataset and exposes it through a clean API
used by notes_data.py (RAG index) and quiz_bank.py (quiz questions).

Unit ID normalisation
─────────────────────
The dataset uses 'UNIT13_DynamicProg'; the curriculum uses
'UNIT13_DynamicProgramming'. All lookups go through _UNIT_ID_MAP
so both files stay in sync automatically.

Dataset coverage (units present in JSON):
  UNIT1_PythonBasics      835 entries  5 topics
  UNIT2_PythonFunctions   668 entries  4 topics
  UNIT3_OOP               835 entries  5 topics
  UNIT5_Arrays            501 entries  3 topics
  UNIT7_StacksQueues      334 entries  2 topics
  UNIT8_Trees             333 entries  2 topics
  UNIT10_Sorting          498 entries  3 topics
  UNIT11_Searching        332 entries  2 topics
  UNIT12_Recursion        332 entries  2 topics
  UNIT13_DynamicProg      332 entries  2 topics

Units in curriculum but NOT in dataset (retained as synthetic notes):
  UNIT4_OOPAdvanced, UNIT6_LinkedLists, UNIT9_HashTables,
  UNIT14_GraphAlgorithms
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────
#  PATH RESOLUTION
#  Supports running from project root or from inside core/content.
# ─────────────────────────────────────────────────────────────────

_CANDIDATES = [
    Path(__file__).parent / "python_course_dataset.json",
    Path(__file__).parent.parent / "python_course_dataset.json",
    Path(__file__).parent.parent / "data" / "python_course_dataset.json",
    Path(__file__).parent.parent.parent / "python_course_dataset.json",
]

def _find_dataset() -> Path:
    for p in _CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "python_course_dataset.json not found. "
        "Place it in the project root or data/ directory."
    )

# ─────────────────────────────────────────────────────────────────
#  UNIT ID NORMALISATION
#  Maps dataset unit IDs → canonical curriculum unit IDs.
# ─────────────────────────────────────────────────────────────────

_UNIT_ID_MAP: Dict[str, str] = {
    # dataset id             → curriculum id
    "UNIT1_PythonBasics":    "UNIT1_PythonBasics",
    "UNIT2_PythonFunctions": "UNIT2_PythonFunctions",
    "UNIT3_OOP":             "UNIT3_OOP",
    "UNIT5_Arrays":          "UNIT5_Arrays",
    "UNIT7_StacksQueues":    "UNIT7_StacksQueues",
    "UNIT8_Trees":           "UNIT8_Trees",
    "UNIT10_Sorting":        "UNIT10_Sorting",
    "UNIT11_Searching":      "UNIT11_Searching",
    "UNIT12_Recursion":      "UNIT12_Recursion",
    # MISMATCH — dataset truncates the name
    "UNIT13_DynamicProg":    "UNIT13_DynamicProgramming",
}

_REVERSE_MAP: Dict[str, str] = {v: k for k, v in _UNIT_ID_MAP.items()}

def normalise_unit_id(raw_id: str) -> str:
    """Translate a dataset unit ID to the canonical curriculum unit ID."""
    return _UNIT_ID_MAP.get(raw_id, raw_id)

def dataset_unit_id(curriculum_id: str) -> str:
    """Translate a curriculum unit ID back to the dataset unit ID."""
    return _REVERSE_MAP.get(curriculum_id, curriculum_id)


# ─────────────────────────────────────────────────────────────────
#  LOADER
# ─────────────────────────────────────────────────────────────────

class CourseDataset:
    """
    Loaded and indexed view of python_course_dataset.json.

    Indexes built at load time:
      _by_unit  : canonical_unit_id  → list of entries
      _by_topic : canonical_unit_id  → topic → list of entries
      _by_id    : entry['id']        → entry
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = path or _find_dataset()
        self._raw: List[Dict] = []
        self._by_unit:  Dict[str, List[Dict]]            = defaultdict(list)
        self._by_topic: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        self._by_id:    Dict[str, Dict]                  = {}
        self._load()

    def _load(self) -> None:
        with open(self._path, encoding="utf-8") as f:
            raw = json.load(f)

        for entry in raw:
            # Normalise unit ID in place (keep original for reference)
            entry = dict(entry)
            entry["_raw_unit"]  = entry["unit"]
            entry["unit"]       = normalise_unit_id(entry["unit"])
            self._raw.append(entry)
            self._by_unit[entry["unit"]].append(entry)
            self._by_topic[entry["unit"]][entry["topic"]].append(entry)
            self._by_id[entry["id"]] = entry

    # ── Accessors ──────────────────────────────────────────────────

    def units_in_dataset(self) -> List[str]:
        """Canonical unit IDs that have data in the JSON file."""
        return list(self._by_unit.keys())

    def topics_for_unit(self, unit_id: str) -> List[str]:
        """All topic names in a unit, sorted."""
        return sorted(self._by_topic[unit_id].keys())

    def entries_for_unit(self, unit_id: str) -> List[Dict]:
        """All entries for a unit."""
        return self._by_unit.get(unit_id, [])

    def entries_for_topic(self, unit_id: str, topic: str) -> List[Dict]:
        """All entries for a specific unit + topic combination."""
        return self._by_topic[unit_id].get(topic, [])

    def get_by_id(self, entry_id: str) -> Optional[Dict]:
        return self._by_id.get(entry_id)

    def representative_entries(
        self,
        unit_id: str,
        per_topic: int = 3,
    ) -> List[Dict]:
        """
        Return up to `per_topic` representative entries for each topic in a unit.
        Used to build RAG notes — avoids flooding ChromaDB with 800+ near-identical
        entries while still covering every topic.
        """
        result = []
        for topic in self.topics_for_unit(unit_id):
            entries = self.entries_for_topic(unit_id, topic)
            # Pick entries that have meaningful code (non-trivial examples)
            with_code = [e for e in entries if _has_real_code(e)]
            pool = with_code if with_code else entries
            result.extend(pool[:per_topic])
        return result

    def __len__(self) -> int:
        return len(self._raw)

    def __repr__(self) -> str:
        return f"CourseDataset({len(self._raw)} entries, {len(self._by_unit)} units)"


def _has_real_code(entry: Dict) -> bool:
    """
    Return True if the entry's code field contains a real example
    (not just a placeholder print statement).
    """
    code = entry.get("code", "").strip()
    if not code:
        return False
    # Filter out trivial placeholder code
    trivial = (
        code.startswith("# Example of") and "print(" in code and len(code.split("\n")) <= 2
    )
    return not trivial


# ─────────────────────────────────────────────────────────────────
#  MODULE-LEVEL SINGLETON
#  Loaded once, reused everywhere.
# ─────────────────────────────────────────────────────────────────

_DATASET: Optional[CourseDataset] = None

def get_dataset() -> CourseDataset:
    """Return the module-level singleton CourseDataset (lazy load)."""
    global _DATASET
    if _DATASET is None:
        _DATASET = CourseDataset()
    return _DATASET
