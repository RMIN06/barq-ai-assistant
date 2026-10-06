"""
Barq Windows Service - Zero-memory background mode.
Runs only the wake detector + minimal engine. Spawns UI on demand.
"""
import sys
import os
import asyncio
import threading
import time
import signal
import atexit
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from wakeword_v2 import wait_for_wake_v2
from listener import listen_for_command
from speaker import speak
from brain import think, record_result
from screen_context import (
    get_light_context,
    format_situation,
    close_browser_tab,
    open_browser_tab,
    open_app,
    screenshot_png_bytes,
)
from vision import describe_screen
from barqlog import get_logger
from health import record_wake_detection, record_command, record_error
from voice_state import is_sleep_command, is_non_request
from spotify_media import requested_spotify_query, play_spotify_query

import subprocess
import json

log = get_logger("service")

UI_PROCESS = None
UI_LOCK = threading.Lock()
AUTH_TOKEN = None
ENGINE_RUNNING = False


def generate_auth_token() -> str:
    import secrets
    return secrets.token_urlsafe(32)


def write_auth_token(token: str):
    token_file = BASE_DIR / "barq_data" / ".barq_auth"
    token_file.write_text(token)
    os.chmod(token_file, 0o600)


def read_auth_token() -> str | None:
    token_file = BASE_DIR / "barq_data" / ".barq_auth"
    if token_file.exists():
        return token_file.read_text().strip()
    return None


def spawn_ui():
    global UI_PROCESS, AUTH_TOKEN
    with UI_LOCK:
        if UI_PROCESS and UI_PROCESS.poll() is None:
            log.info("UI already running")
            return True

        log.info("Spawning UI processes...")
        AUTH_TOKEN = generate_auth_token()
        write_auth_token(AUTH_TOKEN)
        log.info(f"Auth token generated: {AUTH_TOKEN[:8]}...")

        env = os.environ.copy()
        env["BARQ_AUTH_TOKEN"] = AUTH_TOKEN
        env["BARQ_SERVICE_MODE"] = "1"

        venv_py = BASE_DIR / "venv" / "Scripts" / "python.exe"
        ui_dir = BASE_DIR / "barq_ui"

        try:
            UI_PROCESS = subprocess.Popen(
                [str(venv_py), "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8080"],
                cwd=BASE_DIR,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            log.info(f"Backend started (PID: {UI_PROCESS.pid})")

            npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
            next_proc = subprocess.Popen(
                [npm_cmd, "run", "start"],
                cwd=ui_dir,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            log.info(f"Next.js started (PID: {next_proc.pid})")

            time.sleep(2)
            return True
        except Exception as e:
            log.error(f"Failed to spawn UI: {e}")
            return False


def kill_ui():
    global UI_PROCESS
    with UI_LOCK:
        if UI_PROCESS and UI_PROCESS.poll() is None:
            log.info("Terminating UI processes...")
            try:
                UI_PROCESS.terminate()
                UI_PROCESS.wait(timeout=5)
            except subprocess.TimeoutExpired:
                UI_PROCESS.kill()
            except Exception as e:
                log.error(f"Error killing UI: {e}")
            UI_PROCESS = None

async def service_engine_loop():
    global ENGINE_RUNNING
    ENGINE_RUNNING = True
    print(">>> service_engine_loop() started")
    log.info("=== SERVICE ENGINE STARTED - ZERO MEMORY MODE ACTIVE ===")

    is_awake = False
    last_command_at = 0.0
    last_command_text = ""
    ui_spawned = False

    # Check microphone availability at startup
    from health import check_microphone
    mic_check = check_microphone()
    if mic_check["status"] in ("unavailable", "unhealthy"):
        log.warning(f"Microphone not available: {mic_check['message']}. Wake detection disabled.")
        log.info("Use WebSocket/API to wake manually.")
        wake_enabled = False
    else:
        log.info(f"Microphone ready: {mic_check['message']}")
        wake_enabled = True

    print(">>> Entering main engine loop...")
    log.info("Entering main engine loop...")
    while ENGINE_RUNNING:
        log.debug(f"Loop iteration - is_awake={is_awake}, ui_spawned={ui_spawned}")

        if not is_awake:
            if not wake_enabled:
                log.info("Wake detection disabled - waiting for manual wake signal...")
                await asyncio.sleep(5)
                continue

            log.info("Standby - waiting for wake word...")
            try:
                woken = await asyncio.to_thread(wait_for_wake_v2)
            except Exception as e:
                log.error(f"Wake detection error: {e}")
                record_error("wake_detection")
                woken = False

            if woken:
                log.info("*** WAKE WORD DETECTED! ***")
                record_wake_detection()
                is_awake = True
                last_command_at = time.monotonic()

                if not ui_spawned:
                    log.info("Spawning UI...")
                    spawn_ui()
                    ui_spawned = True
                    await asyncio.sleep(2)

            else:
                # Wake detection failed - wait before retrying to prevent tight loop
                await asyncio.sleep(2)
            continue

        log.debug("Active session - listening for command...")
        command = await asyncio.to_thread(listen_for_command)
        if not command:
            continue

        log.info(f"Command: {command}")

        from config import SLEEP_WORDS
        if any(w in command for w in SLEEP_WORDS):
            log.info("Sleep command received")
            is_awake = False
            try:
                await speak("Going dark. Call me if you need me.")
            except Exception:
                pass
            await asyncio.sleep(1)
            kill_ui()
            ui_spawned = False
            continue

        try:
            ctx = get_light_context()
            situation = format_situation(ctx)
        except Exception as e:
            log.error(f"Screen context error: {e}")
            ctx, situation = {}, ""

        result = await asyncio.to_thread(think, command, situation)
        reply = result["speech"]
        log.info(f"Barq: {reply}")

        try:
            await speak(reply)
        except Exception as e:
            log.error(f"Speech error: {e}")

        intent = result.get("intent", "conversation")
        action = result.get("action", "")
        subject = result.get("subject", "")
        record_command(intent)
        stop = None

        if intent == "browser":
            try:
                if action == "close" and subject:
                    res = close_browser_tab(subject)
                    stop = res["message"]
                elif action == "open" and subject:
                    res = open_browser_tab("https://www.google.com/search?q=" + subject)
                    stop = res["message"]
                else:
                    tabs = ctx.get("open_browser_tabs", []) or []
                    stop = ("Tabs: " + " | ".join(tabs[:8])) if tabs else "No browser tabs open."
            except Exception as e:
                record_error("browser_action")
                stop = f"Browser error: {e}"

        elif intent == "screen":
            try:
                png = screenshot_png_bytes()
                item = await asyncio.to_thread(describe_screen, png)
                stop = item
            except Exception as e:
                record_error("screen_vision")
                stop = f"Screen read error: {e}"

        elif intent == "app" and action == "open":
            try:
                res = open_app(subject)
                stop = res["message"]
            except Exception as e:
                record_error("app_launch")
                stop = f"App open error: {e}"

        elif intent == "system":
            try:
                os.environ["GROQ_API_KEY"] = GROQ_API_KEY
                from interpreter import interpreter
                interpreter.llm.api_key = GROQ_API_KEY
                interpreter.llm.model = "openai/llama-3.3-70b-versatile"
                interpreter.llm.api_base = "https://api.groq.com/openai/v1"
                interpreter.auto_run = True
                interpreter.chat(command)
                stop = "Done. Task executed."
            except Exception as e:
                log.error(f"Interpreter error: {e}")
                record_error("interpreter")
                stop = "Execution failed."

        if stop:
            log.info(f"Sitrep: {stop}")
            try:
                await speak(stop)
            except Exception:
                pass

        await asyncio.sleep(0.2)

    log.info("Service engine stopped")


def run_service():
    try:
        asyncio.run(service_engine_loop())
    except KeyboardInterrupt:
        log.info("Service interrupted")
    except Exception as e:
        log.error(f"Service crashed: {e}")
        record_error("service_crash")
    finally:
        ENGINE_RUNNING = False
        kill_ui()


if __name__ == "__main__":
    run_service()