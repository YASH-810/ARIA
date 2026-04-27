import json
import os

MEMORY_PATH = "data/memory.json"

class MemoryManager:
    def __init__(self):
        self.memory = {}
        self.load()

    def load(self):
        if not os.path.exists(MEMORY_PATH):
            self.create_default()
            return  # create_default() already populated self.memory

        with open(MEMORY_PATH, "r") as f:
            self.memory = json.load(f)

    def create_default(self):
        os.makedirs("data", exist_ok=True)
        default = {
            "short_term": [],
            "long_term": {
                "user_name": "Yash",
                "preferences": {}
            }
        }
        self.memory = default  # populate in-memory immediately
        with open(MEMORY_PATH, "w") as f:
            json.dump(default, f, indent=4)

    def save(self):
        with open(MEMORY_PATH, "w") as f:
            json.dump(self.memory, f, indent=4)

    # SHORT TERM MEMORY
    def add_interaction(self, user, ai):
        self.memory["short_term"].append({
            "user": user,
            "ai": ai
        })

        # keep only last 5
        self.memory["short_term"] = self.memory["short_term"][-5:]

        self.save()

    def get_recent_context(self):
        return self.memory["short_term"]

    # LONG TERM MEMORY
    def set_long_term(self, key, value):
        self.memory["long_term"][key] = value
        self.save()

    def get_long_term(self, key, default=None):
        return self.memory["long_term"].get(key, default)

# global instance
memory = MemoryManager()
