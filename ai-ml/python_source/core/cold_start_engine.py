"""
cold_start_engine.py
---------------------
Generates initial unit recommendations for new learners with no history.

When a learner first joins the platform their mastery state is all zeros.
MCTS can't meaningfully distinguish between units because it has no data.
This engine provides a heuristic ranked list that MCTS uses to seed its
first expansions with sensible candidates rather than random choices.

Ranking factors (in priority order):
  1. Interest match  — does the unit's domain match what the learner said they want?
  2. Academic year   — 1st/2nd year learners should start foundational; 3rd/4th advanced
  3. Prerequisite depth — units with fewer prereqs are more accessible to beginners
"""

from typing import Dict, List


class ColdStartEngine:

    # Units with this many or more prereqs are considered "advanced"
    ADVANCED_PREREQ_THRESHOLD = 2

    def __init__(self, knowledge_graph):
        self.kg = knowledge_graph

    # ──────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────

    def get_initial_recommendations(
        self,
        learner_profile: Dict[str, str],
    ) -> List[str]:
        """
        Return a ranked list of unit_ids suitable for a cold-start learner.

        The list is ordered best-first. MCTS picks from the top of this list
        when no historical data is available.

        Parameters
        ----------
        learner_profile : dict with keys
            'interest' — learner's stated topic of interest  e.g. "data structures"
            'year'     — academic year                       e.g. "2nd"
            'degree'   — degree program                      e.g. "BTech"
        """
        interest     = learner_profile.get("interest", "").lower().strip()
        learner_year = learner_profile.get("year", "1st").lower()
        is_low_year  = "1st" in learner_year or "2nd" in learner_year

        scored: List[tuple] = []

        for unit_id, meta in self.kg.units.items():
            score        = 0
            skills_str   = " ".join(meta["skills_taught"]).lower()
            domain       = meta.get("domain", "").lower()
            prereq_count = len(meta["prereq_skills"])

            # ── 1. Interest match (highest weight) ──────────────────────────
            # Check both skills string and domain field for a broader match
            if interest:
                if interest in skills_str or interest in domain:
                    score += 12
                elif any(word in skills_str for word in interest.split()):
                    score += 6   # partial keyword match

            # ── 2. Academic year alignment ───────────────────────────────────
            is_foundational = prereq_count < self.ADVANCED_PREREQ_THRESHOLD
            if is_foundational:
                score += 4 if is_low_year else 1
            else:
                score += 1 if is_low_year else 8

            # ── 3. Tie-break: prefer units with fewer prereqs for beginners ──
            if is_low_year:
                score -= prereq_count  # small nudge toward simpler units

            scored.append((score, unit_id))

        # Sort descending by score, then alphabetically for stable ordering
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [uid for _, uid in scored]

    def get_prior_reward(self, unit_id: str) -> float:
        """
        Seed reward value injected into an MCTS node at cold-start time.
        This biases early iterations toward the recommended unit without
        forcing the choice — MCTS can still explore other options.
        """
        return 0.75
