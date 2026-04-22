"""
Prisoner's Dilemma Tournament — Main Entrypoint

Starts the built-in SPADE XMPP server and creates a single
ManagerAgent that internally orchestrates the full tournament
(all unique strategy pairings, run concurrently).

Usage:
    python main.py
"""

import subprocess
import sys
import time
from uuid import uuid4

import spade

from config.server_config import XMPP_SERVER, PASSWORD
from config.simulation_config import SimulationConfig
from agents.manager_agent import ManagerAgent


def start_spade_server():
    """
    Launch the built-in SPADE XMPP server as a background subprocess.

    Returns:
        subprocess.Popen: The server process handle.
    """
    print("[Tournament] Starting SPADE XMPP server...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "spade", "run"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)  # allow server to initialize
    print("[Tournament] SPADE XMPP server started.")
    return proc


async def main():
    """
    Create a single ManagerAgent that runs the entire tournament.
    The ManagerAgent internally generates all strategy pairings,
    spawns PlayerAgents, and runs all matches concurrently.

    After the tournament, the agent stays alive with its web interface
    at http://127.0.0.1:10000/spade until the user presses Ctrl+C.
    """
    config = SimulationConfig()

    # Create and start the tournament ManagerAgent
    mgr_jid = f"manager_{uuid4()}@{XMPP_SERVER}"
    manager = ManagerAgent(mgr_jid, PASSWORD, config)
    await manager.start(auto_register=True)
    # await manager.tournament_runner.join()
    # Wait until agent is stopped (Ctrl+C triggers shutdown)
    await spade.wait_until_finished(manager)


if __name__ == "__main__":
    server_proc = start_spade_server()
    try:
        spade.run(main())
    finally:
        print("[Tournament] Shutting down SPADE server...")
        server_proc.terminate()
        server_proc.wait()
        print("[Tournament] Done.")
