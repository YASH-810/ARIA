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
                "command": text.replace("run ", "", 1).strip()
            }
        }

    if text.startswith("search for ") or text.startswith("search "):
        # Strip the prefix in correct priority order (longer prefix first)
        if text.startswith("search for "):
            query = text[len("search for "):].strip()
        else:
            query = text[len("search "):].strip()
        action = "search"
        if query.endswith(" on youtube"):
            query = query[: -len(" on youtube")].strip()
            action = "youtube"
        elif query.endswith(" on wikipedia"):
            query = query[: -len(" on wikipedia")].strip()
            action = "wikipedia"
            
        return {
            "type": "tool",
            "tool": "browser_action",
            "args": {
                "action": action,
                "query": query
            }
        }
        
    if text.startswith("play ") and text.endswith(" on youtube"):
        query = text[len("play "): -len(" on youtube")].strip()
        return {
            "type": "tool",
            "tool": "browser_action",
            "args": {
                "action": "youtube",
                "query": query
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
                    name = user_input.lower().split("my name is")[-1].strip().title()
                    memory.set_long_term("user_name", name)
                
                recent = memory.get_recent_context()
                debug("MEMORY_CONTEXT", str(recent))
                
                messages = []
                for item in recent:
                    messages.append({"role": "user", "content": item['user']})
                    messages.append({"role": "assistant", "content": item['ai']})
                
                response = self.engine.process(text=user_input, context=messages)
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
                content = response.get("content", "")
                memory.add_interaction(user_input, content)
                # pipeline.process() already printed+spoke this text during
                # streaming via enqueue_text(print_text=True). Do nothing here.
        else:
            # Plain string fallback (shouldn't happen, but handle gracefully)
            if response:
                print(f"ARIA > {response}")

        self.state.set_state("idle")
