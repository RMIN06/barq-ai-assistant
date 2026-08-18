import speech_recognition as sr
from groq import Groq
from config import GROQ_API_KEY, WHISPER_MODEL

_client = Groq(api_key=GROQ_API_KEY)

LANG = "en"


def transcribe_audio(wav_bytes: bytes) -> str:
    """Send a raw WAV segment to Groq Whisper for high-accuracy transcription."""
    from barqlog import get_logger

    log = get_logger("stt")
    try:
        result = _client.audio.transcriptions.create(
            file=("segment.wav", wav_bytes, "audio/wav"),
            model=WHISPER_MODEL,
            language=LANG,
        )
        text = result.text.lower().strip()
        log.info("Whisper -> %r", text)
        return text
    except Exception as e:
        log.error("Whisper STT error: %s", e)
        return ""


def listen_for_command(timeout: float = 6.0, phrase_time_limit: float = 20.0) -> str:
    """
    Listens for a spoken command using SpeechRecognition's voice-activity
    detection, then decodes the captured audio with Groq Whisper for
    ChatGPT/Gemini-grade accuracy (handles slightly unclear speech well).
    """
    from barqlog import get_logger

    log = get_logger("stt")
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio = recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
            return transcribe_audio(audio.get_wav_data())
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        return ""
    except Exception as e:
        log.error("Mic capture error: %s", e)
        return ""


def _record_wake_audio(duration: float = 3.0, samplerate: int = 16000, channels: int = 1) -> bytes:
    import io
    import wave
    import sounddevice as sd

    try:
        recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=channels, dtype='int16')
        sd.wait()
        with io.BytesIO() as buf:
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(samplerate)
                wf.writeframes(recording.tobytes())
            return buf.getvalue()
    except Exception as e:
        from barqlog import get_logger
        log = get_logger("wake")
        log.error("Wake audio capture error: %s", e)
        return b""


def short_phrase_for_wake() -> str:
    """A short, quick capture used by the wake-word fallback path."""
    from barqlog import get_logger

    log = get_logger("wake")
    log.info("Capturing short wake phrase audio...")
    wav_bytes = _record_wake_audio()
    if not wav_bytes:
        log.error("Wake capture failed, falling back to listen_for_command")
        return listen_for_command(timeout=3.0, phrase_time_limit=3.5)

    text = transcribe_audio(wav_bytes)
    log.info("Wake capture heard: %r", text)
    return text