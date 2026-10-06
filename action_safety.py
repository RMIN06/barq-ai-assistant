"""Checks that a model-proposed file action matches the user's request."""
import re
from pathlib import Path


def authorized_file_action(command: str, action: str, subject: str) -> bool:
    if action not in {"create", "delete", "list", "read", "write", "preview"}:
        return False
    if not subject or not Path(subject).is_absolute():
        return False
    name = Path(subject).name.strip()
    if not name or name in {".", ".."}:
        return False
    words = command.casefold()
    if action == "delete" and not re.search(r"\b(delete|remove)\b", words):
        return False
    # Require the precise final component in the request. A model may resolve
    # a relative path, but cannot substitute a different file or folder name.
    return bool(re.search(r"(?<![\w.-])" + re.escape(name.casefold()) + r"(?![\w.-])", words))
