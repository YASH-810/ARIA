import time
import core.router as router
from core.state_manager import state_manager
from core.logger import debug, info, warn, error
from core.memory_manager import memory

def detect_fast_intent(user_input: str):
    text = user_input.lower().strip()

    if text.startswith("open "):
        return {
            "type": "tool",
            "tool": "open_app",
            "args": {
                "name": text.replace("open ", "", 1).strip()
            }
        }

    if text.startswith("run "):
        return {
            "type": "tool",
            "tool": "run_command",
            "args": {
                # using 'name' to match router.py's target extraction
                "name": text.replace("run ", "", 1).strip()
            }
        }

    return None



class Orchestrator:
    def __init__(self, engine, router_module, state_manager, command_handler):
        self.engine = engine
        self.router = router_module
        self.state = state_manager
        self.command_handler = command_handler
        
        from core.config_manager import config
        user_name = config.get("user_name", "Yash")
        info("SYSTEM", f"User: {user_name}")
        print(f"ARIA > Hello {user_name}, ready.")

    def handle_input(self, user_input: str):
        start = time.time()
        try:
            debug("ORCHESTRATOR", f"Received: {user_input}")
            debug("STATE", "thinking")
            self.state.set_state("thinking")

            # COMMAND HANDLING
            if user_input.startswith("/"):
                # Handle built-in voice trigger as a special case
                if user_input.strip().lower() in ("/v", "/voice"):
                    text = self.engine.listen()
                    if not text.strip():
                        self.state.set_state("idle")
                        info("TIME", f"{time.time() - start:.2f}s")
                        return
                    
                    self.engine.handle_interrupt()
                    from core.event_manager import events
                    events.emit("user_input", {"text": text})
                    self.engine._on_transcript(text)
                    
                    # Route transcribed text recursively so it hits the Fast Path!
                    self.state.set_state("idle")
                    return self.handle_input(text)
                else:
                    self.command_handler.handle(user_input)
                    self.state.set_state("idle")
                    info("TIME", f"{time.time() - start:.2f}s")
                    return
            else:
                # FAST PATH (NO LLM)
                fast_decision = detect_fast_intent(user_input)
                
                if fast_decision:
                    info("FAST_PATH", str(fast_decision))
                    debug("FAST_DECISION", str(fast_decision))
                    self.state.set_state("executing")

                    result = self.router.execute(
                        fast_decision["tool"],
                        fast_decision["args"]
                    )

                    print("ARIA >", result)
                    self.state.set_state("idle")
                    info("TIME", f"{time.time() - start:.2f}s")
                    return

                # SLOW PATH (LLM)
                debug("LLM_FALLBACK", "Triggered")
                debug("ORCHESTRATOR", "Using LLM fallback")
                
                if "my name is" in user_input.lower():
                    name = user_input.lower().split("my name is")[-1].strip()
                    memory.set_long_term("user_name", name)
                
                recent = memory.get_recent_context()
                debug("MEMORY_CONTEXT", str(recent))
                
                context_text = ""
                for item in recent:
                    context_text += f"User: {item['user']}\nAI: {item['ai']}\n"
                
                final_input = context_text + "\nUser: " + user_input
                
                response = self.engine.process(final_input)
                self._handle_llm_response(response, user_input)

        except Exception as e:
            error("SYSTEM", str(e))
            print(f"ARIA > Error: {e}")
            self.state.set_state("idle")

        info("TIME", f"{time.time() - start:.2f}s")

    def _handle_llm_response(self, response, user_input=""):
        debug("RESPONSE_RAW", str(response))
        debug("RESPONSE_TYPE", str(type(response)))
        
        # TOOL EXECUTION
        if isinstance(response, dict):
            if response.get("type") == "tool":
                self.state.set_state("executing")

                tool = response.get("tool")
                args = response.get("args", {})

                debug("ORCHESTRATOR", f"Decision: tool={tool}")
                debug("ROUTER", f"Executing tool: {tool}")

                result = self.router.execute(tool, args)

                info("TOOL", f"{tool} executed successfully")
                print("ARIA >", result)

            elif response.get("type") == "response":
                print("ARIA >", response.get("content"))
                memory.add_interaction(user_input, response.get("content"))
        else:
            print("ARIA >", response)

        self.state.set_state("idle")
