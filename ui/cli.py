import os
import threading
import time
from core.engine import ask_ollama_stream
from core.router import route_command
import core.voice as voice
import core.tts_engine as tts_engine
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

    print("🟢 ARIA Online | Model: phi3")
    print("─" * 50)


def loading_animation(stop_event):
    while not stop_event.is_set():
        for dots in ["Processing   ", "Processing.  ", "Processing.. ", "Processing..."]:
            print(f"\rARIA > {dots}", end="", flush=True)
            time.sleep(0.3)
            if stop_event.is_set():
                break


def run_cli():
    # start.bat already prints 'Starting ARIA...'
    tts_engine.start_tts_engine()
    
    # Pre-load the Whisper model silently
    print("Loading offline models into memory...")
    import os
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    voice.get_whisper_model()
    
    # Now clear the terminal and show the real ARIA UI
    show_banner()
    greet_msg = "Hello Yash, ARIA is online and ready."
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
            user_input = session.prompt("\nYou > (Ctrl+Q or F2 for Voice) ")
            
            # Stop any ongoing speech since the user just provided new input
            if user_input.strip():
                tts_engine.stop_speaking()

            if user_input.strip().lower() in ["/v", "/voice"]:
                user_input = voice.listen_offline()
                if not user_input:
                    continue
                print(f"You (Voice) > {user_input}")

            if user_input.lower() in ["exit", "quit"]:
                print("\nARIA shutting down...")
                break

            # 🔥 FIRST: check if it's a command
            is_command = route_command(user_input)

            if is_command:
                print("\n" + "─" * 50)
                continue  # skip AI part

            # 🔥 Only for AI → start loader
            stop_event = threading.Event()

            loader_thread = threading.Thread(
                target=loading_animation,
                args=(stop_event,)
            )
            loader_thread.start()

            # stop loader when first token arrives
            def stop_loader():
                stop_event.set()
                loader_thread.join()
                print("\rARIA > ", end="", flush=True)

            # 🔥 call AI
            ask_ollama_stream(user_input, on_first_token=stop_loader, on_sentence=tts_engine.speak_chunk)

            print("\n" + "─" * 50)

        except KeyboardInterrupt:
            print("\nARIA stopped")
            break
        except EOFError:
            print("\nARIA stopped")
            break