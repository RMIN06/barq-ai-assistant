# Barq AI Assistant — Product Requirements Document (PRD)

**Version:** 2.0  
**Status:** Active Development  
**Last Updated:** 2026-10-03  
**Author:** Barq Development Team

---

## 1. Executive Summary

Barq is a personal desktop AI assistant inspired by JARVIS — designed to be an always-on, invisible operator that runs your machine, not just chat with you. It listens, talks back, and executes real tasks: filesystem operations, browser automation, code execution, screen understanding, and web scraping.

**Vision:** An AI that consumes near-zero resources when idle, wakes instantly on voice command, and operates as a seamless extension of the user's intent — like a second pair of hands.

---

## 2. Current State Assessment (v1.0)

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      BARQ SYSTEM ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    WebSocket     ┌──────────────┐            │
│  │   Electron   │ ◄──────────────► │   FastAPI    │            │
│  │   Overlay    │   (ws://8000)    │   Backend    │            │
│  │  (Next.js)   │                  │  (Python)    │            │
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
│  │ • Screen Context (win32, psutil, pyautogui)              │  │
│  │ • Vision (screenshot → Groq Vision)                       │  │
│  │ • Browser Control (tab enumeration, close/open)          │  │
│  │ • App Launcher (calc, notepad, explorer, etc.)           │  │
│  │ • Open Interpreter (arbitrary code execution)            │  │
│  │ • Persistent Memory (JSON + future: vector DB)           │  │
│  │ • Wake Word (Porcupine + Whisper fallback)               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Technologies Currently Used

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Backend Language** | Python | 3.12 | Core logic, system integration |
| **LLM Inference** | Groq API | — | Llama-3.3-70B, Whisper-large-v3, Vision |
| **Voice Synthesis** | ElevenLabs | — | Multilingual v2, streaming TTS |
| **Wake Word** | Picovoice Porcupine | 3.x | Hardware-accelerated keyword spotting |
| **Wake Fallback** | Groq Whisper | — | Cloud-based keyword detection |
| **Audio Capture** | sounddevice + SpeechRecognition | — | Microphone input, VAD |
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
| **Memory Storage** | JSON (file-based) | — | Conversation history + facts |

### 2.3 Features Implemented (✅ Done)

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| Wake word detection (Porcupine + Whisper) | ✅ | `wakeword.py` | 30+ wake word variants |
| Voice input (Groq Whisper STT) | ✅ | `listener.py` | VAD + cloud transcription |
| Voice output (ElevenLabs TTS) | ✅ | `speaker.py` | Streaming MP3 playback |
| LLM reasoning (Groq Llama) | ✅ | `brain.py` | JSON-structured output |
| Persistent memory (JSON) | ✅ | `brain.py` | 12-turn history + facts |
| Screen context awareness | ✅ | `screen_context.py` | Active window, browser tabs |
| Vision analysis (screen reading) | ✅ | `vision.py` | Groq Vision API |
| Browser tab control | ✅ | `screen_context.py` | Close/open by keyword |
| App launcher | ✅ | `screen_context.py` | 10+ built-in shortcuts |
| Code execution (Open Interpreter) | ✅ | `main.py`, `server.py` | Arbitrary Python/scripts |
| 3D immersive UI (Three.js) | ✅ | `JarvisOrb.tsx` | State-driven animations |
| Electron desktop wrapper | ✅ | `desktop/main.js` | Frameless, always-on-top |
| System tray integration | ✅ | `desktop/main.js` | Show/hide/quit |
| Auto-start at login | ✅ | `install-startup.ps1` | Windows Task Scheduler |
| Sleep/wake state machine | ✅ | `main.py`, `server.py` | Voice-activated lifecycle |
| WebSocket real-time updates | ✅ | `server.py`, `page.tsx` | State, transcript, sitrep |

---

## 3. Gap Analysis: Current → Target State

### 3.1 Critical Gaps (Must Fix for "Authoritative, Bug-Free")

| Gap | Severity | Impact | Effort |
|-----|----------|--------|--------|
| **No zero-memory background mode** | 🔴 Critical | Runs Electron + Next.js + Python always (~400MB RAM) | High |
| **Wake word latency (Whisper fallback: ~3s)** | 🔴 Critical | Poor UX, feels sluggish | Medium |
| **No authentication on backend API** | 🔴 Critical | Security vulnerability (any local process can control) | Low |
| **No sandboxing for code execution** | 🔴 Critical | Open Interpreter has full system access | High |
| **Single point of failure (no health checks)** | 🟠 High | Engine crash = silent failure | Medium |
| **No automated tests** | 🟠 High | Regression risk, no CI/CD | High |
| **Memory grows unbounded (JSON file)** | 🟠 High | Performance degradation over time | Low |
| **No offline capability** | 🟡 Medium | Requires internet for all features | High |
| **Single monitor assumption** | 🟡 Medium | Breaks on multi-monitor setups | Medium |
| **No plugin/extensibility system** | 🟡 Medium | Hard to add new capabilities | Medium |
| **Error recovery is basic (restart loop)** | 🟡 Medium | Loses context on crash | Medium |
| **No voice activity detection tuning** | 🟡 Medium | False positives/negatives in noise | Low |

### 3.2 Enhancement Opportunities

| Enhancement | Value | Effort |
|-------------|-------|--------|
| Vector memory with semantic search | Long-term context, RAG | Medium |
| Local model support (Ollama, llama.cpp) | Privacy, offline, cost | High |
| Mobile companion app | Remote control | High |
| Multi-user voice profiles | Personalization | Medium |
| Gesture/camera input | Multimodal | High |
| Proactive suggestions | Anticipatory UX | Medium |
| Cross-device sync | Continuity | High |

---

## 4. Detailed Requirements (v2.0 Target)

### 4.1 Core Requirement: Zero-Memory Background Mode

**FR-001: System Service Architecture**
- Barq runs as a Windows Service (or minimized tray process) when idle
- Memory footprint: **< 50 MB RAM** when sleeping (vs current ~400 MB)
- No Electron/Next.js processes running until wake
- Python backend only: wake detector + minimal event loop
- On wake: spawn UI processes on-demand (< 2s cold start)

**FR-002: On-Demand UI Spawning**
- Wake word → spawn Electron + Next.js dev/prod server
- UI appears in < 2 seconds from wake detection
- Graceful shutdown of UI on sleep (configurable timeout)
- State preserved via WebSocket reconnection

**FR-003: Startup Modes**
| Mode | Description | Use Case |
|------|-------------|----------|
| `service` | Windows Service, no UI until wake | Default, production |
| `tray` | Minimized Electron, instant UI | Development, debugging |
| `headless` | Python only, no UI ever | Server/remote, voice-only |

### 4.2 Core Requirement: Perfect Wake Word Detection

**FR-004: Hybrid Wake Detection Pipeline**
```
Audio Input
    │
    ▼
┌─────────────────────┐
│  VAD (Silero/RNNoise)│  ← 10ms frames, CPU-efficient
└─────────┬───────────┘
          │ Voice detected
          ▼
┌─────────────────────┐     ┌─────────────────────┐
│  Porcupine (Primary) │────►│  Whisper (Confirm)  │  ← Optional 2nd pass
│  < 50ms latency      │     │  High accuracy      │
└─────────────────────┘     └─────────────────────┘
          │                          │
          └───────────┬──────────────┘
                      ▼
           ┌─────────────────┐
           │  Confidence     │
           │  Scoring        │
           └────────┬────────┘
                    ▼
         ┌──────────┴──────────┐
         ▼                     ▼
      WAKE                IGNORE
```

**FR-005: Wake Word Configuration**
- Custom "Barq" Porcupine model (train via Picovoice Console)
- Configurable sensitivity (0.0–1.0)
- Multi-word support: "Barq", "Hey Barq", "Barq wake up"
- False positive rejection via Whisper confirmation
- Per-user voice enrollment (optional)

**FR-006: Audio Pipeline Optimization**
- 16kHz mono, 16-bit PCM (Porcupine native)
- Ring buffer for continuous streaming
- Noise suppression (RNNoise) before VAD
- Automatic gain control
- Microphone selection + level monitoring

### 4.3 Core Requirement: Security Hardening

**FR-007: Backend Authentication**
- WebSocket auth via HMAC-signed tokens
- Token generated at startup, stored in `.barq_auth`
- Electron reads token, includes in WebSocket handshake
- Reject unauthenticated connections
- Rate limiting on auth endpoint

**FR-008: Code Execution Sandbox**
- Open Interpreter runs in isolated subprocess
- Allowlist of permitted modules/operations
- Resource limits: CPU time, memory, disk, network
- File system access restricted to `barq_workspace/`
- Audit log of all executed commands

**FR-009: Input Validation & Sanitization**
- All LLM outputs validated against JSON schema
- Command injection prevention in `screen_context.py`
- Path traversal protection
- URL validation for browser actions

### 4.4 Core Requirement: Reliability & Observability

**FR-010: Health Monitoring**
- `/health` endpoint (liveness + readiness)
- Component-level health: mic, speaker, LLM, vision, memory
- Automatic restart with state recovery
- Structured logging (JSON) + metrics export (Prometheus)

**FR-011: Graceful Degradation**
- Offline mode: local STT (Whisper.cpp), local LLM (Ollama)
- TTS fallback: Windows SAPI / pyttsx3
- Vision fallback: OCR (Tesseract) + local LLM
- Feature flags for each cloud dependency

**FR-012: Update Mechanism**
- Auto-update Electron app (electron-updater)
- Python backend version check + pip upgrade
- Rolling updates without downtime

### 4.5 Enhanced Capabilities

**FR-013: Vector Memory (RAG)**
- Embeddings via sentence-transformers (local) or Groq
- Store: conversations, facts, documents, code snippets
- Semantic search for context retrieval
- Automatic fact extraction from conversations

**FR-014: Plugin System**
```
plugins/
├── __init__.py
├── base.py          # Plugin interface
├── registry.py      # Discovery + loading
├── builtin/
│   ├── browser.py
│   ├── filesystem.py
│   ├── code_exec.py
│   └── system.py
└── user/
    └── custom.py    # User plugins
```
- Hook points: pre_command, post_command, on_wake, on_sleep, on_error
- Sandboxed execution (subprocess + allowlist)
- Hot reload without restart

**FR-015: Multi-Monitor & Window Management**
- Detect all monitors, DPI scaling
- UI positioning per monitor
- Window management: move, resize, snap, focus
- Per-monitor wake word sensitivity

---

## 5. Technical Implementation Plan

### Phase 1: Foundation (Weeks 1-2) — *Current Sprint*

| Task | Owner | Deliverable |
|------|-------|-------------|
| Create Windows Service installer | Backend | `install_service.ps1`, `barq_service.py` |
| Refactor backend for service mode | Backend | `service_main.py` entry point |
| Implement VAD + Porcupine pipeline | Backend | `wakeword_v2.py` |
| Add authentication (HMAC) | Backend | `auth.py`, updated `server.py` |
| Write unit tests for core modules | QA | `tests/` with pytest |

### Phase 2: Wake Word Excellence (Weeks 3-4)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Train custom "Barq" Porcupine model | ML | `barq_wakeword.ppn` |
| Implement Silero VAD integration | Backend | `vad.py` |
| Add Whisper confirmation pass | Backend | Updated `wakeword_v2.py` |
| Microphone calibration UI | Frontend | Settings panel in overlay |
| Benchmark: < 200ms wake latency | QA | Test report |

### Phase 3: Security & Sandboxing (Weeks 5-6)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Sandbox Open Interpreter | Backend | `sandbox.py` with nsjail/firejail |
| Implement command allowlist | Backend | `policy.yaml` |
| Audit logging | Backend | `audit.log` structured |
| Penetration testing | Security | Report + fixes |

### Phase 4: Reliability & Memory (Weeks 7-8)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Vector memory (ChromaDB/local) | Backend | `memory_v2.py` |
| Health endpoints + metrics | Backend | `/health`, `/metrics` |
| Graceful degradation modes | Backend | `offline_mode.py` |
| Integration test suite | QA | `tests/integration/` |

### Phase 5: Extensibility & Polish (Weeks 9-10)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Plugin system framework | Backend | `plugins/` package |
| Built-in plugins migration | Backend | Move current features to plugins |
| Multi-monitor support | Frontend/Backend | `display_manager.py` |
| Settings UI | Frontend | React settings panel |
| Documentation + release | Docs | `docs/`, CHANGELOG |

---

## 6. Acceptance Criteria (Definition of Done)

### 6.1 Zero-Memory Background Mode
- [ ] `barq_service.exe` runs as Windows Service
- [ ] RAM < 50 MB when idle (measured via Task Manager)
- [ ] Wake → UI visible in < 2s (cold) / < 500ms (warm)
- [ ] Sleep → UI processes terminated, memory released
- [ ] Survives sleep/hibernate/resume cycles

### 6.2 Perfect Wake Word
- [ ] Porcupine primary: < 100ms detection latency
- [ ] False positive rate < 1 per hour in quiet environment
- [ ] False negative rate < 5% at normal speaking volume
- [ ] Works with background noise (fan, music, typing)
- [ ] Custom "Barq" model trained and deployed

### 6.3 Security
- [ ] Unauthenticated WebSocket connection rejected
- [ ] Open Interpreter cannot access files outside workspace
- [ ] No command injection possible via voice input
- [ ] Audit log captures all system actions

### 6.4 Reliability
- [ ] 99.9% uptime over 7-day stress test
- [ ] Automatic recovery from all simulated failure modes
- [ ] Structured logs queryable via `journalctl` / Event Viewer
- [ ] Zero data loss on crash (memory persisted)

---

## 7. Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Porcupine model training fails | Medium | High | Fallback: use built-in "jarvis" + Whisper confirm |
| Windows Service permissions issues | Medium | High | Test on clean VM, document admin requirements |
| Electron cold start > 2s | Medium | Medium | Pre-warm Next.js build, use `electron-builder` |
| Groq API rate limits / downtime | Low | High | Implement local fallback (Ollama) |
| Microphone access denied by OS | Low | High | Request permission at install, guide user |
| Memory leaks in long-running service | Medium | High | Periodic restart, memory profiling |

---

## 8. Success Metrics (KPIs)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Idle memory usage | < 50 MB | Process Explorer |
| Wake latency (Porcupine) | < 100 ms | Instrumented logging |
| Wake latency (full pipeline) | < 200 ms | End-to-end timestamp |
| False positive rate | < 1/hr | 24h ambient recording |
| False negative rate | < 5% | Scripted test phrases |
| Command success rate | > 95% | Integration test suite |
| Mean time to recovery | < 5 s | Chaos engineering |
| User satisfaction (NPS) | > 50 | Quarterly survey |

---

## 9. Appendix: File Inventory

### Backend (Python)
```
barq-ai-assistant/
├── main.py              # CLI entry (legacy)
├── server.py            # FastAPI + WebSocket + Engine
├── brain.py             # LLM reasoning + memory
├── listener.py          # STT (Whisper)
├── speaker.py           # TTS (ElevenLabs)
├── wakeword.py          # Wake detection (v1)
├── wakeword_v2.py       # Wake detection (v2 - TODO)
├── vad.py               # Voice Activity Detection (TODO)
├── screen_context.py    # Window/tab awareness
├── vision.py            # Screen vision
├── config.py            # Configuration
├── barqlog.py           # Logging
├── auth.py              # HMAC auth (TODO)
├── sandbox.py           # Code execution sandbox (TODO)
├── memory_v2.py         # Vector memory (TODO)
├── plugins/             # Plugin system (TODO)
│   ├── base.py
│   ├── registry.py
│   └── builtin/
├── service_main.py      # Windows Service entry (TODO)
├── health.py            # Health checks (TODO)
├── offline_mode.py      # Local fallbacks (TODO)
└── tests/               # Test suite (TODO)
```

### Frontend (Next.js/React)
```
barq_ui/
├── src/
│   ├── app/
│   │   ├── page.tsx          # Main overlay
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── JarvisOrb.tsx     # 3D orb
│   │   ├── SettingsPanel.tsx # TODO
│   │   └── MicVisualizer.tsx # TODO
│   └── hooks/
│       ├── useWebSocket.ts
│       └── useAudio.ts       # TODO
└── package.json
```

### Desktop (Electron)
```
desktop/
├── main.js              # Electron main process
├── preload.js           # Preload script
├── package.json
├── install-startup.ps1  # Auto-start installer
├── install-service.ps1  # Windows Service installer (TODO)
├── barq_service.py      # Service wrapper (TODO)
└── resources/
    └── barq.ico
```

### Data & Config
```
barq_data/
├── memory.json          # Conversation history
├── barq.log             # Application logs
├── barq_wakeword.ppn    # Custom Porcupine model (TODO)
├── audit.log            # Security audit (TODO)
└── vector_db/           # ChromaDB (TODO)
```

---

## 10. Immediate Next Steps (This Session)

1. **Create Windows Service installer** (`install-service.ps1` + `barq_service.py`)
2. **Refactor backend** to support `service` mode (headless, no UI processes)
3. **Implement VAD + Porcupine v2** wake pipeline in `wakeword_v2.py`
4. **Add HMAC authentication** to WebSocket in `server.py` + Electron
5. **Write first unit tests** for `brain.py`, `config.py`, `screen_context.py`
6. **Commit all changes** with semantic messages

---

*This PRD is a living document. Update as implementation progresses.*