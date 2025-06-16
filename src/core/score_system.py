class ScoreSystem:
    def __init__(self, config):
        self.kill_points       = config["kill_points"]
        self.hit_points        = config["hit_points"]
        self.collision_penalty = config["collision_penalty"]
        self.shot_penalty      = config["shot_penalty"]
        self.life_penalty      = config["life_penalty"]
        self.scores = {}  # {agent_id: score}

    def register_agent(self, agent_id):
        self.scores[agent_id] = 0

    def on_kill(self, killer_id):
        self.scores[killer_id] += self.kill_points

    def on_hit(self, agent_id):
        self.scores[agent_id] += self.hit_points

    def on_collision(self, agent_id):
        self.scores[agent_id] -= self.collision_penalty

    def on_shot(self, agent_id):
        self.scores[agent_id] -= self.shot_penalty

    def on_game_end(self, remaining_life):
        # remaining_life: dict {agent_id: life_points}
        for aid, life in remaining_life.items():
            self.scores[aid] -= life * self.life_penalty

    def get_score(self, agent_id):
        return self.scores.get(agent_id, 0)