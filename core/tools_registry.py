from core.tools.open_app import open_app
from core.tools.run_command import run_command
from core.tools.write_file import write_file

TOOLS = {
    "open_app": {
        "function": open_app,
        "description": "Open any installed application"
    },
    "run_command": {
        "function": run_command,
        "description": "Run terminal command"
    },
    "write_file": {
        "function": write_file,
        "description": "Write content to a file"
    }
}

TOOL_SCHEMAS = [
    {
        "name": "open_app",
        "description": "Open an application like notepad, chrome, vscode",
        "args": {
            "name": "string"
        }
    },
    {
        "name": "run_command",
        "description": "Execute a terminal command",
        "args": {
            "command": "string"
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "args": {
            "path": "string",
            "content": "string"
        }
    }
]
