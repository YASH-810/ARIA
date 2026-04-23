import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"


def ask_ollama_stream(prompt, on_first_token=None, model="phi3"):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": True
            },
            stream=True
        )

        full_text = ""
        first_token = True

        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode("utf-8"))
                    token = data.get("response", "")

                    # 🔥 stop loader when first token arrives
                    if first_token:
                        first_token = False
                        if on_first_token:
                            on_first_token()

                    print(token, end="", flush=True)
                    full_text += token

                    if data.get("done", False):
                        break

                except:
                    continue

        print()
        return full_text

    except Exception as e:
        print(f"\n[ERROR] {e}")
        return ""