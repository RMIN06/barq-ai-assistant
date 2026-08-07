import asyncio
import io
import os

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
from elevenlabs.client import ElevenLabs

from config import ELEVENLAB_KEY, ELEVEN_MODEL, ELEVEN_VOICE_ID

client = ElevenLabs(api_key=ELEVENLAB_KEY)

# Initialize the pygame audio mixer once
pygame.mixer.init()


async def speak(text: str):
    if not text or not text.strip():
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