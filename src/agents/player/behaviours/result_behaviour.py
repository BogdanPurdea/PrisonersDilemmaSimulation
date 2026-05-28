"""
ResultBehaviour — CyclicBehaviour for the PlayerAgent.

Handles ROUND_RESULT messages sent by the ManagerAgent after each round.
Parses the percept payload and appends a structured record to the agent's
local interaction history so that the Strategy can use it in subsequent rounds.

Message body format:
    "<opponent_action>,<my_payoff>,<opponent_payoff>"
    e.g.  "D,1,5"

Registration (done in PlayerAgent.setup):
    template = Template()
    template.set_metadata("performative", "inform")
    template.set_metadata("ontology",     "ROUND_RESULT")
    agent.add_behaviour(ResultBehaviour(), template)

Dependency on ActionBehaviour:
    The agent's own action for the round is retrieved from
    agent._last_action[match_id], which is set by ActionBehaviour
    during the same round before the Manager sends the result.
"""

from spade.behaviour import CyclicBehaviour


class ResultBehaviour(CyclicBehaviour):
    """
    Handles ROUND_RESULT messages from the ManagerAgent.

    Parses the percept and appends it to the agent's local
    interaction history keyed by match_id.

    Expected agent attributes:
        agent.history      dict[str, list[dict]]  — per-match round history
        agent._last_action dict[str, str]  — action taken in the current round
    """

    async def run(self):
        msg = await self.receive(timeout=30)
        if msg is None:
            return

        match_id = msg.get_metadata("match_id")
        if not match_id:
            return

        if match_id not in self.agent.history:
            self.agent.history[match_id] = []

        # Parse percept: "opponent_action,my_payoff,opponent_payoff"
        parts = msg.body.split(",")
        opponent_action = parts[0]
        my_payoff = int(parts[1])
        opponent_payoff = int(parts[2])

        # Retrieve the action we took this round
        my_action = self.agent._last_action.get(match_id, "C")

        # Update local history
        self.agent.history[match_id].append({
            "my_action": my_action,
            "opponent_action": opponent_action,
            "my_payoff": my_payoff,
            "opponent_payoff": opponent_payoff,
        })
