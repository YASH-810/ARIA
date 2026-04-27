from core.config_manager import config
import time
import os

# -------------------------
# LEVELS
# -------------------------
LEVELS = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3
}

# Read from config if present
def get_current_level():
    try:
        return config.get("log_level", "DEBUG")
    except:
        return "DEBUG"

# -------------------------
# COLORS (ANSI)
# -------------------------
COLORS = {
    "DEBUG": "\033[90m",    # gray
    "INFO": "\033[94m",     # blue
    "WARNING": "\033[93m",  # yellow
    "ERROR": "\033[91m",    # red
    "RESET": "\033[0m"
}

# -------------------------
# REQUEST TRACKING
# -------------------------
REQUEST_ID = 0

def new_request():
    global REQUEST_ID
    REQUEST_ID += 1
    return REQUEST_ID

# -------------------------
# FILE LOGGING
# -------------------------
LOG_FILE = "logs/aria.log"

def write_to_file(message):
    try:
        os.makedirs("logs", exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except:
        pass  # never crash logger

# -------------------------
# MAIN LOG FUNCTION
# -------------------------
def log(level, tag, message):
    try:
        debug_enabled = config.get("debug", True)
    except:
        debug_enabled = True

    # suppress debug if disabled
    if level == "DEBUG" and not debug_enabled:
        return

    current_level = get_current_level()

    if LEVELS[level] >= LEVELS[current_level]:
        ts = time.strftime("%H:%M:%S")

        color = COLORS.get(level, "")
        reset = COLORS["RESET"]

        formatted = f"[{ts}] [#{REQUEST_ID}] [{level}] [{tag}] {message}"

        # console (colored)
        print(f"{color}{formatted}{reset}")

        # file (plain)
        write_to_file(formatted)

# -------------------------
# HELPERS
# -------------------------
def debug(tag, msg):
    log("DEBUG", tag, msg)

def info(tag, msg):
    log("INFO", tag, msg)

def warn(tag, msg):
    log("WARNING", tag, msg)

def error(tag, msg):
    log("ERROR", tag, msg)

def set_debug(enabled: bool):
    config.set("debug", enabled)