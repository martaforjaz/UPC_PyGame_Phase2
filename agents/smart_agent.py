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
        self.scan_cooldown = 0.3  # Scan mais rápido para combate
        self.world_model = WorldModel(grid_size=100, resolution=4, agent_id=str(id(self)))
        self.path = []
        self.last_shot_time = 0
        self.shot_cooldown = 0.8  # Tiro mais rápido
        self.last_plan_time = 0
        self.plan_interval = 0.5
        
        # Sistema de evitamento de obstáculos
        self.obstacle_avoidance_mode = False
        self.avoidance_phase = "turn_away"
        self.avoidance_start_time = 0
        self.obstacle_detection_distance = 70
        self.border_detection_distance = 120
        self.alignment_tolerance = 0.15
        
        # Sistema de prevenção proativa
        self.prevention_active = False
        self.last_direction_check = 0

    def connect(self, agent_name="smart_agent_hunter"):
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
                return None
            return response.json()
        except requests.exceptions.RequestException as e:
            return None

    def get_scan(self):
        now = time.time()
        if now - self.last_scan_time < self.scan_cooldown:
            return None  # Não espera, retorna None para velocidade

        try:
            response = requests.get(
                f"{self.api_base}/player/{self.player_id}/scan",
                timeout=0.8
            )
            self.last_scan_time = time.time()

            if response.status_code == 200:
                return response.json()
            else:
                return None
        except requests.exceptions.RequestException as e:
            return None

    def send_action(self, action: str):
        try:
            response = requests.post(
                f"{self.api_base}/player/{self.player_id}/{action}",
                timeout=0.5
            )
        except requests.exceptions.RequestException as e:
            pass  # Ignora erros para velocidade

    def rotate_left(self):
        self.send_action("rotate_left")

    def rotate_right(self):
        self.send_action("rotate_right")

    def thrust(self):
        self.send_action("thrust_forward")
    
    def reverse(self):
        self.send_action("thrust_backward")

    def check_boundary_proximity(self, position):
        """Verifica proximidade às bordas usando limites do mapa"""
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
            return "safe", 200

    def detect_obstacle_or_border(self, scan, position):
        """Detecção de obstáculos e bordas"""
        if not scan or "nearby_objects" not in scan:
            return False, None

        closest_threat = None
        min_distance = float('inf')

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

        # Verifica proximidade às bordas do mapa
        boundary_status, boundary_distance = self.check_boundary_proximity(position)
        
        if boundary_status in ["critical", "danger"] and boundary_distance < min_distance:
            closest_threat = {
                "type": "map_boundary",
                "distance": boundary_distance,
                "relative_position": None
            }

        return closest_threat is not None, closest_threat

    def calculate_escape_direction(self, obstacle_info, position):
        """Calcula direção oposta ao obstáculo para escapar"""
        if obstacle_info.get('relative_position') is None:
            center = [0, 0]
            dx = center[0] - position[0]
            dy = center[1] - position[1]
            return math.atan2(dy, dx)
        
        rel_x, rel_y = obstacle_info['relative_position']
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
        """Executa sequência de evitamento"""
        if self.avoidance_phase == "turn_away":
            print(f"[AVOIDANCE] TURN_AWAY - Virando costas ao {obstacle_info['type']}")
            
            escape_direction = self.calculate_escape_direction(obstacle_info, position)
            angle_diff = (escape_direction - orientation + math.pi) % (2 * math.pi) - math.pi
            
            if abs(angle_diff) < 0.15:
                self.avoidance_phase = "move_away"
                return
            
            if angle_diff > 0:
                self.rotate_right()
            else:
                self.rotate_left()
            
        elif self.avoidance_phase == "move_away":
            print(f"[AVOIDANCE] MOVE_AWAY - Fugindo")
            
            safe_distance = 150 if obstacle_info['type'] in ['border', 'map_boundary'] else 100
            
            if obstacle_info['distance'] > safe_distance:
                self.avoidance_phase = "align"
                return
            
            self.thrust()
            
        elif self.avoidance_phase == "align":
            print(f"[AVOIDANCE] ALIGN - Alinhando com centro")
            
            if self.is_aligned_with_center(position, orientation):
                self.avoidance_phase = "move_to_center"
                return
            
            _, angle_diff = self.calculate_angle_to_center(position, orientation)
            
            if angle_diff > 0:
                self.rotate_right()
            else:
                self.rotate_left()
                
        elif self.avoidance_phase == "move_to_center":
            print(f"[AVOIDANCE] MOVE_TO_CENTER")
            
            distance_to_center = math.sqrt(position[0]**2 + position[1]**2)
            boundary_status, _ = self.check_boundary_proximity(position)
            
            if distance_to_center < 60 or boundary_status == "safe":
                self.obstacle_avoidance_mode = False
                self.avoidance_phase = "turn_away"
                self.path = []
                return
            
            self.thrust()

    def run(self):
        if not self.connect():
            return

        self.ready_up()
        print("[INFO] Smart hunter agent running...")

        try:
            while True:
                scan = self.get_scan()
                self_state = self.get_self_state()

                if not self_state:
                    time.sleep(0.03)
                    continue

                # Atualiza o modelo do mundo
                if scan and "nearby_objects" in scan:
                    self.world_model.update_pose(self_state)
                    self.world_model.update_from_scan(scan)

                position = self_state.get("position", [0, 0])
                orientation = self_state.get("orientation", 0)

                # PRIORIDADE 1: COMBATE AGRESSIVO - SEMPRE persegue inimigos
                enemy_detected = False
                if scan and "nearby_objects" in scan:
                    for obj in scan.get("nearby_objects", []):
                        if obj["type"] == "other_player":
                            rel_x, rel_y = obj["relative_position"]
                            distance = obj["distance"]
                            angle_to_enemy = math.atan2(rel_y, rel_x)
                            angle_diff = (angle_to_enemy - orientation + math.pi) % (2 * math.pi) - math.pi
                            
                            enemy_detected = True
                            print(f"[HUNTER] 🎯 INIMIGO DETECTADO a {distance:.1f}px!")
                            
                            # SEMPRE se orienta para o inimigo PRIMEIRO
                            if abs(angle_diff) > 0.12:  # Tolerância menor = mais preciso
                                if angle_diff > 0:
                                    self.rotate_right()
                                else:
                                    self.rotate_left()
                                print(f"[HUNTER] 🔄 Virando para inimigo (dif: {angle_diff:.2f})")
                            else:
                                # Já está bem orientado para o inimigo
                                print(f"[HUNTER] ✅ ALINHADO com inimigo!")
                                
                                # ATIRA se perfeitamente alinhado
                                if abs(angle_to_enemy) < 0.2:  # ±11.5 graus
                                    now = time.time()
                                    if now - self.last_shot_time > self.shot_cooldown:
                                        print("[HUNTER] 💥 FOGO!")
                                        self.send_action("shoot")
                                        self.last_shot_time = now
                                
                                # PERSEGUE SEMPRE (exceto se extremamente perigoso)
                                boundary_status, boundary_dist = self.check_boundary_proximity(position)
                                
                                if boundary_status != "critical":
                                    self.thrust()
                                    print(f"[HUNTER] 🏃 PERSEGUINDO! (dist: {distance:.1f}px)")
                                else:
                                    print(f"[HUNTER] ⚠️ Zona crítica - só atirando (margem: {boundary_dist:.1f})")
                            
                            break  # Foca no primeiro inimigo

                # PRIORIDADE 2: Evitamento de obstáculos (só se NÃO há inimigo)
                if not enemy_detected:
                    has_obstacle, obstacle_info = self.detect_obstacle_or_border(scan, position)
                    
                    if has_obstacle or self.obstacle_avoidance_mode:
                        if not self.obstacle_avoidance_mode:
                            print(f"[AVOIDANCE] Obstáculo detectado: {obstacle_info}")
                            self.obstacle_avoidance_mode = True
                            self.avoidance_start_time = time.time()
                            self.avoidance_phase = "turn_away"
                            self.path = []
                        
                        self.execute_obstacle_avoidance(position, orientation, obstacle_info or 
                                                       {"type": "unknown", "distance": 50, "relative_position": None})
                        
                        if time.time() - self.avoidance_start_time > 8:
                            self.obstacle_avoidance_mode = False
                            self.avoidance_phase = "turn_away"
                        
                        time.sleep(0.03)
                        continue

                # PRIORIDADE 3: Exploração agressiva (só se NÃO há inimigo)
                if not enemy_detected:
                    # Verifica se há inimigo distante no world_model
                    enemy_pos = self.world_model.get_closest_enemy_position()
                    now = time.time()

                    if enemy_pos:
                        print(f"[HUNTER] 🔍 Perseguindo inimigo distante: {enemy_pos}")
                        goal = enemy_pos
                        self.path = self.world_model.plan_path_a_star(position, goal)
                        self.last_plan_time = now
                    else:
                        # Exploração agressiva
                        if not self.path or len(self.path) < 2 or (now - self.last_plan_time) > self.plan_interval:
                            try:
                                goal = self.world_model.get_smart_exploration_goal(position)
                            except:
                                # Fallback simples
                                center = [0, 0]
                                goal = center
                            
                            new_path = self.world_model.plan_path_a_star(position, goal)
                            if new_path:
                                self.path = new_path
                                self.last_plan_time = now
                                print(f"[HUNTER] 🗺️ Nova exploração: {goal}")

                    # Movimento pelo caminho
                    if self.path:
                        next_target = self.path[0]
                        
                        dx = next_target[0] - position[0]
                        dy = next_target[1] - position[1]
                        angle_to_target = math.atan2(dy, dx)
                        angle_diff = (angle_to_target - orientation + math.pi) % (2 * math.pi) - math.pi

                        if abs(angle_diff) > 0.25:
                            if angle_diff > 0:
                                self.rotate_right()
                            else:
                                self.rotate_left()
                        else:
                            # Verificação mínima de segurança
                            boundary_status, _ = self.check_boundary_proximity(position)
                            if boundary_status != "critical":
                                self.thrust()
                                if math.hypot(dx, dy) < 8:
                                    self.path.pop(0)

                time.sleep(0.03)  # Loop muito rápido

        except KeyboardInterrupt:
            print("\n[INFO] Hunter agent stopped by user")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")

if __name__ == "__main__":
    agent = SmartAgent()
    agent.run()