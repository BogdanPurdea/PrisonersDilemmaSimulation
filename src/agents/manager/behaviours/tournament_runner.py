"""
TournamentRunner — OneShotBehaviour for the ManagerAgent.

Orchestrates the full Prisoner's Dilemma tournament:
  1. Generates all unique strategy pairings via itertools.combinations.
  2. Acquires per-player asyncio.Locks (consistent ordering to avoid deadlocks).
  3. Registers per-match/per-player asyncio.Queues for response routing.
  4. Runs all matches concurrently with asyncio.gather.
  5. Persists per-match results to CSV via CSVWriter.
  6. Keeps the ManagerAgent alive after the tournament for SPADE Web UI inspection.

Communication protocol per round (4-step):
    Step 1 REQUEST  — Manager → Players  [REQUEST_ACTION]
    Step 2 RESPONSE — Players → Manager  [ACTION_RESPONSE]  (via ResponseCollector queues)
    Step 3 COMPUTE  — Manager applies actions to Environment
    Step 4 FEEDBACK — Manager → Players  [ROUND_RESULT]

Expected agent attributes (set by ManagerAgent.__init__ / setup):
    agent.config            SimulationConfig
    agent.strategy_to_jid   dict[str, str]
    agent.player_agents     dict[str, PlayerAgent]
    agent.player_locks      dict[str, asyncio.Lock]
    agent.response_queues   dict[str, asyncio.Queue]
"""

import asyncio
import itertools
import os

from spade.behaviour import OneShotBehaviour
from spade.message import Message

from environment.environment import Environment
from persistence.csv_writer import CSVWriter
from strategies.catalog import STRATEGY_REGISTRY

try:
    from spade.presence import PresenceType, PresenceShow, PresenceInfo
except ImportError:
    PresenceType = None
    PresenceShow = None
    PresenceInfo = None


class TournamentRunner(OneShotBehaviour):
    """
    Orchestrates the full tournament as a OneShotBehaviour.

    Generates all unique strategy pairings, then runs all matches
    concurrently using asyncio.gather.  Each match gets its own
    Environment instance and dedicated response queues.
    """

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self):
        """Generate pairings and run all matches concurrently."""
        strategy_names = [s for s in self.agent.config.strategies if s in STRATEGY_REGISTRY]
        pairings = list(itertools.combinations(strategy_names, 2))

        print(f"\n[Manager] Starting {len(pairings)} matches concurrently...\n")

        tasks = [
            self._run_match(strat_a, strat_b, idx + 1, len(pairings))
            for idx, (strat_a, strat_b) in enumerate(pairings)
        ]
        await asyncio.gather(*tasks)

        print(f"\n{'='*60}")
        print(f"  Tournament complete! {len(pairings)} matches played.")
        print(f"  Results written to results/ directory.")
        print(f"{'='*60}")

    # ------------------------------------------------------------------
    # Lifecycle hook
    # ------------------------------------------------------------------

    async def on_end(self):
        """
        Keep the ManagerAgent alive after the tournament so the user can
        inspect results via the SPADE Web UI at http://127.0.0.1:10000/spade.
        Shuts down cleanly on Ctrl+C.
        """
        print("\n[Manager] Tournament finished. Web interface is running.")

        # Patch contacts to prevent SPADE Web UI PresenceNotFound crash
        # (stopped players may not have finalised their presence object)
        if PresenceType is not None:
            for c in self.agent.presence.contacts.values():
                if c.current_presence is None:
                    c.update_presence(
                        "default",
                        PresenceInfo(PresenceType.UNAVAILABLE, PresenceShow.NONE)
                    )

        print("[Manager] Inspect results at http://127.0.0.1:10000/spade")
        print("[Manager] All player agents remain online for inspection.")
        print("[Manager] Press Ctrl+C to shut down.\n")

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

        # Cleanly stop all persistent PlayerAgents
        print("[Manager] Shutting down persistent PlayerAgents...")
        for player in self.agent.player_agents.values():
            await player.stop()

        await self.agent.stop()

    # ------------------------------------------------------------------
    # Match execution
    # ------------------------------------------------------------------

    async def _run_match(
        self,
        strat_a: str,
        strat_b: str,
        match_idx: int,
        total: int,
    ):
        """
        Run a single match between two strategies.

        Steps:
        1. Look up the persistent PlayerAgents via strategy name.
        2. Acquire per-player locks (consistent order to prevent deadlocks).
        3. Register per-match/per-player asyncio.Queues for response routing.
        4. Execute the round loop (4-step REQUEST → RESPONSE → COMPUTE → FEEDBACK).
        5. Persist CSV results.
        6. Tear down match-specific queues and release locks.

        Args:
            strat_a:   Name of strategy for player 1.
            strat_b:   Name of strategy for player 2.
            match_idx: Match number (1-based, for logging).
            total:     Total number of matches in the tournament.
        """
        from uuid import uuid4

        tag = f"[Match {match_idx}/{total}]"
        match_id = f"match_{uuid4()}"

        # 1. Lookup JIDs for strategies
        p1_jid = self.agent.strategy_to_jid[strat_a]
        p2_jid = self.agent.strategy_to_jid[strat_b]

        print(f"{tag} {strat_a} vs {strat_b} — waiting for player availability...")

        # Acquire locks in a consistent order to prevent deadlocks
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
                    "..", "..", "..", "..", "results",
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

                # 7. Teardown: remove queues (persistent players stay alive)
                del self.agent.response_queues[q1_key]
                del self.agent.response_queues[q2_key]
