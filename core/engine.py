import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"


def ask_ollama_stream(prompt, on_first_token=None, on_sentence=None, model="phi3"):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "system": "You are ARIA. Keep all responses very short, concise, and to the point. Provide only the direct answer without unnecessary context.",
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
                                import time
                                time.sleep(0.05)
                                print(sentence_buffer, end="", flush=True)
                            chunk_count += 1
                        sentence_buffer = ""

                    if data.get("done", False):
                        if sentence_buffer.strip():
                            if on_sentence:
                                on_sentence(sentence_buffer.strip())
                                import time
                                time.sleep(0.05)
                                print(sentence_buffer, end="", flush=True)
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