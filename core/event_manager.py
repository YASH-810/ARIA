"""
core/event_manager.py
---------------------
A minimal, thread-safe event bus for ARIA.

Components register listeners with on() and fire events with emit().
Nothing in the event system blocks the caller — listeners are invoked
synchronously in the order they were registered.

Supported events (by convention):
    "tts_start"          - TTS engine began playing audio
    "tts_end"            - TTS engine finished all queued audio
    "interrupt"          - User interrupted ongoing speech
    "speech_start"       - STT microphone opened / recording started
    "speech_end"         - STT recording stopped, text ready
    "command_executed"   - A system command was dispatched
"""

import threading


class EventManager:
    """Thread-safe, multi-listener event bus."""

    def __init__(self):
        self._listeners: dict[str, list] = {}
        self._lock = threading.Lock()

    # ── Registration ──────────────────────────────────────────────────────────

    def on(self, event_name: str, fn) -> None:
        """Register *fn* as a listener for *event_name*.

        Multiple listeners per event are allowed and are called in
        registration order.  Duplicate registrations of the same
        function are silently skipped.
        """
        with self._lock:
            listeners = self._listeners.setdefault(event_name, [])
            if fn not in listeners:
                listeners.append(fn)

    def off(self, event_name: str, fn) -> None:
        """Remove a previously registered listener.  No-op if not found."""
        with self._lock:
            listeners = self._listeners.get(event_name, [])
            try:
                listeners.remove(fn)
            except ValueError:
                pass

    # ── Emission ──────────────────────────────────────────────────────────────

    def emit(self, event_name: str, data=None) -> None:
        """Call every listener registered for *event_name*.

        Listeners are invoked with a single positional argument (data).
        If data is None the listener is called with no arguments so that
        simple zero-arg lambdas work without modification.

        Exceptions raised inside a listener are caught and printed; they
        never propagate to the caller or silence other listeners.
        """
        with self._lock:
            # Take a snapshot so listeners registered during emit() don't run
            listeners = list(self._listeners.get(event_name, []))

        for fn in listeners:
            try:
                if data is None:
                    fn()
                else:
                    fn(data)
            except Exception as exc:
                print(f"[EventManager] Error in '{event_name}' listener: {exc}")


# ── Global singleton ──────────────────────────────────────────────────────────

events = EventManager()
