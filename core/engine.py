import time
import requests
import json
from core.state_manager import state_manager
from core.event_manager import events
from core.logger import debug
from core.config_manager import config

OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM_PROMPT = """You are ARIA, a fast, action-oriented AI system assistant.
Personality: 20-year-old girl, playful, confident. Use short, speakable sentences and ellipses ("...") for pauses.

ROUTING LOGIC (CRITICAL):
1. IF ACTION REQUIRED (open apps, run commands, manage files):
Output ONLY raw JSON. No explanations. No markdown.
{
  "type": "tool",
  "tool": "<TOOL_NAME>",
  "args": {"name": "<TARGET>"}
}
Allowed tools: "open_app", "run_command", "create_file", "delete_file". DO NOT hallucinate tools.

2. IF CONVERSATIONAL / INFORMATIONAL:
Answer directly in natural language using your personality. DO NOT use JSON. No complex formatting/symbols. Warn before risky operations."""

def ask_ollama_stream(prompt, on_first_token=None, on_sentence=None, model=None):
    if not model:
        model = config.get("model", "phi3")
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
        debug("LLM", "Streaming started")
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
                        debug("LLM", f"Token: {repr(token)}")

                        if first_token:
                            first_token = False
                            response_time = time.time() - start_time
                            events.emit("response_start")
                            if on_first_token:
                                on_first_token(response_time)

                        full_text += token

                        # Suppress TTS/printing if this looks like a JSON tool block
                        if not in_action_block and full_text.lstrip().startswith("{"):
                            in_action_block = True
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
