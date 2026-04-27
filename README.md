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
* ⚙️ **Command Automation & Tools:** Executes shell commands, browser actions, and file operations natively with strict schema validation.
* 🧠 **Intelligent App Routing:** Uses the `rapidfuzz` algorithm to intelligently fuzzy-match and launch local system apps instantly, bypassing the LLM for fast-path commands.
* 🛡️ **Thread-Safe State Manager:** Centralized architecture preventing overlaps between listening, thinking, and speaking.
* 🗃️ **Persistent Memory:** Context-aware interactions with short-term buffers and long-term user preference storage.

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
│   ├── command_handler.py  # Slash-commands parser
│   ├── config_manager.py   # Global configuration management
│   ├── engine.py           # LLM processing & streaming
│   ├── event_manager.py    # Pub/Sub event bus
│   ├── logger.py           # Centralized logging
│   ├── memory_manager.py   # Short & Long-term memory
│   ├── orchestrator.py     # Central brain & intent routing
│   ├── pipeline.py         # Interaction cycle manager
│   ├── router.py           # Tool & application execution
│   ├── state_manager.py    # Thread-safe concurrency control
│   ├── tools_registry.py   # Available LLM capabilities
│   ├── tts_engine.py       # Piper TTS & pygame audio player
│   ├── validator.py        # Tool argument validation
│   └── voice.py            # Faster-Whisper & pyaudio STT
├── commands/
│   ├── actions.py          # OS level execution
│   └── system.py           # Fallback system commands
├── config/
│   └── config.json         # Settings & toggles
├── data/
│   └── memory.json         # Persistent user data
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
  "user_name": "User",
  "model": "phi3",
  "tts_enabled": true,
  "debug": true
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
