from core.tools.open_app import open_app
from core.tools.run_command import run_command
from core.tools.write_file import write_file
from core.tools.browser_action import browser_action

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
    },
    "browser_action": {
        "function": browser_action,
        "description": "Perform an action in the browser like searching Google, Wikipedia, or YouTube"
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
    },
    {
        "name": "browser_action",
        "description": "Perform a search or open a URL in the browser",
        "args": {
            "action": "string (one of: search, youtube, wikipedia, url)",
            "query": "string (the search term or url)"
        }
    }
]
