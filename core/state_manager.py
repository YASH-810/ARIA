import threading
import time

class StateManager:
    _instance = None
    _creation_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._creation_lock:
                if cls._instance is None:
                    cls._instance = super(StateManager, cls).__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._current_state = "idle"
        self._state_lock = threading.Lock()
        self._state_cond = threading.Condition(self._state_lock)
        self._valid_states = {"idle", "listening", "thinking", "speaking", "executing"}
        
        # Define allowed transitions based on requirements + practical edge cases
        self._valid_transitions = {
            "idle": {"listening", "thinking", "executing", "speaking"},
            "listening": {"thinking", "idle"},
            "thinking": {"speaking", "executing", "idle"},
            "speaking": {"idle", "listening", "thinking"},   # thinking: mid-speech interrupt
            "executing": {"idle", "speaking", "listening", "thinking"}
        }

    def set_state(self, new_state):
        with self._state_cond:
            if new_state not in self._valid_states:
                return False
                
            if self._current_state != new_state:
                if new_state not in self._valid_transitions.get(self._current_state, set()):
                    return False
                self._current_state = new_state
                self._state_cond.notify_all()
                
            return True

    def get_state(self):
        with self._state_lock:
            return self._current_state

    def is_state(self, state):
        with self._state_lock:
            return self._current_state == state

    def wait_for_state(self, state, timeout=None):
        start = time.time()
        with self._state_cond:
            while self._current_state != state:
                if timeout is not None:
                    remaining = timeout - (time.time() - start)
                    if remaining <= 0:
                        return False
                    self._state_cond.wait(timeout=remaining)
                else:
                    self._state_cond.wait()
            return True

# Global singleton instance
state_manager = StateManager()
