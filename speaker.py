import asyncio
import io
import os

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
from elevenlabs.client import ElevenLabs

from config import ELEVENLABS_API_KEY, ELEVEN_MODEL, ELEVEN_VOICE_ID

client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

_mixer_initialized = False


def _ensure_mixer():
    global _mixer_initialized
    if not _mixer_initialized:
        try:
            pygame.mixer.init()
            _mixer_initialized = True
        except Exception as e:
            print(f"[Audio] Mixer init failed (headless mode?): {e}")


async def speak(text: str):
    if not text or not text.strip():
        return

    _ensure_mixer()
    if not _mixer_initialized:
        print(f"[Barq (Text Fallback - No Audio)]: {text}")
        return

    try:
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id=ELEVEN_VOICE_ID,
            model_id=ELEVEN_MODEL,
            output_format="mp3_44100_128",
        )
        audio_bytes = b"".join(audio_generator)
        audio_stream = io.BytesIO(audio_bytes)

        pygame.mixer.music.load(audio_stream)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"[ElevenLabs Voice Error]: {e}")
        print(f"[Barq (Text Fallback)]: {text}")


if __name__ == "__main__":
    print("Testing ElevenLabs Voice...")
    asyncio.run(speak("Systems are fully operational."))