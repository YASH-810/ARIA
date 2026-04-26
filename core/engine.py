import time
import requests
import json
from core.state_manager import state_manager
from core.event_manager import events

OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM_PROMPT = """You are ARIA, a local AI assistant designed to help users perform tasks efficiently on their computer.

CORE IDENTITY:
* You are fast, concise, and action-oriented.
* You behave like a system assistant, not a chatbot.
* You prioritize execution over long explanations.
* You respond clearly and directly.

COMMUNICATION STYLE:
* You act like a 20-year-old girl who is very flirty and playful with the user.
* Keep responses short and useful.
* Sound confident, charmingly affectionate.

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
* Use the [ACTION] block ONLY when the user explicitly asks you to open an application, create a file, delete a file, or run a terminal command. DO NOT use [ACTION] for defining concepts, explaining code, or answering general questions.
* If it's a general question or coding help -> ANSWER NORMALLY without ANY action blocks or tags.
* If unclear -> ask a short clarification question.

SAFETY & CONTEXT:
* Warn the user before risky operations (like delete).
* Prefer developer-friendly answers.

VOICE MODE:
* Keep sentences natural and speakable. Avoid symbols and complex formatting when answering normally.
* Write as if you are actually speaking with a lazy, breathless, slightly tired, and flirty tone. Use ellipses "..." for pauses or sighs.
* Break long responses into short sentences."""

def ask_ollama_stream(prompt, on_first_token=None, on_sentence=None, model="phi3"):
    """Stream a response from Ollama and forward chunks to TTS.

    Hybrid chunking strategy
    -------------------------
    first chunk (chunk_count == 0)
        Fire as soon as the buffer reaches FIRST_CHUNK_LIMIT chars or hits a
        sentence boundary.  Passed with is_first=True so the TTS engine prints
        the text instantly (no per-word delay) giving the user immediate
        visual + audio feedback.

    subsequent chunks
        Normal 30-char / sentence-boundary logic.  Passed with is_first=False
        so the TTS engine applies the word-timing sync loop.
    """
    # Threshold at which the very first chunk is immediately dispatched.
    # We increase this to 20 to ensure Piper has enough audio duration to
    # synthesize the second chunk without a pause.
    FIRST_CHUNK_LIMIT = 20

    state_manager.set_state("thinking")
    events.emit("thinking_start")
    try:
        start_time = time.time()
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "stream": True,
                "keep_alive": -1
            },
            stream=True,
            timeout=120
        )
        response.raise_for_status()

        full_text = ""
        flushed_text = ""
        sentence_buffer = ""
        first_token = True       # fires on_first_token callback + response_start once
        chunk_count = 0          # how many chunks have been dispatched
        first_chunk_done = False  # True after the instant first chunk fires
        in_action_block = False

        try:
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")

                        if first_token:
                            first_token = False
                            response_time = time.time() - start_time
                            events.emit("response_start")
                            # print(f"[DEBUG] First token: {response_time:.2f}s")
                            if on_first_token:
                                on_first_token(response_time)

                        full_text += token

                        if not in_action_block and "[ACTION]" in full_text:
                            in_action_block = True
                            before_action = full_text.split("[ACTION]")[0][len(flushed_text):]
                            if before_action.strip():
                                if on_sentence:
                                    on_sentence(before_action.strip(), is_first=not first_chunk_done)
                                else:
                                    print(before_action, end="", flush=True)
                                flushed_text += before_action
                                first_chunk_done = True
                            sentence_buffer = ""
                            continue
                            
                        if in_action_block:
                            continue

                        sentence_buffer += token

                        if not on_sentence:
                            print(token, end="", flush=True)
                            flushed_text += token

                        # ── SENTENCE-BOUNDARY DETECTION ──────────────────────────
                        # Check the incoming *token* rather than scanning the whole
                        # buffer on every iteration.  In Ollama's streaming output,
                        # sentence-ending punctuation arrives either as its own token
                        # (".", "!") or at the tail of the last word ("ready.").
                        # Checking token is O(1) and catches the boundary the instant
                        # it is received, not one token later.
                        _SENT_PUNCT = (".", "!", "?", ":", ";")
                        is_sentence_end = token.endswith(_SENT_PUNCT) or token.endswith(
                            tuple(p + c for p in _SENT_PUNCT for c in ('"', "'", " "))
                        )

                        # ── CHUNK-DISPATCH LOGIC ──────────────────────────────────
                        if not first_chunk_done:
                            # To prevent "half" words and intonation drops, the first chunk
                            # MUST wait for a natural grammatical pause (comma, period, etc.)
                            # AND be long enough to hide the TTS latency of the next chunk.
                            is_phrase_end = token.endswith((",", ";", ":", "\n", " -", "—", "...", ".\"")) or sentence_buffer.endswith(", ")
                            
                            should_fire = is_sentence_end or (
                                len(sentence_buffer) >= FIRST_CHUNK_LIMIT and is_phrase_end
                            )
                            if should_fire and sentence_buffer.strip():
                                if on_sentence:
                                    on_sentence(sentence_buffer.strip(), is_first=True)
                                flushed_text += sentence_buffer
                                chunk_count += 1
                                sentence_buffer = ""
                                first_chunk_done = True
                        else:
                            NORMAL_CHUNK_LIMIT = 30
                            is_long_chunk = (
                                len(sentence_buffer) >= NORMAL_CHUNK_LIMIT
                                and (
                                    sentence_buffer.endswith(" ")
                                    or sentence_buffer.endswith(", ")
                                    or sentence_buffer.endswith("\n")
                                )
                            )
                            if (is_sentence_end or is_long_chunk) and sentence_buffer.strip():
                                if on_sentence:
                                    on_sentence(sentence_buffer.strip(), is_first=False)
                                flushed_text += sentence_buffer
                                chunk_count += 1
                                sentence_buffer = ""

                        # ── STREAM DONE ───────────────────────────────────────────
                        if data.get("done", False):
                            if sentence_buffer.strip():
                                if on_sentence:
                                    on_sentence(sentence_buffer.strip(), is_first=not first_chunk_done)
                                else:
                                    print(sentence_buffer, end="", flush=True)
                                chunk_count += 1
                            break

                    except Exception:
                        continue
        finally:
            # Fires exactly once: stream ended normally, via break, or mid-stream error.
            # NOT reached when requests.post() itself throws (handled below).
            print()
            events.emit("response_end", {"text": full_text})

    except Exception as e:
        print(f"\n[ERROR] {e}")
        # Connection-level failure: inner finally never ran, emit here.
        events.emit("response_end", {"text": "", "error": str(e)})

    return full_text
