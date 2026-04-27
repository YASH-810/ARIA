REQUIRED_ARGS = {
    "open_app": ["name"],
    "run_command": ["command"],
    "write_file": ["path", "content"],
    "browser_action": ["action", "query"],
}

def validate(tool_name: str, args: dict):
    """Check that all required args for a tool are present and non-empty."""
    required = REQUIRED_ARGS.get(tool_name, [])
    for key in required:
        if key not in args or not str(args[key]).strip():
            return False, f"Missing required argument '{key}' for tool '{tool_name}'"
    return True, ""
