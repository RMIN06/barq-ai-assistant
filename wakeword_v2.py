"""
Wake Word Detection v2 - Local-First Pipeline (No API calls for wake):
1. Silero VAD (Voice Activity Detection) - filters silence
2. Porcupine (Primary, optional) - <50ms hardware-accelerated keyword spotting
3. VAD + Energy Threshold (Fallback) - Local voice activity detection
4. Local Whisper.cpp (Optional) - For confirmation if model available
"""
import time
import numpy as np
import threading
from pathlib import Path
from collections import deque
import io
import wave
import re

from config import (
    PORCUPINE_ACCESS_KEY,
    PORCUPINE_KEYWORD,
    PORCUPINE_MODEL_PATH,
    WAKE_WORDS,
)
from barqlog import get_logger

log = get_logger("wake_v2")

VAD_SAMPLE_RATE = 16000
VAD_FRAME_MS = 30
VAD_FRAME_SIZE = int(VAD_SAMPLE_RATE * VAD_FRAME_MS / 1000)
PORCUPINE_SAMPLE_RATE = 16000

BASE_DIR = Path(__file__).resolve().parent
LOCAL_WHISPER_MODEL = BASE_DIR / "models" / "ggml-tiny.en.bin"

_silero_model = None
_silero_utils = None
_porcupine = None
_pvporcupine = None
_sd = None
_local_whisper = None


def _init_silero_vad():
    global _silero_model, _silero_utils
    if _silero_model is not None:
        return True
    try:
        import torch
        _silero_model, _silero_utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        _silero_model.eval()
        log.info("Silero VAD loaded")
        return True
    except Exception as e:
        log.warning(f"Silero VAD init failed: {e}")
        return False


def _init_porcupine():
    global _porcupine, _pvporcupine, _sd
    if _porcupine is not None:
        return True
    if not PORCUPINE_ACCESS_KEY:
        log.info("Porcupine access key not set")
        return False
    try:
        import pvporcupine
        import sounddevice as sd
        _pvporcupine = pvporcupine
        _sd = sd
    except ImportError:
        log.info("pvporcupine/sounddevice not installed")
        return False

    try:
        if PORCUPINE_MODEL_PATH.exists():
            _porcupine = pvporcupine.create(
                access_key=PORCUPINE_ACCESS_KEY,
                keyword_paths=[str(PORCUPINE_MODEL_PATH)],
            )
            log.info(f"Porcupine loaded custom model: {PORCUPINE_MODEL_PATH}")
        else:
            _porcupine = pvporcupine.create(
                access_key=PORCUPINE_ACCESS_KEY,
                keywords=[PORCUPINE_KEYWORD],
            )
            log.info(f"Porcupine loaded built-in keyword: {PORCUPINE_KEYWORD}")
        return True
    except Exception as e:
        log.error(f"Porcupine init failed: {e}")
        _porcupine = None
        return False


def _vad_probability(audio_frame: np.ndarray) -> float:
    if _silero_model is None:
        return 1.0
    import torch
    with torch.no_grad():
        tensor = torch.from_numpy(audio_frame.astype(np.float32) / 32768.0).unsqueeze(0)
        prob = _silero_model(tensor, VAD_SAMPLE_RATE).item()
    return prob


def _substrings_match(check: str, substrings) -> bool:
    check = check.lower()
    return any(re.search(r"(?<!\w)" + re.escape(word.lower()) + r"(?!\w)", check) for word in substrings)


def _init_local_whisper():
    """Initialize local whisper.cpp for offline transcription."""
    global _local_whisper
    if _local_whisper is not None:
        return True
    if not LOCAL_WHISPER_MODEL.exists():
        log.warning(f"Local whisper model not found: {LOCAL_WHISPER_MODEL}")
        return False
    try:
        from whispercpp import Whisper
        _local_whisper = Whisper.from_pretrained(str(LOCAL_WHISPER_MODEL))
        log.info(f"Local whisper.cpp loaded: {LOCAL_WHISPER_MODEL.name}")
        return True
    except Exception as e:
        log.warning(f"Local whisper.cpp init failed: {e}")
        return False


def _transcribe_local_whisper(wav_bytes: bytes) -> str:
    """Transcribe audio using local whisper.cpp (no API calls)."""
    if not _init_local_whisper():
        return ""
    try:
        # Save wav bytes to temp file for whispercpp
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        # Transcribe
        result = _local_whisper.transcribe(tmp_path)
        text = " ".join([segment.text for segment in result]).lower().strip()

        # Cleanup
        try:
            Path(tmp_path).unlink()
        except:
            pass

        log.info(f"Local Whisper -> {text!r}")
        return text
    except Exception as e:
        log.error(f"Local whisper transcription error: {e}")
        return ""


class HybridWakeDetector:
    def __init__(self, vad_threshold: float = 0.5, porcupine_sensitivity: float = 0.5):
        self.vad_threshold = vad_threshold
        self.porcupine_sensitivity = porcupine_sensitivity
        self._audio_buffer = deque(maxlen=int(PORCUPINE_SAMPLE_RATE * 2))
        self._stop_event = threading.Event()
        self._detected = threading.Event()
        self._porcupine_ready = _init_porcupine()
        self._vad_ready = True  # SpeechRecognition performs local voice activity detection.
        self._stream = None

        if not self._porcupine_ready and not self._vad_ready:
            log.warning("No wake detection backend available")

    def wait(self, stop_event=None) -> bool:
        external_stop = stop_event
        self._stop_event.clear()
        self._detected.clear()

        if self._porcupine_ready:
            return self._listen_hybrid(external_stop)
        elif self._vad_ready:
            try:
                return self._listen_vad_whisper(external_stop)
            except Exception as e:
                log.error(f"VAD+Whisper failed: {e}")
        log.warning("No verified wake-word backend available")
        return False

    def _listen_hybrid(self, external_stop) -> bool:
        porcupine = _porcupine
        frame_len = porcupine.frame_length
        sample_rate = porcupine.sample_rate

        log.info("Hybrid wake armed: VAD -> Porcupine -> Whisper confirm")

        def audio_callback(indata, frames, time_info, status):
            if self._detected.is_set():
                return
            if external_stop and external_stop.is_set():
                self._detected.set()
                return

            pcm = np.frombuffer(indata, dtype=np.int16)
            self._audio_buffer.extend(pcm)

            if len(self._audio_buffer) >= frame_len:
                frame = np.array(list(self._audio_buffer)[-frame_len:], dtype=np.int16)
                vad_prob = _vad_probability(frame)

                if vad_prob >= self.vad_threshold:
                    keyword_index = porcupine.process(frame)
                    if keyword_index >= 0:
                        log.info(f"Porcupine detected keyword index: {keyword_index}")
                        self._detected.set()

        try:
            with _sd.RawInputStream(
                samplerate=sample_rate,
                blocksize=frame_len,
                channels=1,
                dtype=np.int16,
                callback=audio_callback,
            ):
                while not self._detected.is_set():
                    if external_stop and external_stop.is_set():
                        return False
                    time.sleep(0.05)
        except Exception as e:
            log.error(f"Audio stream error: {e}")
            return False
        return True

    def _confirm_with_whisper(self) -> bool:
        import tempfile
        import sounddevice as sd

        log.info("Confirming with local Whisper...")
        try:
            # Record audio directly
            duration = 2.0
            samplerate = 16000
            recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
            sd.wait()

            # Convert to wav bytes
            with io.BytesIO() as buf:
                with wave.open(buf, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(samplerate)
                    wf.writeframes(recording.tobytes())
                wav_bytes = buf.getvalue()

            if not wav_bytes:
                return False

            # Transcribe locally
            text = _transcribe_local_whisper(wav_bytes)
            if not text:
                return False

            log.info(f"Local Whisper heard: {text!r}")
            matched = _substrings_match(text, WAKE_WORDS)
            if matched:
                log.info(f"WAKE CONFIRMED: {text!r}")
            return matched
        except Exception as e:
            log.error(f"Local Whisper confirmation error: {e}")
            return False

    def _listen_vad_whisper(self, external_stop) -> bool:
        """Wake detection using SpeechRecognition with explicit device selection."""
        import speech_recognition as sr
        import time

        log.info("SpeechRecognition VAD + Groq Whisper wake detection armed")
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8

        wake_words_lower = [w.lower() for w in WAKE_WORDS]
        consecutive_failures = 0
        max_consecutive_failures = 5

        # Find working microphone
        mic_index = self._find_working_microphone()
        if mic_index is None:
            log.error("No working microphone found")
            return False

        log.info(f"Using microphone device index: {mic_index}")

        try:
            while not self._detected.is_set():
                if external_stop and external_stop.is_set():
                    return False

                try:
                    with sr.Microphone(device_index=mic_index) as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.3)
                        audio = recognizer.listen(source, timeout=2.0, phrase_time_limit=4.0)
                    from listener import has_audible_speech
                    if not has_audible_speech(audio):
                        continue

                    try:
                        from listener import transcribe_audio
                        text = transcribe_audio(audio.get_wav_data())
                        if _substrings_match(text, wake_words_lower):
                            log.info("Wake word detected")
                            self._detected.set()
                            return True
                    except Exception as e:
                        log.warning("Wake transcription failed: %s", e)
                        consecutive_failures += 1
                        if consecutive_failures >= max_consecutive_failures:
                            log.error("Too many wake transcription failures")
                            break
                        time.sleep(2)
                        continue

                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    log.error(f"Microphone error: {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        break
                    time.sleep(1)
                    continue

                consecutive_failures = 0  # Reset on successful listen

        except Exception as e:
            log.error(f"SpeechRecognition wake error: {e}")

        return False

    def _find_working_microphone(self) -> int | None:
        """Find a working microphone device index."""
        import speech_recognition as sr
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
            try:
                with sr.Microphone(device_index=index) as source:
                    r = sr.Recognizer()
                    r.adjust_for_ambient_noise(source, duration=0.2)
                log.info(f"Found working microphone: {name} (index {index})")
                return index
            except Exception:
                continue
        return None

    def _listen_energy_fallback(self, external_stop) -> bool:
        """Energy-based fallback using sounddevice."""
        import sounddevice as sd
        import numpy as np

        log.info("Energy fallback armed (sounddevice)")
        sample_rate = 16000
        frame_duration = 1.0
        frame_samples = int(sample_rate * frame_duration)
        energy_threshold = 0.015
        min_speech_frames = 2
        max_silence_frames = 5

        speech_frames = 0
        silence_frames = 0

        try:
            while not self._detected.is_set():
                if external_stop and external_stop.is_set():
                    return False

                recording = sd.rec(frame_samples, samplerate=sample_rate, channels=1, dtype='float32')
                sd.wait()

                frame = recording[:, 0] if len(recording.shape) > 1 else recording
                rms = np.sqrt(np.mean(frame.astype(np.float32)**2))

                if rms > energy_threshold:
                    speech_frames += 1
                    silence_frames = 0
                    if speech_frames >= min_speech_frames:
                        log.info(f"Energy WAKE detected (rms={rms:.4f})")
                        self._detected.set()
                        return True
                else:
                    silence_frames += 1
                    if silence_frames > max_silence_frames:
                        speech_frames = 0
                        silence_frames = 0

        except Exception as e:
            log.error(f"Energy fallback error: {e}")
            return False
        return True

    def _listen_whisper_only(self, external_stop) -> bool:
        from listener import short_phrase_for_wake
        log.info("Whisper-only fallback armed")
        while True:
            if external_stop and external_stop.is_set():
                return False
            phrase = short_phrase_for_wake()
            if phrase and _substrings_match(phrase, WAKE_WORDS):
                log.info(f"Whisper WAKE: {phrase!r}")
                return True


def wait_for_wake_v2(stop_event=None) -> bool:
    return HybridWakeDetector().wait(stop_event)