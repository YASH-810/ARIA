def write_file(**args):
    path = args.get("path")
    content = args.get("content", "")

    try:
        with open(path, "w") as f:
            f.write(content)
        return f"File written: {path}"
    except Exception as e:
        return f"Error writing file: {e}"
