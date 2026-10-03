"""Pytest configuration and fixtures."""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pytest


@pytest.fixture(scope="session")
def base_dir():
    return BASE_DIR


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVEN_VOICE_ID", "test-voice")
    monkeypatch.setenv("PORCUPINE_ACCESS_KEY", "")