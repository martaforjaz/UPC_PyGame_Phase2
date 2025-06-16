"""
World Model - Representação interna do ambiente do agente
"""

import numpy as np
from collections import deque
import math

class WorldModel:
    def __init__(self, grid_size=100, resolution=1.0):
        """
        Inicializa o modelo interno do mundo
        
        Args:
            grid_size: Tamanho do grid (cria grid_size x grid_size)
            resolution: Metros por célula (escala do mapa)
        """
        self.grid_size = grid_size
        self.resolution = resolution
        self.grid = np.zeros((grid_size, grid_size))  # 0 = livre, 1 = ocupado
        self.agent_pos = (grid_size//2, grid_size//2)  # Posição inicial no centro
        self.agent_angle = 0  # Orientação em radianos
        self.landmarks = {}  # Dicionário de objetos identificados
        self.observation_history = deque(maxlen=100)  # Histórico de observações
        self.time_step = 0
        self.health = 100  # Saúde do agente
    '''  
    def update_position(self, movement, rotation):
        """
        Atualiza a posição estimada do agente usando odometria básica
        
        Args:
            movement: Distância percorrida (em unidades do jogo)
            rotation: Mudança no ângulo (em radianos)
        """
        self.agent_angle += rotation
        dx = movement * math.cos(self.agent_angle)
        dy = movement * math.sin(self.agent_angle)
        
        # Converter para coordenadas do grid
        grid_dx = int(round(dx / self.resolution))
        grid_dy = int(round(dy / self.resolution))
        
        self.agent_pos = (
            max(0, min(self.grid_size-1, self.agent_pos[0] + grid_dx)),
            max(0, min(self.grid_size-1, self.agent_pos[1] + grid_dy))
        )
        self.time_step += 1
     '''   
    def update_from_scan(self, scan_data):
        '''Processa dados do scan para identificar inimigos e obstáculos'''
        if not scan_data:
            print("⚠️ Scan data vazio ou inválido")
            return False

        # Debug: mostra dados recebidos
        print(f"\n📡 Processando dados do scan (Posição atual: {self.agent_pos})")
        
        # Limpa dados anteriores (opcional, dependendo da estratégia)
        self.landmarks.clear()
    
         # Verifica diferentes formatos de dados
        objects = scan_data.get('objects', []) or scan_data.get('nearby_objects', [])
        
        for obj in objects:
            obj_type = obj.get('type', 'unknown')
            rel_pos = obj.get('relative_position', [0, 0])
            distance = obj.get('distance', 0)
            
            # Converte posição relativa para absoluta (considerando orientação)
            abs_x = self.agent_pos[0] + int(rel_pos[0] / self.resolution)
            abs_y = self.agent_pos[1] + int(rel_pos[1] / self.resolution)
        
            # Garante que está dentro dos limites do grid
            abs_x = max(0, min(self.grid_size-1, abs_x))
            abs_y = max(0, min(self.grid_size-1, abs_y))
        
            # Debug das conversões
            print(f"Conversão: Relativo {rel_pos} -> Absoluto ({abs_x}, {abs_y})")
            # Atualiza grid (1 para obstáculos/inimigos)
            if obj_type in ['obstacle', 'other_player']:
                self.grid[abs_x, abs_y] = 1
            
            # Armazena o objeto detectado
            obj_id = f"{obj_type}_{abs_x}_{abs_y}"
            self.landmarks[obj_id] = {
                'type': obj_type,
                'pos': (abs_x, abs_y),
                'distance': distance,
                'relative_pos': rel_pos,
                'last_seen': self.time_step
            }
            
             # Atualiza grid (1 para obstáculos/inimigos)
            if obj_type in ['obstacle', 'other_player']:
                self.grid[abs_x, abs_y] = 1
            
            # Debug: mostra informações do objeto
            print(f"  → {obj_type.upper()} em ({abs_x}, {abs_y}) | Dist: {distance:.1f} | Rel: {rel_pos}")
            
        self.time_step += 1
        return True
    
    def has_nearby_enemies(self, max_distance=50):
        """Verifica se há inimigos dentro de uma distância máxima"""
        enemies = []
        for obj_id, data in self.landmarks.items():
            if data['type'] == 'other_player':
                dx = data['pos'][0] - self.agent_pos[0]
                dy = data['pos'][1] - self.agent_pos[1]
                distance = math.sqrt(dx**2 + dy**2) * self.resolution
                if distance <= max_distance:
                    enemies.append({
                    'id': obj_id,
                    'distance': distance,
                    'pos': data['pos'],
                    'relative_pos': data['relative_pos']
                })
        if enemies:
            print(f"⚠️ INIMIGOS PRÓXIMOS ({len(enemies)}):")
            for enemy in enemies:
                print(f"    - ID: {enemy['id']} | Dist: {enemy['distance']:.1f} | Pos: {enemy['pos']}")
            return True
        return False

 
    def get_navigation_map(self):
        """
        Retorna um mapa de navegação com custos
        """
        # Cria uma cópia do grid básico
        nav_map = np.copy(self.grid)
        
        print(self.grid)
        
         # Aplica dilatação para considerar o tamanho do agente
        kernel_size = 2  # Tamanho do agente em células
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if self.grid[i,j] == 1:
                    for di in range(-kernel_size, kernel_size+1):
                        for dj in range(-kernel_size, kernel_size+1):
                            ni, nj = i+di, j+dj
                            if 0 <= ni < self.grid_size and 0 <= nj < self.grid_size:
                                nav_map[ni,nj] = min(1, nav_map[ni,nj] + 0.2)
        
        return nav_map
            
    '''def find_safe_direction(self):
        """
        Encontra uma direção segura para movimento baseado no mapa interno
        Retorna: 'front', 'right', 'left' ou 'back'
        """
        nav_map = self.get_navigation_map()
        x, y = self.agent_pos
        
        # Definir regiões de análise (ajustar conforme necessário)
        sector_size = 5
        front_range = 10
        
        # Analisar setores ao redor
        sectors = {
            'front': nav_map[x-sector_size//2:x+sector_size//2, 
                            y:y+front_range],
            'right': nav_map[x:x+sector_size, 
                             y:y+front_range//2],
            'left': nav_map[x-sector_size:x, 
                           y:y+front_range//2],
            'back': nav_map[x-sector_size//2:x+sector_size//2, 
                           y-front_range//2:y]
        }
        
        # Escolher setor com menor densidade de obstáculos
        best_sector = min(sectors.items(), key=lambda item: np.mean(item[1]) if item[1].size > 0 else 999)
        return best_sector[0] if best_sector[1].size > 0 else 'front'
    '''
    def print_local_grid(self, radius=5):
        """Mostra uma visualização ampliada do grid"""
        x, y = self.agent_pos
        print("\n🌍 MAPA LOCAL (Agente='A', Obstáculos='▓', Inimigos='E')")
        
        for i in range(max(0, x-radius), min(self.grid_size, x+radius+1)):
            line = []
            for j in range(max(0, y-radius), min(self.grid_size, y+radius+1)):
                if (i, j) == self.agent_pos:
                    line.append("A")
                elif any(obj['pos'] == (i,j) and obj['type'] == 'enemy' 
                        for obj in self.landmarks.values()):
                    line.append("E")
                elif self.grid[i,j] == 1:
                    line.append("▓")
                else:
                    line.append(".")
            print(" ".join(line))