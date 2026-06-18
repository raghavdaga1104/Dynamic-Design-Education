"""
mcts_algorithm.py
-----------------
Monte Carlo Tree Search for personalised learning path recommendation.

The DDE learning engine frames "what should this learner study next?" as a
sequential decision problem on the knowledge graph.  MCTS solves it by:

  1. Selection   — navigate the existing tree using UCT to a leaf
  2. Expansion   — add a new child node (candidate next unit)
  3. Simulation  — play out a random rollout using BKT+IRT to estimate reward
  4. Backprop    — propagate the simulated reward back to the root

After N iterations the child of the root with the highest average reward
is the recommended next unit.

Reward function (0-1):
  overall_mastery_gain  * W_GAIN   — average improvement across all skills
  + goal_skill_gain     * W_GOAL   — targeted improvement on learner's interest
  + redundancy_penalty             — penalise revisiting already-mastered skills
"""

import math
import random
from typing import Dict, List, Optional, Tuple

from python_source.core.knowledge_graph    import KnowledgeGraph
from python_source.core.cold_start_engine  import ColdStartEngine
from python_source.core.adaptive_systems   import (
    bkt_update,
    bkt_expected_update,
    irt_probability_correct,
)
from python_source.core.analytics_logger   import AnalyticsLogger


# ─────────────────────────────────────────────
#  MCTS NODE
# ─────────────────────────────────────────────

class MCTSNode:
    """
    A node in the MCTS search tree.

    unit_id           : which learning unit this node represents
    skill_mastery     : hypothetical mastery state if learner reaches this node
    visits / reward   : statistics used by UCT
    unexplored_actions: units not yet expanded from this node
    """

    __slots__ = (
        "unit_id", "skill_mastery", "visits", "total_reward",
        "parent", "children", "unexplored_actions",
    )

    def __init__(
        self,
        unit_id: str,
        skill_mastery: Dict[str, float],
        parent: Optional["MCTSNode"] = None,
    ):
        self.unit_id            = unit_id
        self.skill_mastery      = dict(skill_mastery)
        self.visits             = 0
        self.total_reward       = 0.0
        self.parent             = parent
        self.children: Dict[str, "MCTSNode"] = {}
        self.unexplored_actions: List[str]   = []

    # ── UCT selection score ──────────────────────────────────────────────────
    def uct_score(self, parent_visits: int, C: float) -> float:
        """
        UCT(v) = Q(v)/N(v) + C * sqrt( ln(N_parent) / N(v) )

        The first term exploits known-good actions.
        The second term explores under-visited actions.
        C controls the exploration/exploitation tradeoff.
        """
        if self.visits == 0:
            return float("inf")
        exploitation = self.total_reward / self.visits
        exploration  = C * math.sqrt(math.log(max(1, parent_visits)) / self.visits)
        return exploitation + exploration

    # ── Backpropagation ──────────────────────────────────────────────────────
    def backpropagate(self, reward: float) -> None:
        """Walk up the tree incrementing visit counts and accumulating reward."""
        node = self
        while node is not None:
            node.visits       += 1
            node.total_reward += reward
            node               = node.parent


# ─────────────────────────────────────────────
#  MCTS CONTROLLER
# ─────────────────────────────────────────────

class MCTSAlgorithm:

    # Tuneable hyperparameters (validated defaults)
    C                    = math.sqrt(2)   # exploration constant
    W_GAIN               = 0.50           # weight for overall mastery gain
    W_GOAL               = 0.35           # FIX: reduced from 0.5 → weights now sum to 1.0
    W_WEAKNESS           = 0.15           # weight for weak-concept units
    P_REDUNDANCY         = -0.1           # penalty for revisiting mastered skills
    MASTERY_THRESHOLD    = 0.5            # prereq gate (unit unlocks above this)
    REDUNDANCY_THRESHOLD = 0.80           # skill considered mastered (for pruning)
    ROLLOUT_DEPTH        = 6              # max simulation steps
    # FIX: W_GAIN + W_GOAL + W_WEAKNESS = 0.50 + 0.35 + 0.15 = 1.00
    # Old weights (0.5+0.5+0.15=1.15) caused reward to regularly exceed 1.0
    # and be hard-clamped, making all top candidates look identical (reward=1.0)
    # and rendering the weakness bonus completely invisible to MCTS.

    # Default BKT parameters used when per-skill params are not provided
    DEFAULT_BKT = {"p_trans": 0.15, "p_guess": 0.20, "p_slip": 0.10}

    def __init__(
        self,
        knowledge_graph:     KnowledgeGraph,
        initial_skill_state: Dict[str, float],
        learner_profile:     Dict[str, str],
        bkt_params:          Optional[Dict[str, Dict[str, float]]] = None,
        logger:              Optional[AnalyticsLogger] = None,
        skill_weakness:      Optional[Dict[str, float]] = None,   # NEW
    ):
        self.kg              = knowledge_graph
        self.root            = MCTSNode("START", initial_skill_state)
        self.learner_profile = learner_profile
        self.bkt_params      = bkt_params or {}
        self.logger          = logger

        # NEW: Normalised weakness scores per skill (0-1).
        # Built from session.concept_index via build_skill_weakness_map().
        # Empty dict = no mistake data yet = bonus is zero everywhere.
        self.skill_weakness: Dict[str, float] = skill_weakness or {}

        self.cold_start      = ColdStartEngine(knowledge_graph)

        # Pre-compute the interest target key once
        interest             = learner_profile.get("interest", "").lower()
        self._target_key: Optional[str] = next(
            (s for s in initial_skill_state if interest in s.lower()),
            None,
        )

    # ──────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────

    def run(self, num_iterations: int = 60) -> None:
        """Execute N MCTS iterations from the root."""
        for i in range(1, num_iterations + 1):
            leaf   = self._select(self.root)
            node   = self._expand(leaf)
            reward = self._simulate(node)
            node.backpropagate(reward)

            if self.logger:
                self.logger.log_mcts_action(i, node.unit_id, reward, self.C)

    def get_best_unit(self) -> Optional[str]:
        """
        Return the recommended next unit after running iterations.

        Selection policy: highest average reward among children.
        Fallback: most visited child (more robust with few iterations).
        """
        if not self.root.children:
            return None

        best = max(
            ((uid, child) for uid, child in self.root.children.items() if child.visits > 0),
            key=lambda x: x[1].total_reward / x[1].visits,
            default=None,
        )
        if best:
            return best[0]

        # Fallback: most visited
        return max(self.root.children.items(), key=lambda x: x[1].visits)[0]

    def get_recommendation_details(self) -> Dict:
        """
        Return the recommended unit plus supporting stats for logging/UI.
        """
        best_uid = self.get_best_unit()
        details: Dict = {"unit_id": best_uid, "candidates": []}

        for uid, child in self.root.children.items():
            if child.visits > 0:
                details["candidates"].append({
                    "unit_id":      uid,
                    "display_name": self.kg.get_display_name(uid),
                    "visits":       child.visits,
                    "avg_reward":   round(child.total_reward / child.visits, 4),
                })

        details["candidates"].sort(key=lambda x: -x["avg_reward"])
        return details

    # ──────────────────────────────────────────
    #  MCTS phases
    # ──────────────────────────────────────────

    def _select(self, node: MCTSNode) -> MCTSNode:
        """Phase 1: traverse the tree using UCT until reaching a leaf."""
        current = node
        while not current.unexplored_actions and current.children:
            current = max(
                current.children.values(),
                key=lambda c: c.uct_score(current.visits, self.C),
            )
        return current

    def _expand(self, node: MCTSNode) -> MCTSNode:
        """Phase 2: add a new child node for an unexplored action."""

        # First visit to this node — populate the action list
        if not node.unexplored_actions:
            possible = self.kg.get_available_units(
                node.skill_mastery, self.MASTERY_THRESHOLD
            )
            # Prune units where all skills are already well-mastered
            valid = [
                u for u in possible
                if not all(
                    node.skill_mastery.get(s, 0.0) >= self.REDUNDANCY_THRESHOLD
                    for s in self.kg.get_unit_skills(u)
                )
            ]
            node.unexplored_actions = valid

            if not valid:
                return node   # fully expanded or terminal state

        # ── Root node: always use cold-start profile ordering ────────────────
        # FIX: old code had `if len(node.unexplored_actions) < 3` which meant
        # after UNIT1 unlocks 3 more units (UNIT2, UNIT3, UNIT5), the condition
        # became False and all expansions fell through to random.choice —
        # learner interest and year profile were ignored for the entire curriculum.
        # Now we always apply the ranked ordering at the root so the profile
        # always influences which unit is expanded first.
        if node.unit_id == "START":
            recs       = self.cold_start.get_initial_recommendations(self.learner_profile)
            valid_recs = [u for u in recs if u in node.unexplored_actions]
            if valid_recs:
                chosen = valid_recs[0]          # top-ranked by interest/year
                node.unexplored_actions.remove(chosen)
                child = self._make_child(node, chosen)
                # Seed with a prior reward so MCTS starts near the right answer
                child.visits       = 1
                child.total_reward = self.cold_start.get_prior_reward(chosen)
                return child
            # No ranked recommendation matches — fall back to random
            chosen = random.choice(node.unexplored_actions)
            node.unexplored_actions.remove(chosen)
            return self._make_child(node, chosen)

        # ── Normal expansion: FIFO order ─────────────────────────────────────
        chosen = node.unexplored_actions.pop(0)
        return self._make_child(node, chosen)

    def _simulate(self, node: MCTSNode) -> float:
        """
        Phase 3: random rollout from the expanded node.

        Simulates the learner progressing through the curriculum by:
          - Randomly picking available units at each step
          - Using IRT to estimate probability of correct answer
          - Updating mastery with BKT based on that simulated answer
          - Accumulating a reward based on mastery gained
        """
        sim_state      = dict(node.skill_mastery)
        initial_state  = dict(node.skill_mastery)
        redundancy_pen = 0.0

        initial_target = initial_state.get(self._target_key, 0.0) if self._target_key else 0.0

        for _ in range(self.ROLLOUT_DEPTH):
            available = self.kg.get_available_units(sim_state, self.MASTERY_THRESHOLD)
            if not available:
                break

            unit    = random.choice(available)
            skills  = self.kg.get_unit_skills(unit)
            diff, disc = self.kg.get_irt_params(unit)

            # Penalise if all skills already mastered (redundant unit)
            if all(sim_state.get(s, 0.0) >= self.REDUNDANCY_THRESHOLD for s in skills):
                redundancy_pen += self.P_REDUNDANCY

            for skill in skills:
                prior  = sim_state.get(skill, 0.1)
                params = self._bkt_params(skill)

                # IRT gives realistic success probability based on mastery
                p_correct      = irt_probability_correct(prior, diff, disc)
                was_correct    = random.random() < p_correct
                sim_state[skill] = bkt_update(
                    prior, was_correct,
                    params["p_guess"], params["p_slip"], params["p_trans"],
                )

        # ── Reward calculation ────────────────────────────────────────────────
        # Component 1: mean mastery across all tracked skills
        overall = sum(sim_state.values()) / max(1, len(sim_state))

        # Component 2: gain specifically in the learner's goal skill
        goal_reward = 0.0
        if self._target_key:
            gain = sim_state.get(self._target_key, 0.0) - initial_target
            # FIX: was gain * 5.0 — even a 0.2 gain produced goal_reward=1.0,
            # filling half the reward budget and causing constant clamping.
            # Reduced to x2 so a 0.5 gain (large) produces goal_reward=1.0.
            goal_reward = max(0.0, gain * 2.0)

        # NEW Component 3: weakness bonus ─────────────────────────────────────
        # Units that teach skills the learner is weak on get a bonus.
        # This connects the mistake tracker output to the MCTS reward signal.
        #
        # How it works:
        #   skill_weakness = {skill: normalised_score_0_to_1}
        #   For each unit visited in the rollout, check if its skills
        #   appear in skill_weakness. If so, add a proportional bonus.
        #
        # The bonus is capped at W_WEAKNESS (0.15) to act as a tie-breaker
        # rather than dominating the mastery/goal components.
        # It only fires when mistake data exists — zero otherwise.
        weakness_bonus = 0.0
        if self.skill_weakness:
            weakness_bonus = self._compute_weakness_bonus(node)
        # ── END NEW ───────────────────────────────────────────────────────────

        raw = (
            self.W_GAIN * overall
            + self.W_GOAL * goal_reward
            + self.W_WEAKNESS * weakness_bonus   # NEW
            + redundancy_pen
        )
        return float(min(1.0, max(0.0, raw)))

    # ──────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────

    def _make_child(self, parent: MCTSNode, unit_id: str) -> MCTSNode:
        """
        Create a child node representing the learner completing `unit_id`.
        Uses BKT expected update (deterministic) during tree building to keep
        the tree structure stable across iterations.
        """
        new_state = dict(parent.skill_mastery)
        for skill in self.kg.get_unit_skills(unit_id):
            prior = new_state.get(skill, 0.1)
            p     = self._bkt_params(skill)
            new_state[skill] = bkt_expected_update(
                prior, p["p_guess"], p["p_slip"], p["p_trans"]
            )

        child = MCTSNode(unit_id, new_state, parent=parent)
        parent.children[unit_id] = child
        return child

    def _bkt_params(self, skill: str) -> Dict[str, float]:
        """Return BKT parameters for a skill, falling back to defaults."""
        overrides = self.bkt_params.get(skill, {})
        return {
            "p_trans": overrides.get("p_trans", self.DEFAULT_BKT["p_trans"]),
            "p_guess": overrides.get("p_guess", self.DEFAULT_BKT["p_guess"]),
            "p_slip":  overrides.get("p_slip",  self.DEFAULT_BKT["p_slip"]),
        }

    def _compute_weakness_bonus(self, node: MCTSNode) -> float:
        """
        NEW — Compute a weakness bonus for the unit represented by this node.

        Returns a value in [0, 1] that is higher when the unit teaches
        skills the learner has recently been struggling with.

        Algorithm
        ---------
        For each skill taught by this unit:
          1. Look up its weakness score in self.skill_weakness (normalised 0-1)
          2. Only apply bonus if the skill is NOT already mastered
             (no point revisiting something already above 0.80)
        Return the average weakness score across all taught skills.

        This means:
          - Unit teaches "recursion" and learner is weak on recursion → high bonus
          - Unit teaches "python basics" already mastered at 0.9 → zero bonus
          - Unit has no weakness data → zero bonus (graceful degradation)

        Why average and not max?
          Max would give full bonus to any unit with even one weak skill.
          Average distributes the bonus proportionally — a unit that teaches
          3 skills where 2 are strong and 1 is weak gets a modest bonus.
        """
        if not self.skill_weakness:
            return 0.0

        skills = self.kg.get_unit_skills(node.unit_id)
        if not skills:
            return 0.0

        bonuses = []
        for skill in skills:
            # Only count bonus if skill is below mastery threshold
            # (no point encouraging revisit of already-mastered skills)
            current_mastery = node.skill_mastery.get(skill, 0.0)
            if current_mastery >= self.REDUNDANCY_THRESHOLD:
                bonuses.append(0.0)
                continue

            weakness = self.skill_weakness.get(skill, 0.0)
            bonuses.append(weakness)

        return sum(bonuses) / len(bonuses) if bonuses else 0.0