"""
HMAC Authentication for Barq WebSocket connections.
"""
import hmac
import hashlib
import os
from pathlib import Path
from fastapi import WebSocket, HTTPException, status

BASE_DIR = Path(__file__).resolve().parent
TOKEN_FILE = BASE_DIR / "barq_data" / ".barq_auth"


def get_auth_token() -> str | None:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    return None


def verify_token(token: str) -> bool:
    expected = get_auth_token()
    if not expected:
        return False
    return hmac.compare_digest(token, expected)


async def authenticate_websocket(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing auth token")
        return False
    if not verify_token(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid auth token")
        return False
    return True


def generate_token() -> str:
    import secrets
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token)
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except Exception:
        pass
    return token