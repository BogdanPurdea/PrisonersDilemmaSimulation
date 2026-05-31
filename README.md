# Prisoner's Dilemma MAS Tournament

This project is a Multi-Agent System (MAS) built using the [SPADE](https://github.com/javipalanca/spade) (Smart Python Agent Development Environment) framework. It simulates a round-robin Iterated Prisoner's Dilemma tournament among a set of autonomous agents, each employing a distinct strategy.

## Project Structure

The project has been restructured into a modular, package-based architecture:

```text
PrisonersDilemmaSimulation/
├── docs/
│   └── unused_code_report.md       # Documented API design constraints and unused variables
├── results/                        # Directory where CSV results are persisted
├── requirements.txt                # Project dependencies
└── src/
    ├── main.py                     # Entry point for the simulation
    ├── agents/                     # Agent package
    │   ├── __init__.py
    │   ├── manager/                # Manager agent module
    │   │   ├── __init__.py
    │   │   ├── manager_agent.py    # Defines ManagerAgent setup and presence hooks
    │   │   └── behaviours/
    │   │       ├── __init__.py
    │   │       ├── response_collector.py # Cyclic behavior for incoming action responses
    │   │       └── tournament_runner.py  # One-shot behavior orchestrating matchups & locks
    │   └── player/                 # Player agent module
    │       ├── __init__.py
    │       ├── player_agent.py     # Defines PlayerAgent properties and local history
    │       └── behaviours/
    │           ├── __init__.py
    │           ├── action_behaviour.py # Cyclic behavior handling action requests
    │           └── result_behaviour.py # Cyclic behavior processing round feedback
    ├── config/                     # Configuration files
    │   ├── __init__.py
    │   ├── server_config.py        # XMPP server host and credentials
    │   └── simulation_config.py    # Payoff matrix constraints and default active strategies
    ├── environment/                # Game environment state tracking
    │   ├── __init__.py
    │   ├── environment.py          # Payoff application and game metrics computation
    │   └── state.py                # Game state representation
    ├── persistence/                # Storage management
    │   ├── __init__.py
    │   └── csv_writer.py           # Standardized CSV exporter for match histories
    └── strategies/                 # Decision-making strategies registry
        ├── __init__.py
        ├── base.py                 # Abstract base class Strategy and Action enum
        └── catalog.py              # Concrete strategies implementations
```

## Architecture & Agent Design

The system is designed with highly decoupled and modular agents. Individual agent behaviors are extracted into dedicated sub-packages:

### `ManagerAgent`
The central orchestrator of the tournament.
*   **Persistent & Reusable Players**: Instead of creating and destroying agents dynamically, the tournament instantiates exactly **one persistent player agent per strategy** at startup.
*   **Concurrency & Locking**: Matches run concurrently using `asyncio.gather`. To prevent state contamination and race conditions on shared player agents, the `ManagerAgent` uses `asyncio.Lock`s. Before starting a match, the manager acquires locks for both participating agents in a consistent ordering (by sorted JID string) to avoid deadlocks.
*   **ResponseCollector**: A template-filtered cyclic behaviour (`performative="inform"`, `ontology="ACTION_RESPONSE"`) that intercepts player actions and routes them to match-specific `asyncio.Queue`s.
*   **TournamentRunner**: A one-shot behavior that generates combinations, executes matches, saves results to `.csv`, and holds the web inspector server open upon termination.

### `PlayerAgent`
An autonomous participant in the simulation representing a specific strategy.
*   **ActionBehaviour**: A cyclic behavior (`performative="request"`, `ontology="REQUEST_ACTION"`) that listens for action requests, queries its underlying `Strategy` decision logic, and transmits its choice back to the manager.
*   **ResultBehaviour**: A cyclic behavior (`performative="inform"`, `ontology="ROUND_RESULT"`) that receives round outcomes, parses opponents' moves, and updates local memory.

### `Environment`
A state tracker for each match. Applies the action pairs, computes the game-theoretic payoffs, and tracks step histories.

---

## Communication Protocol

For every round of a match, the agents follow this 4-step protocol:
1.  **Request** (`REQUEST_ACTION`): `ManagerAgent` $\rightarrow$ `PlayerAgents`. Includes the unique `match_id` so players register decisions for the correct game.
2.  **Response** (`ACTION_RESPONSE`): `PlayerAgents` $\rightarrow$ `ManagerAgent`. Returns either `C` (Cooperate) or `D` (Defect).
3.  **Computation**: `ManagerAgent` computes the round payoffs using the `Environment`.
4.  **Feedback** (`ROUND_RESULT`): `ManagerAgent` $\rightarrow$ `PlayerAgents`. Distributes opponent actions and payoffs to players to update their internal history.

---

## Available Strategies

The strategy catalog contains the following classic Prisoner's Dilemma policies:
*   `AlwaysCooperate`
*   `AlwaysDefect`
*   `Random`
*   `TitForTat`
*   `TitForTatWithForgiveness`
*   `GrimTrigger`
*   `WinStayLoseShift`
*   `SuspiciousTitForTat`
*   `Adaptive`

> [!NOTE]
> Participation is restricted strictly to strategies specified in `DEFAULT_STRATEGIES` inside `src/config/simulation_config.py`.

---

## Prerequisites

To run this simulation, you will need:
1.  **Python 3.9+**
2.  **SPADE**: `pip install spade`
3.  **An XMPP Server**: A local or remote XMPP server (e.g., Prosody).

---

## Configuration

1.  Specify XMPP Server credentials in `src/config/server_config.py`:
    ```python
    XMPP_SERVER = "localhost"
    PASSWORD = "your_password"
    ```
2.  Modify game-theoretic payoffs or participating strategies in `src/config/simulation_config.py`. The payoff configuration validates $T > R > P > S$ on startup.

---

## How to Run

1.  Ensure the SPADE XMPP server is running locally (e.g., via `spade run` or a local system service).
2.  Run the main tournament simulation script:
    ```bash
    cd PrisonersDilemmaSimulation
    python src/main.py
    ```
3.  Upon completion, individual game logs and summary metrics are saved as CSV files under the `results/` directory.
4.  **Web Inspection**: Once the tournament concludes, the manager hosts the SPADE web dashboard at:
    ```
    http://127.0.0.1:10000/spade
    ```
    Press `Ctrl+C` in the terminal to cleanly terminate the persistent player agents and shut down the XMPP connections.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
