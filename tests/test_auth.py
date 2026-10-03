"""Tests for auth module."""
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def clean_token_file():
    import auth
    original = auth.TOKEN_FILE
    test_file = Path("test_auth_token")
    auth.TOKEN_FILE = test_file
    if test_file.exists():
        test_file.unlink()
    yield
    if test_file.exists():
        test_file.unlink()
    auth.TOKEN_FILE = original


def test_generate_token(clean_token_file):
    import auth
    token = auth.generate_token()
    assert token is not None
    assert len(token) > 20
    assert auth.TOKEN_FILE.exists()
    assert auth.TOKEN_FILE.read_text().strip() == token


def test_get_auth_token(clean_token_file):
    import auth
    assert auth.get_auth_token() is None
    auth.generate_token()
    token = auth.get_auth_token()
    assert token is not None


def test_verify_token_valid(clean_token_file):
    import auth
    token = auth.generate_token()
    assert auth.verify_token(token) is True


def test_verify_token_invalid(clean_token_file):
    import auth
    auth.generate_token()
    assert auth.verify_token("wrong-token") is False


def test_verify_token_empty(clean_token_file):
    import auth
    assert auth.verify_token("") is False


@pytest.mark.asyncio
async def test_authenticate_websocket_success(clean_token_file):
    import auth
    token = auth.generate_token()

    mock_ws = MagicMock()
    mock_ws.query_params = {"token": token}
    mock_ws.close = AsyncMock()

    result = await auth.authenticate_websocket(mock_ws)
    assert result is True
    mock_ws.close.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_websocket_missing_token(clean_token_file):
    import auth
    auth.generate_token()

    mock_ws = MagicMock()
    mock_ws.query_params = {}
    mock_ws.close = AsyncMock()

    result = await auth.authenticate_websocket(mock_ws)
    assert result is False
    mock_ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_websocket_invalid_token(clean_token_file):
    import auth
    auth.generate_token()

    mock_ws = MagicMock()
    mock_ws.query_params = {"token": "invalid"}
    mock_ws.close = AsyncMock()

    result = await auth.authenticate_websocket(mock_ws)
    assert result is False
    mock_ws.close.assert_called_once()