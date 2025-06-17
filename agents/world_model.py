import numpy as np
from collections import deque
import time
import matplotlib.pyplot as plt
import heapq  
import random


class WorldModel:
    def __init__(self, grid_size=100, resolution=10, agent_id="unknown"):
        #self.grid = np.zeros((grid_size, grid_size), dtype=np.float32)
        self.position_history = deque(maxlen=1000)
        self.estimated_pose = np.array([0.0, 0.0, 0.0]) 
        self.resolution = resolution
        #self.grid_center = grid_size // 2
        
        self.world_width = 1000
        self.world_height = 1000
        self.resolution = resolution  # já vem do init (ex: 2)
        self.grid_width = self.world_width // self.resolution  # = 500
        self.grid_height = self.world_height // self.resolution
        self.grid = np.zeros((self.grid_width, self.grid_height), dtype=np.float32)


        # Gurada limites maximos e mínimos observados das posições do agente
        self.min_x = float('inf')
        self.max_x = float('-inf')
        self.min_y = float('inf')
        self.max_y = float('-inf')

        self.known_objects = []
        self.first_update = True
        self.agent_id = agent_id

        self.accumulated_obstacles = set()  # <- NOVO
        self.accumulated_enemies = set()


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
        
        grid_x, grid_y = self.world_to_grid(self.estimated_pose[:2])
        self.position_history.append((grid_x, grid_y, self.estimated_pose[2]))

        x, y = self.estimated_pose[0], self.estimated_pose[1]
        self.min_x = min(self.min_x, x)
        self.max_x = max(self.max_x, x)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)

        print(f"[DEBUG MAP SIZE] X ∈ [{self.min_x:.2f}, {self.max_x:.2f}] | Y ∈ [{self.min_y:.2f}, {self.max_y:.2f}]")

    def update_from_scan(self, scan_data):
        print("[DEBUG] update_from_scan foi chamado")
        if not scan_data or 'nearby_objects' not in scan_data:
            return

        temp_objects = []

        for obj in scan_data['nearby_objects']:
            print(f"[DEBUG] Objeto recebido: {obj}")
            rel_x, rel_y = obj['relative_position']
            abs_x = self.estimated_pose[0] + rel_x
            abs_y = self.estimated_pose[1] + rel_y

            grid_x, grid_y = self.world_to_grid((abs_x, abs_y))
            if grid_x is None or grid_y is None:
                print(f"[DEBUG] Objeto ignorado fora do mapa: ({abs_x:.2f}, {abs_y:.2f})")
                continue  # ignora objetos fora do mapa


            if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
                if obj['type'] == 'obstacle' or obj['type'] == 'border':
                    self.grid[grid_y, grid_x] = 1.0
                    self.accumulated_obstacles.add((grid_x, grid_y))
                elif obj['type'] == 'other_player':
                    self.accumulated_enemies.add((grid_x, grid_y))
                else:
                    self.grid[grid_y, grid_x] = max(0.0, self.grid[grid_y, grid_x] - 0.1)
                
            temp_objects.append({
                'type': obj['type'],
                'position': (abs_x, abs_y),
                'distance': obj['distance'],
                'last_seen': time.time()
            })
            
        for (ox, oy) in self.accumulated_obstacles:
                try:
                    gx, gy = self.world_to_grid((ox, oy))
                    if 0 <= gx < self.grid_width and 0 <= gy < self.grid_height:
                        self.grid[gy, gx] = 1  # marca célula como ocupada
                except Exception as e:
                    print(f"[DEBUG] Erro ao converter obstáculo ({ox},{oy}) para grid: {e}")

            
        n_ocupadas = np.count_nonzero(self.grid)
        print(f"[DEBUG] Nº células ocupadas: {n_ocupadas}")

        self.known_objects = temp_objects
        #print(f"[DEBUG] Objetos armazenados: {len(self.known_objects)}")

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
        #limites ao eixo para garantir que a figura representa todo o mundo:
        plt.xlim(0, self.grid_width)
        plt.ylim(0, self.grid_height)

        plt.grid(True)
        plt.title("Mapa de Obstáculos Acumulados")
        plt.xlabel("Grid X")
        plt.ylabel("Grid Y")
        plt.legend()
        plt.axis("equal")
        plt.show()
        
        plt.savefig(f"mapa_obstaculos_{int(time.time())}.png")
    
    def world_to_grid(self, pos):
        x, y = pos
        if not (0 <= x < self.world_width and 0 <= y < self.world_height):
            return None, None
        gx = int(x / self.resolution)
        gy = int(y / self.resolution)
        
        return gx, gy

    def grid_to_world(self, gx, gy):
        """Converte coordenadas da grelha (gx, gy) para posição real no mundo (x, y)."""
        x = gx * self.resolution
        y = gy * self.resolution
        return x, y

    #Encontrar o melhor caminho (mais curto) entre a 
    # posição inicial start_pos e a posição final goal_pos
    # evitando obstáculos registados na grelha self.grid.
    def plan_path_a_star(self, start_pos, goal_pos):
        # Converter coordenadas reais para coordenadas da grelha
        start = self.world_to_grid(start_pos)
        goal = self.world_to_grid(goal_pos)
        if None in start or None in goal:
            return []  # posição inválida

        #Para cada nó (x, y) verifica os vizinhos 
        # 4-conectados (esquerda, direita, cima, baixo).
        def neighbors(node):
            x, y = node
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_width and 0 <= ny < self.grid_height:
                    if self.grid[ny][nx] < 0.5:  # <<< INVERTIDO AQUI!
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
                return [self.grid_to_world(x, y) for (x, y) in path]

            for neighbor in neighbors(current):
                tentative_g = g_score[current] + 1
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    priority = tentative_g + np.linalg.norm(np.subtract(neighbor, goal))
                    heapq.heappush(open_set, (priority, neighbor))
                    came_from[neighbor] = current

        return []

    
    def get_occupancy_grid(self, grid_size=21):
        cx, cy = self.world_to_grid(self.estimated_pose[:2])
        half = grid_size // 2
        occupancy = []

        for dy in range(-half, half + 1):
            row = []
            for dx in range(-half, half + 1):
                gx = cx + dx
                gy = cy + dy
                if 0 <= gx < self.grid_width and 0 <= gy < self.grid_height:
                    if self.grid[gy][gx] > 0.5:
                        row.append('#')  # obstáculo
                    else:
                        row.append('.')  # livre
                else:
                    row.append('#')  # fora do mapa é bloqueado
            occupancy.append(row)
        return occupancy

    def get_closest_enemy_position(self):
        if not self.known_objects:
            return None
        enemies = [o for o in self.known_objects if o['type'] == 'other_player']
        if not enemies:
            return None
        enemies.sort(key=lambda e: e['distance'])
        return enemies[0]['position']

    def get_random_free_goal(self, position, tries=20):
        for _ in range(tries):
            gx = random.randint(0, self.grid_width - 1)
            gy = random.randint(0, self.grid_height - 1)
            if self.grid[gy][gx] < 0.5:
                goal = self.grid_to_world(gx, gy)
                print(f"[DEBUG] Novo goal aleatório escolhido: {goal}")
                return goal
        print("[WARN] Nenhum goal livre encontrado.")
        return position

