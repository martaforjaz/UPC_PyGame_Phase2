"""
Smart Agent - Versão com Modelo de Mundo Interno
"""

import requests
import time
import math
from src.settings import API_URL
from world_model import WorldModel  # Importa o modelo de mundo

class SmartAgent:
    def __init__(self):
        self.player_id = None
        self.angle = 0
        self.health = 100
        self.game_started = False
        self.last_scan_time = 0
        self.connection_retries = 3
        self.world_model = WorldModel()  # Instancia o modelo de mundo
        self.connect()

    def robust_request(self, method, endpoint, **kwargs):
        """Método de requisição com tratamento de erros avançado"""
        for attempt in range(self.connection_retries):
            try:
                response = requests.request(
                    method,
                    f"{API_URL}{endpoint}",
                    timeout=1.5,
                    **kwargs
                )
                return response
            except requests.exceptions.ConnectionError as e:
                print(f"⚠️ Erro de conexão (tentativa {attempt + 1}): {str(e)}")
                if attempt < self.connection_retries - 1:
                    time.sleep(1)
            except requests.exceptions.Timeout:
                print(f"⌛ Timeout (tentativa {attempt + 1})")
                if attempt < self.connection_retries - 1:
                    time.sleep(1)
            except Exception as e:
                print(f"⚠️ Erro inesperado: {str(e)}")
                break
        return None

    def connect(self):
        """Conecta ao servidor com múltiplas tentativas"""
        print("🟢 Conectando ao servidor...")
        response = self.robust_request("POST", "/connect", json={"agent_name": "SmartAgent_Pro"})
        
        if response and response.status_code == 200:
            self.player_id = response.json().get("player_id")
            print(f"✅ Conectado como jogador {self.player_id}")
        else:
            print("❌ Falha na conexão após várias tentativas")
            raise ConnectionError("Não foi possível conectar ao servidor")

    def send_ready(self):
        """Envia sinal de pronto com confirmação"""
        response = self.robust_request("POST", f"/player/ready/{self.player_id}")
        if response and response.status_code == 200:
            print("✅ Sinal de pronto confirmado")
            return True
        return False

    def update_game_state(self):
        """Atualiza o estado do jogo de forma consistente"""
        response = self.robust_request("GET", f"/player/{self.player_id}/game-state")
         
        if response and response.status_code == 200:
            game_state = response.json()
            
            print("\n=== ESTADO DO JOGO ===")
            print(f"Tempo de jogo: {game_state.get('game_time', 0):.1f}s")
        
            self.angle = game_state.get('angle', self.angle)
            
            # Mostra informações de todos os jogadores
            players = game_state.get('players', [])
            print(f"Jogadores ativos: {len(players)}")
            for player in players:
                status = "✅" if player.get('health', 0) > 0 else "💀"
                print(f"  {status} {player.get('name', 'unknown')} - Saúde: {player.get('health', 0)} | Pos: {player.get('position', [0,0])}")
            
             # Atualiza saúde do próprio agente
            self.health = game_state.get('health', self.health)
            self.world_model.health = self.health
            
            return True
        print("⚠️ Não foi possível atualizar o estado do jogo")
        return False

    def update_scan_data(self):
        response = self.robust_request("GET", f"/player/{self.player_id}/scan")
        if response and response.status_code == 200:
            scan_data = response.json()
            
            print("\n=== DADOS DO SCAN ===")
            print(f"Timestamp: {time.strftime('%H:%M:%S')}")
        
             # Processa dados do scan
            success = self.world_model.update_from_scan(scan_data)

            # Verifica inimigos próximos
            self.world_model.has_nearby_enemies()
            
            # Mostra mapa local
            self.world_model.print_local_grid(radius=10)
            
            return success
    
        print("❌ Falha ao obter dados do scan")
        return False

    def strategic_movement(self):
        if not self.game_started:
            return
        
        # Atualiza o mapa de navegação
        nav_map = self.world_model.get_navigation_map()
        
        # Debug: mostra o estado atual
        print("\n🧭 Estado Atual:")
        print(f"- Posição: {self.world_model.agent_pos}")
        print(f"- Ângulo: {math.degrees(self.world_model.agent_angle):.1f}°")
        '''
        # Encontra direção segura
        safe_dir = self.world_model.find_safe_direction()
        print(f"🎯 Direção escolhida: {safe_dir.upper()}")
        
        # Executa ação
        if safe_dir == 'front':
            self.robust_request("POST", f"/player/{self.player_id}/thrust_forward")
        elif safe_dir == 'right':
            self.robust_request("POST", f"/player/{self.player_id}/rotate_right")
        elif safe_dir == 'left':
            self.robust_request("POST", f"/player/{self.player_id}/rotate_left")
        else:  # back
            self.robust_request("POST", f"/player/{self.player_id}/thrust_backward")
        
        # Atualiza posição estimada
        self.world_model.update_position(
            movement=1.0, 
            rotation=0.1 if safe_dir == 'right' else -0.1 if safe_dir == 'left' else 0
        )
        '''
    def run(self):
        """Loop principal do agente"""
        if not self.send_ready():
            print("⚠️ Atenção: Sinal de pronto não confirmado - continuando...")

        print("🕒 Aguardando início do jogo...")
        start_time = time.time()
        
        # Espera ativa pelo início do jogo
        while time.time() - start_time < 30:
            if self.update_scan_data():
                self.game_started = True
                print("🎮 JOGO INICIADO!")
                break
            time.sleep(0.5)
        
        if not self.game_started:
            print("❌ Timeout: Jogo não iniciou")
            return
    
        # Loop principal do jogo
        while self.game_started:
            try:
                # Atualiza estados
                self.update_game_state()
                has_enemies = self.update_scan_data()
                
                # Executa movimento estratégico
                self.strategic_movement()
                
                # Intervalo para reduzir carga
                time.sleep(0.3)
                
            except KeyboardInterrupt:
                print("\n🛑 Agente interrompido pelo usuário")
                break
            except Exception as e:
                print(f"\n⚠️ Erro no loop principal: {str(e)}")
                time.sleep(1)

if __name__ == "__main__":
    try:
        agent = SmartAgent()
        agent.run()
    except Exception as e:
        print(f"❌ Erro fatal: {str(e)}")