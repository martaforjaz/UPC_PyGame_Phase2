import pygame
import math
import pymunk
import time
from ..settings import *

class Triangle(pygame.sprite.Sprite):
    """
    Represents a player character as a triangle.
    
    Handles both the physical representation (using pymunk) and the visual
    representation (using pygame). Also manages spawn protection, health,
    and removal from the game world.
    """
    def __init__(self, position, angle=0, color=(0, 128, 255), game_world=None):
        """
        Initializes a new Triangle instance.
        
        Args:
            position (tuple): Starting (x, y) position.
            angle (float): Starting angle in degrees. Defaults to 0.
            color (tuple): RGB color for the triangle.
            game_world (GameWorld): Reference to the main game world.
        """
        super().__init__()
        self.color = color
        self.radius = 15
        self.game_world = game_world
        self.health = PLAYER_START_HEALTH  # Set initial health
        self.player_id = None  # To be assigned by the GameWorld
        # Spawn protection prevents damage immediately after spawn.
        self.spawn_protection_duration = 3.0  # Seconds of protection
        self.spawn_protection_until = -1
        self.collisions = 0
        self.lifetime = time.time()

        mass = 1
        moment = pymunk.moment_for_poly(mass, [
            (self.radius, 0),
            (-self.radius, self.radius),
            (-self.radius, -self.radius)
        ])
        self.body = pymunk.Body(mass, moment)
        self.body.position = position
        self.body.angle = math.radians(angle)
        self.body.damping = 0.99
        self.shape = pymunk.Poly(self.body, [
            (self.radius, 0),
            (-self.radius, self.radius),
            (-self.radius, -self.radius)
        ])
        self.shape.collision_type = 1   # Collision type for players
        self.shape.sprite_ref = self    # Link back to this sprite
        self.ready = False  # Indicates if the player is ready to play

        if game_world:
            game_world.space.add(self.body, self.shape)

        # Create the base image for rendering, preserving an original version for rotations.
        self.original_image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        self._create_base_image()
        self.image = self.original_image.copy()
        self.rect = self.image.get_rect(center=position)

    def _create_base_image(self):
        """
        Creates the original (non-rotated) image for the triangle sprite.
        
        The image is created on a transparent surface taking into account rotation.
        Also draws a small white circle at the tip as an indicator.
        """
        size = int(self.radius * 2 * 1.5)  # Safety factor for rotations
        self.original_image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.original_image.fill((0, 0, 0, 0))  # Transparent background

        # Calculate triangle points relative to the center of the surface.
        center_x, center_y = size // 2, size // 2
        points = [
            (center_x + self.radius * math.cos(math.radians(deg)),
             center_y - self.radius * math.sin(math.radians(deg)))
            for deg in [0, 120, 240]
        ]
        pygame.draw.polygon(self.original_image, self.color, points)

        # Draw an indicator at the tip (at 0°)
        tip_x = center_x + self.radius * math.cos(math.radians(0))
        tip_y = center_y - self.radius * math.sin(math.radians(0))
        indicator_color = (255, 255, 255)  # White indicator
        indicator_radius = 3
        pygame.draw.circle(self.original_image, indicator_color, (int(tip_x), int(tip_y)), indicator_radius)

    def update(self, dt):
        """
        Updates the Triangle sprite's position, rotation, and visual effects.
        Also ensures the player's speed does not exceed PLAYER_MAX_SPEED.
        
        Args:
            dt (float): Delta time since the last update.
        """
        # Limit the player's speed
        speed = self.body.velocity.length
        if speed > PLAYER_MAX_SPEED:
            scale = PLAYER_MAX_SPEED / speed
            self.body.velocity = self.body.velocity * scale

        # Update position and rotation
        pos = self.body.position
        self.rect.center = (int(pos.x), int(pos.y))
        self.angle = math.degrees(self.body.angle)
        rotated_image = pygame.transform.rotate(self.original_image, -self.angle)
        self.rect = rotated_image.get_rect(center=self.rect.center)
        self.image = rotated_image

        # Change transparency if still under spawn protection
        if not self.ready:
            self.image.set_alpha(80)
        elif time.time() < self.spawn_protection_until:
            # Make alpha pulsate between 64 and 192
            alpha = 128 + 64 * math.sin(time.time() * 5)  # Pulsate with a frequency of 5 Hz
            self.image.set_alpha(int(alpha))
        elif self.ready:
            self.image.set_alpha(255)
        else:
            self.image.set_alpha(255)  # Fully opaque

    def take_damage(self, amount):
        """
        Reduces the player's health by the specified amount.
        
        Damage is ignored if spawn protection is active. If health drops to zero or below,
        the player is removed from the game world.
        
        Args:
            amount (int or float): The damage to apply.
        """
        if time.time() < self.spawn_protection_until:
            print(f"Player {self.player_id} is spawn protected. Damage ignored.")
            return

        self.health -= amount
        print(f"Player {self.player_id} took {amount} damage. Current health: {self.health}")
        if self.health <= 0:
            self.lifetime = time.time() - self.lifetime
            print(f"Player {self.player_id} destroyed after {self.lifetime:.2f} seconds.")
            if self.game_world:
                if self.body in self.game_world.space.bodies:
                    self.game_world.space.remove(self.body)
                if self.shape in self.game_world.space.shapes:
                    self.game_world.space.remove(self.shape)
                if self in self.game_world.objects:
                    self.game_world.objects.remove(self)

    def remove_from_world(self):
        """
        Removes the player from the physics space, game world's object lists,
        and any sprite groups.
        """
        if self.game_world:
            if self.body in self.game_world.space.bodies:
                self.game_world.space.remove(self.body)
            if self.shape in self.game_world.space.shapes:
                self.game_world.space.remove(self.shape)
            if self in self.game_world.objects:
                self.game_world.objects.remove(self)
            # Remove from players dictionary.
            player_id_to_remove = None
            for pid, player_obj in self.game_world.players.items():
                if player_obj is self:
                    player_id_to_remove = pid
                    break
            if player_id_to_remove in self.game_world.players:
                del self.game_world.players[player_id_to_remove]
                print(f"Player {player_id_to_remove} removed from players dictionary.")
        self.kill()  # Remove from all pygame sprite groups
        print("Player sprite killed.")

class CircleObstacle(pygame.sprite.Sprite):
    """
    Represents a static circular obstacle that is part of the game arena.
    
    It is added to the physics space as a static body. It also has a visual representation
    drawn using pygame.
    """
    def __init__(self, position, radius, color=(128, 128, 128), game_world=None):
        """
        Initializes a new CircleObstacle.
        
        Args:
            position (tuple): (x, y) position for the obstacle.
            radius (int): Radius of the circle.
            color (tuple): RGB color.
            game_world (GameWorld): Reference to the game world.
        """
        super().__init__()
        self.color = color
        self.radius = radius
        self.game_world = game_world
        mass = 1
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
        self.body.position = position
        self.shape = pymunk.Circle(self.body, radius)
        self.shape.collision_type = 2   # Collision type for obstacles
        self.shape.sprite_ref = self
        self.shape.elasticity = 0.9     # Makes obstacle bouncy
        self.shape.friction = 0.5

        if game_world:
            game_world.space.add(self.body, self.shape)
        self.image = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (radius, radius), radius)
        self.rect = self.image.get_rect(center=position)

    def update(self, dt):
        """
        Updates the obstacle's position in case of external movement.
        
        Args:
            dt (float): Delta time since last update.
        """
        pos = self.body.position
        self.rect.center = (int(pos.x), int(pos.y))

    def to_dict(self):
        """
        Serializes the obstacle for external use (e.g., networking).
        
        Returns:
            dict: Dictionary containing type, position, and radius.
        """
        return {
            "type": "circle",
            "position": [self.body.position.x, self.body.position.y],
            "radius": self.radius
        }

class Projectile(pygame.sprite.Sprite):
    """
    Represents a projectile fired by a player.
    
    The projectile is subject to physics simulation and has a limited lifetime. It is removed
    from the game world when its lifetime expires or upon collisions.
    """
    def __init__(self, position, angle_rad, owner, color, radius=PROJECTILE_RADIUS, speed=PROJECTILE_SPEED, game_world=None):
        """
        Initializes a new Projectile instance.
        
        Args:
            position (tuple): Starting (x, y) position.
            angle_rad (float): Firing angle in radians.
            owner (Triangle): The player who fired the projectile.
            color (tuple): Color for the projectile.
            radius (int): Radius for both physics shape and drawing.
            speed (int): Speed at which the projectile is fired.
            game_world (GameWorld): Reference to the game world.
        """
        super().__init__()
        self.color = color
        self.radius = radius
        self.game_world = game_world
        self.lifetime = PROJECTILE_LIFETIME_SECONDS  # Time before expiration
        self.owner = owner  # The firing player

        mass = 0.1  # Light weight for projectiles
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self.body = pymunk.Body(mass, moment)
        self.body.position = position
        self.body.angle = angle_rad
        
        # Calculate initial velocity based on the firing angle and speed
        velocity_x = math.cos(angle_rad) * speed
        velocity_y = math.sin(angle_rad) * speed
        self.body.velocity = (velocity_x, velocity_y)

        self.shape = pymunk.Circle(self.body, radius)
        self.shape.collision_type = 4  # Collision type for projectiles
        self.shape.sensor = False      # Projectile affects collisions
        self.shape.sprite_ref = self
        self.shape.elasticity = 0.6    # Bounciness
        self.shape.friction = 0.1
        # Note: Owner-check in collision handler prevents damage to the firing player.

        if game_world:
            game_world.space.add(self.body, self.shape)
            game_world.add_object(self)

        # Create the visual representation
        self.image = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.color, (radius, radius), radius)
        self.rect = self.image.get_rect(center=position)

    def update(self, dt):
        """
        Updates the projectile's position and decreases its lifetime.
        
        Args:
            dt (float): Delta time since last update.
        """
        pos = self.body.position
        self.rect.center = (int(pos.x), int(pos.y))
        
        # Decrease lifetime and remove if expired.
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.remove_from_world()

    def remove_from_world(self):
        """
        Removes the projectile from the physics space, game objects list,
        and all sprite groups.
        """
        if self.game_world:
            if self.body in self.game_world.space.bodies:
                self.game_world.space.remove(self.body)
            if self.shape in self.game_world.space.shapes:
                self.game_world.space.remove(self.shape)
            if self in self.game_world.objects:
                self.game_world.objects.remove(self)
            self.kill()  # Remove sprite from all groups
    

    def to_dict(self):
        """
        Serializes the projectile state.
        
        Returns:
            dict: Dictionary containing type, position, and radius.
        """
        return {
            "type": "projectile",
            "position": [self.body.position.x, self.body.position.y],
            "radius": self.radius
        }

# ---------------- Collision Handlers ----------------

def collision_begin(arbiter, space, data):
    """
    A generic collision begin handler that increments the player collision counter.
    
    Args:
        arbiter (pymunk.Arbiter): Contains collision shapes.
        space (pymunk.Space): The physics space.
        data (dict): Additional data (expects 'game_world').
    
    Returns:
        bool: True to process the collision normally.
    """
    shape_a, shape_b = arbiter.shapes
    game_world = data.get("game_world", None)
    if game_world:
        game_world.player_collisions += 1
    return True

def player_hit_obstacle(arbiter, space, data):
    """
    Handles collision between a player and an obstacle.
    
    Increments the collision counter and prints the player's health.
    Accounts for cases where shapes may be in the reverse order.
    
    Args:
        arbiter (pymunk.Arbiter): Contains collision information.
        space (pymunk.Space): The physics space.
        data (dict): Expects 'game_world'.
    
    Returns:
        bool: True, so that pymunk resolves the collision (bouncing, etc.).
    """
    player_shape, obstacle_shape = arbiter.shapes
    game_world = data.get("game_world", None)

    # Versuche beide Reihenfolgen (Spieler kann shape[0] oder shape[1] sein)
    for shape in [player_shape, obstacle_shape]:
        if game_world and hasattr(shape, 'sprite_ref') and isinstance(shape.sprite_ref, Triangle):
            player_sprite = shape.sprite_ref
            velocity = player_sprite.body.velocity.length
            if velocity >= PLAYER_MAX_SPEED * 0.9:  # Nur wenn Schaden entsteht!
                player_sprite.collisions += 1
                player_sprite.take_damage(OBSTACLE_DAMAGE)
                game_world.player_collisions += 1
                game_world.score_sys.on_collision(player_sprite.player_id)
                print(f"Player collided with obstacle at high speed. Health: {player_sprite.health}")
            else:
                print(f"Player collided with obstacle at low speed. No damage taken.")
            break  # Nur einmal pro Kollision zählen
    return True

def projectile_hit_player(arbiter, space, data):
    """
    Handles collision between a projectile and a player.
    
    Applies damage to the player, removes the projectile, and checks for friendly fire.
    
    Args:
        arbiter (pymunk.Arbiter): Contains collision shapes.
        space (pymunk.Space): The physics space.
        data (dict): Expects 'game_world'.
    
    Returns:
        bool: True if collision should be processed further; False otherwise.
    """
    projectile_shape, player_shape = arbiter.shapes
    game_world = data.get("game_world", None)

    projectile = getattr(projectile_shape, 'sprite_ref', None)
    player = getattr(player_shape, 'sprite_ref', None)

    if not isinstance(projectile, Projectile) or not isinstance(player, Triangle):
        # Try swapping shapes if order is reversed.
        projectile_shape, player_shape = player_shape, projectile_shape
        projectile = getattr(projectile_shape, 'sprite_ref', None)
        player = getattr(player_shape, 'sprite_ref', None)
        if not isinstance(projectile, Projectile) or not isinstance(player, Triangle):
            print("Collision 4-1: Invalid shapes found.")
            return False

    # Prevent self-hit if friendly fire is disabled.
    if not ALLOW_FRIENDLY_FIRE and projectile.owner is player:
        print("Friendly fire disabled, ignoring hit.")
        return False

    print(f"Player hit by projectile! Applying {PROJECTILE_DAMAGE} damage.")
    player.take_damage(PROJECTILE_DAMAGE)
    # Points for hitting a player
    if game_world and projectile.owner and hasattr(projectile.owner, "player_id"):
        shooter_id = projectile.owner.player_id
        game_world.score_sys.on_hit(shooter_id)
    # Points for killing a player
    if player.health <= 0 and game_world and projectile.owner and hasattr(projectile.owner, "player_id"):
        killer_id = projectile.owner.player_id
        game_world.score_sys.on_kill(killer_id)
    projectile.remove_from_world()
    return True

def projectile_hit_obstacle(arbiter, space, data):
    """
    Handles collision between a projectile and an obstacle.
    
    Prints a debug message and allows pymunk to resolve the collision by bouncing.
    
    Args:
        arbiter (pymunk.Arbiter): Contains collision shapes.
        space (pymunk.Space): The physics space.
        data (dict): Expects 'game_world'.
    
    Returns:
        bool: True to allow normal collision resolution.
    """
    projectile_shape, obstacle_shape = arbiter.shapes
    print("Projectile hit obstacle - bouncing off.")
    return True

def projectile_hit_border(arbiter, space, data):
    """
    Handles collision between a projectile and the game border.
    
    Removes the projectile upon collision.
    
    Args:
        arbiter (pymunk.Arbiter): Contains collision shapes.
        space (pymunk.Space): The physics space.
        data (dict): Expects 'game_world'.
    
    Returns:
        bool: True to allow border collision handling.
    """
    projectile_shape, border_shape = arbiter.shapes
    if hasattr(projectile_shape, 'sprite_ref') and isinstance(projectile_shape.sprite_ref, Projectile):
        projectile_shape.sprite_ref.remove_from_world()
    return True

def on_player_collision(arbiter, space, data):
    shapes = arbiter.shapes
    player1 = getattr(shapes[0], "sprite_ref", None)
    player2 = getattr(shapes[1], "sprite_ref", None)
    for player in (player1, player2):
        if player is not None:
            player.collisions += 1
    return True

def setup_collision_handlers(space, game_world):
    """
    Sets up collision handlers for the physics space.
    
    Handlers for collisions between:
        - Player (1) and Obstacle (2)
        - Projectile (4) and Obstacle (2)
        - Projectile (4) and Border (3)
        - Projectile (4) and Player (1)
    
    Args:
        space (pymunk.Space): The physics space to set up handlers in.
        game_world (GameWorld): Reference to the game world (passed as data).
    """
    # Player (1) vs Obstacle (2)
    handler_player_obstacle = space.add_collision_handler(1, 2)
    handler_player_obstacle.begin = player_hit_obstacle
    handler_player_obstacle.data["game_world"] = game_world

    # Projectile (4) vs Obstacle (2)
    handler_projectile_obstacle = space.add_collision_handler(4, 2)
    handler_projectile_obstacle.begin = projectile_hit_obstacle
    handler_projectile_obstacle.data["game_world"] = game_world

    # Projectile (4) vs Border (3)
    handler_projectile_border = space.add_collision_handler(4, 3)
    handler_projectile_border.begin = projectile_hit_border
    handler_projectile_border.data["game_world"] = game_world

    # Projectile (4) vs Player (1)
    handler_projectile_player = space.add_collision_handler(4, 1)
    handler_projectile_player.begin = projectile_hit_player
    handler_projectile_player.data["game_world"] = game_world

    handler = space.add_collision_handler(1, 1)  # Beispiel: Spieler vs Spieler
    handler.begin = on_player_collision