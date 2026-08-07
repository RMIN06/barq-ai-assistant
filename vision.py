"""Groq vision analysis of the screen so Barq can describe what you're seeing."""
import base64

from groq import Groq

from config import GROQ_API_KEY, VISION_MODEL

_client = Groq(api_key=GROQ_API_KEY)


def describe_screen(png_bytes: bytes, question: str = None) -> str:
    """Send a screenshot to Groq's vision model and return a text description."""
    try:
        data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
        user_text = (
            question
            or "Look at this computer screen. Describe what the user is doing: "
            "which app is focused, what content is visible, and any browser tab details. "
            "Be concise and practical."
        )
        completion = _client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
            temperature=0.4,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Vision error]: {e}")
        return "I could not analyze the screen right now."