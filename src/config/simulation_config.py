"""
Simulation configuration for the Prisoner's Dilemma tournament.

Defines the payoff matrix parameters, round count, and strategy list.
Validates the game-theoretic constraint T > R > P > S.
"""

from dataclasses import dataclass, field
from typing import Dict, List


# Default payoff values (Component 2 specification)
DEFAULT_T = 10  # Temptation to defect
DEFAULT_R = 5   # Reward for mutual cooperation
DEFAULT_P = 1   # Punishment for mutual defection
DEFAULT_S = 0   # Sucker's payoff

DEFAULT_ROUNDS = 1000

DEFAULT_STRATEGIES = [
    "AlwaysCooperate",
    # "AlwaysDefect",
    "Random",
    "TitForTat",
    "TitForTatWithForgiveness",
    "GrimTrigger",
    "WinStayLoseShift",
    "SuspiciousTitForTat",
    "Adaptive",
]


@dataclass
class SimulationConfig:
    """
    Configuration for a Prisoner's Dilemma tournament simulation.

    Attributes:
        payoff: Dictionary mapping payoff labels to values.
                Must satisfy T > R > P > S.
        rounds: Number of rounds per match.
        strategies: List of strategy names participating in the tournament.
    """
    payoff: Dict[str, int] = field(default_factory=lambda: {
        "T": DEFAULT_T,
        "R": DEFAULT_R,
        "P": DEFAULT_P,
        "S": DEFAULT_S,
    })
    rounds: int = DEFAULT_ROUNDS
    strategies: List[str] = field(default_factory=lambda: list(DEFAULT_STRATEGIES))

    def __post_init__(self):
        """Validate that the payoff values satisfy T > R > P > S."""
        t, r, p, s = self.payoff["T"], self.payoff["R"], self.payoff["P"], self.payoff["S"]
        if not (t > r > p > s):
            raise ValueError(
                f"Payoff constraint violated: T({t}) > R({r}) > P({p}) > S({s}) must hold."
            )
