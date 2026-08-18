"""
Wake-word detection so Barq sleeps 24/7 and activates like Siri.

Primary: Picovoice Porcupine (set PORCUPINE_ACCESS_KEY in .env / env vars).
Fallback: Groq Whisper keyword check on short audio clips if Porcupine is
not configured.
"""
import time

import numpy as np

from config import (
    PORCUPINE_ACCESS_KEY,
    PORCUPINE_KEYWORD,
    PORCUPINE_MODEL_PATH,
    WAKE_WORDS,
)


def _substrings_match(check: str, substrings) -> bool:
    check = check.lower()
    return any(sub in check for sub in substrings)


class WakeWordDetector:
    def __init__(self):
        self._porcupine = None
        self._pvporcupine = None
        self._sd = None
        self._init_porcupine()

    def _init_porcupine(self):
        if not PORCUPINE_ACCESS_KEY:
            print("[Wake] Porcupine access key missing - using Whisper fallback.")
            return
        try:
            import pvporcupine
            import sounddevice as sd
        except ImportError:
            print("[Wake] pvporcupine/sounddevice not installed - Whisper fallback.")
            return

        self._pvporcupine = pvporcupine
        self._sd = sd
        try:
            if PORCUPINE_MODEL_PATH.exists():
                self._porcupine = pvporcupine.create(
                    access_key=PORCUPINE_ACCESS_KEY,
                    keyword_paths=[str(PORCUPINE_MODEL_PATH)],
                )
            else:
                self._porcupine = pvporcupine.create(
                    access_key=PORCUPINE_ACCESS_KEY,
                    keywords=[PORCUPINE_KEYWORD],
                )
            print(f"[Wake] Porcupine armed (keyword: {PORCUPINE_KEYWORD}).")
        except Exception as e:
            print(f"[Wake] Porcupine init failed ({e}) - using Whisper fallback.")
            self._porcupine = None

    def wait(self, stop_event=None) -> bool:
        """Block until a wake word is heard. Returns True when woken."""
        if self._porcupine is not None:
            return self._listen_porcupine(stop_event)
        return self._listen_whisper_fallback(stop_event)

    # ------------------------------------------------------------------ #
    def _listen_porcupine(self, stop_event) -> bool:
        porcupine = self._porcupine
        detected = {"value": False}

        def audio_callback(indata, frames, time_info, status):
            pcm = np.frombuffer(indata, dtype=np.int16)
            if porcupine.process(pcm) >= 0:
                detected["value"] = True

        try:
            with self._sd.RawInputStream(
                samplerate=porcupine.sample_rate,
                blocksize=porcupine.frame_length,
                channels=1,
                dtype=np.int16,
                callback=audio_callback,
            ):
                while not detected["value"]:
                    if stop_event and stop_event.is_set():
                        return False
                    time.sleep(0.05)
        except Exception as e:
            print(f"[Wake] Porcupine stream error: {e}")
            return False
        return True

    def _listen_whisper_fallback(self, stop_event) -> bool:
        """Repeatedly capture short clips and check them with Groq Whisper."""
        from listener import short_phrase_for_wake
        from barqlog import get_logger

        log = get_logger("wake")
        log.info("Wake fallback armed. Listening (Whisper)...")
        while True:
            if stop_event and stop_event.is_set():
                return False
            phrase = short_phrase_for_wake()
            if phrase:
                log.info("Heard: %r", phrase)
            if phrase and _substrings_match(phrase, WAKE_WORDS):
                log.info("WAKE WORD MATCHED: %r", phrase)
                return True


def wait_for_wake(stop_event=None) -> bool:
    return WakeWordDetector().wait(stop_event)