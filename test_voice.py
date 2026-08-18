"""Voice diagnostics: list microphones, then test capture + Whisper + wake words."""
import sys

from config import GROQ_API_KEY, WHISPER_MODEL


def list_devices():
    import sounddevice as sd

    print("=" * 60)
    print("Audio input devices:")
    try:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                print(f"  [{i}] {d['name']}  (in={d['max_input_channels']}, def={d['default_high_input_dev']})")
    except Exception as e:
        print(f"  (could not list devices: {e})")
    try:
        d = sd.query_devices(kind="input")
        print(f"-> Default input device: {sd.query_devices(d['index'])['name']}")
    except Exception as e:
        print(f"  (no default input: {e})")
    print("=" * 60)


def test_capture():
    from listener import transcribe_audio
    import speech_recognition as sr

    print("\nListening for 6 seconds... say something (e.g. 'jarvis').\n")
    r = sr.Recognizer()
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True
    with sr.Microphone() as source:
        try:
            r.adjust_for_ambient_noise(source, duration=0.3)
            audio = r.listen(source, timeout=6, phrase_time_limit=5)
        except sr.WaitTimeoutError:
            print("No speech detected within 6s (mic may be muted or not the default).")
            return
    text = transcribe_audio(audio.get_wav_data())
    print(f"Whisper heard: {text!r}")
    return text


def main():
    print(f"Groq key present: {bool(GROQ_API_KEY)}")
    print(f"Whisper model: {WHISPER_MODEL}")
    list_devices()
    text = test_capture()
    if text:
        wake = ("jarvis", "barq", "bark", "hey barq")
        print("\nWake-word check:", "MATCH" if any(w in text for w in wake) else "no match")


if __name__ == "__main__":
    main()