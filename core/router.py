import os
import subprocess

def open_anything(target):
    try:
        # Try Windows start command
        subprocess.Popen(f'start {target}', shell=True)
        print(f"Opening {target}...")
    except Exception as e:
        print(f"Failed to open {target}: {e}")


def route_command(text):
    text = text.lower()

    # 🔥 Dynamic OPEN handler
    if text.startswith("open "):
        target = text.replace("open ", "").strip()
        open_anything(target)
        return True

    return False