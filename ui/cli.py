import os
import threading
import time
import core.voice as voice
import core.tts_engine as tts_engine
from core.state_manager import state_manager
from core.memory_manager import memory
from core.pipeline import VoicePipeline
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from core.logger import info, error, set_debug


def show_banner():
    from core.config_manager import config
    model_name = config.get("model", "phi3")
    
    active_engines = 0
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=1)
        if resp.status_code == 200:
            models_data = resp.json().get("models", [])
            active_engines = len(models_data)
    except Exception:
        pass
        
    os.system("cls" if os.name == "nt" else "clear")

    print(r"""
                 █████╗ ██████╗ ██╗ █████╗ 
                ██╔══██╗██╔══██╗██║██╔══██╗
                ███████║██████╔╝██║███████║
                ██╔══██║██╔══██╗██║██╔══██║
                ██║  ██║██║  ██║██║██║  ██║
                ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝
""")

    print(f"🟢 ARIA Online | Model: {model_name} | Engine online: {active_engines}")
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
    _spinner_started = False

    def _start_loader():
        nonlocal _loader_thread, _spinner_started
        _stop_loader_event.clear()
        _loader_thread = threading.Thread(
            target=loading_animation, args=(_stop_loader_event,), daemon=True
        )
        _loader_thread.start()
        _spinner_started = True

    def _stop_loader(response_time: float = 0.0):
        nonlocal _spinner_started
        _stop_loader_event.set()
        if _loader_thread:
            _loader_thread.join()
        if _spinner_started:
            print(f"\rARIA > [response time {response_time:.1f}s]", end="", flush=True)
            _spinner_started = False

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
    user_name = memory.get_long_term("user_name", "Yash")
    greeting = f"Welcome back, {user_name}. All systems online and ready."
    print(f"ARIA > {greeting}")
    tts_engine.speak_chunk(greeting)

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
            # Only start spinner for plain-text input (not commands, not /voice —
            # /voice triggers its own spinner via _on_transcript).
            if not user_input.startswith("/"):
                _start_loader()

            try:
                orchestrator.handle_input(user_input)
            except Exception as e:
                error("CRASH", str(e))
            finally:
                _stop_loader()  # Always print [response time Xs] and kill spinner
                
            print("\n" + "─" * 50)

        except KeyboardInterrupt:
            tts_engine.stop_speaking()
            _stop_loader_event.set()        # kill spinner if running
            print("\n[Interrupted] You can type your next message.")
            continue
        except EOFError:
            print("\nARIA stopped")
            break