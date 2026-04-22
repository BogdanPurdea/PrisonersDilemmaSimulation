"""
Concrete Prisoner's Dilemma strategy implementations.

Each strategy implements the Strategy ABC from base.py.
A STRATEGY_REGISTRY dict maps string names to classes for
config-driven instantiation.
"""

import random
from strategies.base import Action, Strategy


class AlwaysCooperate(Strategy):
    """Always cooperates regardless of opponent behaviour."""

    @property
    def name(self) -> str:
        return "AlwaysCooperate"

    def decide(self, history: list[dict]) -> Action:
        return Action.COOPERATE


class AlwaysDefect(Strategy):
    """Always defects regardless of opponent behaviour."""

    @property
    def name(self) -> str:
        return "AlwaysDefect"

    def decide(self, history: list[dict]) -> Action:
        return Action.DEFECT


class Random(Strategy):
    """Chooses COOPERATE or DEFECT with equal probability."""

    @property
    def name(self) -> str:
        return "Random"

    def decide(self, history: list[dict]) -> Action:
        return random.choice([Action.COOPERATE, Action.DEFECT])


class TitForTat(Strategy):
    """
    Cooperates on the first move, then mirrors the opponent's last action.
    One of the most successful strategies in Axelrod's tournament.
    """

    @property
    def name(self) -> str:
        return "TitForTat"

    def decide(self, history: list[dict]) -> Action:
        if not history:
            return Action.COOPERATE
        return Action(history[-1]["opponent_action"])


class TitForTatWithForgiveness(Strategy):
    """
    Like TitForTat, but with a 10% chance of forgiving a defection
    (cooperating even when the opponent defected last round).
    Helps break defection spirals.
    """

    FORGIVENESS_RATE = 0.10

    @property
    def name(self) -> str:
        return "TitForTatWithForgiveness"

    def decide(self, history: list[dict]) -> Action:
        if not history:
            return Action.COOPERATE
        opponent_last = Action(history[-1]["opponent_action"])
        if opponent_last == Action.DEFECT and random.random() < self.FORGIVENESS_RATE:
            return Action.COOPERATE
        return opponent_last


class GrimTrigger(Strategy):
    """
    Cooperates until the opponent defects once, then defects forever.
    Also known as the "Grim" or "Trigger" strategy.
    """

    @property
    def name(self) -> str:
        return "GrimTrigger"

    def decide(self, history: list[dict]) -> Action:
        for entry in history:
            if entry["opponent_action"] == Action.DEFECT.value:
                return Action.DEFECT
        return Action.COOPERATE


class WinStayLoseShift(Strategy):
    """
    Also known as Pavlov. Repeats the last action if it received a high
    payoff (R or T), switches otherwise (received P or S).
    Cooperates on the first move.
    """

    @property
    def name(self) -> str:
        return "WinStayLoseShift"

    def decide(self, history: list[dict]) -> Action:
        if not history:
            return Action.COOPERATE
        last = history[-1]
        my_last_action = Action(last["my_action"])
        my_last_payoff = last["my_payoff"]
        # "Win" = got T or R (the two higher payoffs)
        # We consider a "win" if both players did the same thing or we defected while they cooperated
        # Simpler: if payoff was high (>= R), stay; otherwise shift
        # Using the payoff directly: T and R are "wins", P and S are "losses"
        if my_last_payoff >= 5:  # R=5 threshold — win
            return my_last_action
        else:  # P=1 or S=0 — lose, shift
            if my_last_action == Action.COOPERATE:
                return Action.DEFECT
            else:
                return Action.COOPERATE


class SuspiciousTitForTat(Strategy):
    """
    Like TitForTat but defects on the first move instead of cooperating.
    Tests the opponent's willingness to cooperate.
    """

    @property
    def name(self) -> str:
        return "SuspiciousTitForTat"

    def decide(self, history: list[dict]) -> Action:
        if not history:
            return Action.DEFECT
        return Action(history[-1]["opponent_action"])


class Adaptive(Strategy):
    """
    Cooperates initially, then tracks the opponent's cooperation rate.
    If the opponent cooperates less than half the time, defects.
    """

    @property
    def name(self) -> str:
        return "Adaptive"

    def decide(self, history: list[dict]) -> Action:
        if not history:
            return Action.COOPERATE
        opponent_cooperations = sum(
            1 for entry in history if entry["opponent_action"] == Action.COOPERATE.value
        )
        cooperation_rate = opponent_cooperations / len(history)
        if cooperation_rate < 0.5:
            return Action.DEFECT
        return Action.COOPERATE


# Registry mapping strategy names to classes for config-driven instantiation
STRATEGY_REGISTRY: dict[str, type[Strategy]] = {
    "AlwaysCooperate": AlwaysCooperate,
    "AlwaysDefect": AlwaysDefect,
    "Random": Random,
    "TitForTat": TitForTat,
    "TitForTatWithForgiveness": TitForTatWithForgiveness,
    "GrimTrigger": GrimTrigger,
    "WinStayLoseShift": WinStayLoseShift,
    "SuspiciousTitForTat": SuspiciousTitForTat,
    "Adaptive": Adaptive,
}
