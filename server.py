import asyncio
import json
import os
import re
import subprocess
import threading

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import GROQ_API_KEY, SLEEP_WORDS
from listener import listen_for_command
from speaker import speak
from brain import think
from wakeword import wait_for_wake
from screen_context import (
    get_light_context,
    format_situation,
    close_browser_tab,
    open_browser_tab,
    open_app,
    screenshot_png_bytes,
)
from vision import describe_screen

# --- Open Interpreter (for complex system/code tasks) ---
from interpreter import interpreter

os.environ["GROQ_API_KEY"] = GROQ_API_KEY
interpreter.llm.api_key = GROQ_API_KEY
interpreter.llm.model = "openai/llama-3.3-70b-versatile"
interpreter.llm.api_base = "https://api.groq.com/openai/v1"
interpreter.auto_run = True
interpreter.system_message += "\nYou are Barq, Ibrahim's personal AI assistant."


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
        try:
            await speak("Systems initialized. I am here, Ibrahim.")
        except Exception as e:
            log.error("Init speech error: %s", e)

        is_awake = False

        while True:
            # ---------------- STANDBY / WAKE WORD ----------------
            if not is_awake:
                await manager.broadcast({
                    "type": "state", "aiState": "sleeping",
                    "transcript": "Standby - listening for the wake word.",
                })
                try:
                    woken = await asyncio.to_thread(wait_for_wake)
                except Exception as e:
                    log.error("Wake error: %s", e, exc_info=True)
                    woken = False
                if woken:
                    is_awake = True
                    log.info("Wake word detected.")
                    await manager.broadcast({"type": "wake"})
                    await manager.broadcast({
                        "type": "state", "aiState": "listening",
                        "transcript": "I am online.",
                    })
                    try:
                        await speak("I am awake and listening.")
                    except Exception as e:
                        log.error("Voice error: %s", e)
                continue

            # ---------------- ACTIVE SESSION ----------------
            await manager.broadcast({
                "type": "state", "aiState": "listening",
                "transcript": "Listening...",
            })
            command = await asyncio.to_thread(listen_for_command)
            if not command:
                continue
            log.info("Command: %r", command)
            await manager.broadcast({"type": "user", "text": command})

            if any(w in command for w in SLEEP_WORDS):
                is_awake = False
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

            fast = fast_route_execution(command)
            if fast:
                await manager.broadcast({"type": "ai", "text": fast})
                try:
                    await speak(fast)
                except Exception:
                    pass
                continue

            # Cheap screen context -> brain
            try:
                ctx = get_light_context()
                situation = format_situation(ctx)
            except Exception as e:
                print("[Screen ctx error]", e)
                ctx, situation = {}, ""

            await manager.broadcast({
                "type": "state", "aiState": "thinking",
                "transcript": "Thinking...",
            })
            result = await asyncio.to_thread(think, command, situation)
            reply = result["speech"]

            await manager.broadcast({"type": "ai", "text": reply})
            try:
                await speak(reply)
            except Exception:
                pass

            intent = result.get("intent", "conversation")
            action = result.get("action", "")
            subject = result.get("subject", "")
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
                    interpreter.chat(command)
                    stop = "Done. Task executed."
                except Exception as e:
                    print("[Interpreter error]", e)
                    stop = "I hit an issue while executing that."

            # ===== SPOKEN SITREP =====
            if stop:
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
            import time as _time

            _time.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=run_barq_engine, daemon=True)
    thread.start()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
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