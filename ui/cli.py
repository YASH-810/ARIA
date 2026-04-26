import os
import threading
import time
import core.voice as voice
import core.tts_engine as tts_engine
from core.state_manager import state_manager
from core.pipeline import VoicePipeline
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from core.logger import info, error, set_debug


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
    
    # Set up Orchestrator
    from core.orchestrator import Orchestrator
    from core.command_handler import CommandHandler
    import core.router as router_module
    
    orchestrator = Orchestrator(
        engine=pipeline,
        router_module=router_module,
        state_manager=state_manager,
        command_handler=CommandHandler()
    )

    show_banner()
    from core.config_manager import config
    user_name = config.get("user_name", "Yash")
    tts_engine.speak_chunk(f"Hello {user_name}, ready.")

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





            # ── Exit ──────────────────────────────────────────────────────────
            if user_input.lower() in ("exit", "quit"):
                print("\nARIA shutting down...")
                break

            info("INPUT", user_input)

            # ── All other input: route through Orchestrator ───────────────────
            # Start the spinner before handing off; the pipeline's on_first_token
            # callback (_stop_loader) will dismiss it when the LLM responds.
            # Only start spinner for non-commands and non-voice triggers
            if not user_input.startswith("/") or user_input.strip().lower() in ("/v", "/voice"):
                _start_loader()
                
            try:
                orchestrator.handle_input(user_input)
            except Exception as e:
                error("CRASH", str(e))
            finally:
                _stop_loader_event.set()  # Guarantee the spinner stops!
                
            print("\n" + "─" * 50)

        except KeyboardInterrupt:
            tts_engine.stop_speaking()
            _stop_loader_event.set()        # kill spinner if running
            print("\n[Interrupted] You can type your next message.")
            continue
        except EOFError:
            print("\nARIA stopped")
            break