import os
import threading
import time
from core.engine import ask_ollama_stream
from core.router import route_command

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

    print("🤖 ARIA Online | Model: phi3")
    print("─" * 50)


def loading_animation(stop_event):
    while not stop_event.is_set():
        for dots in ["Processing   ", "Processing.  ", "Processing.. ", "Processing..."]:
            print(f"\rARIA > {dots}", end="", flush=True)
            time.sleep(0.3)
            if stop_event.is_set():
                break


def run_cli():
    show_banner()

    while True:
        try:
            user_input = input("\nYou > ")

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
            ask_ollama_stream(user_input, on_first_token=stop_loader)

            print("\n" + "─" * 50)

        except KeyboardInterrupt:
            print("\nARIA stopped")
            break