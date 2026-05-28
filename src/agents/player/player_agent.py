"""
PlayerAgent — Autonomous SPADE agent for the Prisoner's Dilemma.

Uses two CyclicBehaviours, each registered with a distinct Template:
  - ActionBehaviour (Template: ontology=REQUEST_ACTION)
    Sense → Deliberate → Execute loop: asks strategy for an action.
    → agents/player/behaviours/action_behaviour.py
  - ResultBehaviour (Template: ontology=ROUND_RESULT)
    Parses round percept and updates the agent's local history.
    → agents/player/behaviours/result_behaviour.py

Presence is set to AVAILABLE on setup() so the ManagerAgent can
detect readiness before starting the match.
"""

from spade.agent import Agent
from spade.template import Template

from agents.player.behaviours.action_behaviour import ActionBehaviour
from agents.player.behaviours.result_behaviour import ResultBehaviour
from strategies.base import Strategy

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
        self.history: dict[str, list[dict]] = {}
        self._last_action: dict[str, str] = {}  # track our last action for history per match

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
        self.add_behaviour(ActionBehaviour(), action_template)

        # --- Template for round results from Manager ---
        result_template = Template()
        result_template.set_metadata("performative", "inform")
        result_template.set_metadata("ontology", "ROUND_RESULT")
        self.add_behaviour(ResultBehaviour(), result_template)

        # --- Presence: announce availability ---
        if PresenceType is not None:
            self.presence.set_presence(
                presence_type=PresenceType.AVAILABLE,
                show=PresenceShow.CHAT,
                status=f"Ready to play ({self.strategy.name})"
            )

            # Auto-approve subscription requests from Manager and subscribe back (bidirectional)
            def on_subscribe(peer_jid):
                self.presence.approve_subscription(peer_jid)
                self.presence.subscribe(peer_jid)

            self.presence.on_subscribe = on_subscribe

    # Behaviours are defined in their own modules:
    #   agents/player/behaviours/action_behaviour.py  → ActionBehaviour
    #   agents/player/behaviours/result_behaviour.py  → ResultBehaviour
    # They are imported at the top of this file and registered in setup() above.
