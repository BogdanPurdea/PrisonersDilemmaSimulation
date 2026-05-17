"""
ManagerAgent — Central tournament coordinator for the Prisoner's Dilemma.

Architecture:
  - ResponseCollector (CyclicBehaviour + Template: ontology=ACTION_RESPONSE)
    Routes incoming player responses to per-player asyncio.Queues.
  - TournamentRunner (OneShotBehaviour)
    Generates all unique strategy pairings, spawns PlayerAgents,
    and runs all matches CONCURRENTLY via asyncio.gather.
    Each match has its own Environment and dedicated queues.

Communication protocol per round:
  1. Request:     Manager → Players [REQUEST_ACTION]
  2. Response:    Players → Manager [ACTION_RESPONSE]
  3. Computation: Manager applies actions to Environment
  4. Feedback:    Manager → Players [ROUND_RESULT]
"""

import asyncio
import itertools
import os
from uuid import uuid4

from spade.agent import Agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.message import Message
from spade.template import Template

from config.server_config import XMPP_SERVER, PASSWORD
from environment.environment import Environment
from persistence.csv_writer import CSVWriter
from strategies.catalog import STRATEGY_REGISTRY
from agents.player_agent import PlayerAgent

try:
    from spade.presence import PresenceType, PresenceShow, PresenceInfo
except ImportError:
    PresenceType = None
    PresenceShow = None
    PresenceInfo = None


class ManagerAgent(Agent):
    """
    Central tournament coordinator agent for the Prisoner's Dilemma.

    Responsibilities:
    - Initialize and manage matches between player agents
    - Enforce synchronization across simulation rounds
    - Collect player actions and compute corresponding payoffs
    - Maintain the global state of the simulation
    - Persist results to .CSV storage

    The ManagerAgent runs the entire tournament internally:
    it generates all unique strategy pairings, dynamically spawns
    PlayerAgents for each match, and executes all matches concurrently.
    """

    def __init__(self, jid: str, password: str, config, *args, **kwargs):
        """
        Initialize the ManagerAgent.

        Args:
            jid: XMPP JID for this agent.
            password: XMPP password.
            config: SimulationConfig instance.
        """
        super().__init__(jid, password, *args, **kwargs)
        self.config = config

        # Per-match response routing: match_id → asyncio.Queue
        # Populated dynamically as matches start
        self.response_queues: dict[str, asyncio.Queue] = {}

        # Track presence readiness
        self.players_ready: set = set()

        # Track our 9 reusable player agents
        self.strategy_to_jid: dict[str, str] = {}
        self.player_agents: dict[str, PlayerAgent] = {}
        self.player_locks: dict[str, asyncio.Lock] = {}

    async def setup(self):
        """
        Set up the ResponseCollector (Template-filtered) and TournamentRunner.
        """
        strategy_names = [s for s in self.config.strategies if s in STRATEGY_REGISTRY]
        n_matches = len(list(itertools.combinations(strategy_names, 2)))

        print(f"[Manager] ManagerAgent {self.jid} starting...")
        print(f"[Manager] Strategies: {', '.join(strategy_names)}")
        print(f"[Manager] Matches to play: {n_matches} (all unique pairs)")
        print(f"[Manager] Rounds per match: {self.config.rounds}")
        print(
            f"[Manager] Payoff matrix: T={self.config.payoff['T']}, "
            f"R={self.config.payoff['R']}, P={self.config.payoff['P']}, "
            f"S={self.config.payoff['S']}"
        )

        # --- Presence setup and wait for players ---
        if PresenceType is not None:
            def on_available(peer_jid, presence_info, last_presence):
                jid_str = str(peer_jid).split("/")[0]
                self.players_ready.add(jid_str)

            def on_subscribe(peer_jid):
                self.presence.approve_subscription(peer_jid)

            self.presence.on_available = on_available
            self.presence.on_subscribe = on_subscribe
            self.presence.set_presence(
                presence_type=PresenceType.AVAILABLE,
                show=PresenceShow.CHAT,
                status="Tournament Manager ready",
            )

        print(f"[Manager] Spawning {len(strategy_names)} persistent PlayerAgents...")
        for strat_name in strategy_names:
            p_jid = f"{strat_name.lower()}_{uuid4()}@{XMPP_SERVER}"
            self.strategy_to_jid[strat_name] = p_jid
            player = PlayerAgent(p_jid, PASSWORD, STRATEGY_REGISTRY[strat_name]())
            self.player_agents[p_jid] = player
            self.player_locks[p_jid] = asyncio.Lock()
            await player.start(auto_register=True)

            if PresenceType is not None:
                self.presence.subscribe(p_jid)

        if PresenceType is not None:
            print("[Manager] Waiting for all players to come online...")
            expected_jids = set(self.strategy_to_jid.values())
            wait_timeout = 20  # seconds
            elapsed = 0.0
            while not (expected_jids <= self.players_ready):
                await asyncio.sleep(0.5)
                elapsed += 0.5
                if elapsed >= wait_timeout:
                    print("[Manager] Warning: Timeout waiting for some players to become available.")
                    break

        # --- ResponseCollector: routes ACTION_RESPONSE to per-player queues ---
        response_template = Template()
        response_template.set_metadata("performative", "inform")
        response_template.set_metadata("ontology", "ACTION_RESPONSE")
        self.add_behaviour(self.ResponseCollector(), response_template)

        # --- TournamentRunner: orchestrates all matches concurrently ---
        self.tournament_runner = self.TournamentRunner()
        self.add_behaviour(self.tournament_runner)

        # --- Web GUI: start the built-in SPADE web interface ---
        self.web.start(hostname="127.0.0.1", port="10000")
        print("[Manager] Web interface started at http://127.0.0.1:10000/spade")

    class ResponseCollector(CyclicBehaviour):
        """
        Collects incoming ACTION_RESPONSE messages and routes them
        to the correct match via per-player asyncio.Queues.

        Registered with a Template filtering on:
            performative=inform, ontology=ACTION_RESPONSE
        """

        async def run(self):
            msg = await self.receive(timeout=5)
            if msg is not None:
                match_id = msg.get_metadata("match_id")
                queue_key = f"{match_id}_{str(msg.sender).split('/')[0]}"
                queue = self.agent.response_queues.get(queue_key)
                if queue is not None:
                    await queue.put(msg)

    class TournamentRunner(OneShotBehaviour):
        """
        Orchestrates the full tournament.

        Generates all unique strategy pairings, spawns fresh
        PlayerAgents per match, and runs all matches concurrently
        using asyncio.gather. Each match has its own Environment
        instance and dedicated response queues.
        """

        async def run(self):
            """Generate pairings and run all matches concurrently."""
            strategy_names = [s for s in self.agent.config.strategies if s in STRATEGY_REGISTRY]
            pairings = list(itertools.combinations(strategy_names, 2))

            print(f"\n[Manager] Starting {len(pairings)} matches concurrently...\n")

            # Launch all matches concurrently
            tasks = [
                self._run_match(strat_a, strat_b, idx + 1, len(pairings))
                for idx, (strat_a, strat_b) in enumerate(pairings)
            ]
            await asyncio.gather(*tasks)

            print(f"\n{'='*60}")
            print(f"  Tournament complete! {len(pairings)} matches played.")
            print(f"  Results written to results/ directory.")
            print(f"{'='*60}")

        async def on_end(self):
            """
            Pause after the tournament so the user can inspect results
            via the SPADE web interface at http://127.0.0.1:10000/spade.
            The agent stays alive until the user presses Ctrl+C.
            """
            print("\n[Manager] Tournament finished. Web interface is running.")

            # Patch contacts to prevent SPADE Web UI PresenceNotFound crash
            # Since players are stopped, some might not have finalised presence
            if PresenceType is not None:
                for c in self.agent.presence.contacts.values():
                    if c.current_presence is None:
                        # inject a fallback presence so the SPADE web server doesn't crash parsing them
                        c.update_presence(
                            "default",
                            PresenceInfo(PresenceType.UNAVAILABLE, PresenceShow.NONE)
                        )

            print("[Manager] Inspect results at http://127.0.0.1:10000/spade")
            print("[Manager] All player agents remain online for inspection.")
            print("[Manager] Press Ctrl+C to shut down.\n")

            # Keep the agent alive for inspection
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            
            # Cleanly stop all players
            print("[Manager] Shutting down persistent PlayerAgents...")
            for player in self.agent.player_agents.values():
                await player.stop()

            await self.agent.stop()

        async def _run_match(
            self,
            strat_a: str,
            strat_b: str,
            match_idx: int,
            total: int,
        ):
            """
            Run a single match between two strategies.

            This method:
            1. Looks up the appropriate persistent PlayerAgents via strategy name
            2. Acquires per-player locks to prevent concurrent matches on the same agent
            3. Registers per-match/per-player asyncio.Queues for response routing
            4. Executes the round loop (4-step protocol) using match_id
            5. Computes metrics and persists CSV
            6. Tears down the match-specific queues and releases locks

            Args:
                strat_a: Name of strategy for player 1.
                strat_b: Name of strategy for player 2.
                match_idx: Match number (1-based, for logging).
                total: Total number of matches.
            """
            tag = f"[Match {match_idx}/{total}]"
            match_id = f"match_{uuid4()}"

            # 1. Lookup JIDs for strategies
            p1_jid = self.agent.strategy_to_jid[strat_a]
            p2_jid = self.agent.strategy_to_jid[strat_b]

            print(f"{tag} {strat_a} vs {strat_b} — waiting for player availability...")
            
            # Acquire locks for both players in a consistent order to prevent deadlocks
            lock1_jid, lock2_jid = min(p1_jid, p2_jid), max(p1_jid, p2_jid)
            
            async with self.agent.player_locks[lock1_jid]:
                async with self.agent.player_locks[lock2_jid]:
                    
                    # 2. Register match-specific response queues BEFORE starting rounds
                    q1 = asyncio.Queue()
                    q2 = asyncio.Queue()
                    q1_key = f"{match_id}_{p1_jid}"
                    q2_key = f"{match_id}_{p2_jid}"
                    
                    self.agent.response_queues[q1_key] = q1
                    self.agent.response_queues[q2_key] = q2

                    # 3. Create a fresh Environment for this match
                    env = Environment(
                        payoff=self.agent.config.payoff,
                        max_rounds=self.agent.config.rounds,
                    )

                    jid_to_strategy = {p1_jid: strat_a, p2_jid: strat_b}

                    print(f"{tag} {strat_a} vs {strat_b} — starting {self.agent.config.rounds} rounds")

                    # 4. Execute round loop
                    for round_num in range(self.agent.config.rounds):
                        # Step 1: REQUEST — send action requests to both players
                        for pjid in [p1_jid, p2_jid]:
                            request_msg = Message(to=pjid)
                            request_msg.set_metadata("performative", "request")
                            request_msg.set_metadata("ontology", "REQUEST_ACTION")
                            request_msg.set_metadata("match_id", match_id)
                            request_msg.body = f"round_{round_num + 1}"
                            await self.send(request_msg)

                        # Step 2: RESPONSE — await ACTION_RESPONSE from each player's queue
                        try:
                            r1 = await asyncio.wait_for(q1.get(), timeout=30)
                            p1_action = r1.body
                        except asyncio.TimeoutError:
                            print(f"{tag} Warning: {strat_a} timeout in round {round_num + 1}, defaulting to D")
                            p1_action = "D"

                        try:
                            r2 = await asyncio.wait_for(q2.get(), timeout=30)
                            p2_action = r2.body
                        except asyncio.TimeoutError:
                            print(f"{tag} Warning: {strat_b} timeout in round {round_num + 1}, defaulting to D")
                            p2_action = "D"

                        # Step 3: COMPUTATION — apply actions to environment
                        payoffs = env.apply_actions(p1_jid, p1_action, p2_jid, p2_action)

                        # Step 4: FEEDBACK — send ROUND_RESULT to each player
                        result_p1 = Message(to=p1_jid)
                        result_p1.set_metadata("performative", "inform")
                        result_p1.set_metadata("ontology", "ROUND_RESULT")
                        result_p1.set_metadata("match_id", match_id)
                        result_p1.body = f"{p2_action},{payoffs['p1_payoff']},{payoffs['p2_payoff']}"
                        await self.send(result_p1)

                        result_p2 = Message(to=p2_jid)
                        result_p2.set_metadata("performative", "inform")
                        result_p2.set_metadata("ontology", "ROUND_RESULT")
                        result_p2.set_metadata("match_id", match_id)
                        result_p2.body = f"{p1_action},{payoffs['p2_payoff']},{payoffs['p1_payoff']}"
                        await self.send(result_p2)

                    # 5. Persist results to CSV
                    metrics = env.get_metrics()
                    state = env.get_state()

                    results_dir = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "..", "results",
                    )
                    filepath = os.path.join(results_dir, f"{strat_a}_vs_{strat_b}.csv")

                    CSVWriter.write_round_data(
                        filepath=filepath,
                        history=state.history,
                        metrics=metrics,
                        strategy_names=jid_to_strategy,
                    )

                    # 6. Log summary
                    print(
                        f"{tag} {strat_a} vs {strat_b} — DONE | "
                        f"Scores: {strat_a}={metrics.get('total_payoff_p1', 'N/A')}, "
                        f"{strat_b}={metrics.get('total_payoff_p2', 'N/A')} | "
                        f"Coop: {strat_a}={metrics.get('cooperation_rate_p1', 0):.0%}, "
                        f"{strat_b}={metrics.get('cooperation_rate_p2', 0):.0%}"
                    )

                    # 7. Teardown: remove queues (we keep the persistent player alive)
                    del self.agent.response_queues[q1_key]
                    del self.agent.response_queues[q2_key]
