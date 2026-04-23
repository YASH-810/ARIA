import os
import subprocess
import tempfile
import threading

def _monitor_stream(stream, prefix):
    """
    Reads lines from a subprocess stream in the background
    and prints them with a consistent prefix, then reprints the prompt.
    """
    try:
        for line in iter(stream.readline, ''):
            if line:
                print(f"\n{prefix}{line.strip()}\nYou > ", end="", flush=True)
    except Exception:
        pass
    finally:
        stream.close()

def run_command(cmd):
    try:
        # If it's a multiline command, execute it via a temp batch file
        if "\n" in cmd:
            with tempfile.NamedTemporaryFile("w", suffix=".bat", delete=False) as f:
                f.write("@echo off\n" + cmd)
                temp_bat = f.name
            
            proc = subprocess.Popen(temp_bat, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print("ARIA > Running multiline command block...")
        else:
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(f"ARIA > Running: {cmd}")
        
        # Attach background monitors
        threading.Thread(target=_monitor_stream, args=(proc.stdout, "ARIA > "), daemon=True).start()
        threading.Thread(target=_monitor_stream, args=(proc.stderr, "ARIA > Error: "), daemon=True).start()

    except Exception as e:
        print(f"ARIA > Error running command: {e}")

def launch_app(target_path):
    """
    Launches an application and safely wraps its stderr 
    so it doesn't leak raw into the console prompt.
    """
    try:
        path_str = f'"{target_path}"'
        proc = subprocess.Popen(path_str, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        threading.Thread(target=_monitor_stream, args=(proc.stderr, "ARIA > Error: "), daemon=True).start()
    except Exception as e:
        print(f"ARIA > Error: {e}")

def create_file(filename):
    try:
        if os.path.exists(filename):
            print(f"File already exists: {filename}")
            return

        with open(filename, "w") as f:
            f.write("")

        print(f"Created file: {filename}")
    except Exception as e:
        print(f"Error creating file: {e}")

def delete_file(filename):
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return

    confirm = input(f"Delete '{filename}'? (y/n): ")

    if confirm.lower() == "y":
        os.remove(filename)
        print(f"Deleted file: {filename}")
    else:
        print("Cancelled.")