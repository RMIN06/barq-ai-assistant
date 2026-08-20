import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "barq_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- API keys (set via .env / environment variables) ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# --- ElevenLabs voice ---
ELEVEN_VOICE_ID = os.environ.get("ELEVEN_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
ELEVEN_MODEL = os.environ.get("ELEVEN_MODEL", "eleven_multilingual_v2")

# --- Picovoice (wake word). Optional: set PORCUPINE_ACCESS_KEY in .env ---
# A custom "Barq" model file can be dropped at PORCUPINE_MODEL_PATH for an exact match.
PORCUPINE_ACCESS_KEY = os.environ.get("PORCUPINE_ACCESS_KEY", "")
PORCUPINE_MODEL_PATH = DATA_DIR / "barq_wakeword.ppn"
PORCUPINE_KEYWORD = os.environ.get("PORCUPINE_KEYWORD", "jarvis")
WAKE_WORDS = [
    "barq", "bark", "park", "mark", "spark", "bart", "borg", "brq", "work",
    "jarvis", "hey barq", "hey jarvis", "barq wake", "wake up", "wakeup",
    "wake up barq", "wake up jarvis", "wakeup barq", "wakeup jarvis",
    "hey barq wake", "hey jarvis wake", "hi barq", "hi jarvis",
]
SLEEP_WORDS = ["go to sleep", "sleep mode", "standby", "shut down", "goodnight", "turn off"]

# --- Model IDs ---
LLM_MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
VISION_MODEL = os.environ.get("VISION_MODEL", "llama-3.2-90b-vision-preview")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "whisper-large-v3-turbo")

# --- Data files ---
MEMORY_FILE = DATA_DIR / "memory.json"