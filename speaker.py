import asyncio
import io
import os

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
import aiohttp

from config import DEEPGRAM_API_KEY, DEEPGRAM_VOICE, DEEPGRAM_MODEL

DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"

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

    if not DEEPGRAM_API_KEY:
        print(f"[Barq (Text Fallback - No Deepgram Key)]: {text}")
        return

    try:
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "application/json",
        }
        params = {
            "model": DEEPGRAM_MODEL or "aura-asteria-en",
        }
        payload = {"text": text}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPGRAM_TTS_URL,
                headers=headers,
                params=params,
                json=payload,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"[Deepgram TTS Error]: {resp.status} - {error_text}")
                    print(f"[Barq (Text Fallback)]: {text}")
                    return

                audio_bytes = await resp.read()

        audio_stream = io.BytesIO(audio_bytes)
        pygame.mixer.music.load(audio_stream)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)

    except Exception as e:
        print(f"[Deepgram Voice Error]: {e}")
        print(f"[Barq (Text Fallback)]: {text}")


if __name__ == "__main__":
    print("Testing Deepgram Voice...")
    asyncio.run(speak("Systems are fully operational."))