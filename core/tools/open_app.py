import os

def open_app(name):
    try:
        os.system(f"start {name}")
        return f"{name} opened"
    except Exception as e:
        return f"Error opening {name}: {e}"
