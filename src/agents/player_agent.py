"""
PlayerAgent — Autonomous SPADE agent for the Prisoner's Dilemma.

Implements the Player Agent specification from Component 2 §2.0.3
and the PAGE(S) conceptual model from Component 3.

Uses two CyclicBehaviours, each registered with a distinct Template:
  - ActionBehaviour (Template: ontology=REQUEST_ACTION)
  - ResultBehaviour (Template: ontology=ROUND_RESULT)

Presence is set to AVAILABLE on setup() so the ManagerAgent can
detect readiness before starting the match.
"""

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from strategies.base import Strategy, Action

try:
    from spade.presence import PresenceType, PresenceShow
except ImportError:
    PresenceType = None
    PresenceShow = None


class PlayerAgent(Agent):
    """
    A SPADE agent that participates in the Prisoner's Dilemma.

    Each PlayerAgent is assigned a Strategy at construction time and
    maintains a local history of its interactions. It listens for
    messages from the ManagerAgent — action requests trigger the
    deliberation cycle, and round results update the local history.
    """

    def __init__(self, jid: str, password: str, strategy: Strategy, *args, **kwargs):
        """
        Initialize the PlayerAgent.

        Args:
            jid: XMPP JID for this agent.
            password: XMPP password.
            strategy: A Strategy instance defining this agent's decision-making.
        """
        super().__init__(jid, password, *args, **kwargs)
        self.strategy = strategy
        self.history: list[dict] = []
        self._last_action: str | None = None  # track our last action for history

    async def setup(self):
        """
        Set up the agent's behaviours with Template-based message routing
        and announce presence as AVAILABLE.
        """
        print(f"[{self.strategy.name}] PlayerAgent {self.jid} starting...")

        # --- Template for action requests from Manager ---
        action_template = Template()
        action_template.set_metadata("performative", "request")
        action_template.set_metadata("ontology", "REQUEST_ACTION")
        self.add_behaviour(self.ActionBehaviour(), action_template)

        # --- Template for round results from Manager ---
        result_template = Template()
        result_template.set_metadata("performative", "inform")
        result_template.set_metadata("ontology", "ROUND_RESULT")
        self.add_behaviour(self.ResultBehaviour(), result_template)

        # --- Presence: announce availability ---
        if PresenceType is not None:
            self.presence.set_presence(
                presence_type=PresenceType.AVAILABLE,
                show=PresenceShow.CHAT,
                status=f"Ready to play ({self.strategy.name})"
            )

            # Auto-approve subscription requests from Manager
            def on_subscribe(peer_jid):
                self.presence.approve_subscription(peer_jid)

            self.presence.on_subscribe = on_subscribe

    class ActionBehaviour(CyclicBehaviour):
        """
        Handles REQUEST_ACTION messages from the ManagerAgent.

        Implements the deliberation cycle (Component 3 / README §5.2):
        1. Sense: receive the action request
        2. Deliberate: call strategy.decide(history)
        3. Execute: send ACTION_RESPONSE with the chosen action
        """

        async def run(self):
            msg = await self.receive(timeout=30)
            if msg is None:
                return

            # Deliberate: invoke the strategy
            action = self.agent.strategy.decide(self.agent.history)

            # Track our action so ResultBehaviour can record it
            self.agent._last_action = action.value

            # Respond with chosen action
            reply = Message(to=str(msg.sender))
            reply.set_metadata("performative", "inform")
            reply.set_metadata("ontology", "ACTION_RESPONSE")
            reply.body = action.value  # "C" or "D"
            await self.send(reply)

    class ResultBehaviour(CyclicBehaviour):
        """
        Handles ROUND_RESULT messages from the ManagerAgent.

        Parses the percept and appends it to the agent's local
        interaction history. The body format is:
            "<opponent_action>,<my_payoff>,<opponent_payoff>"

        The agent's own action is retrieved from _last_action,
        which was set by ActionBehaviour during the same round.
        """

        async def run(self):
            msg = await self.receive(timeout=30)
            if msg is None:
                return

            # Parse percept: "opponent_action,my_payoff,opponent_payoff"
            parts = msg.body.split(",")
            opponent_action = parts[0]
            my_payoff = int(parts[1])
            opponent_payoff = int(parts[2])

            # Retrieve the action we took this round
            my_action = self.agent._last_action or "C"

            # Update local history
            self.agent.history.append({
                "my_action": my_action,
                "opponent_action": opponent_action,
                "my_payoff": my_payoff,
                "opponent_payoff": opponent_payoff,
            })
