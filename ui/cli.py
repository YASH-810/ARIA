import os
import threading
import time
import core.voice as voice
import core.tts_engine as tts_engine
from core.state_manager import state_manager
from core.pipeline import VoicePipeline
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings


def show_banner():
    os.system("cls" if os.name == "nt" else "clear")

    print(r"""
                 █████╗ ██████╗ ██╗ █████╗ 
                ██╔══██╗██╔══██╗██║██╔══██╗
                ███████║██████╔╝██║███████║
                ██╔══██║██╔══██╗██║██╔══██║
                ██║  ██║██║  ██║██║██║  ██║
                ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝
""")

    print("🟢 ARIA Online | Model: phi3 ")
    print("─" * 50)


def loading_animation(stop_event):
    while not stop_event.is_set():
        for dots in ["Thinking   ", "Thinking.  ", "Thinking.. ", "Thinking..."]:
            print(f"\rARIA > {dots}", end="", flush=True)
            if stop_event.wait(0.3):
                break


def run_cli():
    tts_engine.start_tts_engine()

    # Pre-load Whisper silently so voice mode starts instantly
    print("Loading offline models into memory...")
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    voice.get_whisper_model()

    # Build the loading-spinner callback the pipeline will call on first token
    # We keep the spinner here in the CLI because it is a pure UI concern.
    _stop_loader_event = threading.Event()
    _loader_thread: threading.Thread | None = None

    def _start_loader():
        nonlocal _loader_thread
        _stop_loader_event.clear()
        _loader_thread = threading.Thread(
            target=loading_animation, args=(_stop_loader_event,), daemon=True
        )
        _loader_thread.start()

    def _stop_loader(response_time: float = 0.0):
        _stop_loader_event.set()
        if _loader_thread:
            _loader_thread.join()
        print(f"\rARIA > [response time {response_time:.1f}s]", end="", flush=True)

    def _on_transcript(text: str):
        print(f"\nYou > {text}")
        _start_loader()

    # Single pipeline instance — Whisper model is already warm above
    pipeline = VoicePipeline(on_transcript=_on_transcript, on_first_token=_stop_loader)

    show_banner()
    greet_msg = "Good to see you, Yash. ARIA is online and ready to assist."
    print(f"ARIA > {greet_msg}")
    tts_engine.speak_chunk(greet_msg)

    bindings = KeyBindings()

    @bindings.add('c-q')
    @bindings.add('f2')
    def _(event):
        event.app.exit(result='/voice')

    session = PromptSession(key_bindings=bindings)

    while True:
        try:
            state_manager.set_state("idle")
            user_input = session.prompt("\nYou > ")

            if not user_input.strip():
                continue

            # ── Voice mode triggered by F2 / Ctrl+Q / /v / /voice ────────────
            if user_input.strip().lower() in ("/v", "/voice"):
                pipeline.run_once()          # no text → STT path
                print("\n" + "─" * 50)
                continue

            # ── Exit ──────────────────────────────────────────────────────────
            if user_input.lower() in ("exit", "quit"):
                print("\nARIA shutting down...")
                break

            # ── All other input: route through pipeline ───────────────────────
            # Start the spinner before handing off; the pipeline's on_first_token
            # callback (_stop_loader) will dismiss it when the LLM responds.
            _start_loader()
            pipeline.run_once(text=user_input)
            print("\n" + "─" * 50)

        except KeyboardInterrupt:
            tts_engine.stop_speaking()
            _stop_loader_event.set()        # kill spinner if running
            print("\n[Interrupted] You can type your next message.")
            continue
        except EOFError:
            print("\nARIA stopped")
            break