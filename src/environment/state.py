"""
State dataclass for the Prisoner's Dilemma environment.

Represents the full simulation state at any point in time,
including initialization parameters, round tracking, cumulative
scores, and round-by-round history.

"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class State:
    """
    Immutable snapshot of the simulation state.

    Attributes:
        round_number: Current round (0-indexed, incremented after each round).
        max_rounds: Total number of rounds in the match.
        scores: Cumulative scores indexed by player JID string.
        history: Ordered list of round records. Each record is a dict with:
            - "round": int
            - "p1_jid": str
            - "p1_action": str ("C" or "D")
            - "p2_jid": str
            - "p2_action": str ("C" or "D")
            - "p1_payoff": int
            - "p2_payoff": int
            - "p1_cumulative": int
            - "p2_cumulative": int
        payoff: Payoff matrix parameters {"T", "R", "P", "S"}.
    """
    round_number: int = 0
    max_rounds: int = 1000
    scores: Dict[str, int] = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)
    payoff: Dict[str, int] = field(default_factory=lambda: {
        "T": 10, "R": 5, "P": 1, "S": 0
    })
