import threading
import time

class StateManager:
    _instance = None
    _creation_lock = threading.Lock()

    def __new__(cls):
        with cls._creation_lock:
            if cls._instance is None:
                cls._instance = super(StateManager, cls).__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        self._current_state = "idle"
        self._state_lock = threading.Lock()
        self._valid_states = {"idle", "listening", "thinking", "speaking", "executing"}
        
        # Define allowed transitions based on requirements + practical edge cases
        self._valid_transitions = {
            "idle": {"listening", "thinking", "executing", "speaking"}, # speaking for greetings
            "listening": {"thinking", "idle"}, 
            "thinking": {"speaking", "executing", "idle"},
            "speaking": {"idle", "listening"},
            "executing": {"idle", "speaking", "listening"}
        }

    def set_state(self, new_state):
        with self._state_lock:
            if new_state not in self._valid_states:
                return False
                
            if self._current_state != new_state:
                if new_state not in self._valid_transitions.get(self._current_state, set()):
                    return False
                self._current_state = new_state
                
            return True

    def get_state(self):
        with self._state_lock:
            return self._current_state

    def is_state(self, state):
        with self._state_lock:
            return self._current_state == state

    def wait_for_state(self, state, timeout=None):
        start = time.time()
        while True:
            if self.is_state(state):
                return True
            if timeout and time.time() - start > timeout:
                return False
            time.sleep(0.05)

# Global singleton instance
state_manager = StateManager()
