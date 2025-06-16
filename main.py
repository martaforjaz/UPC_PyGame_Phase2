import threading
import time
import uvicorn
from src.settings import API_HOST, API_PORT

# --- Function to run the API server ---
def run_api_server():
    """
    Starts the FastAPI application using the Uvicorn ASGI server.
    The API server handles game logic requests and manages the physics engine
    via FastAPI's startup events (defined in src.api.api_endpoints).
    """
    uvicorn.run(
        "src.api.api_endpoints:app",  # Path to the FastAPI app instance
        host=API_HOST,                # Host address from settings
        port=API_PORT,                # Port number from settings
        log_level="info"              # Logging level for the server
    )

# --- Main execution block ---
if __name__ == "__main__":
    # 1. Start the API server in a separate background thread.
    #    Setting 'daemon=True' ensures the thread exits when the main program exits.
    print("Starting API server thread...")
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()

    # 2. Wait briefly to allow the API server and its startup events (physics engine)
    #    to initialize before starting the visualizer.
    print("Waiting for API server to initialize...")
    time.sleep(5) # Adjust this delay if needed

    # 3. Import the global game world instance.
    #    This instance is created in src/core/game_world.py and managed by the API server.
    print("Importing game world instance...")
    from src.core.game_world import game_world_instance

    # 4. Run the Pygame visualizer in the main thread.
    #    This function contains the main Pygame loop for drawing the game state.
    #    It blocks execution until the visualizer window is closed.
    print("Starting visualizer...")
    game_world_instance.run_visualizer()

    print("Visualizer closed. Main program exiting.")
