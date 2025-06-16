from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
from src.core.game_world import game_world_instance
from fastapi import Request
from ..settings import PHYSICS_DT

app = FastAPI()

# Allow cross-origin requests (for client/websocket connections)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Cooldown Management ---
# Simple in-memory storage for cooldowns.  Consider Redis for production.
# Structure: { "player_id": { "endpoint_name": last_call_timestamp }}
player_cooldowns = {}

# Cooldown durations (in seconds)
COOLDOWN_SCAN_ENVIRONMENT = 0.5
COOLDOWN_PLAYER_STATE = 0.5
COOLDOWN_GAME_STATE = 0.5
COOLDOWN_SHOOT = 0.1

def check_cooldown(player_id: str, endpoint_name: str, cooldown_duration: float):
    """
    Checks and updates the cooldown for a player and endpoint.

    Args:
        player_id: The ID of the player.
        endpoint_name: The name of the endpoint being accessed.
        cooldown_duration: The cooldown duration in seconds.

    Returns:
        True if the cooldown has passed.

    Raises:
        HTTPException: (429 Too Many Requests) if the cooldown is still active.
    """
    now = time.time()
    if player_id not in player_cooldowns:
        player_cooldowns[player_id] = {}

    last_call = player_cooldowns[player_id].get(endpoint_name, 0)

    if now - last_call < cooldown_duration:
        remaining_cooldown = cooldown_duration - (now - last_call)
        raise HTTPException(
            status_code=429,  # Too Many Requests
            detail=f"Cooldown active: {endpoint_name}. Wait {remaining_cooldown:.2f} seconds.",
        )
    player_cooldowns[player_id][endpoint_name] = now
    return True  # Cooldown passed

@app.on_event("startup")
async def startup_event():
    """
    Startup event handler that starts the physics engine.

    This event runs when the FastAPI application starts. It initializes and starts the
    physics loop (using PHYSICS_DT as the delta time) in the game world.
    """
    print("Startup event: Starting physics engine")
    game_world_instance.start_physics_engine(dt=PHYSICS_DT)
    print("Startup event: Physics engine successfully started")

@app.get("/")
def read_root():
    """
    Root endpoint.

    Returns a simple welcome message.
    """
    return {"message": "Welcome to the UPC Game API with WebSockets!"}

@app.get("/player/{player_id}/scan")
async def get_scan_environment(player_id: str):
    """
    Retrieves the game state relative to a specific player.

    Args:
        player_id: The ID of the player.

    Returns:
        The scan data.

    Raises:
        HTTPException: (429) if the cooldown is active.
    """
    check_cooldown(player_id, "scan_environment", COOLDOWN_SCAN_ENVIRONMENT)
    scan_data = game_world_instance.scan_environment(player_id)
    if scan_data is None:
        pass
    return scan_data

@app.get("/player/{player_id}/state")
async def get_player_own_state(player_id: str):
    """
    Retrieves the state of a specific player.

    Args:
        player_id: The ID of the player.

    Returns:
        The player's state data.

    Raises:
        HTTPException: (429) if the cooldown is active, (404) if player not found.
    """
    check_cooldown(player_id, "state", COOLDOWN_PLAYER_STATE)
    state_data = game_world_instance.player_state(player_id)
    if state_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Player {player_id} not found or no state available.",
        )
    return state_data

@app.get("/player/{player_id}/game-state")
async def get_overall_game_state(player_id: str):
    """
    Retrieves the overall game state.

    Args:
        player_id: The ID of the player.  (Currently not used, but kept for consistency).

    Returns:
        The overall game state.

    Raises:
        HTTPException: (429) if the cooldown is active, (404) if game state cannot be retrieved.
    """
    check_cooldown(player_id, "game_state", COOLDOWN_GAME_STATE)
    state_data = game_world_instance.game_state(player_id)
    if state_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not retrieve game state for player {player_id}.",
        )
    return state_data

@app.post("/player/ready/{player_id}")
async def ready_to_play(player_id: str):
    """
    Sets a player's readiness status.

    Args:
        player_id: The ID of the player.

    Returns:
        A message indicating the player is ready.

    Raises:
        HTTPException: (404) if the player is not found.
    """
    if player_id not in game_world_instance.players:
        raise HTTPException(status_code=404, detail="Player not found")
    game_world_instance.player_ready(player_id)
    return {"message": f"Player {player_id} is ready to play"}

@app.post("/connect")
async def connect_player(request: Request):
    """
    Connects a new player to the game.
    Returns:
        The new player's ID.
    """
    data = await request.json()
    agent_name = data.get("agent_name") if isinstance(data, dict) else None
    player_id = game_world_instance.add_player(agent_name=agent_name)  # <-- agent_name übergeben!
    return {"player_id": player_id}

@app.post("/disconnect/{player_id}")
async def disconnect_player(player_id: str):
    """
    Disconnects a player from the game.

    Args:
        player_id: The ID of the player to disconnect.

    Returns:
        A message confirming disconnection.

    Raises:
        HTTPException: (404) if the player is not found.
    """
    if player_id not in game_world_instance.players:
        raise HTTPException(status_code=404, detail="Player not found")
    game_world_instance.remove_player(player_id)
    return {"message": f"Player {player_id} disconnected"}

@app.post("/player/{player_id}/thrust_forward")
async def thrust_forward(player_id: str):
    """
    Applies forward thrust to a player.

    Args:
        player_id: The ID of the player.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: (404) if the player is not found.
    """
    if player_id not in game_world_instance.players:
        raise HTTPException(status_code=404, detail="Player not found")
    game_world_instance.positive_player_thrust(player_id)
    return {"message": f"Player {player_id} thrust forward"}

@app.post("/player/{player_id}/rotate_right")
async def rotate_right(player_id: str):
    """
    Rotates a player to the right.

    Args:
        player_id: The ID of the player.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: (404) if the player is not found.
    """
    if player_id not in game_world_instance.players:
        raise HTTPException(status_code=404, detail="Player not found")
    game_world_instance.right_player_rotation(player_id)
    return {"message": f"Player {player_id} rotated right"}

@app.post("/player/{player_id}/shoot")
async def shoot(player_id: str):
    """
    Initiates a shooting action for a player.

    Args:
        player_id: The ID of the player.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: (404) if the player is not found, (429) if cooldown active.
    """
    if player_id not in game_world_instance.players:
        raise HTTPException(status_code=404, detail="Player not found")
    check_cooldown(player_id, "shoot", COOLDOWN_SHOOT)
    game_world_instance.shoot(player_id)
    return {"message": f"Player {player_id} shot"}

@app.post("/player/{player_id}/thrust_backward")
async def thrust_backward(player_id: str):
    """
    Applies backward thrust to a player.

    Args:
        player_id: The ID of the player.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: (404) if the player is not found.
    """
    if player_id not in game_world_instance.players:
        raise HTTPException(status_code=404, detail="Player not found")
    game_world_instance.negative_player_thrust(player_id)
    return {"message": f"Player {player_id} thrust backward"}

@app.post("/player/{player_id}/rotate_left")
async def rotate_left(player_id: str):
    """
    Rotates a player to the left.

    Args:
        player_id: The ID of the player.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: (404) if the player is not found.
    """
    if player_id not in game_world_instance.players:
        raise HTTPException(status_code=404, detail="Player not found")
    game_world_instance.left_player_rotation(player_id)
    return {"message": f"Player {player_id} rotated left"}

@app.post("/game/restart")
async def restart_game_endpoint():
    """
    Resets the game to its initial state.
    All players will be disconnected, and the game world will be reset.
    """
    game_world_instance.restart_game()
    # Optionally, clear cooldowns if they should reset with the game
    # player_cooldowns.clear()
    return {"message": "Game restart initiated. World has been reset."}