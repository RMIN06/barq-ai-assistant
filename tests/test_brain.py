"""Tests for brain module."""
import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_groq_client():
    with patch("brain.client") as mock:
        yield mock


@pytest.fixture
def clean_memory():
    import brain
    original = brain.MEMORY_FILE
    test_file = Path("test_memory.json")
    brain.MEMORY_FILE = test_file
    if test_file.exists():
        test_file.unlink()
    yield
    if test_file.exists():
        test_file.unlink()
    brain.MEMORY_FILE = original


def test_default_memory():
    import brain
    mem = brain._default_memory()
    assert "history" in mem
    assert "facts" in mem
    assert mem["history"] == []
    assert mem["facts"] == []


def test_load_memory_creates_default(clean_memory):
    import brain
    mem = brain.load_memory()
    assert mem == brain._default_memory()


def test_save_and_load_memory(clean_memory):
    import brain
    test_mem = {"history": [{"role": "user", "content": "test"}], "facts": ["fact1"]}
    brain.save_memory(test_mem)
    loaded = brain.load_memory()
    assert loaded == test_mem


def test_add_turn_trims_history(clean_memory):
    import brain
    mem = brain._default_memory()
    for i in range(30):
        brain.add_turn(mem, "user", f"msg{i}")
    assert len(mem["history"]) <= brain.MAX_HISTORY * 2


def test_think_returns_valid_structure(mock_groq_client, clean_memory):
    import brain
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "speech": "Test response",
        "intent": "conversation",
        "action": "",
        "subject": ""
    })
    mock_groq_client.chat.completions.create.return_value = mock_response

    result = brain.think("Hello")

    assert "speech" in result
    assert "intent" in result
    assert "action" in result
    assert "subject" in result
    assert result["speech"] == "Test response"
    assert result["intent"] == "conversation"


def test_think_handles_api_error(mock_groq_client, clean_memory):
    import brain
    mock_groq_client.chat.completions.create.side_effect = Exception("API Error")

    result = brain.think("Hello")

    assert result["speech"] == "I am having trouble connecting to my logic center."
    assert result["intent"] == "conversation"


def test_think_intent_classification(mock_groq_client, clean_memory):
    import brain
    test_cases = [
        ("close the youtube tab", "browser", "close", "youtube"),
        ("what's on my screen", "screen", "", ""),
        ("open calculator", "app", "open", "calculator"),
        ("run a script", "system", "", ""),
    ]

    for prompt, expected_intent, expected_action, expected_subject in test_cases:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "speech": "OK",
            "intent": expected_intent,
            "action": expected_action,
            "subject": expected_subject
        })
        mock_groq_client.chat.completions.create.return_value = mock_response

        result = brain.think(prompt)
        assert result["intent"] == expected_intent
        assert result["action"] == expected_action
        assert result["subject"] == expected_subject.lower()