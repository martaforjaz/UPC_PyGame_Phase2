import numpy as np
from collections import deque
import time
import matplotlib.pyplot as plt
import heapq  
import random
import math


class WorldModel:
    def __init__(self, grid_size=100, resolution=10, agent_id="unknown"):
        self.grid = np.zeros((grid_size, grid_size), dtype=np.float32)
        self.position_history = deque(maxlen=1000)
        self.estimated_pose = np.array([0.0, 0.0, 0.0]) 
        self.resolution = resolution
        self.grid_center = grid_size // 2
        self.known_objects = []
        self.first_update = True
        self.agent_id = agent_id

        self.accumulated_obstacles = set()
        self.accumulated_enemies = set()
        
        # NOVO: Limites baseados nas dimensões da tela (800x600)
        self.SCREEN_WIDTH = 800
        self.SCREEN_HEIGHT = 600
        
        # Limites do mapa
        self.MAP_LIMITS = {
            'min_x': -self.SCREEN_WIDTH // 2,   # -400
            'max_x': self.SCREEN_WIDTH // 2,    # +400
            'min_y': -self.SCREEN_HEIGHT // 2,  # -300
            'max_y': self.SCREEN_HEIGHT // 2    # +300
        }
        
        # NOVO: Margens de segurança progressivas
        self.DANGER_MARGIN = 120     # Zona de perigo - começa evasão
        self.CRITICAL_MARGIN = 80    # Zona crítica - NUNCA entrar
        self.SAFE_ZONE_MARGIN = 150  # Zona segura para exploração
        
        # NOVO: Memória de posições problemáticas
        self.stuck_positions = deque(maxlen=50)  # Últimas 50 posições onde ficou preso
        self.last_positions = deque(maxlen=10)   # Últimas 10 posições para detectar travamento
        
        # NOVO: Direções preferidas para exploração
        self.exploration_angles = [0, math.pi/4, math.pi/2, 3*math.pi/4, 
                                 math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4]
        self.last_exploration_angle_index = 0

    def update_pose(self, current_state):
        if not current_state or 'position' not in current_state or 'angle' not in current_state:
            return

        if self.first_update:
            self.estimated_pose = np.array([
                current_state['position'][0],
                current_state['position'][1],
                current_state['angle']
            ])
            self.first_update = False
        else:
            self.estimated_pose = 0.7 * self.estimated_pose + 0.3 * np.array([
                current_state['position'][0],
                current_state['position'][1],
                current_state['angle']
            ])
        
        grid_x = int(self.estimated_pose[0] / self.resolution + self.grid_center)
        grid_y = int(self.estimated_pose[1] / self.resolution + self.grid_center)
        self.position_history.append((grid_x, grid_y, self.estimated_pose[2]))
        
        # NOVO: Atualiza memória de posições
        position = [current_state['position'][0], current_state['position'][1]]
        self.last_positions.append(position)

    def update_from_scan(self, scan_data):
        if not scan_data or 'nearby_objects' not in scan_data:
            return

        temp_objects = []

        for obj in scan_data['nearby_objects']:
            rel_x, rel_y = obj['relative_position']
            abs_x = self.estimated_pose[0] + rel_x
            abs_y = self.estimated_pose[1] + rel_y

            grid_x = int(abs_x / self.resolution + self.grid_center)
            grid_y = int(abs_y / self.resolution + self.grid_center)

            if 0 <= grid_x < self.grid.shape[0] and 0 <= grid_y < self.grid.shape[1]:
                if obj['type'] == 'obstacle':
                    self.grid[grid_x, grid_y] = min(1.0, self.grid[grid_x, grid_y] + 0.3)
                    self.accumulated_obstacles.add((grid_x, grid_y))
                elif obj['type'] == 'border':
                    # Marca bordas como obstáculos no grid
                    self.grid[grid_x, grid_y] = 1.0
                elif obj['type'] == 'other_player':
                    self.accumulated_enemies.add((grid_x, grid_y))
                else:
                    self.grid[grid_x, grid_y] = max(0.0, self.grid[grid_x, grid_y] - 0.1)
                
            temp_objects.append({
                'type': obj['type'],
                'position': (abs_x, abs_y),
                'distance': obj['distance'],
                'last_seen': time.time()
            })

        self.known_objects = temp_objects

    def get_distance_to_boundary(self, position):
        """Calcula distância mínima até qualquer borda do mapa"""
        x, y = position
        distances = [
            x - self.MAP_LIMITS['min_x'],  # distância à borda esquerda
            self.MAP_LIMITS['max_x'] - x,  # distância à borda direita
            y - self.MAP_LIMITS['min_y'],  # distância à borda inferior
            self.MAP_LIMITS['max_y'] - y   # distância à borda superior
        ]
        return min(distances)

    def is_position_safe(self, position, margin_type="normal"):
        """
        Verifica se uma posição está segura
        margin_type: "critical", "danger", "safe", "normal"
        """
        distance = self.get_distance_to_boundary(position)
        
        if margin_type == "critical":
            return distance > self.CRITICAL_MARGIN
        elif margin_type == "danger":
            return distance > self.DANGER_MARGIN
        elif margin_type == "safe":
            return distance > self.SAFE_ZONE_MARGIN
        else:  # normal
            return distance > 100

    def is_stuck(self):
        """
        NOVO: Detecta se o agente está preso (pouco movimento nas últimas posições)
        """
        if len(self.last_positions) < 8:
            return False
        
        recent_positions = list(self.last_positions)[-8:]
        
        # Calcula variação de posição
        x_coords = [pos[0] for pos in recent_positions]
        y_coords = [pos[1] for pos in recent_positions]
        
        x_var = max(x_coords) - min(x_coords)
        y_var = max(y_coords) - min(y_coords)
        
        # Se variação muito pequena, está preso
        return x_var < 5 and y_var < 5

    def add_stuck_position(self, position):
        """NOVO: Adiciona posição à memória de locais problemáticos"""
        self.stuck_positions.append(tuple(position))

    def is_near_stuck_position(self, position, threshold=20):
        """NOVO: Verifica se está perto de uma posição onde já ficou preso"""
        for stuck_pos in self.stuck_positions:
            distance = math.sqrt((position[0] - stuck_pos[0])**2 + (position[1] - stuck_pos[1])**2)
            if distance < threshold:
                return True
        return False

    def find_safe_direction(self, position, current_orientation, scan_distance=100):
        """
        NOVO: Encontra direção segura varrendo incrementalmente ângulos
        """
        best_direction = None
        max_safe_distance = 0
        
        # Varre ângulos em incrementos de 30 graus
        for angle_offset in range(0, 360, 30):
            test_angle = current_orientation + math.radians(angle_offset)
            
            # Calcula posição futura nesta direção
            future_x = position[0] + math.cos(test_angle) * scan_distance
            future_y = position[1] + math.sin(test_angle) * scan_distance
            future_pos = [future_x, future_y]
            
            # Verifica distância às bordas
            boundary_distance = self.get_distance_to_boundary(future_pos)
            
            # Verifica se não está perto de posição onde ficou preso
            near_stuck = self.is_near_stuck_position(future_pos)
            
            # Pontuação baseada na segurança
            if boundary_distance > self.SAFE_ZONE_MARGIN and not near_stuck:
                score = boundary_distance
                if score > max_safe_distance:
                    max_safe_distance = score
                    best_direction = test_angle
        
        return best_direction

    def get_smart_exploration_goal(self, position):
        """
        NOVO: Estratégia de exploração inteligente e segura
        """
        # Se está preso, adiciona à memória
        if self.is_stuck():
            self.add_stuck_position(position)
            print(f"[WORLD_MODEL] Detectado travamento em {position}")
        
        # Tenta encontrar direção segura
        safe_direction = self.find_safe_direction(position, self.estimated_pose[2])
        
        if safe_direction is not None:
            # Gera goal na direção segura
            goal_distance = random.uniform(30, 70)  # Distância moderada
            goal_x = position[0] + math.cos(safe_direction) * goal_distance
            goal_y = position[1] + math.sin(safe_direction) * goal_distance
            
            # Garante que o goal está dentro dos limites seguros
            goal_x = max(self.MAP_LIMITS['min_x'] + self.SAFE_ZONE_MARGIN, 
                        min(self.MAP_LIMITS['max_x'] - self.SAFE_ZONE_MARGIN, goal_x))
            goal_y = max(self.MAP_LIMITS['min_y'] + self.SAFE_ZONE_MARGIN, 
                        min(self.MAP_LIMITS['max_y'] - self.SAFE_ZONE_MARGIN, goal_y))
            
            return [goal_x, goal_y]
        
        # Fallback: usa ângulos de exploração predefinidos
        angle = self.exploration_angles[self.last_exploration_angle_index]
        self.last_exploration_angle_index = (self.last_exploration_angle_index + 1) % len(self.exploration_angles)
        
        goal_distance = 60
        goal_x = position[0] + math.cos(angle) * goal_distance
        goal_y = position[1] + math.sin(angle) * goal_distance
        
        # Força limites seguros
        goal_x = max(self.MAP_LIMITS['min_x'] + self.SAFE_ZONE_MARGIN, 
                    min(self.MAP_LIMITS['max_x'] - self.SAFE_ZONE_MARGIN, goal_x))
        goal_y = max(self.MAP_LIMITS['min_y'] + self.SAFE_ZONE_MARGIN, 
                    min(self.MAP_LIMITS['max_y'] - self.SAFE_ZONE_MARGIN, goal_y))
        
        print(f"[WORLD_MODEL] Goal exploração segura: ({goal_x:.1f}, {goal_y:.1f})")
        return [goal_x, goal_y]

    def get_safe_center(self):
        """Retorna o centro seguro do mapa"""
        return [0, 0]

    def get_closest_enemy_position(self):
        if not self.known_objects:
            return None
        enemies = [o for o in self.known_objects if o['type'] == 'other_player']
        if not enemies:
            return None
        enemies.sort(key=lambda e: e['distance'])
        enemy_pos = enemies[0]['position']
        
        # NOVO: Verifica se perseguir o inimigo é seguro
        if not self.is_position_safe(enemy_pos, "danger"):
            print(f"[WORLD_MODEL] Inimigo em zona perigosa, ignorando perseguição")
            return None
        
        return enemy_pos

    def get_random_free_goal(self, position, grid_size=21, tries=20):
        """
        Versão melhorada que SEMPRE gera goals seguros
        """
        # NOVO: Usa estratégia inteligente em vez de random
        return self.get_smart_exploration_goal(position)

    # Resto das funções mantém-se igual...
    def world_to_grid(self, pos, grid_size=21, resolution=10):
        cx = grid_size // 2
        gx = int(pos[0] / resolution) + cx
        gy = -int(pos[1] / resolution) + cx
        return gx, gy

    def grid_to_world(self, gx, gy, grid_size=21, resolution=10):
        cx = grid_size // 2
        x = (gx - cx) * resolution
        y = -(gy - cx) * resolution
        return x, y

    def plan_path_a_star(self, start_pos, goal_pos, grid_size=21, resolution=10):
        # NOVO: Verifica se o goal é seguro antes de planejar
        if not self.is_position_safe(goal_pos, "danger"):
            print(f"[WORLD_MODEL] Goal inseguro rejeitado: {goal_pos}")
            goal_pos = self.get_safe_center()
        
        occupancy_grid = self.get_occupancy_grid(grid_size)
        start = self.world_to_grid(start_pos, grid_size, resolution)
        goal = self.world_to_grid(goal_pos, grid_size, resolution)

        def neighbors(node):
            x, y = node
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = x+dx, y+dy
                if 0 <= nx < grid_size and 0 <= ny < grid_size:
                    if occupancy_grid[ny][nx] == '.':
                        # NOVO: Verifica se o waypoint é seguro
                        world_pos = self.grid_to_world(nx, ny, grid_size, resolution)
                        if self.is_position_safe(world_pos, "critical"):
                            yield (nx, ny)

        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0}

        while open_set:
            _, current = heapq.heappop(open_set)
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return [self.grid_to_world(x, y, grid_size, resolution) for (x, y) in path]

            for neighbor in neighbors(current):
                tentative_g = g_score[current] + 1
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    priority = tentative_g + abs(neighbor[0]-goal[0]) + abs(neighbor[1]-goal[1])
                    heapq.heappush(open_set, (priority, neighbor))
                    came_from[neighbor] = current

        return []  # caminho não encontrado

    def get_occupancy_grid(self, grid_size=21):
        cx = self.grid_center
        half = grid_size // 2
        occupancy = []

        for y in range(-half, half + 1):
            row = []
            for x in range(-half, half + 1):
                gx = cx + x
                gy = cx + y
                if 0 <= gx < self.grid.shape[0] and 0 <= gy < self.grid.shape[1]:
                    if self.grid[gx][gy] > 0.5:
                        row.append('#')  # obstáculo
                    else:
                        row.append('.')  # livre
                else:
                    row.append('#')  # fora do mapa é bloqueado
            occupancy.append(row)
        return occupancy

    def plot_accumulated_obstacles(self):
        if not self.accumulated_obstacles:
            print("Nenhum obstáculo acumulado ainda.")
            return

        xs, ys = zip(*self.accumulated_obstacles)
        plt.figure(figsize=(8, 8))
        plt.scatter(xs, ys, c='gray', s=20, label='Obstáculos')

        if self.position_history:
            hist = np.array(self.position_history)
            plt.plot(hist[:, 0], hist[:, 1], 'b-', label='Trajetória')
            plt.plot(hist[-1, 0], hist[-1, 1], 'ro', label='Agente')
        if self.accumulated_enemies:
            ex, ey = zip(*self.accumulated_enemies)
            plt.scatter(ex, ey, c='red', s=30, label='Inimigos')

        plt.grid(True)
        plt.title("Mapa de Obstáculos Acumulados")
        plt.xlabel("Grid X")
        plt.ylabel("Grid Y")
        plt.legend()
        plt.axis("equal")
        plt.show()
        
        plt.savefig(f"mapa_obstaculos_{int(time.time())}.png")