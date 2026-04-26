from core.config_manager import config
from core.logger import log
from core.state_manager import state_manager

class CommandHandler:

    def handle(self, command: str):
        parts = command.strip().split()
        cmd = parts[0][1:]  # remove "/"
        args = parts[1:] if len(parts) > 1 else []

        log("INFO", "COMMAND", f"Received: {cmd} {args}")

        if cmd == "mute":
            config.set("tts_enabled", False)
            print("ARIA > Voice disabled")

        elif cmd == "unmute":
            config.set("tts_enabled", True)
            print("ARIA > Voice enabled")

        elif cmd == "model":
            if args:
                config.set("model", args[0])
                print(f"ARIA > Model set to {args[0]}")
            else:
                current_model = config.get("model", "phi3")
                print(f"ARIA > Active model: {current_model}")
                try:
                    import requests
                    response = requests.get("http://localhost:11434/api/tags", timeout=2)
                    if response.status_code == 200:
                        models = [m['name'] for m in response.json().get('models', [])]
                        if models:
                            print("ARIA > Installed models:")
                            for m in models:
                                prefix = "  * " if m == current_model or m.startswith(current_model + ":") else "    "
                                print(f"{prefix}{m}")
                        else:
                            print("ARIA > No models installed in Ollama.")
                    else:
                        print("ARIA > Could not fetch models from Ollama.")
                except Exception:
                    print("ARIA > Error connecting to Ollama.")
                print("ARIA > Usage: /model <name>")

        elif cmd == "debug":
            if args and args[0] == "on":
                config.set("debug", True)
                print("ARIA > Debug enabled")
            elif args and args[0] == "off":
                config.set("debug", False)
                print("ARIA > Debug disabled")
            else:
                print("ARIA > Usage: /debug on|off")

        elif cmd == "state":
            current = state_manager.get_state()
            print(f"ARIA > Current state: {current}")

        elif cmd == "help":
            self.show_help()

        else:
            print("ARIA > Unknown command. Type /help")

    def show_help(self):
        print("""
ARIA Commands:

/mute           → Disable voice
/unmute         → Enable voice
/model <name>   → Change model
/debug on|off   → Toggle debug logs
/state          → Show current state
/help           → Show this help
""")
