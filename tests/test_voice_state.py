from voice_state import is_sleep_command, is_non_request
from wakeword_v2 import _substrings_match


def test_sleep_requires_explicit_command():
    assert is_sleep_command("Jarvis, go to sleep.")
    assert is_sleep_command("standby")
    assert is_sleep_command("ok now you can go to sleep")
    assert not is_sleep_command("turn off the lights")
    assert not is_sleep_command("tell me about sleep mode")


def test_incidental_audio_does_not_trigger_reply():
    assert is_non_request("Thank you.")
    assert is_non_request("welcome")
    assert not is_non_request("open Spotify")


def test_wake_requires_whole_word():
    assert _substrings_match("Hey Jarvis!", ["jarvis"])
    assert not _substrings_match("work on the project", ["barq", "jarvis"])
    assert not _substrings_match("jarvison", ["jarvis"])


def test_silence_is_not_sent_to_transcription():
    import speech_recognition as sr
    from listener import has_audible_speech

    assert not has_audible_speech(sr.AudioData(b"\x00\x00" * 1600, 16000, 2))
    assert has_audible_speech(sr.AudioData(b"\x00\x08" * 1600, 16000, 2))


def test_manual_state_endpoints(monkeypatch):
    from fastapi.testclient import TestClient
    import server
    from auth import get_auth_token

    monkeypatch.setattr(server, "SERVICE_MODE", True)
    server.manual_wake_event.clear()
    server.manual_sleep_event.clear()
    with TestClient(server.app) as client:
        token = get_auth_token()
        assert client.post("/wake").status_code == 401
        assert client.post("/wake", headers={"X-Barq-Token": token}).status_code == 200
        assert server.manual_wake_event.is_set()
        assert client.post("/sleep", headers={"X-Barq-Token": token}).status_code == 200
        assert server.manual_sleep_event.is_set()
        with client.websocket_connect(f"/ws?token={token}") as socket:
            socket.send_json({"type": "command", "text": "Jarvis, go to sleep"})
            assert socket.receive_json()["type"] == "sleep"
    server.manual_wake_event.clear()
    server.manual_sleep_event.clear()
