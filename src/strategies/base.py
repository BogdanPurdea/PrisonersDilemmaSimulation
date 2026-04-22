"""
Strategy base classes for the Prisoner's Dilemma.

Defines the Action enum (COOPERATE / DEFECT) and the abstract
Strategy interface that all concrete strategies must implement.
Corresponds to the Strategy interface in Component 3 Figure 2.
"""

from abc import ABC, abstractmethod
from enum import Enum


class Action(Enum):
    """Possible actions in the Prisoner's Dilemma."""
    COOPERATE = "C"
    DEFECT = "D"


class Strategy(ABC):
    """
    Abstract base class for a Prisoner's Dilemma decision-making strategy.

    Each concrete strategy implements `decide()` which, given the interaction
    history, returns either COOPERATE or DEFECT.
    """

    @abstractmethod
    def decide(self, history: list[dict]) -> Action:
        """
        Determine the next action based on past interactions.

        Args:
            history: List of dicts, each containing:
                - "my_action": Action taken by this player
                - "opponent_action": Action taken by the opponent
                - "my_payoff": Payoff received
                - "opponent_payoff": Payoff received by the opponent

        Returns:
            Action.COOPERATE or Action.DEFECT
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this strategy."""
        ...

    def __repr__(self) -> str:
        return f"Strategy({self.name})"
