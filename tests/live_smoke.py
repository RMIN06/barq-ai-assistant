"""Opt-in live provider smoke test. Run directly, never during unit tests."""
import io

import requests
from groq import Groq
from PIL import Image, ImageDraw

from config import DEEPGRAM_API_KEY, DEEPGRAM_MODEL, GROQ_API_KEY, LLM_MODEL, VISION_MODEL, WHISPER_MODEL
from vision import describe_screen
from voice_state import is_sleep_command


def main():
    groq = Groq(api_key=GROQ_API_KEY, timeout=45.0, max_retries=2)
    available = {item.id for item in groq.models.list().data}
    for model in (LLM_MODEL, VISION_MODEL, WHISPER_MODEL):
        assert model in available, f"Configured Groq model unavailable: {model}"
    completion = groq.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": "Reply with exactly: ready"}],
        temperature=0,
    )
    assert "ready" in (completion.choices[0].message.content or "").lower()
    print("Groq chat: OK")

    picture = Image.new("RGB", (128, 128), "white")
    ImageDraw.Draw(picture).rectangle((24, 24, 104, 104), fill="red")
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    answer = describe_screen(buffer.getvalue(), "What color is the square? Answer briefly.")
    assert "red" in answer.lower(), answer
    print("Groq vision: OK")

    response = requests.post(
        "https://api.deepgram.com/v1/speak",
        headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
        params={"model": DEEPGRAM_MODEL},
        json={"text": "Jarvis, go to sleep."},
        timeout=30,
    )
    response.raise_for_status()
    assert len(response.content) > 1000
    print("Deepgram voice synthesis: OK")
    transcription = groq.audio.transcriptions.create(
        model=WHISPER_MODEL,
        file=("voice.mp3", response.content, "audio/mpeg"),
        language="en",
    )
    assert "jarvis" in transcription.text.lower() and "sleep" in transcription.text.lower(), transcription.text
    assert is_sleep_command(transcription.text), transcription.text
    print("Groq speech transcription: OK")


if __name__ == "__main__":
    main()
