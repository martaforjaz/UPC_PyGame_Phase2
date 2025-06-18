import requests
import time
from world_model import WorldModel
import heapq
import math
import numpy as np

class SmartAgent:
    def __init__(self):
        self.player_id = None
        self.api_base = "http://127.0.0.1:8000"
        self.last_scan_time = 0
        self.start_time = time.time()
        self.scan_cooldown = 0.
        self.world_model = WorldModel(grid_size=100, resolution=4, agent_id=str(id(self)))
        self.path = []
        self.last_shot_time = 0
        self.shot_cooldown = 1.0
        self.last_plan_time = 0
        self.plan_interval = 0.5
        
        # NOVO: Sistema melhorado de evitamento de obstáculos
        self.obstacle_avoidance_mode = False
        self.avoidance_phase = "turn_away"
        self.avoidance_start_time = 0
        self.obstacle_detection_distance = 70
        self.border_detection_distance = 120
        self.alignment_tolerance = 0.15
        
        # NOVO: Sistema de prevenção proativa
        self.prevention_active = False
        self.last_direction_check = 0

    def connect(self, agent_name="smart_agent_safe"):
        try:
            response = requests.post(
                f"{self.api_base}/connect",
                json={"agent_name": agent_name},
                timeout=2
            )
            response.raise_for_status()
            data = response.json()
            self.player_id = data.get("player_id")
            print(f"[INFO] Connected successfully. Player ID: {self.player_id}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def ready_up(self):
        try:
            response = requests.post(
                f"{self.api_base}/player/ready/{self.player_id}",
                timeout=1
            )
            response.raise_for_status()
            print(f"[INFO] Player {self.player_id} is ready to play.")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to set ready status: {e}")

    def get_self_state(self):
        try:
            response = requests.get(
                f"{self.api_base}/player/{self.player_id}/state",
                timeout=1
            )
            if response.status_code == 404:
                print(f"[WARN] Player state not found for {self.player_id}")
                return None
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Exception getting player state: {e}")
            return None

    def get_scan(self):
        now = time.time()
        if now - self.last_scan_time < self.scan_cooldown:
            time.sleep(self.scan_cooldown - (now - self.last_scan_time))

        try:
            response = requests.get(
                f"{self.api_base}/player/{self.player_id}/scan",
                timeout=1
            )
            self.last_scan_time = time.time()

            if response.status_code == 429:
                wait_time = float(response.headers.get('Retry-After', 0.6))
                time.sleep(wait_time)
                return self.get_scan()
            elif response.status_code == 200:
                return response.json()
            else:
                print(f"[WARN] Scan failed with status {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Scan exception: {e}")
            return None

    def send_action(self, action: str):
        try:
            response = requests.post(
                f"{self.api_base}/player/{self.player_id}/{action}",
                timeout=1
            )
            if response.status_code != 200:
                print(f"[WARN] Action '{action}' failed with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to send action '{action}': {e}")

    def rotate_left(self):
        self.send_action("rotate_left")

    def rotate_right(self):
        self.send_action("rotate_right")

    def thrust(self):
        self.send_action("thrust_forward")
    
    def reverse(self):
        self.send_action("thrust_backward")

    def basic_movement(self):
        self.send_action("rotate_right")
        self.send_action("thrust_forward")

    def check_boundary_proximity(self, position):
        """
        NOVO: Verifica proximidade às bordas usando limites do mapa
        """
        try:
            distance = self.world_model.get_distance_to_boundary(position)
            
            if distance < self.world_model.CRITICAL_MARGIN:
                return "critical", distance
            elif distance < self.world_model.DANGER_MARGIN:
                return "danger", distance
            elif distance < self.world_model.SAFE_ZONE_MARGIN:
                return "warning", distance
            else:
                return "safe", distance
        except:
            return "safe", 200  # Fallback se função não existe

    def detect_obstacle_or_border(self, scan, position):
        """
        Detecção melhorada de obstáculos e bordas
        """
        if not scan or "nearby_objects" not in scan:
            return False, None

        closest_threat = None
        min_distance = float('inf')

        # Verifica objetos do scan
        for obj in scan["nearby_objects"]:
            if obj["type"] in ["obstacle", "border"]:
                distance = obj["distance"]
                detection_limit = (self.border_detection_distance if obj["type"] == "border" 
                                 else self.obstacle_detection_distance)
                
                if distance < detection_limit and distance < min_distance:
                    min_distance = distance
                    closest_threat = {
                        "type": obj["type"],
                        "distance": distance,
                        "relative_position": obj["relative_position"]
                    }

        # NOVO: Verifica proximidade às bordas do mapa
        boundary_status, boundary_distance = self.check_boundary_proximity(position)
        
        if boundary_status in ["critical", "danger"] and boundary_distance < min_distance:
            closest_threat = {
                "type": "map_boundary",
                "distance": boundary_distance,
                "relative_position": None
            }

        return closest_threat is not None, closest_threat

    def proactive_boundary_prevention(self, position, orientation):
        """
        NOVO: Sistema de prevenção proativa - evita chegar às bordas
        """
        boundary_status, distance = self.check_boundary_proximity(position)
        
        if boundary_status == "critical":
            print(f"[PREVENTION] ZONA CRÍTICA! Distância: {distance:.1f} - Reorientando para centro")
            self.prevention_active = True
            
            # Calcula direção para o centro
            center = self.world_model.get_safe_center()
            dx = center[0] - position[0]
            dy = center[1] - position[1]
            angle_to_center = math.atan2(dy, dx)
            angle_diff = (angle_to_center - orientation + math.pi) % (2 * math.pi) - math.pi
            
            if abs(angle_diff) > 0.2:
                if angle_diff > 0:
                    self.rotate_right()
                else:
                    self.rotate_left()
                return True
            else:
                self.thrust()
                return True
                
        elif boundary_status == "danger":
            # Verifica se movimento atual é perigoso
            future_x = position[0] + math.cos(orientation) * 30
            future_y = position[1] + math.sin(orientation) * 30
            future_status, _ = self.check_boundary_proximity([future_x, future_y])
            
            if future_status == "critical":
                print(f"[PREVENTION] Movimento perigoso detectado - reorientando")
                self.prevention_active = True
                
                # Encontra direção segura
                safe_direction = self.world_model.find_safe_direction(position, orientation)
                if safe_direction is not None:
                    angle_diff = (safe_direction - orientation + math.pi) % (2 * math.pi) - math.pi
                    if abs(angle_diff) > 0.3:
                        if angle_diff > 0:
                            self.rotate_right()
                        else:
                            self.rotate_left()
                        return True
                
        # Sai do modo prevenção se está seguro
        if boundary_status == "safe" and self.prevention_active:
            print(f"[PREVENTION] Saiu da zona de perigo - distância: {distance:.1f}")
            self.prevention_active = False
            
        return False

    def calculate_escape_direction(self, obstacle_info, position):
        """Calcula direção oposta ao obstáculo para escapar"""
        if obstacle_info.get('relative_position') is None:
            # Para map_boundary, calcula direção para o centro
            center = [0, 0]
            dx = center[0] - position[0]
            dy = center[1] - position[1]
            return math.atan2(dy, dx)
        
        rel_x, rel_y = obstacle_info['relative_position']
        # Direção OPOSTA ao obstáculo
        escape_angle = math.atan2(-rel_y, -rel_x)
        return escape_angle

    def calculate_angle_to_center(self, position, orientation):
        """Calcula ângulo para alinhar com o centro do mapa"""
        center = [0, 0]
        dx = center[0] - position[0]
        dy = center[1] - position[1]
        angle_to_center = math.atan2(dy, dx)
        angle_diff = (angle_to_center - orientation + math.pi) % (2 * math.pi) - math.pi
        return angle_to_center, angle_diff

    def is_aligned_with_center(self, position, orientation):
        """Verifica se está alinhado com o centro"""
        _, angle_diff = self.calculate_angle_to_center(position, orientation)
        return abs(angle_diff) < self.alignment_tolerance

    def execute_obstacle_avoidance(self, position, orientation, obstacle_info):
        """
        Executa sequência de evitamento em 4 fases
        """
        if self.avoidance_phase == "turn_away":
            print(f"[AVOIDANCE] TURN_AWAY - Virando costas ao {obstacle_info['type']} a {obstacle_info['distance']:.1f}px")
            
            escape_direction = self.calculate_escape_direction(obstacle_info, position)
            angle_diff = (escape_direction - orientation + math.pi) % (2 * math.pi) - math.pi
            
            if abs(angle_diff) < 0.15:
                print(f"[AVOIDANCE] Orientado para escapar, passando para MOVE_AWAY")
                self.avoidance_phase = "move_away"
                return
            
            if angle_diff > 0:
                self.rotate_right()
            else:
                self.rotate_left()
            
        elif self.avoidance_phase == "move_away":
            print(f"[AVOIDANCE] MOVE_AWAY - Fugindo do {obstacle_info['type']} a {obstacle_info['distance']:.1f}px")
            
            if obstacle_info['type'] == 'border' or obstacle_info['type'] == 'map_boundary':
                safe_distance = 150  # Maior distância para bordas
            else:
                safe_distance = 100
            
            if obstacle_info['distance'] > safe_distance:
                print(f"[AVOIDANCE] Distância segura alcançada, passando para ALIGN")
                self.avoidance_phase = "align"
                return
            
            # Verifica se ainda está orientado corretamente
            escape_direction = self.calculate_escape_direction(obstacle_info, position)
            angle_diff = (escape_direction - orientation + math.pi) % (2 * math.pi) - math.pi
            
            if abs(angle_diff) > 0.3:
                print(f"[AVOIDANCE] Perdeu orientação de escape, voltando para TURN_AWAY")
                self.avoidance_phase = "turn_away"
                return
            
            self.thrust()
            
        elif self.avoidance_phase == "align":
            print(f"[AVOIDANCE] ALIGN - Alinhando com centro")
            
            if self.is_aligned_with_center(position, orientation):
                print(f"[AVOIDANCE] Alinhado! Passando para MOVE_TO_CENTER")
                self.avoidance_phase = "move_to_center"
                return
            
            _, angle_diff = self.calculate_angle_to_center(position, orientation)
            
            if angle_diff > 0:
                self.rotate_right()
            else:
                self.rotate_left()
                
        elif self.avoidance_phase == "move_to_center":
            print(f"[AVOIDANCE] MOVE_TO_CENTER - Indo para centro")
            
            distance_to_center = math.sqrt(position[0]**2 + position[1]**2)
            boundary_status, _ = self.check_boundary_proximity(position)
            
            if distance_to_center < 60 or boundary_status == "safe":
                print(f"[AVOIDANCE] Chegou ao centro/zona segura! Saindo do modo evitamento")
                self.obstacle_avoidance_mode = False
                self.avoidance_phase = "turn_away"
                self.path = []
                return
            
            if not self.is_aligned_with_center(position, orientation):
                print(f"[AVOIDANCE] Perdeu alinhamento, voltando para ALIGN")
                self.avoidance_phase = "align"
                return
            
            self.thrust()

    def run(self):
        if not self.connect():
            return

        self.ready_up()
        print("[INFO] Smart agent with safe strategy running...")

        try:
            while True:
                scan = self.get_scan()
                self_state = self.get_self_state()

                if not scan or "nearby_objects" not in scan or not self_state:
                    time.sleep(0.1)
                    continue

                # Atualiza o modelo do mundo
                self.world_model.update_pose(self_state)
                self.world_model.update_from_scan(scan)

                position = self_state.get("position") or self_state.get("pos") or [0, 0]
                orientation = self_state.get("orientation") or self_state.get("angle") or 0

                # PRIORIDADE 1: COMBATE - Se deteta inimigo próximo, SEMPRE persegue e atira
                enemy_detected = False
                for obj in scan.get("nearby_objects", []):
                    if obj["type"] == "other_player":
                        rel_x, rel_y = obj["relative_position"]
                        distance = obj["distance"]
                        angle_to_enemy = math.atan2(rel_y, rel_x)
                        angle_diff = (angle_to_enemy - orientation + math.pi) % (2 * math.pi) - math.pi
                        
                        enemy_detected = True
                        print(f"[COMBAT] Inimigo detectado a {distance:.1f}px, ângulo: {angle_to_enemy:.2f}")
                        
                        # TIRO IMEDIATO se alinhado
                        if abs(angle_to_enemy) < 0.26:  # ±15 graus
                            now = time.time()
                            if now - self.last_shot_time > self.shot_cooldown:
                                print("[COMBAT] ALINHADO! DISPARAR!")
                                self.send_action("shoot")
                                self.last_shot_time = now
                        
                        # PERSEGUIÇÃO DIRETA - ignora sistemas de segurança para combate
                        if abs(angle_diff) > 0.2:
                            if angle_diff > 0:
                                self.rotate_right()
                            else:
                                self.rotate_left()
                            print(f"[COMBAT] Rodando para inimigo - diferença: {angle_diff:.2f}")
                        else:
                            # Se inimigo está longe, aproxima-se
                            if distance > 40:
                                # Verifica se movimento é EXTREMAMENTE perigoso (muito perto das bordas)
                                future_x = position[0] + math.cos(orientation) * 20
                                future_y = position[1] + math.sin(orientation) * 20
                                future_distance = self.world_model.get_distance_to_boundary([future_x, future_y])
                                
                                if future_distance > 50:  # Margem mínima para combate
                                    self.thrust()
                                    print(f"[COMBAT] Perseguindo inimigo")
                                else:
                                    print(f"[COMBAT] Movimento muito perigoso, só atirando")
                            else:
                                print(f"[COMBAT] Inimigo próximo, mantendo posição e atirando")
                        
                        break  # Só processa o primeiro inimigo
                
                # PRIORIDADE 2: Sistema de prevenção (só se NÃO há inimigo próximo)
                if not enemy_detected and self.proactive_boundary_prevention(position, orientation):
                    time.sleep(0.05)
                    continue

                # PRIORIDADE 3: Sistema de evitamento de obstáculos (só se NÃO há inimigo próximo)
                if not enemy_detected:
                    has_obstacle, obstacle_info = self.detect_obstacle_or_border(scan, position)
                    
                    if has_obstacle or self.obstacle_avoidance_mode:
                        if not self.obstacle_avoidance_mode:
                            print(f"[AVOIDANCE] ATIVADO! Detectado: {obstacle_info}")
                            self.obstacle_avoidance_mode = True
                            self.avoidance_start_time = time.time()
                            self.avoidance_phase = "turn_away"
                            self.path = []
                        
                        self.execute_obstacle_avoidance(position, orientation, obstacle_info or 
                                                       {"type": "unknown", "distance": 50, "relative_position": None})
                        
                        if time.time() - self.avoidance_start_time > 12:
                            print("[AVOIDANCE] TIMEOUT! Forçando saída")
                            self.obstacle_avoidance_mode = False
                            self.avoidance_phase = "turn_away"
                        
                        time.sleep(0.05)
                        continue

                # PRIORIDADE 4: Exploração/perseguição de longo alcance (só se NÃO há inimigo próximo)
                if not enemy_detected:
                    enemy_pos = self.world_model.get_closest_enemy_position()
                    now = time.time()

                    if enemy_pos:
                        # Para perseguição de longo alcance, verifica segurança
                        enemy_boundary_status, _ = self.check_boundary_proximity(enemy_pos)
                        
                        if enemy_boundary_status in ["safe", "warning"]:
                            goal = enemy_pos
                            self.path = self.world_model.plan_path_a_star(position, goal)
                            self.last_plan_time = now
                            print(f"[DEBUG] Perseguição longo alcance: {goal}")
                        else:
                            print(f"[DEBUG] Inimigo distante em zona perigosa, explorando")
                            goal = self.world_model.get_smart_exploration_goal(position)
                            self.path = self.world_model.plan_path_a_star(position, goal)
                            self.last_plan_time = now
                    else:
                        # Exploração normal
                        if not self.path or len(self.path) < 2 or (now - self.last_plan_time) > self.plan_interval:
                            goal = self.world_model.get_smart_exploration_goal(position)
                            new_path = self.world_model.plan_path_a_star(position, goal)
                            if new_path:
                                self.path = new_path
                                self.last_plan_time = now
                                print(f"[DEBUG] Nova exploração: {goal}")
                            else:
                                print("[DEBUG] Caminho não encontrado. Indo para centro.")
                                goal = self.world_model.get_safe_center()
                                self.path = self.world_model.plan_path_a_star(position, goal)

                    print(f"[DEBUG] Planeado {len(self.path)} passos até goal")
                    
                    # Movimento seguro pelo caminho (só para exploração)
                    if self.path:
                        next_target = self.path[0]
                        
                        target_boundary_status, target_distance = self.check_boundary_proximity(next_target)
                        
                        if target_boundary_status == "critical":
                            print(f"[DEBUG] Próximo target crítico (dist: {target_distance:.1f}), limpando")
                            self.path = []
                            time.sleep(0.05)
                            continue
                        
                        dx = next_target[0] - position[0]
                        dy = next_target[1] - position[1]
                        angle_to_target = math.atan2(dy, dx)
                        angle_diff = (angle_to_target - orientation + math.pi) % (2 * math.pi) - math.pi

                        if abs(angle_diff) > 0.3:
                            if angle_diff > 0:
                                self.rotate_right()
                            else:
                                self.rotate_left()
                        else:
                            # Verificação antes de thrust para exploração
                            future_x = position[0] + math.cos(orientation) * 15
                            future_y = position[1] + math.sin(orientation) * 15
                            future_status, _ = self.check_boundary_proximity([future_x, future_y])
                            
                            if future_status not in ["critical"]:
                                self.thrust()
                                if math.hypot(dx, dy) < 5:
                                    self.path.pop(0)
                            else:
                                print(f"[DEBUG] Thrust exploração cancelado - zona crítica")
                                self.path = []

                time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n[INFO] Agent stopped by user")
        except Exception as e:
            print(f"[ERROR] Unexpected error in main loop: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    agent = SmartAgent()
    agent.run()