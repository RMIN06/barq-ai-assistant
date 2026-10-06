"""Explicit voice state commands, kept separate from model routing."""
import re

_SLEEP = {"go to sleep", "sleep", "sleep mode", "standby", "goodnight", "shut down", "turn off"}


def is_sleep_command(text: str) -> bool:
    normalized = re.sub(r"[^\w\s]", " ", text.casefold())
    normalized = " ".join(normalized.split())
    for name in ("hey jarvis ", "jarvis ", "hey barq ", "barq "):
        if normalized.startswith(name):
            normalized = normalized[len(name):]
            break
    while True:
        updated = re.sub(r"^(?:ok(?:ay)?|please|now|you can|could you|can you)\s+", "", normalized)
        if updated == normalized:
            break
        normalized = updated
    return normalized in _SLEEP or normalized in {"go to standby", "go to sleep now"}


def is_non_request(text: str) -> bool:
    """Avoid replying to common incidental acknowledgements and STT filler."""
    normalized = " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())
    return normalized in {"", "you", "thank you", "thanks", "okay", "ok", "welcome", "you re welcome"}
