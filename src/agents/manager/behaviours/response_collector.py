"""
ResponseCollector — CyclicBehaviour for the ManagerAgent.

Collects incoming ACTION_RESPONSE messages from PlayerAgents and routes
each message to the correct per-match asyncio.Queue so that the
TournamentRunner can await player decisions without polling.

Registration (done in ManagerAgent.setup):
    template = Template()
    template.set_metadata("performative", "inform")
    template.set_metadata("ontology",     "ACTION_RESPONSE")
    agent.add_behaviour(ResponseCollector(), template)

Queue key convention:
    "{match_id}_{player_bare_jid}"

The queue itself is created by TournamentRunner._run_match before the
round loop starts, and removed after the match ends.
"""

from spade.behaviour import CyclicBehaviour


class ResponseCollector(CyclicBehaviour):
    """
    Routes incoming ACTION_RESPONSE messages to per-match asyncio.Queues.

    Registered on the ManagerAgent with a Template filtering on:
        performative=inform, ontology=ACTION_RESPONSE

    The agent is expected to expose:
        agent.response_queues: dict[str, asyncio.Queue]
            Keyed by "{match_id}_{bare_player_jid}".
    """

    async def run(self):
        msg = await self.receive(timeout=5)
        if msg is not None:
            match_id = msg.get_metadata("match_id")
            queue_key = f"{match_id}_{str(msg.sender).split('/')[0]}"
            queue = self.agent.response_queues.get(queue_key)
            if queue is not None:
                await queue.put(msg)
