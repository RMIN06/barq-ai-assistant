"""
Wake Word Detection v2 - Hybrid Pipeline:
1. Silero VAD (Voice Activity Detection) - filters silence
2. Porcupine (Primary) - <50ms hardware-accelerated keyword spotting
3. Groq Whisper (Confirmation) - High accuracy verification
"""
import time
import numpy as np
import threading
from pathlib import Path
from collections import deque

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

_silero_model = None
_silero_utils = None
_porcupine = None
_pvporcupine = None
_sd = None


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
    return any(sub in check for sub in substrings)


class HybridWakeDetector:
    def __init__(self, vad_threshold: float = 0.5, porcupine_sensitivity: float = 0.5):
        self.vad_threshold = vad_threshold
        self.porcupine_sensitivity = porcupine_sensitivity
        self._audio_buffer = deque(maxlen=int(PORCUPINE_SAMPLE_RATE * 2))
        self._stop_event = threading.Event()
        self._detected = threading.Event()
        self._porcupine_ready = _init_porcupine()
        self._vad_ready = _init_silero_vad()
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
            return self._listen_vad_whisper(external_stop)
        else:
            return self._listen_whisper_only(external_stop)

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
                        if self._confirm_with_whisper():
                            self._detected.set()
                        else:
                            log.info("Whisper confirmation failed, continuing...")

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
        from listener import transcribe_audio, _record_wake_audio
        import io
        import wave

        log.info("Confirming with Whisper...")
        try:
            wav_bytes = _record_wake_audio(duration=2.0)
            if not wav_bytes:
                return False
            text = transcribe_audio(wav_bytes)
            if not text:
                return False
            log.info(f"Whisper heard: {text!r}")
            matched = _substrings_match(text, WAKE_WORDS)
            if matched:
                log.info(f"WAKE CONFIRMED: {text!r}")
            return matched
        except Exception as e:
            log.error(f"Whisper confirmation error: {e}")
            return False

    def _listen_vad_whisper(self, external_stop) -> bool:
        from listener import short_phrase_for_wake
        log.info("VAD + Whisper fallback armed")
        while True:
            if self._detected.is_set() or (external_stop and external_stop.is_set()):
                return self._detected.is_set()
            phrase = short_phrase_for_wake()
            if phrase and _substrings_match(phrase, WAKE_WORDS):
                log.info(f"VAD+Whisper WAKE: {phrase!r}")
                self._detected.set()
                return True
            time.sleep(0.1)

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