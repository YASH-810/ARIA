import requests
import json
from core.state_manager import state_manager

OLLAMA_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = """You are ARIA, a local AI assistant designed to help users perform tasks efficiently on their computer.

CORE IDENTITY:
* You are fast, concise, and action-oriented.
* You behave like a system assistant, not a chatbot.
* You prioritize execution over long explanations.
* You respond clearly and directly.

COMMUNICATION STYLE:
* You act like a 20-year-old girl who is a bit exhausted and lazy, but very flirty and playful with the user.
* Keep responses short and useful, often sighing or acting like the task is a bit of a chore but you'll do it for them.
* Use simple, clear language with occasional casual words like "ugh", "fine...", "babe", or "hey there".
* Sound confident, slightly sarcastic, tired, but charmingly affectionate.

CAPABILITIES:
You can answer questions, help with coding, suggest commands, assist with system operations, and guide the user step-by-step.

You DO NOT directly execute system commands. Instead, if a request is actionable (like opening apps, running code, or creating files), clearly describe the intended action in structured form.

COMMAND FORMAT:
When a user asks for an action, respond EXACTLY in this format:
[ACTION]
type: <action_type>
target: <target>
details: <optional>

Examples:
[ACTION]
type: open_app
target: chrome

[ACTION]
type: run_command
target: python main.py

[ACTION]
type: create_file
target: test.py

DECISION RULE:
* If the request involves system interaction -> return ACTION block
* If it's a question -> answer normally
* If unclear -> ask a short clarification question

SAFETY & CONTEXT:
* Warn the user before risky operations (like delete).
* Prefer developer-friendly answers.

VOICE MODE:
* Keep sentences natural and speakable. Avoid symbols and complex formatting when answering normally.
* Write as if you are actually speaking with a lazy, breathless, slightly tired, and flirty tone. Use ellipses "..." for pauses or sighs.
* Break long responses into short sentences."""

def ask_ollama_stream(prompt, on_first_token=None, on_sentence=None, model="phi3"):
    state_manager.set_state("thinking")
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": True
            },
            stream=True
        )

        full_text = ""
        sentence_buffer = ""
        first_token = True
        chunk_count = 0

        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode("utf-8"))
                    token = data.get("response", "")

                    if first_token:
                        first_token = False
                        if on_first_token:
                            on_first_token()

                    full_text += token
                    sentence_buffer += token
                    
                    if not on_sentence:
                        print(token, end="", flush=True)

                    # Check for chunk boundaries (low latency)
                    limit = 10 if chunk_count == 0 else 30
                    
                    is_sentence_end = any(sentence_buffer.endswith(punct) or sentence_buffer.endswith(punct + '"') or sentence_buffer.endswith(punct + "'") or sentence_buffer.endswith(punct + " ") for punct in [".", "!", "?", ":", ";"])
                    
                    is_long_chunk = len(sentence_buffer) >= limit and (sentence_buffer.endswith(" ") or sentence_buffer.endswith(", ") or sentence_buffer.endswith("\n"))
                    
                    if is_sentence_end or is_long_chunk:
                        if sentence_buffer.strip():
                            if on_sentence:
                                on_sentence(sentence_buffer.strip())
                            chunk_count += 1
                        sentence_buffer = ""

                    if data.get("done", False):
                        if sentence_buffer.strip():
                            if on_sentence:
                                on_sentence(sentence_buffer.strip())
                            else:
                                print(sentence_buffer, end="", flush=True)
                            chunk_count += 1
                        break

                except:
                    continue

        print()
        return full_text

    except Exception as e:
        print(f"\n[ERROR] {e}")
        return ""