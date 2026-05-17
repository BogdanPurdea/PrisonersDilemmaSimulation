# Prisoner's Dilemma MAS Tournament

This project is a Multi-Agent System (MAS) built using the [SPADE](https://github.com/javierggg/spade) (Smart Python Agent Development Environment) framework. It simulates a round-robin Iterated Prisoner's Dilemma tournament among a set of autonomous agents, each employing a distinct strategy.

## Architecture

The system consists of the following core components:

*   **`ManagerAgent`**: The central orchestrator of the tournament. It dynamically pairs agents, manages the environment state for each match, coordinates the synchronization of rounds (using a 4-step communication protocol), computes payoffs, and saves the final results.
*   **`PlayerAgent`**: Autonomous agents that represent the players in the simulation. Each `PlayerAgent` is assigned a specific strategy and communicates with the `ManagerAgent` to deliberate and submit actions ("C" for Cooperate, "D" for Defect) based on the history of the current match.
*   **`Environment`**: A state manager for each individual match. It applies the actions chosen by the agents, computes the game-theoretic payoffs (T, R, P, S), and keeps track of the match history and scores.
*   **Strategies**: The decision-making logic used by the agents. The available strategies are defined in the configuration and loaded from the strategy registry.

### Communication Protocol

For every round of a match, the agents follow this protocol:
1.  **Request**: `ManagerAgent` → `PlayerAgents` (`REQUEST_ACTION`)
2.  **Response**: `PlayerAgents` → `ManagerAgent` (`ACTION_RESPONSE` containing "C" or "D")
3.  **Computation**: `ManagerAgent` computes the payoffs using the `Environment`.
4.  **Feedback**: `ManagerAgent` → `PlayerAgents` (`ROUND_RESULT` containing opponent's action and payoffs).

## Available Strategies

The tournament includes several classic Prisoner's Dilemma strategies:
*   `AlwaysCooperate`
*   `AlwaysDefect`
*   `Random`
*   `TitForTat`
*   `TitForTatWithForgiveness`
*   `GrimTrigger`
*   `WinStayLoseShift`
*   `SuspiciousTitForTat`
*   `Adaptive`

*Note: You can configure which strategies participate by editing `DEFAULT_STRATEGIES` in `src/config/simulation_config.py`.*

## Prerequisites

To run this simulation, you will need:

1.  **Python 3.9+**
2.  **SPADE**: `pip install spade`
3.  **An XMPP Server**: SPADE agents communicate over XMPP. You need a local or remote XMPP server (e.g., Prosody, Openfire, or a public server).

## Configuration

Before running the project, make sure your XMPP server credentials are set correctly.

Ensure you have a file at `src/config/server_config.py` that specifies the XMPP server and password for your agents:
```python
XMPP_SERVER = "your-xmpp-server.local"
PASSWORD = "your-agent-password"
```

You can also tweak the tournament settings (like the number of rounds or the payoff matrix) in `src/config/simulation_config.py`.

## How to Run

1.  Open the SPADE local XMPP server:
    ```bash
    spade run
    ```
    Or use an existing XMPP server.

2.  Run the main simulation script:
    ```bash
    cd PrisonersDilemmaSimulation
    python src/main.py
    ```

3.  The simulation will start, establishing connections for the `ManagerAgent` and spawning all the necessary `PlayerAgent`s. Matches will be executed concurrently, and progress will be printed to the console.

4.  **Results**: Upon completion, the round-by-round history and aggregated metrics (cooperation rates, total payoffs) for each match will be written as CSV files to the `results/` directory.

5.  **Web Inspection**: Once the tournament concludes, the script pauses and hosts the SPADE web interface. You can inspect the agents and their presence status by opening your browser to:
    ```
    http://127.0.0.1:10000/spade
    ```
    Press `Ctrl+C` in your terminal to shut down the agents and exit.
