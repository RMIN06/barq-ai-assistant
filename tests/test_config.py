"""Tests for config module."""
import os
from pathlib import Path
import pytest


def test_config_loads_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-eleven-key")

    import importlib
    import config
    importlib.reload(config)

    assert config.GROQ_API_KEY == "test-groq-key"
    assert config.ELEVENLABS_API_KEY == "test-eleven-key"


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("PORCUPINE_ACCESS_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    import importlib
    import config
    importlib.reload(config)

    assert config.GROQ_API_KEY == ""
    assert config.ELEVENLABS_API_KEY == ""
    assert config.PORCUPINE_ACCESS_KEY == ""
    assert config.LLM_MODEL == "llama-3.3-70b-versatile"


def test_wake_words_list():
    import config
    assert "barq" in config.WAKE_WORDS
    assert "jarvis" in config.WAKE_WORDS
    assert "hey barq" in config.WAKE_WORDS
    assert len(config.WAKE_WORDS) > 20


def test_sleep_words_list():
    import config
    assert "go to sleep" in config.SLEEP_WORDS
    assert "standby" in config.SLEEP_WORDS
    assert len(config.SLEEP_WORDS) >= 5


def test_data_dir_exists():
    import config
    assert config.DATA_DIR.exists()
    assert config.DATA_DIR.is_dir()


def test_memory_file_path():
    import config
    assert config.MEMORY_FILE.name == "memory.json"
    assert config.MEMORY_FILE.parent == config.DATA_DIR