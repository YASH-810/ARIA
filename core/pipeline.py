"""
core/pipeline.py
----------------
Central controller for ARIA's full interaction cycle.

Connects STT → LLM → TTS as a single coordinated flow using the existing
modules.  No logic is duplicated — every step delegates to its own module.

Interaction paths
-----------------

Text input (CLI typing):
    pipeline.run_once(text="tell me a joke")
        → interrupt any ongoing speech
        → emit user_input
        → route_command()  →  execute command, done
        → ask_ollama_stream()  →  enqueue_text() × N  →  TTS speaks

Voice input (F2 / /voice):
    pipeline.run_once()          # no text argument → triggers STT first
        → listen() (Whisper STT)
        → same path as above

Continuous voice loop:
    pipeline.run_loop()          # blocks; call pipeline.stop() from another thread

State flow
----------
    idle  →  thinking  →  speaking  →  idle
    interrupt:  speaking  →  idle  (stop_speaking resets)

Event catalogue (emitted here)
-------------------------------
    "user_input"      data: {"text": str}      — new input received
    "response_start"  data: None               — first LLM token arrived
    "response_end"    data: {"text": str}      — emitted by engine.py
    "interrupt"       data: None               — user interrupted speech
    "speech_start"    data: None               — microphone opened
    "speech_end"      data: {"transcript": str}— STT finished
"""

import threading
import time

import core.voice as voice
import core.tts_engine as tts_engine
from core.engine import ask_ollama_stream
from core.router import route_command
from core.state_manager import state_manager
from core.event_manager import events


class VoicePipeline:
    """Central orchestrator: text/STT → LLM → TTS.

    Parameters
    ----------
    model : str
        Ollama model tag (default: ``"phi3"``).
    on_transcript : callable | None
        Called with the raw STT string once transcription finishes.
        Defaults to printing ``You (Voice) > <text>``.
    on_first_token : callable | None
        Called the moment the first LLM token arrives (use to dismiss a
        loading spinner).  Receives no arguments.
    """

    def __init__(
        self,
        model: str = "phi3",
        on_transcript=None,
        on_first_token=None,
    ):
        self.model = model
        self._on_transcript = on_transcript or self._default_transcript_handler
        self._on_first_token = on_first_token   # None → no special callback

        self._running = False
        self._stop_event = threading.Event()

    # ── Public API ─────────────────────────────────────────────────────────────

    def process(self, text: str = "") -> str:
        """
        Orchestrates a single turn of interaction:
        1. Listen (if no text provided)
        2. Call LLM
        3. Stream audio
        Returns the full text of the LLM response.
        """
        # ── Step 1: obtain input ──────────────────────────────────────────────
        is_voice = False
        if not text.strip():
            text = self.listen()
            is_voice = True

        if not text.strip():
            return ""

        # ── Step 2: interrupt any ongoing speech ──────────────────────────────
        self.handle_interrupt()

        # ── Step 3: announce input ────────────────────────────────────────────
        events.emit("user_input", {"text": text})
        if is_voice:
            self._on_transcript(text)

        # ── Step 4: command routing ───────────────────────────────────────────
        # Removed legacy NLP routing so the LLM handles all intents natively.

        # ── Step 4: LLM → TTS ────────────────────────────────────────────────
        full_text = self._stream_response(text)

        # Wait for all queued audio to finish before returning
        self._wait_for_speech()
        
        import json
        from core.logger import debug
        
        debug("JSON_RAW", full_text)
        
        # Helper to extract the first complete JSON object
        def extract_json(text):
            start = text.find('{')
            if start == -1:
                return text
            depth = 0
            for i in range(start, len(text)):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1]
            return text
            
        json_str = extract_json(full_text)
        
        try:
            parsed = json.loads(json_str)
            debug("JSON_PARSED", str(parsed))
            return parsed
        except Exception as e:
            debug("JSON_PARSE_ERROR", str(e))
            return {
                "type": "response",
                "content": full_text
            }

    def handle_interrupt(self) -> None:
        """Stop any ongoing TTS and reset to idle.

        Safe to call even when ARIA is not speaking — ``stop_speaking()``
        is a no-op when the queues are already empty.
        """
        if tts_engine.is_speaking() or state_manager.is_state("speaking"):
            tts_engine.stop_speaking()
            events.emit("interrupt")

    def listen(self) -> str:
        """Capture microphone input and return the transcribed text.

        Returns an empty string if the user said nothing or an error occurred.
        The ``speech_start`` / ``speech_end`` events bracket the recording.
        """
        events.emit("speech_start")
        transcript = voice.listen_offline()   # sets state: listening → thinking
        events.emit("speech_end", {"transcript": transcript})
        return transcript

    def run_loop(self) -> None:
        """Run continuous voice interaction cycles until ``stop()`` is called.

        Each iteration calls ``process()`` with no text argument (STT mode).
        Say "exit", "quit", or "stop" to break the loop naturally.

        This method blocks the calling thread.  Run it in a daemon thread
        if you need the main thread free (e.g. alongside a CLI).
        """
        self._running = True
        self._stop_event.clear()
        print("\nARIA > Entering continuous voice mode. Say 'exit' to stop.")

        while self._running and not self._stop_event.is_set():
            try:
                transcript = self.process()

                if transcript.lower().strip() in ("exit", "quit", "stop"):
                    print("\nARIA > Exiting voice mode.")
                    break

            except KeyboardInterrupt:
                tts_engine.stop_speaking()
                events.emit("interrupt")
                print("\n[Voice loop interrupted]")
                break

            except Exception as exc:
                print(f"[Pipeline Error] {exc}")
                time.sleep(1)   # throttle on persistent errors

        self._running = False

    def stop(self) -> None:
        """Signal ``run_loop()`` to exit cleanly after the current cycle."""
        self._stop_event.set()
        self._running = False

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _stream_response(self, text: str) -> str:
        """Send *text* to the LLM and pipe each sentence chunk to TTS.

        ``ask_ollama_stream`` handles:
          - state transition  →  "thinking"
          - emitting          "thinking_start", "response_start", "response_end"
          - chunking into sentences with the hybrid first/subsequent logic

        This method provides the ``on_sentence`` callback that routes each
        chunk into the TTS queue with the correct ``is_first`` flag.
        """
        # Build the on_first_token callback — merge the caller-supplied one
        # (e.g. a loading spinner dismissal) with our event emission.
        def _first_token_cb(response_time: float = 0.0):
            events.emit("response_start")
            if self._on_first_token:
                self._on_first_token(response_time)

        def _on_sentence(chunk: str, is_first: bool = False) -> None:
            tts_engine.enqueue_text(chunk, print_text=True, is_first=is_first)

        return ask_ollama_stream(
            text,
            on_first_token=_first_token_cb,
            on_sentence=_on_sentence,
            model=self.model,
        )

    def _wait_for_speech(self) -> None:
        """Block until the TTS queue is drained or a stop is requested."""
        while tts_engine.is_speaking():
            if self._stop_event.is_set():
                tts_engine.stop_speaking()
                break
            time.sleep(0.05)

    @staticmethod
    def _default_transcript_handler(text: str) -> None:
        # Only print voice transcripts — text input is already shown by the CLI
        pass
