import subprocess

def open_app(name: str) -> str:
    """Open an application by name. Handles names with spaces correctly."""
    try:
        # `start "" "<name>"` — the empty "" is the required window title argument
        subprocess.Popen(
            f'start "" "{name}"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"{name} opened"
    except Exception as e:
        return f"Error opening {name}: {e}"
