# Barq AI Assistant

![Python](https://img.shields.io/badge/Backend-Python-blue)
![Next.js](https://img.shields.io/badge/Frontend-Next.js-black)
![Three.js](https://img.shields.io/badge/UI-Three.js-lightgrey)
![Groq](https://img.shields.io/badge/LLM-Groq-purple)
![Deepgram](https://img.shields.io/badge/Voice-Deepgram-orange)
![Tests](https://img.shields.io/badge/Tests-65%20passing-brightgreen)
![License](https://img.shields.io/badge/License-MIT-green)

A personal desktop AI assistant inspired by JARVIS — built to actually run your machine, not just chat with you. Barq listens, talks back, and executes: it has full access to your computer, can browse and scrape the web, and carries out real tasks on request, all wrapped in a 3D interactive interface.

---

## Overview

Most AI assistants are boxed into a chat window. Barq isn't. It's a control layer over your own desktop — capable of taking a spoken or typed command and turning it into real action, whether that's running a script, pulling data off a website, or managing files. Think less "chatbot," more "always-on operator."

---

## Key Features

### 🎯 Core Capabilities
- **Login Standby** — Desktop app starts hidden and listens for Barq or Jarvis
- **Wake Word Detection** — Microphone voice activity detection followed by Groq Whisper; optional Porcupine
- **Voice Interaction** — Deepgram synthesis and Groq Whisper transcription; playback requires a working Windows output device
- **System Control** — File operations, process management, browser tab control, app launching
- **Code Execution** — Automatic arbitrary code execution is disabled
- **Screen Understanding** — Window/tab awareness + Groq Vision for screen analysis
- **Multi-Monitor Support** — Full window management across all displays

### 🛡️ Security & Reliability
- **HMAC Authentication** — WebSocket connections require signed tokens
- **Health Monitoring** — `/health/live`, `/health/ready`, `/health/metrics` (Prometheus)
- **Structured Logging** — JSON logs with component-level diagnostics
- **Graceful Degradation** — Offline fallbacks for all cloud dependencies
- **Error Recovery** — Automatic engine restart with state preservation

### 🧠 Intelligence & Memory
- **Vector Memory (RAG)** — Semantic search over conversations, facts, code snippets
- **Persistent Memory** — JSON + ChromaDB with sentence-transformers embeddings
- **Plugin System** — Extensible architecture with 6 built-in plugins
- **Context Awareness** — Real-time screen context fed to LLM

### 🖥️ Immersive Interface
- **Orb Visualization** — Dashboard orb with listening state
- **Real-time Transcript** — Live conversation log with SITREP markers
- **System Tray Integration** — Hide/show/quit from tray
- **Auto-start at Login** — User Startup shortcut launches Electron hidden

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Backend Language** | Python | 3.12 | Core logic, system integration |
| **LLM Inference** | Groq API | — | Llama-3.3-70B, Whisper, Vision |
| **Voice Synthesis** | Deepgram | — | Consistent configured voice |
| **Wake Word** | Picovoice Porcupine | 3.x | Hardware-accelerated keyword spotting |
| **Wake Fallback** | Groq Whisper | — | Cloud-based keyword detection |
| **Audio Capture** | sounddevice + SpeechRecognition | — | Microphone input, VAD |
| **VAD** | Silero | — | Voice Activity Detection |
| **Vector DB** | ChromaDB | 1.5+ | Semantic memory storage |
| **Embeddings** | sentence-transformers | 6.1+ | Local embedding model (all-MiniLM-L6-v2) |
| **Web Framework** | FastAPI | 0.115+ | REST + WebSocket server |
| **Async Runtime** | asyncio | stdlib | Concurrent operations |
| **System Control** | psutil, pyautogui, ctypes | — | Window/process management |
| **Code Execution** | Open Interpreter | 0.4+ | LLM-driven code execution |
| **Frontend Framework** | Next.js | 16.3 | React-based UI server |
| **UI Runtime** | React | 19.2 | Component framework |
| **3D Graphics** | Three.js + @react-three/fiber | 0.185 | Immersive orb visualization |
| **Animation** | Framer Motion | 13.x | UI transitions |
| **Desktop Wrapper** | Electron | 33.x | Native window, tray, auto-start |
| **Logging** | stdlib logging + custom | — | Structured file + console logging |
| **Config Management** | python-dotenv | — | Environment variables |
| **Memory Storage** | JSON + ChromaDB | — | Conversation history + vector memory |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      BARQ SYSTEM ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    WebSocket     ┌──────────────┐            │
│  │   Electron   │ ◄──────────────► │   FastAPI    │            │
│  │   Overlay    │   (ws://8000)    │   Backend    │            │
│  │  (Next.js)   │   + HMAC Auth    │  (Python)    │            │
│  └──────────────┘                  └──────┬───────┘            │
│         ▲                                 │                    │
│         │                                 ▼                    │
│  ┌──────┴──────┐                ┌──────────────────┐          │
│  │  Three.js   │                │  Groq API        │          │
│  │  3D Orb UI  │                │  • LLM (Llama)   │          │
│  └─────────────┘                │  • Whisper STT   │          │
│                                 │  • Vision        │          │
│                                 └────────┬─────────┘          │
│                                          │                    │
│                                 ┌────────┴─────────┐          │
│                                 │  ElevenLabs TTS  │          │
│                                 └──────────────────┘          │
│                                                                 │
│  SYSTEM INTEGRATION LAYER (Python)                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ • Display Manager (multi-monitor, window management)     │  │
│  │ • Screen Context (win32, psutil, pyautogui)              │  │
│  │ • Vision (screenshot → Groq Vision)                       │  │
│  │ • Browser Control (tab enumeration, close/open)          │  │
│  │ • App Launcher (calc, notepad, explorer, etc.)           │  │
│  │ • Open Interpreter (arbitrary code execution)            │  │
│  │ • Vector Memory (ChromaDB + sentence-transformers)       │  │
│  │ • Plugin System (browser, filesystem, system, code,      │  │
│  │   vision, memory + user plugins)                         │  │
│  │ • Wake Word (Porcupine + Silero VAD + Whisper fallback)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  SERVICE LAYER (Windows)                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ • barq_service.py - Zero-memory background engine        │  │
│  │ • Windows Service (NSSM) - Auto-start, crash recovery    │  │
│  │ • On-demand UI spawning (<2s cold start)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Getting Started

### Prerequisites

- Windows 10/11
- Python 3.12+
- Node.js 20+
- Groq API key (https://console.groq.com)
- Deepgram API key (https://deepgram.com)
- Optional: Picovoice access key for faster wake word (https://console.picovoice.ai)

### 1. Clone the Repository

```powershell
git clone https://github.com/your-username/barq-ai-assistant.git
cd barq-ai-assistant
```

### 2. Backend Setup

```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Configure environment
copy .env.example .env
# Edit .env with your API keys:
# GROQ_API_KEY=your_key
# DEEPGRAM_API_KEY=your_key
# PORCUPINE_ACCESS_KEY=your_key (optional)
```

### 3. Frontend Setup

```powershell
cd barq_ui
npm install
cd ..
```

### 4. Desktop Setup

```powershell
cd desktop
npm install
cd ..
```

### 5. Run the Assistant

**Development Mode (with UI):**
```powershell
cd desktop
npm start
```

**Production Service Mode (zero-memory background):**
```powershell
# Install as Windows Service (run as Administrator)
cd "D:\Barq Assistant\barq-ai-assistant"
.\install-service.ps1

# Or run manually
.\venv\Scripts\python.exe barq_service.py
```

---

## Running Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Development** | `cd desktop && npm start` | Full stack with hot reload |
| **Service** | `.\venv\Scripts\python.exe barq_service.py` | Headless background engine |
| **Windows Service** | `.\install-service.ps1` (Admin) | Persistent service, auto-start |
| **Headless CLI** | `.\venv\Scripts\python.exe main.py` | CLI-only, no UI |

---

## Wake Words

Say any of these to activate Barq:
- `Barq`, `Jarvis`, `Hey Barq`, `Hey Jarvis`

## Sleep Words

Say any of these to dismiss Barq:
- `go to sleep`, `sleep mode`, `standby`
- `shut down`, `goodnight`, `turn off`

---

## API Endpoints

### Health Checks
- `GET /health/live` — Liveness probe (always 200 if process alive)
- `GET /health/ready` — Readiness probe (checks all dependencies)
- `GET /health/` — Combined health status
- `GET /health/metrics` — Prometheus metrics

### WebSocket
- `WS /ws?token=<auth_token>` — Real-time communication
  - Requires HMAC token from `.barq_auth` file
  - Messages: state, user, ai, wake, sleep, sitrep

---

## Plugin System

Barq uses a plugin architecture for extensibility:

```python
# plugins/builtin/
├── browser.py      # Browser tab management
├── filesystem.py   # File operations
├── system.py       # App launching, process management
├── code_exec.py    # Open Interpreter integration
├── vision.py       # Screen analysis
└── memory.py       # Persistent memory
```

### Creating Custom Plugins

```python
from plugins import BasePlugin, PluginManifest, HookPoint

class MyPlugin(BasePlugin):
    def get_manifest(self):
        return PluginManifest(
            name="my_plugin",
            version="1.0.0",
            description="My custom capability",
            author="Me",
            hooks=[HookPoint.PRE_COMMAND, HookPoint.ON_WAKE],
            permissions=["filesystem"]
        )

    async def on_wake(self, ctx):
        # Called when wake word detected
        pass

    async def pre_command(self, ctx):
        # Return False to block command
        return True
```

---

## Vector Memory (RAG)

Semantic search over your conversation history and knowledge:

```python
from memory_v2 import vector_memory, add_conversation, add_fact, search_memory

# Store conversations
add_conversation("What's the weather?", "It's sunny in London")

# Store facts
add_fact("Python 3.12 released in October 2023", category="tech")

# Search
results = search_memory("weather london", n_results=3)
results = search_memory("python release", filter_type="fact")
```

---

## Multi-Monitor & Window Management

```python
from display_manager import (
    get_all_monitors, get_all_windows,
    find_windows_by_title, snap_window,
    move_window_to_monitor, bring_window_to_front
)

# List monitors
monitors = get_all_monitors()
for m in monitors:
    print(f"{m.device_name}: {m.rect} @ {m.scale_factor}x")

# Find and manipulate windows
windows = find_windows_by_title("chrome")
for w in windows:
    snap_window(w.hwnd, "left")  # Snap to left half
    # or
    move_window_to_monitor(w.hwnd, monitors[1])  # Move to second monitor
```

---

## Configuration

### Environment Variables (.env)

```env
# Required
GROQ_API_KEY=your_groq_key
ELEVENLABS_API_KEY=your_elevenlabs_key

# Optional
ELEVEN_VOICE_ID=pNInz6obpgDQGcFmaJgB
ELEVEN_MODEL=eleven_multilingual_v2
PORCUPINE_ACCESS_KEY=your_picovoice_key
PORCUPINE_KEYWORD=jarvis
LLM_MODEL=llama-3.3-70b-versatile
VISION_MODEL=llama-3.2-90b-vision-preview
WHISPER_MODEL=whisper-large-v3-turbo
```

### Config File (config.py)

All settings are in `config.py` with sensible defaults.

---

## Testing

```powershell
# Run all tests
.\venv\Scripts\python.exe -m pytest tests/ -v

# Run specific test file
.\venv\Scripts\python.exe -m pytest tests/test_plugins.py -v

# Run with coverage
.\venv\Scripts\python.exe -m pytest tests/ --cov=. --cov-report=html
```

### Test Suite (62 tests)
- `test_auth.py` - HMAC authentication (8 tests)
- `test_brain.py` - LLM reasoning & memory (8 tests)
- `test_config.py` - Configuration (6 tests)
- `test_display_manager.py` - Multi-monitor/window (11 tests)
- `test_memory_v2.py` - Vector memory RAG (14 tests)
- `test_plugins.py` - Plugin system (8 tests)
- `test_screen_context.py` - Screen awareness (8 tests)

---

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`):
- Backend tests (Python + pytest + mypy + bandit)
- Frontend tests (Next.js + ESLint + TypeScript + build)
- Desktop tests (Electron build)
- Integration tests (health endpoints)
- Automated releases on tag push

---

## Project Structure

```
barq-ai-assistant/
├── barq_service.py          # Windows Service entry point
├── server.py                # FastAPI + WebSocket + Engine
├── brain.py                 # LLM reasoning + JSON memory
├── listener.py              # STT (Whisper)
├── speaker.py               # TTS (ElevenLabs)
├── wakeword.py              # Wake detection v1 (Porcupine)
├── wakeword_v2.py           # Wake detection v2 (VAD+Porcupine+Whisper)
├── screen_context.py        # Window/tab awareness
├── vision.py                # Screen vision (Groq Vision)
├── display_manager.py       # Multi-monitor/window management
├── memory_v2.py             # Vector memory (ChromaDB)
├── health.py                # Health checks + Prometheus metrics
├── auth.py                  # HMAC authentication
├── config.py                # Configuration
├── barqlog.py               # Logging
├── plugins/                 # Plugin system
│   ├── __init__.py          # Base classes, registry
│   └── builtin/             # 6 built-in plugins
├── tests/                   # 62 unit/integration tests
├── barq_ui/                 # Next.js frontend
│   ├── src/app/page.tsx     # Main overlay
│   └── src/components/JarvisOrb.tsx  # 3D orb
├── desktop/                 # Electron wrapper
│   ├── main.js              # Main process
│   └── install-startup.ps1  # Auto-start installer
├── install-service.ps1      # Windows Service installer
├── PRD.md                   # Product Requirements Document
├── RUN_GUIDE.md             # Quick start guide
└── requirements*.txt        # Python dependencies
```

---

## Safety & Security

⚠️ **Important**: Barq has full access to the host machine. 
- Run only in trusted environments
- Review command permissions before granting
- Never expose backend to internet without authentication
- Audit logs available at `barq_data/barq.log` and `barq_data/audit.log`

---

## Roadmap

- [ ] Local model support (Ollama, llama.cpp)
- [ ] Mobile companion app
- [ ] Cross-device sync
- [ ] Proactive suggestions
- [ ] Gesture/camera input
- [ ] Sandbox for code execution (nsjail)

---

## Authors

Muhammad Ibrahim
Muhammad Hashim

---

## Contributing

This is a personal project, but issues and suggestions are welcome. 
1. Fork the repo
2. Create a feature branch
3. Submit a PR with tests

---

## License

MIT License - See LICENSE file for details.
