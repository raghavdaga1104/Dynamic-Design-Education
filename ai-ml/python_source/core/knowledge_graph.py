"""
knowledge_graph.py
------------------
Represents the DDE curriculum as a directed prerequisite graph.

Each node (unit) stores:
  - skills_taught    : list of skill ids this unit develops
  - prereq_skills    : skills required before starting this unit
  - display_name     : human-readable name shown in UI
  - domain           : subject area (python / oop / dsa / algorithms)
  - irt_difficulty   : IRT difficulty parameter for this unit's quiz
  - irt_discrimination: IRT discrimination parameter
  - description      : short description shown to learner

The graph is loaded from curriculum.py at startup and can be extended
without changing any algorithm code.
"""

from typing import Dict, List, Set, Tuple, Optional


class KnowledgeGraph:
    """
    Prerequisite-based knowledge graph for DDE learning units.
    """

    def __init__(self):
        # unit_id → unit metadata dict
        self.units: Dict[str, Dict] = {}

    # ──────────────────────────────────────────
    #  Unit management
    # ──────────────────────────────────────────

    def add_unit(
        self,
        unit_id: str,
        skills_taught: List[str],
        prereq_skills: Optional[Set[str]] = None,
        display_name: str = "",
        domain: str = "",
        irt_difficulty: float = 0.5,
        irt_discrimination: float = 1.0,
        description: str = "",
    ) -> None:
        """
        Register a learning unit in the graph.

        Parameters
        ----------
        unit_id            : unique identifier  e.g. "UNIT3_DataStructures"
        skills_taught      : skills this unit develops  e.g. ["data structures"]
        prereq_skills      : skills required before attempting this unit
        display_name       : label shown in UI  e.g. "Data Structures"
        domain             : subject category
        irt_difficulty     : IRT b-parameter (0.3=easy … 1.2=very hard)
        irt_discrimination : IRT a-parameter (higher = sharper separation)
        description        : one-line unit description for UI
        """
        self.units[unit_id] = {
            "skills_taught":      list(skills_taught),
            "prereq_skills":      set(prereq_skills or []),
            "display_name":       display_name or unit_id,
            "domain":             domain,
            "irt_difficulty":     irt_difficulty,
            "irt_discrimination": irt_discrimination,
            "description":        description,
        }

    # ──────────────────────────────────────────
    #  Prerequisite checking
    # ──────────────────────────────────────────

    def get_available_units(
        self,
        skill_mastery: Dict[str, float],
        mastery_threshold: float = 0.5,
    ) -> List[str]:
        """
        Return units whose prerequisite skills are all sufficiently mastered.

        A unit is available when every required skill has mastery ≥ threshold.
        Units with no prerequisites are always available.
        """
        available = []
        for uid, meta in self.units.items():
            prereqs_met = all(
                skill_mastery.get(skill, 0.0) >= mastery_threshold
                for skill in meta["prereq_skills"]
            )
            if prereqs_met:
                available.append(uid)
        return available

    def are_prereqs_met(
        self,
        unit_id: str,
        skill_mastery: Dict[str, float],
        mastery_threshold: float = 0.5,
    ) -> bool:
        """Check whether a specific unit's prerequisites are satisfied."""
        meta = self.units.get(unit_id)
        if not meta:
            return False
        return all(
            skill_mastery.get(skill, 0.0) >= mastery_threshold
            for skill in meta["prereq_skills"]
        )

    # ──────────────────────────────────────────
    #  Accessors
    # ──────────────────────────────────────────

    def get_unit_skills(self, unit_id: str) -> List[str]:
        """Skills developed by this unit."""
        return self.units.get(unit_id, {}).get("skills_taught", [])

    def get_irt_params(self, unit_id: str) -> Tuple[float, float]:
        """Return (difficulty, discrimination) IRT parameters for a unit."""
        meta = self.units.get(unit_id, {})
        return (
            meta.get("irt_difficulty",     0.5),
            meta.get("irt_discrimination", 1.0),
        )

    def get_display_name(self, unit_id: str) -> str:
        return self.units.get(unit_id, {}).get("display_name", unit_id)

    def get_description(self, unit_id: str) -> str:
        return self.units.get(unit_id, {}).get("description", "")

    def get_domain(self, unit_id: str) -> str:
        return self.units.get(unit_id, {}).get("domain", "")

    def get_all_skills(self) -> Set[str]:
        """Return the complete set of all skills in the graph."""
        skills: Set[str] = set()
        for meta in self.units.values():
            skills.update(meta["skills_taught"])
        return skills

    def get_unit_metadata(self, unit_id: str) -> Dict:
        """Return the full metadata dict for a unit."""
        return self.units.get(unit_id, {})

    def all_unit_ids(self) -> List[str]:
        return list(self.units.keys())

    def __len__(self) -> int:
        return len(self.units)

    def __repr__(self) -> str:
        return f"KnowledgeGraph({len(self.units)} units)"