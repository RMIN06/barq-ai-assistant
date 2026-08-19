import asyncio
import logging
import os
import subprocess

from config import GROQ_API_KEY, SLEEP_WORDS, WAKE_WORDS
from listener import listen_for_command
from speaker import speak
from brain import think
from wakeword import wait_for_wake
from screen_context import format_situation, get_light_context

# --- OPEN INTERPRETER CONFIGURATION ---
os.environ["GROQ_API_KEY"] = GROQ_API_KEY
from interpreter import interpreter

interpreter.llm.api_key = GROQ_API_KEY
interpreter.llm.model = "openai/llama-3.3-70b-versatile"
interpreter.llm.api_base = "https://api.groq.com/openai/v1"
interpreter.auto_run = True
interpreter.system_message += "\nYou are Barq, Ibrahim's personal AI assistant."


async def continuous_main_loop():
    print("\n[Booting Barq Core Engine...]")
    await speak("Systems initialized.")

    is_awake = False

    while True:
        # --- STATE 1: SLEEPING / WAIT FOR WAKE WORD ---
        if not is_awake:
            print("\n[Status: Standby Mode - Waiting for wake word...]")
            if await asyncio.to_thread(wait_for_wake):
                is_awake = True
                print("\n>>> WAKE WORD DETECTED <<<")
                await speak("I am online and listening.")
            continue

        # --- STATE 2: ACTIVE SESSION ---
        print("\n[Status: Active Session - Say a command...]")
        command = await asyncio.to_thread(listen_for_command)
        if not command:
            continue

        print(f"\n[You]: {command}")

        if any(w in command for w in SLEEP_WORDS):
            await speak("Going dark. Call me if you need me.")
            is_awake = False
            print("\n[Status: Returned to Standby Mode]")
            continue

        try:
            situation = format_situation(get_light_context())
        except Exception:
            situation = ""

        response_data = think(command, situation)
        spoken_reply = response_data.get("speech", "On it.")
        print(f"[Barq]: {spoken_reply}")
        await speak(spoken_reply)

        intent = response_data.get("intent", "conversation")
        if intent == "system":
            try:
                print("[Status: Executing Task...]")
                interpreter.chat(command)
                print("[Task Complete]")
                await speak("Done. Task executed.")
            except Exception as e:
                print(f"[Execution Error]: {e}")
                await speak("I ran into an issue executing that command.")


if __name__ == "__main__":
    logging.getLogger("open_interpreter").setLevel(logging.ERROR)
    asyncio.run(continuous_main_loop())