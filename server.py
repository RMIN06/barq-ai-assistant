import asyncio
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi import Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from listener import listen_for_command
from speaker import speak
from brain import think, record_result
from wakeword_v2 import wait_for_wake_v2
from screen_context import (
    get_light_context,
    format_situation,
    close_browser_tab,
    open_browser_tab,
    open_app,
    screenshot_png_bytes,
    create_folder,
    delete_folder,
    preview_delete,
    list_folder,
    create_file,
    read_file,
    delete_file,
)
from vision import describe_screen
from auth import authenticate_websocket, get_auth_token, verify_token, generate_token
from health import router as health_router, record_wake_detection, record_command, record_error
import psutil
from action_safety import authorized_file_action
from voice_state import is_sleep_command, is_non_request
from weather import get_weather
from spotify_media import requested_spotify_query, play_spotify_query

SERVICE_MODE = os.environ.get("BARQ_SERVICE_MODE", "0") == "1"


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send(self, websocket, message: dict):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            pass

    async def broadcast(self, message: dict):
        for conn in self.active_connections:
            await self.send(conn, message)


manager = ConnectionManager()
manual_wake_event = threading.Event()
manual_sleep_event = threading.Event()


def fast_route_execution(command: str) -> str | None:
    cmd = command.lower().strip()
    if "open calculator" in cmd or "calc" in cmd:
        subprocess.Popen("calc.exe")
        return "Opening Calculator now."
    if "open notepad" in cmd:
        subprocess.Popen("notepad.exe")
        return "Opening Notepad."
    math_match = re.search(r"(\d+\s*[\+\-\*/]\s*\d+)", cmd)
    if math_match and ("calculate" in cmd or "what is" in cmd or "compute" in cmd):
        try:
            expr = math_match.group(1)
            return f"The result of {expr} is {eval(expr)}."
        except Exception:
            pass
    return None


def run_barq_engine():
    """Background engine: sleep / wake / listen / think / act / SITREP."""
    from barqlog import get_logger

    log = get_logger("engine")

    async def loop():
        log.info("Engine loop started.")
        await manager.broadcast({
            "type": "state", "aiState": "sleeping",
            "transcript": "Sleeping. Say the wake word to activate me.",
        })
        is_awake = False
        last_command_at = 0.0
        last_command_text = ""

        while True:
            # ---------------- STANDBY / WAKE WORD ----------------
            if not is_awake:
                manual_sleep_event.clear()
                await manager.broadcast({
                    "type": "state", "aiState": "sleeping",
                    "transcript": "Standby - listening for the wake word.",
                })
                try:
                    woken = await asyncio.to_thread(wait_for_wake_v2, manual_wake_event)
                except Exception as e:
                    log.error("Wake error: %s", e, exc_info=True)
                    record_error("wake_detection")
                    woken = False
                if woken or manual_wake_event.is_set():
                    manual_wake_event.clear()
                    is_awake = True
                    last_command_at = time.monotonic()
                    log.info("Wake word detected.")
                    record_wake_detection()
                    await manager.broadcast({"type": "wake"})
                    await manager.broadcast({
                        "type": "state", "aiState": "listening",
                        "transcript": "I am online.",
                    })
                continue

            # ---------------- ACTIVE SESSION ----------------
            await manager.broadcast({
                "type": "state", "aiState": "listening",
                "transcript": "Listening...",
            })
            command = await asyncio.to_thread(listen_for_command)
            if manual_sleep_event.is_set():
                manual_sleep_event.clear()
                manual_wake_event.clear()
                is_awake = False
                await manager.broadcast({"type": "sleep"})
                continue
            if not command:
                if time.monotonic() - last_command_at > 45:
                    is_awake = False
                    await manager.broadcast({"type": "sleep"})
                continue
            if is_non_request(command):
                continue
            if command.casefold().strip() == last_command_text and time.monotonic() - last_command_at < 15:
                continue
            last_command_text = command.casefold().strip()
            last_command_at = time.monotonic()
            log.info("Command: %r", command)
            await manager.broadcast({"type": "user", "text": command})

            if is_sleep_command(command):
                is_awake = False
                manual_wake_event.clear()
                await manager.broadcast({"type": "sleep"})
                await manager.broadcast({
                    "type": "state", "aiState": "sleeping",
                    "transcript": "Going dark.",
                })
                try:
                    await speak("Going dark. Call me if you need me.")
                except Exception:
                    pass
                continue

            spotify_query = requested_spotify_query(command)
            if spotify_query:
                outcome = await asyncio.to_thread(play_spotify_query, spotify_query)
                stop = outcome["message"]
                await asyncio.to_thread(record_result, command, stop)
                await manager.broadcast({"type": "ai", "text": stop})
                await speak(stop)
                continue

            fast = fast_route_execution(command)
            if fast:
                await manager.broadcast({"type": "ai", "text": fast})
                try:
                    await speak(fast)
                except Exception:
                    pass
                record_command("fast_route")
                continue

            # Cheap screen context -> brain
            try:
                ctx = get_light_context()
                situation = format_situation(ctx)
            except Exception as e:
                print("[Screen ctx error]", e)
                record_error("screen_context")
                ctx, situation = {}, ""

            await manager.broadcast({
                "type": "state", "aiState": "thinking",
                "transcript": "Thinking...",
            })
            result = await asyncio.to_thread(think, command, situation)
            reply = result["speech"]

            intent = result.get("intent", "conversation")
            action = result.get("action", "")
            subject = result.get("subject", "")
            record_command(intent)
            stop = None
            if intent == "conversation":
                stop = reply

            if intent == "browser":
                try:
                    if action == "close" and subject:
                        res = close_browser_tab(subject)
                        stop = res["message"]
                    elif action == "open" and subject:
                        from urllib.parse import quote_plus
                        res = open_browser_tab("https://www.google.com/search?q=" + quote_plus(subject))
                        stop = res["message"]
                    else:
                        tabs = ctx.get("open_browser_tabs", []) or []
                        stop = ("You have these tabs open: " + " | ".join(tabs[:8])) if tabs \
                            else "I don't see any browser tabs open right now."
                except Exception as e:
                    stop = f"I could not manage that browser tab ({e})."

            elif intent == "screen":
                await manager.broadcast({
                    "type": "state", "aiState": "thinking",
                    "transcript": "Looking at your screen...",
                })
                try:
                    png = screenshot_png_bytes()
                    item = await asyncio.to_thread(describe_screen, png)
                    stop = item
                except Exception as e:
                    stop = f"I could not read your screen ({e})."

            elif intent == "app" and action == "open":
                try:
                    res = open_app(subject)
                    stop = res["message"]
                except Exception as e:
                    stop = f"I could not open that ({e})."

            elif intent == "system":
                await manager.broadcast({
                    "type": "state", "aiState": "working",
                    "transcript": "Executing on your machine...",
                })
                try:
                    stop = "I can help plan this task, but automatic code execution is disabled."
                except Exception as e:
                    log.error("[Interpreter error] %s", e)
                    record_error("interpreter")
                    stop = "I hit an issue while executing that."

            elif intent == "filesystem":
                await manager.broadcast({
                    "type": "state", "aiState": "working",
                    "transcript": "Working on filesystem...",
                })
                try:
                    if not authorized_file_action(command, action, subject):
                        res = {"ok": False, "message": "I need the exact file or folder name in your request before acting."}
                    elif action == "create" and subject:
                        # Check if it's a folder or file (simple heuristic: if ends with / or no extension)
                        if subject.endswith('/') or '.' not in Path(subject).name:
                            res = create_folder(subject)
                        else:
                            res = create_file(subject)
                    elif action == "delete" and subject:
                        # Safety: preview first, then delete
                        preview = preview_delete(subject)
                        if not preview.get("ok"):
                            res = preview
                        else:
                            res = delete_folder(subject) if preview["item_count"] == 0 else {
                                "ok": False, "message": f"{subject} contains files. Review its contents before deleting it."
                            }
                    elif action == "preview" and subject:
                        res = preview_delete(subject)
                    elif action == "list" and subject:
                        res = list_folder(subject)
                    elif action == "read" and subject:
                        res = read_file(subject)
                    elif action == "write" and subject:
                        # For write, we need content - extract from command or use empty
                        res = create_file(subject, "")
                    else:
                        res = {"ok": False, "message": f"Unknown filesystem action: {action}"}
                    stop = res.get("message") or str(res)
                except Exception as e:
                    log.error("[Filesystem error] %s", e)
                    record_error("filesystem")
                    stop = "I hit an issue with the filesystem."

            # ===== SPOKEN SITREP =====
            if stop:
                if intent != "conversation":
                    await asyncio.to_thread(record_result, command, stop)
                await manager.broadcast({"type": "ai", "text": stop,
                                         "sitrep": True})
                try:
                    await speak(stop)
                except Exception:
                    pass
            await asyncio.sleep(0.2)

    # ---- run the loop, restart it if it ever crashes ----
    while True:
        try:
            asyncio.run(loop())
        except Exception as e:
            log.error("Engine crashed, restarting in 3s: %s", e, exc_info=True)
            record_error("engine_crash")
            import time as _time

            _time.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not get_auth_token():
        generate_token()
    if not SERVICE_MODE:
        thread = threading.Thread(target=run_barq_engine, daemon=True)
        thread.start()
    else:
        from barqlog import get_logger
        log = get_logger("server")
        log.info("Running in SERVICE MODE - engine runs in barq_service.py")
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    if not await authenticate_websocket(websocket):
        return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import logging

    import uvicorn

    logging.getLogger("open_interpreter").setLevel(logging.ERROR)
    uvicorn.run(app, host="127.0.0.1", port=8000)