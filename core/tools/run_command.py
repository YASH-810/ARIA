import os

def run_command(command):
    try:
        os.system(command)
        return f"Command executed: {command}"
    except Exception as e:
        return f"Error: {e}"
