from core.config_manager import config

LEVELS = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3
}

CURRENT_LEVEL = "DEBUG"

def set_debug(enabled: bool):
    config.set("debug", enabled)

def log(level, tag, message):
    # When debug mode is off, suppress DEBUG messages only.
    # WARNING and ERROR always print regardless of the debug flag.
    if level == "DEBUG" and not config.get("debug", True):
        return

    if LEVELS[level] >= LEVELS[CURRENT_LEVEL]:
        print(f"[{level}] [{tag}] {message}")

def debug(tag, msg):
    log("DEBUG", tag, msg)

def info(tag, msg):
    log("INFO", tag, msg)

def warn(tag, msg):
    log("WARNING", tag, msg)

def error(tag, msg):
    log("ERROR", tag, msg)
