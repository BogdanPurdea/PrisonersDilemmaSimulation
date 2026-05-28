"""
ActionBehaviour — CyclicBehaviour for the PlayerAgent.

Implements the player's deliberation cycle for each game round:
    1. Sense     — receive a REQUEST_ACTION message from the ManagerAgent.
    2. Deliberate — invoke strategy.decide(history) to choose C or D.
    3. Execute   — reply with an ACTION_RESPONSE containing the chosen action.

Registration (done in PlayerAgent.setup):
    template = Template()
    template.set_metadata("performative", "request")
    template.set_metadata("ontology",     "REQUEST_ACTION")
    agent.add_behaviour(ActionBehaviour(), template)

Side-effect:
    Stores the chosen action in agent._last_action[match_id] so that
    ResultBehaviour can record it alongside the opponent's action and payoffs.
"""

from spade.behaviour import CyclicBehaviour
from spade.message import Message


class ActionBehaviour(CyclicBehaviour):
    """
    Handles REQUEST_ACTION messages from the ManagerAgent.

    Sense → Deliberate → Execute loop per round.

    Expected agent attributes:
        agent.strategy     Strategy  — decision-making object
        agent.history      dict[str, list[dict]]  — per-match round history
        agent._last_action dict[str, str]  — last action taken per match
    """

    async def run(self):
        msg = await self.receive(timeout=30)
        if msg is None:
            return

        match_id = msg.get_metadata("match_id")
        if not match_id:
            print(f"[PlayerAgent {self.agent.jid}] Warning: Message without match_id received.")
            return

        if match_id not in self.agent.history:
            self.agent.history[match_id] = []

        # Deliberate: invoke the strategy
        action = self.agent.strategy.decide(self.agent.history[match_id])

        # Track our action so ResultBehaviour can record it
        self.agent._last_action[match_id] = action.value

        # Respond with chosen action
        reply = Message(to=str(msg.sender))
        reply.set_metadata("performative", "inform")
        reply.set_metadata("ontology", "ACTION_RESPONSE")
        reply.set_metadata("match_id", match_id)
        reply.body = action.value  # "C" or "D"
        await self.send(reply)
