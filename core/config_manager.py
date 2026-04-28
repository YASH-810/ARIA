import json
import os

CONFIG_PATH = "config/config.json"

class ConfigManager:
    def __init__(self):
        self.config = {}
        self.load()

    def load(self):
        if not os.path.exists(CONFIG_PATH):
            self.create_default()

        with open(CONFIG_PATH, "r") as f:
            self.config = json.load(f)

    def create_default(self):
        os.makedirs("config", exist_ok=True)
        default_config = {
            "user_name": "Yash",
            "model": "phi3",
            "tts_enabled": True,
            "context_enabled": True,
            "debug": True
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(default_config, f, indent=4)

    def save(self):
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.config, f, indent=4)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

# Global instance
config = ConfigManager()
