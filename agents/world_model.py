import numpy as np
from collections import deque
import time
import matplotlib.pyplot as plt
import heapq  
import random
import math
from scipy.signal import correlate2d
from scipy.ndimage import gaussian_filter

class WorldModel:
    def __init__(self, grid_size=100, resolution=10, agent_id="unknown"):
        #self.grid = np.zeros((grid_size, grid_size), dtype=np.float32)
        
        self.enemy_history = {}  # {enemy_id: {"last_pos": (x,y), "last_time": t, "velocity": (vx, vy)}}
        
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

    def update_from_scan(self, scan_data):
        #print("[DEBUG] update_from_scan foi chamado")
        if not scan_data or 'nearby_objects' not in scan_data:
            return

        temp_objects = []
        border_safety_margin = 3  # Número de células a marcar como perigosas antes da borda real

        for obj in scan_data['nearby_objects']:
            #print(f"[DEBUG] Objeto recebido: {obj}")
            rel_x, rel_y = obj['relative_position']
            abs_x = self.estimated_pose[0] + rel_x
            abs_y = self.estimated_pose[1] + rel_y

            grid_x, grid_y = self.world_to_grid((abs_x, abs_y))
            
            if grid_x is None or grid_y is None:
                #print(f"[DEBUG] Objeto ignorado fora do mapa: ({abs_x:.2f}, {abs_y:.2f})")
                continue  # ignora objetos fora do mapa


            if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
            
                # Objeto é borda ou obstáculo
                if obj['type'] == 'border' or obj['type'] == 'obstacle':
                    self.grid[grid_y, grid_x] = 1.0
                    self.accumulated_obstacles.add((grid_x, grid_y))
                    
                    # Marca células adjacentes à borda como perigosas (zona de segurança)
                    for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
                        nx, ny = grid_x + dx, grid_y + dy
                        if 0 <= nx < self.grid_width and 0 <= ny < self.grid_height:
                            if obj['type'] == 'border':  # Só aplica margem de segurança para bordas
                                self.grid[ny, nx] = min(1.0, self.grid[ny, nx] + 0.5)  # Valor intermediário
                                
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
            
        # Atualiza obstáculos acumulados
        for (ox, oy) in self.accumulated_obstacles:
            try:
                gx, gy = self.world_to_grid((ox, oy))
                if 0 <= gx < self.grid_width and 0 <= gy < self.grid_height:
                    self.grid[gy, gx] = 1
            except Exception as e:
                print(f"[DEBUG] Erro ao converter obstáculo ({ox},{oy}) para grid: {e}")

        self.known_objects = temp_objects

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
        start = self.world_to_grid(start_pos)
        goal = self.world_to_grid(goal_pos)
        if None in start or None in goal:
            return []

        # Usar fila prioritária mais eficiente
        open_set = []
        heapq.heappush(open_set, (0, start))
        
        came_from = {}
        g_score = {start: 0}
        f_score = {start: math.hypot(start[0]-goal[0], start[1]-goal[1])}
        
        # Usar um set para verificação mais rápida
        open_set_hash = {start}

        while open_set:
            _, current = heapq.heappop(open_set)
            open_set_hash.remove(current)
            
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return [self.grid_to_world(x, y) for (x, y) in path]

            # Modifique o loop de vizinhos para incluir diagonais:
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:  # 8-direções
                neighbor = (current[0] + dx, current[1] + dy)
                if 0 <= neighbor[0] < self.grid_width and 0 <= neighbor[1] < self.grid_height:
                    if self.grid[neighbor[1]][neighbor[0]] < 0.5:
                        # Custo diagonal: sqrt(2) ≈ 1.4
                        cost = 1.4 if dx != 0 and dy != 0 else 1.0
                        tentative_g = g_score[current] + cost
                        if neighbor not in g_score or tentative_g < g_score[neighbor]:
                            came_from[neighbor] = current
                            g_score[neighbor] = tentative_g
                            f_score[neighbor] = tentative_g + 1.5 * math.hypot(neighbor[0]-goal[0], neighbor[1]-goal[1])  # Heurística mais agressiva
                            if neighbor not in open_set_hash:
                                heapq.heappush(open_set, (f_score[neighbor], neighbor))
                                open_set_hash.add(neighbor)

        return []

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

    '''
    def refine_pose_with_correlation(self, scan_data):
        if not scan_data or 'nearby_objects' not in scan_data:
            return

        grid_bin = (self.grid > 0.5).astype(np.uint8)
        mask = self.build_scan_mask(scan_data, size=21)

        # Verifica se a máscara tem alguma coisa útil
        if np.sum(mask) == 0:
            return

        # Fazer correlação (valid = sem extrapolar fronteiras)
        corr = correlate2d(grid_bin, mask, mode='valid')

        # Encontrar posição de melhor matching
        gy, gx = np.unravel_index(np.argmax(corr), corr.shape)

        self.estimated_pose[0] = gx * self.resolution
        self.estimated_pose[1] = gy * self.resolution

        print(f"[REFINE-CORR] Nova pose refinada com correlação: ({self.estimated_pose[0]:.2f}, {self.estimated_pose[1]:.2f})")
    
    def build_scan_mask(self, scan_data, size=21):
        mask = np.zeros((size, size), dtype=np.uint8)
        center = size // 2

        for obj in scan_data.get("nearby_objects", []):
            if obj["type"] not in ("obstacle", "border"):
                continue
            rel_x, rel_y = obj["relative_position"]
            gx = int(center + rel_x / self.resolution)
            gy = int(center - rel_y / self.resolution)
            if 0 <= gx < size and 0 <= gy < size:
                mask[gy, gx] = 1

        return gaussian_filter(mask, sigma=1)
'''