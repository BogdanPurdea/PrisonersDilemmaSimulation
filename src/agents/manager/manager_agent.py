"""
ManagerAgent — Central tournament coordinator for the Prisoner's Dilemma.

Architecture:
  - ResponseCollector (CyclicBehaviour + Template: ontology=ACTION_RESPONSE)
    Routes incoming player responses to per-player asyncio.Queues.
    → agents/manager/behaviours/response_collector.py
  - TournamentRunner (OneShotBehaviour)
    Generates all unique strategy pairings, runs all matches CONCURRENTLY
    via asyncio.gather. Each match has its own Environment and queues.
    → agents/manager/behaviours/tournament_runner.py

Communication protocol per round:
  1. Request:     Manager → Players [REQUEST_ACTION]
  2. Response:    Players → Manager [ACTION_RESPONSE]
  3. Computation: Manager applies actions to Environment
  4. Feedback:    Manager → Players [ROUND_RESULT]
"""

import asyncio
import itertools
from uuid import uuid4

from spade.agent import Agent
from spade.template import Template

from agents.manager.behaviours.response_collector import ResponseCollector
from agents.manager.behaviours.tournament_runner import TournamentRunner

from config.server_config import XMPP_SERVER, PASSWORD
from strategies.catalog import STRATEGY_REGISTRY
from agents.player.player_agent import PlayerAgent

try:
    from spade.presence import PresenceType, PresenceShow
except ImportError:
    PresenceType = None
    PresenceShow = None


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
        self.add_behaviour(ResponseCollector(), response_template)

        # --- TournamentRunner: orchestrates all matches concurrently ---
        self.tournament_runner = TournamentRunner()
        self.add_behaviour(self.tournament_runner)

        # --- Web GUI: start the built-in SPADE web interface ---
        self.web.start(hostname="127.0.0.1", port="10000")
        print("[Manager] Web interface started at http://127.0.0.1:10000/spade")

    # Behaviours are defined in their own modules:
    #   agents/manager/behaviours/response_collector.py  → ResponseCollector
    #   agents/manager/behaviours/tournament_runner.py   → TournamentRunner
    # They are imported at the top of this file and registered in setup() above.
