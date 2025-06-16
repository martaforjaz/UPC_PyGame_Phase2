import pymunk
import pygame
import threading
import asyncio
import uuid
import math
import random
import time
import os
import csv
import matplotlib.pyplot as plt
from .game_objects import *
from ..settings import *
from .score_system import ScoreSystem
from ..settings      import SCORE_CONFIG, MAX_GAME_DURATION


# Predefined player colors used cyclically when creating new players.
PLAYER_COLORS = [
    (255, 0, 0),     # Red
    (0, 191, 255),   # Deep Sky Blue
    (50, 205, 50),   # Lime Green
    (255, 255, 0),   # Yellow
    (0, 255, 255),   # Cyan
    (255, 0, 255),   # Magenta
    (255, 165, 0),   # Orange
    (238, 130, 238), # Violet
    (255, 255, 255), # White
    (192, 192, 192)  # Silver
]

class GameWorld:
    """
    The GameWorld class encapsulates the entire state of the game.
    
    It manages the physics simulation (using pymunk), rendering (using pygame), 
    players, obstacles, projectiles, and power-ups. It also provides methods to 
    add/remove players/objects, update the simulation, and run the visualizer.
    """
    def __init__(self, width, height):
        """
        Initializes the GameWorld instance.
        
        Args:
            width (int): Width of the game world (and visualization screen).
            height (int): Height of the game world.
        """
        self.width = width
        self.height = height
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)
        self.objects = []    # List of non-player objects (obstacles, projectiles, power-ups, etc.)
        self.players = {}    # Dictionary mapping player IDs to player objects
        self.shot_count = 0  # Total number of shots fired
        self.player_collisions = 0  # Counter for collisions involving players
        self._physics_task = None   # Holds the asyncio task for the physics loop
        self.is_running = False     # Flag indicating whether the physics loop is active
        self.next_color_index = 0   # Index to select the next player color from PLAYER_COLORS
        self.game_started = False # Flag indicating whether the game has started
        self.waiting_for_players = True # Flag indicating whether the game is waiting for players to join
        self.score_sys = ScoreSystem(SCORE_CONFIG) # Initialize the score system with the provided configuration from settings.py
        # NEU: Countdown-Zustandsvariablen
        self.countdown_active = False
        self.countdown_seconds_remaining = 0.0

        self.add_borders()  # Create and add border segments to the physics space
        self.initialize_world_objects() # *** HINDERNISSE SOFORT INITIALISIEREN ***
        self.initialize_collision_handlers() # Kollisionshandler auch früh initialisieren

    def add_player(self, given_player_id=None, agent_name=None):
        """
        Creates and adds a new player to the game.
        
        Attempts to find a safe spawn position (without collisions).
        If given_player_id is provided, it is used; otherwise, a new UUID is generated.
        
        Returns:
            str or None: The player's unique ID if spawn is successful; otherwise, None.
        """
        if self.game_started:
            print("Game has already started. No new players can join.")
            return None

        player_id = given_player_id if given_player_id is not None else str(uuid.uuid4())
        max_attempts = 10
        safe_spawn_pos = None
        player_radius = 15

        for attempt in range(max_attempts):
            if attempt == 0:
                potential_pos = pymunk.Vec2d(self.width / 2, self.height / 2)
            else:
                pad = player_radius + 10
                potential_pos = pymunk.Vec2d(
                    random.uniform(pad, self.width - pad),
                    random.uniform(pad, self.height - pad)
                )

            temp_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            temp_body.position = potential_pos
            temp_shape = pymunk.Poly(temp_body, [
                (player_radius, 0),
                (-player_radius, player_radius),
                (-player_radius, -player_radius)
            ])
            temp_shape.collision_type = 1

            collision_found = False
            for info in self.space.shape_query(temp_shape):
                if info.shape and info.shape.collision_type in [1, 2]:
                    collision_found = True
                    print(f"Spawn attempt {attempt+1} at {potential_pos} failed due to collision.")
                    break

            if not collision_found:
                safe_spawn_pos = potential_pos
                print(f"Spawn attempt {attempt+1}: Safe position at {safe_spawn_pos} found.")
                break

        if safe_spawn_pos:
            player_color = PLAYER_COLORS[self.next_color_index % len(PLAYER_COLORS)]
            self.next_color_index += 1
            new_player = Triangle(safe_spawn_pos, color=player_color, game_world=self)
            new_player.player_id = player_id
            if agent_name:
                new_player.agent_name = agent_name  # <-- Name setzen!
            self.players[player_id] = new_player
            self.score_sys.register_agent(player_id)
            print(f"Player added with ID: {player_id} (Name: {getattr(new_player, 'agent_name', player_id[:6])}) at {safe_spawn_pos} with color {player_color}.")
            return player_id
        else:
            print(f"Error: No safe spawn position found after {max_attempts} attempts.")
            return None
        
        

    def remove_player(self, player_id):
        """
        Removes a player from the game using its ID.
        
        Delegates the removal process to the player's own remove_from_world method.
        
        Args:
            player_id (str): The unique identifier of the player to remove.
        """
        if player_id in self.players:
            player_to_remove = self.players[player_id]
            print(f"Attempting to remove player {player_id}...")
            player_to_remove.remove_from_world()
            print(f"Player remove process initiated for ID: {player_id}")
        else:
            print(f"Attempted to remove non-existent player ID: {player_id}")

    def add_object(self, obj):
        """
        Adds a game object (obstacle, projectile, power-up, etc.) to the world.
        
        Args:
            obj: The game object to add.
        """
        if obj not in self.objects:
            self.objects.append(obj)

    def add_borders(self):
        """
        Creates border segments around the game world and adds them to the physics space.
        
        The borders are used to contain the game objects inside the visible area.
        """
        static_body = self.space.static_body
        borders = [
            pymunk.Segment(static_body, (0, 0), (self.width, 0), 1),              # Bottom border
            pymunk.Segment(static_body, (0, self.height), (self.width, self.height), 1),  # Top border
            pymunk.Segment(static_body, (0, 0), (0, self.height), 1),               # Left border
            pymunk.Segment(static_body, (self.width, 0), (self.width, self.height), 1)      # Right border
        ]
        for border in borders:
            border.elasticity = 1.0  # Perfect bounce
            border.friction = 0.0
            border.collision_type = 3  # Collision type for borders
            self.space.add(border)

    def initialize_world_objects(self):
        """Initializes obstacles. Called early.""" # Geändert: Wird jetzt früh aufgerufen
        # Sicherstellen, dass Objekte nur einmal hinzugefügt werden, falls diese Methode
        # aus irgendeinem Grund mehrmals aufgerufen werden könnte.
        # Da es jetzt im __init__ ist, ist die "if not self.objects" Bedingung
        # für Hindernisse nicht mehr so kritisch, aber schadet nicht.
        existing_obstacle_count = sum(1 for obj in self.objects if isinstance(obj, CircleObstacle))
        if existing_obstacle_count == 0:
            arena_obstacles = [
                CircleObstacle([150, 150], 40, game_world=self),
                CircleObstacle([650, 150], 40, game_world=self),
                CircleObstacle([150, 450], 40, game_world=self),
                CircleObstacle([650, 450], 40, game_world=self),
                CircleObstacle([400, 150], 30, game_world=self),
                CircleObstacle([400, 450], 30, game_world=self),
                CircleObstacle([250, 300], 50, game_world=self),
                CircleObstacle([550, 300], 50, game_world=self),
            ]
            for obstacle in arena_obstacles:
                self.add_object(obstacle)
            print("Game world objects (obstacles) initialized.")
        else:
            print("Obstacles already initialized.")

    def initialize_collision_handlers(self):
        """Initializes collision handlers. Can be called early."""
        from .game_objects import setup_collision_handlers
        setup_collision_handlers(self.space, self)
        print("Collision handlers initialized.")

    def check_if_all_players_ready(self):
        """
        Prüft, ob alle verbundenen Spieler bereit sind.
        Wenn ja und noch kein Countdown läuft, wird der Countdown gestartet.
        Diese Methode blockiert NICHT mehr mit time.sleep.
        """
        if not self.players: # Keine Spieler, also nicht bereit und kein Countdown
            self.waiting_for_players = True
            self.game_started = False
            self.countdown_active = False
            return False

        all_currently_ready = all(player.ready for player in self.players.values())

        if all_currently_ready and self.waiting_for_players and not self.countdown_active:
            # Alle Bedingungen erfüllt, um den Countdown zu STARTEN
            print("All players ready! Starting countdown...")
            self.countdown_active = True
            self.countdown_seconds_remaining = COUNTDOWN_DURATION
            self.waiting_for_players = False # Wechsel in den Countdown-Modus
            for player in self.players.values():
                player.spawn_protection_until = time.time() + player.spawn_protection_duration + COUNTDOWN_DURATION
        elif not all_currently_ready and self.countdown_active:
            # Jemand wurde während des Countdowns unready (z.B. Disconnect)
            print("Not all players ready during countdown. Resetting to waiting state.")
            self.countdown_active = False
            self.waiting_for_players = True
            # game_started bleibt False
        elif not all_currently_ready and not self.game_started:
            # Allgemeiner Fall: Nicht alle bereit, kein Countdown, Spiel nicht gestartet -> Wartezustand sicherstellen
            self.waiting_for_players = True
            self.game_started = False # Sicherstellen, dass Spiel nicht als gestartet markiert ist

        return all_currently_ready

    def player_ready(self, player_id):
        player = self.players.get(player_id)
        if player:
            if self.game_started:
                print(f"Player {player_id} tried to set ready, but game has already started.")
                return

            if not player.ready:
                player.ready = True
                print(f"Player {player_id} is now ready.")
                self.check_if_all_players_ready() # Prüfen, ob Countdown gestartet werden kann
            else:
                print(f"Player {player_id} was already ready.")
        else:
            print(f"Player_ready called for non-existent player {player_id}")

    def positive_player_thrust(self, player_id):
        """
        Applies a forward thrust to the specified player.
        
        Args:
            player_id (str): The identifier of the player.
        """
        if not self.game_started: return # Spiel noch nicht gestartet
        player = self.players.get(player_id)
        if player:
            radians = player.body.angle
            thrust_vector = pygame.math.Vector2(1, 0).rotate_rad(radians) * PLAYER_THRUST
            player.body.velocity += thrust_vector

    def negative_player_thrust(self, player_id):
        """
        Applies a reverse thrust (braking) to the specified player.
        
        Args:
            player_id (str): The identifier of the player.
        """
        if not self.game_started: return
        player = self.players.get(player_id)
        if player:
            radians = player.body.angle
            thrust_vector = pygame.math.Vector2(1, 0).rotate_rad(radians) * (-PLAYER_THRUST)
            player.body.velocity += thrust_vector

    def right_player_rotation(self, player_id):
        """
        Rotates a player to the right.
        
        Args:
            player_id (str): The identifier of the player.
        """
        if not self.game_started: return
        player = self.players.get(player_id)
        if player:
            player.body.angular_velocity += PLAYER_ROTATION

    def left_player_rotation(self, player_id):
        """
        Rotates a player to the left.
        
        Args:
            player_id (str): The identifier of the player.
        """
        if not self.game_started: return
        player = self.players.get(player_id)
        if player:
            player.body.angular_velocity -= PLAYER_ROTATION

    def shoot(self, player_id):
        """
        Initiates a shooting action for the specified player.
        
        Checks for spawn protection; if allowed, spawns a projectile in front of the player.
        
        Args:
            player_id (str): The identifier of the player who is firing.
        """
        if not self.game_started:
            print(f"Player {player_id} tried to shoot, but game has not started.")
            return
        player = self.players.get(player_id)
        if player:
            # Prevent shooting when spawn protection is active.
            if time.time() < player.spawn_protection_until:
                print(f"Player {player_id} cannot shoot during spawn protection.")
                return
            
            # --- Count shots per player ---
            if hasattr(player, "shots_fired"):
                player.shots_fired += 1
            else:
                player.shots_fired = 1

            player_angle_rad = player.body.angle
            offset_distance = player.radius + PROJECTILE_RADIUS + 1
            start_offset_x = math.cos(player_angle_rad) * offset_distance
            start_offset_y = math.sin(player_angle_rad) * offset_distance
            start_pos = player.body.position + pymunk.Vec2d(start_offset_x, start_offset_y)

            # Use the player's color for the projectile.
            projectile = Projectile(
                position=start_pos,
                angle_rad=player.body.angle,
                owner=player,
                color=player.color,
                game_world=self
            )
            self.increment_shot_count()
            print(f"Shot fired by {player_id}! Total shots: {self.shot_count}")
            self.score_sys.on_shot(player_id) # Register shot in the score system

    def increment_shot_count(self):
        """
        Increments the shot counter, tracking the number of projectiles fired.
        """
        self.shot_count += 1

    def update(self, dt):
        """
        Updates the physics simulation and game objects.
        
        Steps the physics engine, updates angular velocities, and calls each object's update method.
        
        Args:
            dt (float): Delta time since the last update.
        """

        if self.game_started:
            if not hasattr(self, "start_time"):
                self.start_time = time.time()
            elif time.time() - self.start_time > MAX_GAME_DURATION:
                # Maximale Spielzeit erreicht: Restleben bestrafen und Spiel neu starten
                remaining = {pid: p.health for pid, p in self.players.items()}
                self.score_sys.on_game_end(remaining)
                self.restart_game()
                return  # Early-exit, damit nicht mehr weiter upgedatet wird
    
        self.space.step(dt)
        for player in self.players.values():
            player.body.angular_velocity *= 1 - 0.1 * PHYSICS_DT
        for shape in self.space.shapes:
            if hasattr(shape, "sprite_ref"):
                shape.sprite_ref.update(dt)

        # Countdown-Logik
        if self.countdown_active:
            self.countdown_seconds_remaining -= dt
            if self.countdown_seconds_remaining <= 0:
                self.countdown_seconds_remaining = 0 # Verhindere negative Werte
                print("Countdown timer reached zero. Final check for player readiness...")
                # Finale Prüfung: Sind ALLE aktuell verbundenen Spieler bereit?
                if self.players and all(p.ready for p in self.players.values()):
                    self.waiting_for_players = False
                    self.game_started = True
                    self.countdown_active = False
                    self.start_time = time.time()
                    for player in self.players.values():
                        player.lifetime = self.start_time
                else:
                    print("Not all players ready after countdown (or no players left). Resetting to waiting state.")
                    self.countdown_active = False
                    self.waiting_for_players = True # Zurück zum Wartezustand
                    # game_started bleibt False
            # Der Visualizer zeigt countdown_seconds_remaining an

        if not self.players:
            self.game_started = False
            self.waiting_for_players = True
            self.countdown_active = False
            self.countdown_seconds_remaining = 0.0
            self.shot_count = 0
            self.player_collisions = 0
            self.next_color_index = 0

    async def _run_physics_loop(self, dt):
        """
        Runs the continuous physics simulation loop asynchronously.
        
        This method is intended to be run as an asyncio task. It repeatedly calls update()
        and then sleeps for the given delta time.
        
        Args:
            dt (float): Delta time between physics updates.
        """
        while self.is_running:
            self.update(dt)
            await asyncio.sleep(dt)

    def start_physics_engine(self, dt=PHYSICS_DT):
        """
        Starts the physics engine in an asynchronous loop.
        
        Attempts to retrieve the current event loop or creates a new one if necessary 
        (running it in a separate daemon thread). Schedules the physics loop as a task.
        
        Args:
            dt (float, optional): Delta time between physics updates. Defaults to PHYSICS_DT.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop; create a new one and run it in a daemon thread.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            threading.Thread(target=loop.run_forever, daemon=True).start()
        self.is_running = True
        self._physics_task = loop.create_task(self._run_physics_loop(dt))

    def stop_physics_engine(self):
        """
        Stops the physics engine loop and cancels the associated asyncio task.
        """
        if self.is_running:
            self.is_running = False
            if self._physics_task:
                self._physics_task.cancel()
                self._physics_task = None

    def restart_game(self):
        """
        Resets the game to its initial state.
        
        Removes non-player objects and resets global game state variables.
        For each connected player, it removes the old instance and re-adds a new one using the existing player ID.
        """
        print("Restarting game...")

        remaining = {pid: p.health for pid, p in self.players.items()}
        self.score_sys.on_game_end(remaining)

        # Show statistics plot before resetting players/objects
        self.plot_game_statistics()
        plot_csv_statistics()

        # Reset global game state variables.
        self.game_started = False
        self.waiting_for_players = True
        self.countdown_active = False
        self.countdown_seconds_remaining = 0.0
        self.shot_count = 0
        self.player_collisions = 0
        self.next_color_index = 0

        # Remove all non-player objects (e.g. projectiles, power-ups).
        objects_to_remove = list(self.objects)
        for obj in objects_to_remove:
            if hasattr(obj, 'remove_from_world'):
                obj.remove_from_world()
            elif hasattr(obj, 'body') and obj.body in self.space.bodies:
                self.space.remove(obj.body)
                if hasattr(obj, 'shape') and obj.shape in self.space.shapes:
                    self.space.remove(obj.shape)
        self.objects.clear()

        # Speichere bestehende Spieler (um ihre Eigenschaften ggf. später zu erhalten).
        old_players = list(self.players.items())
        self.players.clear()  # Leere die Spielerliste, damit add_player einen neuen Eintrag erstellen kann.
        for player_id, old_player in old_players:
            # Entferne alte Player-Ressourcen.
            old_player.remove_from_world()
            # Erzeuge einen neuen Spieler mit der alten ID und neuer Spawnposition.
            new_player_id = self.add_player(given_player_id=player_id)
            if new_player_id is None:
                print(f"Failed to respawn player {player_id}.")
            else:
                # Optional: Alte Eigenschaften (wie Farbe) beibehalten.
                self.players[player_id].color = old_player.color
                print(f"Player {player_id} restarted.")

        # Re-initialisiere statische Weltobjekte (z. B. Hindernisse).
        self.initialize_world_objects()

        print("Game has been reset to initial state.")




# ------------------------------------------------------------
    # Sensors for the Player are here now defined

    def scan_environment(self, player_id):
        if not self.game_started:
            # Return a consistent structure even if game not started, or handle differently
            return {"nearby_objects": [], "message": "Game not started yet."}
        player = self.players.get(player_id)
        if not player:
            return {"nearby_objects": [], "message": f"Player {player_id} not found."}

        player_pos = player.body.position
        player_angle_rad = player.body.angle
        player_vel = player.body.velocity
        player_angular_vel = player.body.angular_velocity
        player_health = player.health
        radius = SCANNING_RADIUS

        nearby_objects_relative = []

        # --- Rauschparameter (entweder aus settings.py oder hier direkt definieren) ---
        # Falls nicht in settings.py definiert:
        _POSITION_NOISE_MAX_OFFSET = 0.8
        _VELOCITY_NOISE_MAX_OFFSET = 0.4
        _DISTANCE_NOISE_MAX_PERCENTAGE = 0.04
        # Wenn aus settings.py importiert, verwende z.B. POSITION_NOISE_MAX_OFFSET direkt.


        # Process non-player objects (obstacles, projectiles).
        for obj in self.objects:
            if obj is player or not hasattr(obj, 'body') or not hasattr(obj, 'radius'): # Sicherstellen, dass obj.radius existiert
                continue

            obj_pos = obj.body.position
            distance = player_pos.get_distance(obj_pos) -obj.radius - player.radius # Distanz von Oberfläche zu Oberfläche (ungefähr)

            if distance <= radius: # Prüfe, ob das Objekt im Scan-Radius ist (basierend auf Oberflächendistanz)
                delta_pos = obj_pos - player_pos
                relative_pos_rotated = delta_pos.rotated(-player_angle_rad)

                obj_vel = getattr(obj.body, 'velocity', pymunk.Vec2d(0, 0))
                delta_vel = obj_vel - player_vel
                relative_vel_rotated = delta_vel.rotated(-player_angle_rad)

                # --- Rauschen hinzufügen ---
                noisy_relative_pos_x = relative_pos_rotated.x + random.uniform(-_POSITION_NOISE_MAX_OFFSET, _POSITION_NOISE_MAX_OFFSET)
                noisy_relative_pos_y = relative_pos_rotated.y + random.uniform(-_POSITION_NOISE_MAX_OFFSET, _POSITION_NOISE_MAX_OFFSET)

                noisy_relative_vel_x = relative_vel_rotated.x + random.uniform(-_VELOCITY_NOISE_MAX_OFFSET, _VELOCITY_NOISE_MAX_OFFSET)
                noisy_relative_vel_y = relative_vel_rotated.y + random.uniform(-_VELOCITY_NOISE_MAX_OFFSET, _VELOCITY_NOISE_MAX_OFFSET)

                noise_factor_distance = 1 + random.uniform(-_DISTANCE_NOISE_MAX_PERCENTAGE, _DISTANCE_NOISE_MAX_PERCENTAGE)
                noisy_distance = max(0, distance * noise_factor_distance) # Sicherstellen, dass Distanz nicht negativ wird

                obj_type = "unknown"
                if isinstance(obj, CircleObstacle):
                    obj_type = "obstacle"
                elif isinstance(obj, Projectile):
                    obj_type = "projectile"

                if obj_type != "unknown":
                    nearby_objects_relative.append({
                        "type": obj_type,
                        "relative_position": [noisy_relative_pos_x, noisy_relative_pos_y],
                        "relative_velocity": [noisy_relative_vel_x, noisy_relative_vel_y],
                        "distance": noisy_distance,
                        "color": getattr(obj, 'color', None) if obj_type == "projectile" else None
                    })

        # Process other players.
        for other_pid, other_player_obj in self.players.items(): # Variable umbenannt, um Konflikt zu vermeiden
            if other_pid == player_id:
                continue

            other_player_pos = other_player_obj.body.position
            # Distanz von Oberfläche zu Oberfläche (ungefähr)
            distance = player_pos.get_distance(other_player_pos) - other_player_obj.radius - player.radius


            if distance <= radius:
                delta_pos = other_player_pos - player_pos
                relative_pos_rotated = delta_pos.rotated(-player_angle_rad)

                other_player_vel = other_player_obj.body.velocity
                delta_vel = other_player_vel - player.body.velocity # Korrigiert
                relative_vel_rotated = delta_vel.rotated(-player_angle_rad)

                # --- Rauschen hinzufügen ---
                noisy_relative_pos_x = relative_pos_rotated.x + random.uniform(-_POSITION_NOISE_MAX_OFFSET, _POSITION_NOISE_MAX_OFFSET)
                noisy_relative_pos_y = relative_pos_rotated.y + random.uniform(-_POSITION_NOISE_MAX_OFFSET, _POSITION_NOISE_MAX_OFFSET)

                noisy_relative_vel_x = relative_vel_rotated.x + random.uniform(-_VELOCITY_NOISE_MAX_OFFSET, _VELOCITY_NOISE_MAX_OFFSET)
                noisy_relative_vel_y = relative_vel_rotated.y + random.uniform(-_VELOCITY_NOISE_MAX_OFFSET, _VELOCITY_NOISE_MAX_OFFSET)

                noise_factor_distance = 1 + random.uniform(-_DISTANCE_NOISE_MAX_PERCENTAGE, _DISTANCE_NOISE_MAX_PERCENTAGE)
                noisy_distance = max(0, distance * noise_factor_distance)

                nearby_objects_relative.append({
                    "type": "other_player",
                    "relative_position": [noisy_relative_pos_x, noisy_relative_pos_y],
                    "relative_velocity": [noisy_relative_vel_x, noisy_relative_vel_y],
                    "distance": noisy_distance,
                    "color": other_player_obj.color, # Korrigiert
                })

        # Process borders
        for shape in self.space.shapes:
            if isinstance(shape, pymunk.Segment) and shape.collision_type == 3:
                query_info = shape.point_query(player_pos)
                distance = query_info.distance # Kürzeste Distanz zur Border-Linie

                if distance <= radius:
                    closest_point = query_info.point
                    delta_pos = closest_point - player_pos
                    relative_pos_rotated = delta_pos.rotated(-player_angle_rad)

                    # --- Rauschen hinzufügen ---
                    noisy_relative_pos_x = relative_pos_rotated.x + random.uniform(-_POSITION_NOISE_MAX_OFFSET, _POSITION_NOISE_MAX_OFFSET)
                    noisy_relative_pos_y = relative_pos_rotated.y + random.uniform(-_POSITION_NOISE_MAX_OFFSET, _POSITION_NOISE_MAX_OFFSET)

                    noise_factor_distance = 1 + random.uniform(-_DISTANCE_NOISE_MAX_PERCENTAGE, _DISTANCE_NOISE_MAX_PERCENTAGE)
                    noisy_distance = max(0, distance * noise_factor_distance)


                    nearby_objects_relative.append({
                        "type": "border",
                        "relative_position": [noisy_relative_pos_x, noisy_relative_pos_y],
                        "distance": noisy_distance
                    })

        return {
            "nearby_objects": nearby_objects_relative
        }

    def player_state(self, player_id):
        """
        Retrieves the state of a specific player.
        
        Args:
            player_id (str): The identifier of the player.
        
        Returns:
            dict: The player's state including position, velocity, angle, and health.
        """
        player = self.players.get(player_id)
        if player:
            return {
                "velocity": [player.body.velocity.x, player.body.velocity.y],
                "angle": player.body.angle,
                "health": player.health,
                "angular_velocity": player.body.angular_velocity
            }
            
    def game_state(self, player_id):
        player = self.players.get(player_id)
        if player:
            # Berechne die vergangene Zeit seit Spielstart
            if self.game_started and hasattr(self, "start_time"):
                elapsed = time.time() - self.start_time
            else:
                elapsed = 0.0
            return {
                "game_started": self.game_started,
                "waiting_for_players": self.waiting_for_players,
                "countdown_active": self.countdown_active,
                "countdown_seconds_remaining": math.ceil(self.countdown_seconds_remaining) if self.countdown_active else 0,
                "ready": player.ready,
                "elapsed_game_time": round(elapsed, 1) 
            }

                # "Last Man Standing": player.last
                # "Vote for Restart":  player.vote_for_restart
    
    def plot_game_statistics(self):
        try:
            """
            Plots bar charts for shots, collisions, and final scores for each player,
            and saves the plot as a PDF and PNG file.
            """
            player_names = []
            shots = []
            collisions = []
            scores = []
            lifetimes = []

            for pid, player in self.players.items():
                name = getattr(player, "agent_name", pid[:6])
                player_names.append(name)
                shots.append(getattr(player, "shots_fired", 0))
                collisions.append(getattr(player, "collisions", 0))
                scores.append(self.score_sys.get_score(pid))
                lifetime = getattr(player, "lifetime", 0)
                if isinstance(lifetime, (int, float)):
                    if lifetime > MAX_GAME_DURATION:
                        lifetime = time.time() - lifetime
                        lifetime = round(lifetime, 1)
                        lifetimes.append(lifetime)
                    else:
                        lifetimes.append(round(lifetime, 1))
                else:
                    lifetimes.append(0)

            fig, axs = plt.subplots(1, 3, figsize=(16, 6))
            bar_width = 0.7

            # Farben für Spieler wie im Spiel (falls vorhanden)
            bar_colors = []
            for pid in self.players:
                color = getattr(self.players[pid], "color", (100, 100, 100))
                # Matplotlib erwartet Farben als 0-1 floats
                bar_colors.append(tuple([c/255 for c in color]))

            # Shots fired
            bars0 = axs[0].bar(player_names, shots, color=bar_colors, width=bar_width, edgecolor='black')
            axs[0].set_title("Shots Fired", fontsize=16, fontweight='bold')
            axs[0].set_ylabel("Shots", fontsize=13)
            axs[0].grid(axis='y', linestyle='--', alpha=0.5)
            for bar in bars0:
                height = bar.get_height()
                axs[0].annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 5), textcoords="offset points", ha='center', va='bottom', fontsize=12, fontweight='bold')

            # Collisions
            bars1 = axs[1].bar(player_names, collisions, color=bar_colors, width=bar_width, edgecolor='black')
            axs[1].set_title("Collisions", fontsize=16, fontweight='bold')
            axs[1].set_ylabel("Collisions", fontsize=13)
            axs[1].grid(axis='y', linestyle='--', alpha=0.5)
            for bar in bars1:
                height = bar.get_height()
                axs[1].annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 5), textcoords="offset points", ha='center', va='bottom', fontsize=12, fontweight='bold')

            # Final Score
            bars2 = axs[2].bar(player_names, scores, color=bar_colors, width=bar_width, edgecolor='black')
            axs[2].set_title("Final Score", fontsize=16, fontweight='bold')
            axs[2].set_ylabel("Points", fontsize=13)
            axs[2].grid(axis='y', linestyle='--', alpha=0.5)
            for bar in bars2:
                height = bar.get_height()
                axs[2].annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 5), textcoords="offset points", ha='center', va='bottom', fontsize=12, fontweight='bold')

            for ax in axs:
                ax.set_xlabel("Player", fontsize=13)
                ax.tick_params(axis='x', labelrotation=20)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)

            fig.suptitle("Game Statistics", fontsize=20, fontweight='bold')
            plt.tight_layout(rect=[0, 0, 1, 0.96])

            # --- Save as PDF and PNG ---
            if PLOT_OUTPUT: 
                stats_dir = "game_stats"
                os.makedirs(stats_dir, exist_ok=True)
                pdf_path = os.path.join(stats_dir, "game_stats_latest.pdf")
                png_path = os.path.join(stats_dir, "game_stats_latest.png")
                plt.savefig(pdf_path)
                plt.savefig(png_path)
                print(f"Game statistics saved as {pdf_path} and {png_path}")

                plt.close(fig)
        except Exception as e:
                print(f"Error while saving game statistics: {e}")

        # --- Save last 10 games to CSV ---
        stats_dir = "game_stats"
        os.makedirs(stats_dir, exist_ok=True)
        csv_path = os.path.join(stats_dir, "game_stats_last10.csv")

        # 1. Lade bestehende Daten (falls vorhanden)
        history = []
        if os.path.exists(csv_path):
            with open(csv_path, "r", newline="") as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader, None)
                for row in reader:
                    history.append(row)

        # 2. Füge aktuelle Runde(n) hinzu
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        for name, shot, collision, score, lifetime in zip(player_names, shots, collisions, scores, lifetimes):
            history.append([timestamp, name, shot, collision, score, lifetime])

        # 3. Nur die letzten 10 Spiele behalten (je Spiel = alle Spieler einer Runde)
        if len(history) > 0:
            # Finde die letzten 10 Zeitstempel
            unique_timestamps = []
            for row in history:
                if row[0] not in unique_timestamps:
                    unique_timestamps.append(row[0])
            last_10_timestamps = unique_timestamps[-10:]
            # Filtere alle Zeilen, die zu den letzten 10 Spielen gehören
            history = [row for row in history if row[0] in last_10_timestamps]

        # 4. Schreibe die CSV neu
        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["timestamp", "player", "shots", "collisions", "score", "lifetime"])
            for row in history:
                writer.writerow(row)
# ------------------------------------------------------------

    def run_visualizer(self):
        """
        Runs the Pygame visualizer which is used for debugging and visualization.
        
        This function initializes Pygame, creates the window, processes events, updates 
        all sprites, draws static elements (like obstacles), displays health bars, and updates the screen.
        The loop runs until the window is closed.
        """
        pygame.init()
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Game Visualizer")
        clock = pygame.time.Clock()
        all_game_sprites = pygame.sprite.Group()
        running = True
        font = pygame.font.SysFont(None, 36) # Slightly larger font for countdown
        score_font = pygame.font.SysFont(None, 24) # Smaller font for scores

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            screen.fill((0, 0, 0)) # Always fill background black

            all_game_sprites.empty()

            # Always add players to the sprite group
            for player in self.players.values():
                if player.health > 0:
                    all_game_sprites.add(player)

            # Add obstacles and other objects (projectiles, power-ups)
            for obj in self.objects:
                if isinstance(obj, pygame.sprite.Sprite):
                    all_game_sprites.add(obj)
            
            dt_visual = clock.tick(FPS) / 1000.0
            all_game_sprites.update(dt_visual) # Sprite updates (position, alpha, etc.)
            all_game_sprites.draw(screen) # Draw all sprites

            # Display health bars
            bar_width = 30; bar_height = 5; bar_offset_y = 5
            health_color = (0, 255, 0); lost_health_color = (255, 0, 0); border_color = (255, 255, 255)
            for player in self.players.values():
                if player.health > 0:    
                    bar_x = player.rect.centerx - bar_width // 2
                    bar_y = player.rect.bottom + bar_offset_y
                    health_percentage = max(0, player.health / PLAYER_START_HEALTH)
                    background_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
                    pygame.draw.rect(screen, lost_health_color, background_rect)
                    current_bar_width = int(bar_width * health_percentage)
                    if current_bar_width > 0:
                        health_rect = pygame.Rect(bar_x, bar_y, current_bar_width, bar_height)
                        pygame.draw.rect(screen, health_color, health_rect)
                    pygame.draw.rect(screen, border_color, background_rect, 1)

          
            # Text display based on game state
            display_text = ""
            text_color = (255, 255, 0) # Default Yellow

            if self.waiting_for_players:
                display_text = "Waiting for players..."
            elif self.game_started and self.countdown_active: 
                display_text = ""
                text_color = (0, 0, 0)
            elif self.countdown_active:
                display_text = f"Game starting in {math.ceil(self.countdown_seconds_remaining)}..."
                text_color = (0, 255, 255) # Cyan for countdown
            
            if display_text: # Only render and blit if there's text to display
                text_surface = font.render(display_text, True, text_color)
                text_rect = text_surface.get_rect(center=(self.width // 2, 30))
                screen.blit(text_surface, text_rect)


            # --- SCORING DISPLAY ---
            # Display scores in a semi-transparent box at the bottom

            score_strings = []
            for pid, player in self.players.items():
                color = player.color if hasattr(player, "color") else (255,255,255)
                agent_name = getattr(player, "agent_name", pid[:6])
                score = self.score_sys.get_score(pid) 
                score_strings.append((f"{agent_name}: {score}", color))

            # Layout: max 4 scores per row, then wrap
            scores_per_row = 4
            rows = [score_strings[i:i+scores_per_row] for i in range(0, len(score_strings), scores_per_row)]

            padding_x = 30
            padding_y = 12
            spacing = 40
            font_height = score_font.get_height()
            row_heights = []
            row_widths = []

            # Prepare text surfaces and calculate width for each row
            row_surfaces = []
            for row in rows:
                text_surfaces = []
                total_width = -spacing
                for score_str, color in row:
                    surf = score_font.render(score_str, True, color)
                    text_surfaces.append((surf, color))
                    total_width += surf.get_width() + spacing
                row_surfaces.append(text_surfaces)
                row_widths.append(total_width)
                row_heights.append(font_height)

            box_width = max(max(row_widths) + 2 * padding_x, 250) if row_widths else 250
            box_height = len(rows) * (font_height + padding_y) + padding_y
            box_x = (screen.get_width() - box_width) // 2
            box_y = screen.get_height() - box_height - 18

            # Draw semi-transparent background box with rounded corners
            box_surface = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
            box_surface.fill((0, 0, 0, 0))  # Fully transparent base

            # Draw a glowing border (outer glow)
            for glow in range(8, 0, -2):
                pygame.draw.rect(
                    box_surface,
                    (255, 215, 0, 30),  # Gold, low alpha for glow
                    pygame.Rect(glow, glow, box_width - 2*glow, box_height - 2*glow),
                    border_radius=18
                )

            # Draw main box
            pygame.draw.rect(
                box_surface,
                (40, 40, 60, 220),  # Slightly bluish dark, semi-transparent
                box_surface.get_rect(),
                border_radius=18
            )

            # Draw border
            pygame.draw.rect(
                box_surface,
                (255, 215, 0),  # Gold border
                box_surface.get_rect(),
                width=4,
                border_radius=18
            )

            # Blit score texts centered inside the box, row by row
            y = padding_y
            for text_surfaces in row_surfaces:
                # Center this row horizontally in the box
                row_width = sum(surf.get_width() for surf, _ in text_surfaces) + spacing * (len(text_surfaces)-1)
                x = (box_width - row_width) // 2
                for surf, color in text_surfaces:
                    box_surface.blit(surf, (x, y))
                    x += surf.get_width() + spacing
                y += font_height + padding_y

            # Blit the box onto the main screen
            screen.blit(box_surface, (box_x, box_y))

            # # --- Scoring display above the players ---
            # # Uncomment if you want to show scores above player avatars
            # for player in self.players.values():
            #     # score_sys ist in GameWorld angelegt
            #     score = self.score_sys.get_score(player.player_id)
            #     score_text = score_font.render(f"Score: {score}", True, (255, 255, 255))
            #     # Position: über dem Spieler-Avatar, z.B. 20 px darüber
            #     score_rect = score_text.get_rect(center=(player.rect.centerx, player.rect.top - 10))
            #     screen.blit(score_text, score_rect)

            # --- Game timer display with shrinking bar at the top ---

            if self.game_started and hasattr(self, "start_time"):
                elapsed = time.time() - self.start_time
                remaining = max(0, int(MAX_GAME_DURATION - elapsed))
                minutes = remaining // 60
                seconds = remaining % 60
                timer_text = f"Time left: {minutes:02d}:{seconds:02d}"

                # Timer bar dimensions (thinner bar, smaller font)
                bar_margin_x = 60
                bar_margin_y = 10
                bar_height = 12  # thinner bar
                bar_width_full = self.width - 2 * bar_margin_x
                bar_x = bar_margin_x
                bar_y = bar_margin_y

                # Calculate bar fill (shrinks as time passes)
                percent_left = max(0, min(1.0, remaining / MAX_GAME_DURATION))
                bar_width_current = int(bar_width_full * percent_left)

                # Draw background bar (empty)
                pygame.draw.rect(
                    screen,
                    (60, 60, 60, 180),  # dark gray
                    (bar_x, bar_y, bar_width_full, bar_height),
                    border_radius=8
                )
                # Draw filled bar (remaining time)
                pygame.draw.rect(
                    screen,
                    (0, 200, 0),  # green
                    (bar_x, bar_y, bar_width_current, bar_height),
                    border_radius=8
                )
                # Draw border
                pygame.draw.rect(
                    screen,
                    (255, 215, 0),  # gold
                    (bar_x, bar_y, bar_width_full, bar_height),
                    width=2,
                    border_radius=8
                )

                # Draw timer text centered in the bar (smaller font)
                timer_font = pygame.font.SysFont(None, 20)
                timer_surface = timer_font.render(timer_text, True, (255, 255, 255))
                timer_rect = timer_surface.get_rect(center=(self.width // 2, bar_y + bar_height // 2))
                screen.blit(timer_surface, timer_rect)

    

            pygame.display.flip()

        pygame.quit()


# Create global instance after initialization:
game_world_instance = GameWorld(SCREEN_WIDTH, SCREEN_HEIGHT)