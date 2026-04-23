"""
Prisoner's Dilemma Environment.

Manages the game state, applies actions, computes payoffs, and
provides percepts and aggregated metrics.

"""

from copy import deepcopy
from typing import Dict, Tuple

from environment.state import State


class Environment:
    """
    The environment for an iterated Prisoner's Dilemma match.

    Maintains the full simulation state and provides methods for
    the Manager Agent to apply actions and retrieve percepts/metrics.
    """

    def __init__(self, payoff: Dict[str, int], max_rounds: int):
        """
        Initialize the environment.

        Args:
            payoff: Dict with keys "T", "R", "P", "S" satisfying T > R > P > S.
            max_rounds: Total number of rounds in the match.
        """
        self._state = State(
            round_number=0,
            max_rounds=max_rounds,
            scores={},
            history=[],
            payoff=dict(payoff),
        )

    def _compute_payoffs(self, action1: str, action2: str) -> Tuple[int, int]:
        """
        Compute payoffs for a pair of actions using the payoff matrix.

        Args:
            action1: Action of player 1 ("C" or "D").
            action2: Action of player 2 ("C" or "D").

        Returns:
            Tuple of (player1_payoff, player2_payoff).
        """
        t = self._state.payoff["T"]
        r = self._state.payoff["R"]
        p = self._state.payoff["P"]
        s = self._state.payoff["S"]

        if action1 == "C" and action2 == "C":
            return r, r
        elif action1 == "C" and action2 == "D":
            return s, t
        elif action1 == "D" and action2 == "C":
            return t, s
        else:  # D, D
            return p, p

    def apply_actions(
        self,
        p1_jid: str,
        p1_action: str,
        p2_jid: str,
        p2_action: str,
    ) -> Dict:
        """
        Apply a pair of actions, compute payoffs, update state.

        This is the core state transition function. It computes the
        payoff for each player, updates cumulative scores, appends
        a round record to history, and increments the round counter.

        Args:
            p1_jid: JID string of player 1.
            p1_action: Action of player 1 ("C" or "D").
            p2_jid: JID string of player 2.
            p2_action: Action of player 2 ("C" or "D").

        Returns:
            Dict with keys "p1_payoff" and "p2_payoff".
        """
        # Initialize scores on first round
        if p1_jid not in self._state.scores:
            self._state.scores[p1_jid] = 0
        if p2_jid not in self._state.scores:
            self._state.scores[p2_jid] = 0

        # Compute payoffs
        p1_payoff, p2_payoff = self._compute_payoffs(p1_action, p2_action)

        # Update cumulative scores
        self._state.scores[p1_jid] += p1_payoff
        self._state.scores[p2_jid] += p2_payoff

        # Append round record to history
        round_record = {
            "round": self._state.round_number + 1,
            "p1_jid": p1_jid,
            "p1_action": p1_action,
            "p2_jid": p2_jid,
            "p2_action": p2_action,
            "p1_payoff": p1_payoff,
            "p2_payoff": p2_payoff,
            "p1_cumulative": self._state.scores[p1_jid],
            "p2_cumulative": self._state.scores[p2_jid],
        }
        self._state.history.append(round_record)

        # Increment round counter
        self._state.round_number += 1

        return {"p1_payoff": p1_payoff, "p2_payoff": p2_payoff}

    def get_percept(self, player_jid: str, round_idx: int) -> Dict:
        """
        Return the percept for a specific player after a specific round.

        The percept contains the opponent's action and payoffs, which
        the player uses to update its local history.

        Args:
            player_jid: JID string of the player requesting the percept.
            round_idx: 0-based index of the round in history.

        Returns:
            Dict with "opponent_action", "my_payoff", "opponent_payoff".
        """
        record = self._state.history[round_idx]

        if player_jid == record["p1_jid"]:
            return {
                "opponent_action": record["p2_action"],
                "my_payoff": record["p1_payoff"],
                "opponent_payoff": record["p2_payoff"],
            }
        else:
            return {
                "opponent_action": record["p1_action"],
                "my_payoff": record["p2_payoff"],
                "opponent_payoff": record["p1_payoff"],
            }

    def get_state(self) -> State:
        """Return a deep copy of the current full state snapshot."""
        return deepcopy(self._state)

    def get_metrics(self) -> Dict:
        """
        Compute aggregated performance metrics across the entire match.

        Returns a dict containing:
            - cooperation_rate_p1: fraction of rounds p1 cooperated
            - cooperation_rate_p2: fraction of rounds p2 cooperated
            - defection_rate_p1: fraction of rounds p1 defected
            - defection_rate_p2: fraction of rounds p2 defected
            - total_payoff_p1: cumulative score of p1
            - total_payoff_p2: cumulative score of p2
            - avg_payoff_p1: average payoff per round for p1
            - avg_payoff_p2: average payoff per round for p2
            - total_rounds: number of rounds played
        """
        if not self._state.history:
            return {}

        total = len(self._state.history)
        first_record = self._state.history[0]
        p1_jid = first_record["p1_jid"]
        p2_jid = first_record["p2_jid"]

        p1_cooperations = sum(1 for r in self._state.history if r["p1_action"] == "C")
        p2_cooperations = sum(1 for r in self._state.history if r["p2_action"] == "C")

        return {
            "p1_jid": p1_jid,
            "p2_jid": p2_jid,
            "total_rounds": total,
            "cooperation_rate_p1": p1_cooperations / total,
            "cooperation_rate_p2": p2_cooperations / total,
            "defection_rate_p1": (total - p1_cooperations) / total,
            "defection_rate_p2": (total - p2_cooperations) / total,
            "total_payoff_p1": self._state.scores[p1_jid],
            "total_payoff_p2": self._state.scores[p2_jid],
            "avg_payoff_p1": self._state.scores[p1_jid] / total,
            "avg_payoff_p2": self._state.scores[p2_jid] / total,
        }

    def is_finished(self) -> bool:
        """Check if the match has reached the maximum number of rounds."""
        return self._state.round_number >= self._state.max_rounds
