# --- API Server Configuration ---
API_HOST = "127.0.0.1"              # Host address for the FastAPI server
API_PORT = 8000                     # Port number for the FastAPI server
API_URL = f"http://{API_HOST}:{API_PORT}"  # Base URL for API requests (used by agents)

# --- Visualizer / Screen Configuration ---
SCREEN_WIDTH = 800                # Width of the Pygame window in pixels
SCREEN_HEIGHT = 600               # Height of the Pygame window in pixels
FPS = 60                          # Target frames per second for the visualizer and physics updates

# --- Physics Engine Configuration ---
PHYSICS_DT = 1 / FPS              # Time step for each physics simulation update (delta time)

# --- Player Movement Parameters ---
PLAYER_THRUST = 5                 # Force applied when the player accelerates forward
PLAYER_ROTATION = 0.08            # Angular velocity applied when the player rotates (in radians per update)
PLAYER_MAX_SPEED = 100            # Maximum linear velocity the player can reach

# --- Player Attributes ---
PLAYER_START_HEALTH = 5           # Initial health points for each player
SCANNING_RADIUS = 150             # Radius within which a player can detect other objects (in pixels)

# --- Projectile Configuration ---
PROJECTILE_SPEED = 200            # Initial speed of a fired projectile
PROJECTILE_RADIUS = 4             # Radius of the projectile's physics shape and visual representation
PROJECTILE_LIFETIME_SECONDS = 3.0 # Duration in seconds before a projectile is automatically removed
PROJECTILE_DAMAGE = 1             # Amount of health points deducted when a projectile hits a player
ALLOW_FRIENDLY_FIRE = False       # If True, projectiles can damage the player who fired them

# --- Obstacle Configuration ---
OBSTACLE_DAMAGE = 1              # Amount of health points deducted when a player collides with an obstacle

# --- Countdown Configuration ---
COUNTDOWN_DURATION = 1.0         # Duration of the countdown (in seconds) before the game starts

# --- Score System Configuration ---
SCORE_CONFIG = {
    "kill_points": 10,           # Points awarded for killing another player
    "hit_points": 2,             # Points awarded for hitting another player with a projectile
    "collision_penalty": 5,      # Points deducted for colliding with another player
    "shot_penalty": 1,           # Points deducted for firing a shot
    "life_penalty": 1            # Points deducted for each remaining life point at game end
}

# --- Game State Configuration ---
MAX_GAME_DURATION = 30           # Maximum duration of the game in seconds
PLOT_OUTPUT = False              # If True, game statistics plots are saved upon game end

# # --- Game State Configuration ---
# GAME_STATES = {
#     "WAITING": 0,              # Waiting for players to join
#     "COUNTDOWN": 1,            # Countdown before the game starts
#     "RUNNING": 2,              # Game is currently running
#     "ENDED": 3                 # Game has ended
# }
# # --- Game Over Configuration ---
# GAME_OVER_DURATION = 3.0     # Duration in seconds before the game resets after it ends
