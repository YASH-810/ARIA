# 🤖 ARIA — Portable Local AI Assistant

## 🧠 Overview

ARIA is a **local AI assistant** designed to run **offline** with minimal setup.

It supports:

* 💻 PC mode (full features)
* 🔑 USB mode (portable AI system)

ARIA is built to be:

* Lightweight
* Modular
* Easy to run using scripts (no manual installs required)

---

# 🚀 Installation & Setup

## ⚡ Option 1 — Quick Start (Recommended)

Run ARIA using setup script:

### Windows:

```bash
run.bat
```

This script will:

* Check if Ollama is installed
* Install Ollama (if missing)
* Start Ollama server
* Load required model
* Launch ARIA

---

## 🧠 How Installation Works

ARIA handles setup automatically using CLI.

### Internally it runs:

```bash
ollama serve
ollama pull phi3
```

👉 No need to manually download from website

---

## 🔑 Option 2 — USB Portable Mode

ARIA can run directly from a pendrive.

### USB Structure:

```plaintext
ARIA_USB/
 ├── models/
 ├── memory/
 ├── config/
 └── run.bat
```

---

### How it works:

1. Plug USB
2. Run:

```bash
run.bat
```

3. ARIA will:

* Detect USB models
* Start Ollama engine (PC)
* Use models from USB

---

## ⚙️ Model Handling

### Option A — Auto Download

If model not found:

```bash
ollama pull phi3
```

---

### Option B — USB Models

* Place `.gguf` or Ollama models in:

```plaintext
USB/models/
```

ARIA will:

* Detect models
* Load automatically

---

# 🧠 System Architecture

```plaintext
User
 ↓
CLI (ARIA)
 ↓
Router
 ↓
Engine
 ↓
Ollama
 ↓
Model (USB or PC)
```

---

# 📁 Project Structure

```plaintext
ARIA/
├── core/
├── commands/
├── context/
├── ui/
├── config/
├── main.py
└── run.bat
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

# 🧩 Modes

## 🟢 Lite Mode

* CLI only
* Small models
* Works on low-end devices

## 🔵 Mid Mode

* Better models
* More features

## 🔴 Pro Mode

* Full UI
* Advanced capabilities

---

# ⚡ Features

* 💬 AI chat (offline)
* 💻 Coding assistant
* ⚙️ Command automation
* 📂 File reading (limited context)
* 🔊 Text-to-speech
* 🔑 USB-based model system

---

# ⚠️ Important Notes

* ARIA uses local models → performance depends on hardware
* Small models recommended for low-end systems
* Avoid running heavy models on limited RAM

---

# 🤖 Agent Instructions

When using ARIA:

* Do NOT scan entire project
* Use minimal file context (1–3 files)
* Confirm before modifying files
* Prefer fast and lightweight execution
* Avoid heavy operations unless necessary

---

# 🔮 Future Features

* Screen interaction (OCR)
* Voice commands + wake word
* Advanced automation
* React UI dashboard

---

# 🧠 Summary

ARIA is:

* A **portable AI assistant**
* A **developer tool**
* A **local-first system**

Run anywhere. No cloud required.

---
