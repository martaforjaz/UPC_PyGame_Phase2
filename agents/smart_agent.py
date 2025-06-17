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
        self.start_time = time.time()  # <- NOVO
        self.scan_cooldown = 0.6
        self.world_model = WorldModel(grid_size=200, resolution=2, agent_id=str(id(self)))
        self.path = []  # Caminho planeado a seguir com A*
        self.last_shot_time = 0
        self.shot_cooldown = 1.0  # segundos
        self.last_plan_time = 0  # Tempo do último planeamento de caminho
        self.plan_interval = 2.0  # Intervalo entre planos de caminho (em segundos)

    def connect(self, agent_name="smart_agent"):
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

    def basic_movement(self):
        self.send_action("rotate_right")
        self.send_action("thrust_forward")

    def run(self):
        if not self.connect():
            return

        self.ready_up()
        print("[INFO] Agent running...")

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

                # Estado atual
                position = self_state.get("position") or self_state.get("pos") or [0, 0]
                orientation = self_state.get("orientation") or self_state.get("angle") or 0

                # Objetivo: seguir inimigo mais próximo
                enemy_pos = self.world_model.get_closest_enemy_position()

                now = time.time()

                if enemy_pos:
                    # Se há inimigo, o objetivo é esse
                    goal = enemy_pos
                    # Replaneia sempre que há inimigo
                    self.path = self.world_model.plan_path_a_star(position, goal)
                    self.last_plan_time = now
                else:
                    goal = self.world_model.get_random_free_goal(position)
                    new_path = self.world_model.plan_path_a_star(position, goal)
                    if new_path:
                        self.path = new_path
                        self.last_plan_time = now
                    else:
                        print("[DEBUG] Caminho não encontrado. Ignorar este goal.")
                        self.path = []  # <- evita reutilizar caminho inválido

                print(f"[DEBUG] Planeado {len(self.path)} passos até goal {goal}")
                # Movimento pelo caminho
                if self.path:
                    next_target = self.path[0]
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
                        self.thrust()
                        if math.hypot(dx, dy) < 5:
                            self.path.pop(0)
                #print(f"[DEBUG] Dir. alvo: {angle_to_target:.2f} rad | Dir. atual: {orientation:.2f} | Diferença: {angle_diff:.2f}")

                # Disparo automático se inimigo estiver alinhado
                for obj in scan.get("nearby_objects", []):
                    if obj["type"] == "other_player":
                        rel_x, rel_y = obj["relative_position"]
                        angle_to_enemy = math.atan2(rel_y, rel_x)
                        if abs(angle_to_enemy) < 0.26:  # ±15 graus
                            now = time.time()
                            if now - self.last_shot_time > self.shot_cooldown:
                                print("[DEBUG] ALINHADO! DISPARAR!")
                                self.send_action("shoot")
                                self.last_shot_time = now

                time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n[INFO] Agent stopped by user")
        except Exception as e:
            print(f"[ERROR] Unexpected error in main loop: {e}")

if __name__ == "__main__":
    agent = SmartAgent()
    agent.run()