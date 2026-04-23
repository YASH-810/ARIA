import os

def open_vscode():
    print("Opening VS Code...")
    os.system("code")

def open_chrome():
    print("Opening Chrome...")
    os.system("start chrome")

def open_notepad():
    print("Opening Notepad...")
    os.system("notepad")

def open_folder(path="."):
    print(f"Opening folder: {path}")
    os.system(f"start {path}")