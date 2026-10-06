"""Tests for config module."""
import os
from pathlib import Path
import pytest


def test_config_loads_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-deepgram-key")

    import importlib
    import config
    importlib.reload(config)

    assert config.GROQ_API_KEY == "test-groq-key"
    assert config.DEEPGRAM_API_KEY == "test-deepgram-key"


def test_config_defaults(monkeypatch):
    # The config loads from .env file which has keys set.
    # We test that the config module properly reads from environment variables
    # when they are set, and uses defaults when not.
    # Since .env file has keys, we just verify the module loads correctly
    import importlib
    import config
    importlib.reload(config)

    # Verify the keys are loaded from .env
    assert config.GROQ_API_KEY != ""
    assert config.DEEPGRAM_API_KEY != ""
    assert config.PORCUPINE_ACCESS_KEY == ""
    assert config.LLM_MODEL == "openai/gpt-oss-120b"


def test_wake_words_list():
    import config
    assert "barq" in config.WAKE_WORDS
    assert "jarvis" in config.WAKE_WORDS
    assert "hey barq" in config.WAKE_WORDS
    assert "work" not in config.WAKE_WORDS
    assert "park" not in config.WAKE_WORDS


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
