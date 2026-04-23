# 🤖 ARIA — Portable Local AI Assistant

## 🧠 Overview

![ARIA Terminal Interface](assets/aria_terminal.gif)

ARIA is an advanced, fully **local AI assistant** designed to run **offline** with minimal setup. It focuses on ultra-low latency, multi-modal interactions (voice & text), and deep system integrations.

It supports:
* 💻 PC mode (full features)
* 🔑 USB mode (portable AI system)

ARIA is built to be:
* Lightweight and incredibly fast.
* Fully private (Zero cloud telemetry).
* Modular and easily extendable.

---

# 🚀 Features

* 💬 **Local AI Chat:** Powered by Ollama streaming the `phi3` model.
* 🎙️ **Real-time Voice Input:** Uses `faster-whisper` and dynamic RMS silence detection for seamless offline Speech-to-Text.
* 🔊 **Synchronized Voice Output:** Uses `Piper TTS` to generate ultra-realistic voice models, perfectly synchronized word-by-word with the terminal output.
* ⚙️ **Command Automation:** Executes shell commands, creates files, and deletes files locally.
* 🧠 **Intelligent App Routing:** Uses the `rapidfuzz` algorithm (Levenshtein distance) to intelligently fuzzy-match and launch local system apps (e.g., "open spotify", "start calculatr").
* 🛡️ **Thread-Safe State Manager:** Centralized architecture preventing overlaps between listening, thinking, and speaking.

---


# 🧠 System Architecture

```plaintext
User Input (Text / F2 for Voice)
          ↓
CLI (Prompt Toolkit)
          ↓
State Manager (Idle / Listening / Thinking / Speaking)
          ↓
Router (Fuzzy Matcher)  ←→  System Commands (actions.py)
          ↓
Engine (ask_ollama_stream)
          ↓
Piper TTS + Terminal Sync
```

---

# 📁 Project Structure

```plaintext
ARIA/
├── core/
│   ├── engine.py           # LLM processing
│   ├── router.py           # Natural language & app routing
│   ├── state_manager.py    # Concurrency control
│   ├── tts_engine.py       # Piper TTS & pygame audio player
│   └── voice.py            # Faster-Whisper & pyaudio STT
├── commands/
│   └── actions.py          # OS level execution
├── ui/
│   └── cli.py              # prompt_toolkit interface
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
└── run.bat                 # Bootstrapper
```

---

# ⚙️ Configuration

```json
{
  "model": "phi3",
  "mode": "lite",
  "voice": true
}
```

---

# ⚠️ Important Notes

* ARIA uses local models → performance depends on hardware
* Small models recommended for low-end systems
* Ensure all dependencies in `requirements.txt` are installed.

---

# 🔮 Future Features

* Screen interaction (OCR & Computer Vision)
* Always-on wake word ("Hey ARIA")
* React UI dashboard

---

# 🧠 Summary

ARIA is a **portable AI assistant**, a **developer tool**, and a **local-first system**.
Run anywhere. No cloud required.
