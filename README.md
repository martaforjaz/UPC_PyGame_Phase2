**Deadline Notice:** The first submission for agents must occur by June 1st. No changes will be accepted after June 19th. For further details, please refer to the Discussion Tab.

# UPC_PyGame Simulation

## Updates
- **Agent Mapping:** When players connect, the system now records the originating agent/program name along with the player UUID. This ensures that even when a player reconnects (receiving a new UUID), their statistics can be traced back to their originating agent.
- **Improved Statistics:** The survival lifetime of players is now precisely tracked and written to CSV and plot outputs for detailed post-game analysis.
- **Enhanced Game Restart:** The game restart functionality has been improved. When restarted, existing connections are maintained (with the same UUIDs) and players are reset for a fresh match.
- **Optimized API Endpoints:** Several API endpoints have been refined for smoother agent interactions and reliable state updates.

## Overview

UPC_PyGame is a 2D multiplayer arena shooter simulation that combines a robust FastAPI server with a realistic Pymunk physics engine. Players are represented by autonomous agents that connect via a simple HTTP API to control their uniquely colored spacecraft in a dynamic arena. A Pygame-based visualizer gives you real-time, eye-catching graphics of the action as players battle, dodge obstacles, and fire projectiles.

## Game Rules

The objective is to be the last surviving player in the arena.

- **Setup:** Connect as an agent to control your uniquely colored triangular spacecraft. The arena is filled with static circular obstacles and enclosed by energetic reflective boundaries.
- **Game Start:** Once all players in the pre-game lobby signal they are ready (using the Right Shift key), a countdown begins. When the countdown expires, the match commences.
- **Gameplay:** Navigate your spacecraft using directional thrust and rotational commands. Avoid collisions with obstacles and boundaries while engaging opponents. Skillful maneuvering and precise shooting are key to victory.
- **Combat:** Engage opponents by firing colored energy projectiles. Direct hits reduce an opponent’s health. Beware of spawn protection: newly spawned players have temporary invulnerability and shooting restrictions.
- **Elimination:** A player is eliminated when their health reaches zero. Their survival time (lifetime) is recorded for post-match statistics.
- **Winning:** The last player standing (with health above zero) wins the match.

## Features

- **Multiplayer Support:** Host multiple players controlled by independent agents through a unified FastAPI-based HTTP API.
- **Realistic 2D Physics:** Enjoy responsive and lifelike interactions powered by Pymunk, simulating movement, collisions, and ricochets.
- **Intuitive and Optimized API:** Easily control your spacecraft with endpoints for movement, rotation, shooting, and state queries. New parameters now capture agent origin to preserve your identity across game sessions.
- **Real-time Visualizer:** Watch the arena come alive with Pygame’s dynamic graphical interface.
- **Detailed Statistics & Analysis:** Game statistics such as shots fired, collisions, scores, and precise survival lifetimes are plotted and logged in CSV for ultimate post-match insights.
- **Strategic Obstacles & Boundaries:** Use static obstacles for tactical cover and navigate dynamic, bouncing boundaries for strategic gameplay.
- **Pre-Game Readiness & Spawn Protection:** Ensure all players are ready before the game starts. Receive temporary spawn protection for a fair start.
- **Enhanced Restart Functionality:** Restart the game while retaining connected players and mapping each to their originating agent for continuity in scoring.

## Architecture

The system consists of three main components:

1. **Game Server (FastAPI + Pymunk):**
    - Located in `src/api/` and `src/core/`.
    - Manages the central game loop, physics simulation, and object interactions.
    - Exposes a clear and optimized HTTP API for agent interactions (see [API Overview](#api-overview)).
    - Launched via `main.py`.

2. **Visualizer (Pygame):**
    - Embedded within `src/core/game_world.py` (using the `run_visualizer` method).
    - Renders the arena with smooth animations and detailed game statistics.
    - Runs in the main thread alongside the server.

3. **Agent (Client):**
    - Example implementations such as [`dummy1.py`](agents/dummy1.py) and [`dummy2.py`](agents/dummy2.py) demonstrate agent behavior.
    - Agents connect via HTTP, sending movement and action commands and receiving game state updates.
    - Each agent is now tagged with an origin (agent name) to maintain persistent identity even if a new UUID is assigned upon reconnection.

## Installation

1. **Clone the Repository:**
    ```bash
    git clone git@github.com:DaniFabi24/UPC_PyGame.git
    ```

2. **Create and Activate a Virtual Environment:**
    Open your terminal in the project root (where [`requirements.txt`](requirements.txt) is located) and run:
    ```bash
    python -m venv venv
    # On Linux/macOS:
    source venv/bin/activate
    # On Windows:
    .\venv\Scripts\activate
    ```

3. **Install Dependencies:**
    With the virtual environment activated, install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Simulation

You can run the simulation in two ways:

### Running Everything at Once (Using `run_game.sh` or `run_game_windows.bat`)

- **For Linux:**
    ```bash
    chmod +x run_game_linux.sh
    ./run_game_linux.sh
    ```
- **For Windows:**
    Double-click or run `run_game_windows.bat` in a command prompt.

These scripts will:
- Start the FastAPI server and Pygame visualizer.
- Wait for a few seconds to allow the server to initialize.
- Automatically detect and launch all agents from the `agents/` folder.

### Running Components Individually

1. **Start the Server and Visualizer:**
    ```bash
    python main.py
    ```
    Wait for the visualizer window and console logs showing the server status.

2. **Start Agent(s) in Separate Terminals:**
    ```bash
    python agents/dummy1.py
    python agents/dummy2.py
    ```
    Each agent will connect to the running game server.

## API Overview

The FastAPI server exposes the following key endpoints (base URL defined in [`src/settings.py`](src/settings.py)):

- **Player Management:**
  - `POST /connect`: Connects a new agent. The server now records the agent’s origin.
  - `POST /disconnect/{player_id}`: Disconnects the specified player.
- **State Retrieval:**
  - `GET /player/{player_id}/state`: Retrieves your specific state (velocity, health, etc.).
  - `GET /player/{player_id}/game-state`: Retrieves the overall game state.
  - `GET /player/{player_id}/scan`: Retrieves nearby objects and relative state information.
- **Gameplay Actions:**
  - `POST /player/{player_id}/thrust_forward`: Apply forward thrust.
  - `POST /player/{player_id}/thrust_backward`: Apply reverse thrust.
  - `POST /player/{player_id}/rotate_left`: Rotate left.
  - `POST /player/{player_id}/rotate_right`: Rotate right.
  - `POST /player/{player_id}/shoot`: Fire a projectile.
  - `POST /player/ready/{player_id}`: Signal readiness to start the game.
- **Game Management:**
  - `POST /game/restart`: Restart the game while preserving connected players and remapping them to their originating agents.

## Configuration

Adjust key game parameters in [`src/settings.py`](src/settings.py), such as:
- API host/port.
- Screen dimensions and FPS.
- Physics timestep.
- Player movement forces, rotation speed, maximum speed, and health.
- Projectile speed, size, lifetime, and damage.
- Game duration and scoring rules.

## Contributing

Feel free to report issues or suggest improvements using:
- [Issue Template](.github/ISSUE_TEMPLATE/general_issue.md)
- [Discussion Template](.github/DISCUSSIONS_TEMPLATE/general_discussion.md)

Happy gaming and coding – welcome to the best simulation ever!
