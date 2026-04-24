import os
import subprocess
from rapidfuzz import process
from commands.actions import run_command, create_file, delete_file, launch_app
from core.tts_engine import speak_chunk

# Known apps for fallback standard commands
KNOWN_APPS = [
    "chrome", "notepad", "calc", "calculator",
    "cmd", "powershell", "explorer",
    "vscode", "code", "spotify"
]

# Common folders
COMMON_PATHS = {
    "downloads": os.path.expanduser("~/Downloads"),
    "documents": os.path.expanduser("~/Documents"),
    "desktop": os.path.expanduser("~/Desktop"),
}

def get_installed_apps():
    apps = {}
    paths = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs")
    ]
    for base_path in paths:
        if not os.path.exists(base_path): continue
        for root, _, files in os.walk(base_path):
            for file in files:
                if file.endswith(".lnk"):
                    name = os.path.splitext(file)[0].lower()
                    apps[name] = os.path.join(root, file)
    return apps

# Cache installed apps at startup
INSTALLED_APPS = get_installed_apps()


def fuzzy_match(target, choices):
    if not choices:
        return None
    try:
        match, score, _ = process.extractOne(target, choices)
        if score > 70:
            return match
    except Exception:
        pass
    return None


def open_anything(target):
    target = target.lower().strip()

    # 1. Native Folders
    if target in COMMON_PATHS:
        os.startfile(COMMON_PATHS[target])
        print(f"ARIA > Opening {target}...")
        speak_chunk(f"Opening {target}")
        return

    # 2. Hard paths
    if os.path.exists(target):
        launch_app(target)
        print(f"ARIA > Opening {target}...")
        speak_chunk(f"Opening {target}")
        return

    # 3. Installed Apps (Exact Match)
    if target in INSTALLED_APPS:
        launch_app(INSTALLED_APPS[target])
        print(f"ARIA > Opening {target}...")
        speak_chunk(f"Opening {target}")
        return

    # 4. Known CLI apps (Exact Match)
    if target in KNOWN_APPS:
        launch_app(target)
        print(f"ARIA > Opening {target}...")
        speak_chunk(f"Opening {target}")
        return

    # 5. Installed Apps (Fuzzy Match)
    match = fuzzy_match(target, list(INSTALLED_APPS.keys()))
    if match:
        launch_app(INSTALLED_APPS[match])
        print(f"ARIA > Opening {match}...")
        speak_chunk(f"Opening {match}")
        return

    # 6. Known CLI Apps (Fuzzy Match)
    match = fuzzy_match(target, KNOWN_APPS)
    if match:
        launch_app(match)
        print(f"ARIA > Opening {match}...")
        speak_chunk(f"Opening {match}")
        return

    # 7. Blind fallback (cmd /c start)
    try:
        subprocess.Popen(f"start {target}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"ARIA > Attempting to open {target}...")
        speak_chunk(f"Attempting to open {target}")
        return
    except:
        pass

    print(f"ARIA > Could not find or open '{target}'.")
    speak_chunk(f"Could not find or open {target}")


def _extract_filename(text):
    for word in text.split():
        if "." in word:
            clean_word = word.rstrip(".,!?\"';:")
            if "." in clean_word:
                return clean_word
    return None

# 🔥 Natural language parsing
def parse_natural(text):
    text = text.lower().strip()

    if "create" in text or "make" in text:
        target_file = _extract_filename(text)
        
        if target_file:
            target_path = target_file
            if "in downloads" in text:
                target_path = os.path.join(COMMON_PATHS["downloads"], target_file)
            elif "in documents" in text:
                target_path = os.path.join(COMMON_PATHS["documents"], target_file)
            elif "in desktop" in text:
                target_path = os.path.join(COMMON_PATHS["desktop"], target_file)
            return "create_file", target_path

    if "delete" in text or "remove" in text:
        target_file = _extract_filename(text)
        if target_file:
            return "delete_file", target_file

    if text.startswith("run ") or text.startswith("start "):
        target = text[4:] if text.startswith("run ") else text[6:]
        return "run", target.strip()

    if text.startswith("open "):
        target = text[5:].strip()
        # strip " app" if user says "open xyz app"
        if target.endswith(" app"):
            target = target[:-4].strip()
        return "open", target

    return None, None


import re

def route_command(text):
    text = text.lower()
    
    # Split the multi-action prompt using natural conjunctions
    parts = re.split(r'\s+and then\s+|\s+and\s+|\s+then\s+', text)
    
    executed_any = False

    for part in parts:
        action, target = parse_natural(part)

        if action == "create_file":
            create_file(target)
            executed_any = True

        elif action == "delete_file":
            delete_file(target)
            executed_any = True

        elif action == "run":
            run_command(target)
            executed_any = True

        elif action == "open":
            open_anything(target)
            executed_any = True

    return executed_any