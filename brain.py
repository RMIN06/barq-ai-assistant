import json
import os

from groq import Groq

from config import GROQ_API_KEY, LLM_MODEL, MEMORY_FILE
from memory_v2 import vector_memory, add_conversation, search_memory

client = Groq(api_key=GROQ_API_KEY)

MAX_HISTORY = 12  # number of recent turns kept in memory


# --------------------------------------------------------------------------- #
# Persistent memory
# --------------------------------------------------------------------------- #
def _default_memory():
    return {"history": [], "facts": []}


def load_memory():
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _default_memory()


def save_memory(memory):
    try:
        MEMORY_FILE.write_text(json.dumps(memory, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Memory write error]: {e}")


def add_turn(mem, role, content):
    mem["history"].append({"role": role, "content": content})
    if len(mem["history"]) > MAX_HISTORY * 2:
        mem["history"] = mem["history"][-MAX_HISTORY * 2:]


def record_result(command: str, result: str) -> None:
    """Remember only the observed result of an attempted action."""
    mem = load_memory()
    add_turn(mem, "user", command)
    add_turn(mem, "assistant", result)
    save_memory(mem)
    try:
        vector_memory.add_conversation(command, result)
    except Exception as e:
        print(f"[Vector memory save error]: {e}")


# --------------------------------------------------------------------------- #
def think(prompt: str, situation: str = "", last_speech: str = "") -> dict:
    """
    Returns {"speech": str, "intent": str, "action": str, "subject": str}.
    intent: conversation | screen | browser | app | system | web
    """
    mem = load_memory()

    # Get relevant context from vector memory
    vector_context = ""
    try:
        if vector_memory.is_available():
            recent = vector_memory.get_recent_context(3)
            relevant = vector_memory.search_conversations(prompt, 3)
            if recent:
                vector_context += "Recent conversation:\n" + "\n".join(
                    f"User: {r['metadata'].get('user_msg', '')}\nAssistant: {r['metadata'].get('assistant_msg', '')}"
                    for r in recent
                )
            if relevant:
                vector_context += "\nRelevant history:\n" + "\n".join(
                    f"Q: {r['content'].split('User: ')[1].split('Assistant: ')[0] if 'User: ' in r['content'] else ''}"
                    for r in relevant
                )
    except Exception as e:
        print(f"[Vector memory error]: {e}")
        vector_context = ""

    system = (
        "You are BARQ, a battle-hardened tactical AI operator for Ibrahim. "
        "You talk like a Call of Duty: Modern Warfare comms officer: short, sharp, "
        "confident radio bursts. Zero filler, zero corporate nonsense. "
        "Example tone: 'Copy.', 'Roger that.', 'Tabs locked.', 'Target down.', "
        "'Moving out.', 'All hostiles cleared.', 'Systems hot.', 'On my last mag' "
        "(when short/unsure). CRC flags clipped to one line. "
        "Rules: NEVER invent facts, numbers, dates, or data you do not know - "
        "when unsure say so plainly ('Source ambiguous') instead of guessing. "
        "Keep every spoken reply under ~18 words. Punchy and engaging, never generic. "
        "When asked to do something on the machine (open/close a tab, run a task, "
        "check the screen), confirm briefly you are on it, then report the result "
        "like a mission after-action report. "
        "You are given a SITREP (situation report) of the user's screen each turn - "
        "use it to sense the environment. "
        "If the request involves a browser tab or window (close 'my youtube tab', "
        "what tab am I on), set intent 'browser' and put the target in 'subject' (lowercase). "
        "If it needs screen contents, set intent to 'screen'. If it is a Windows app, set "
        "intent 'app' and the app in subject. If it needs arbitrary code/scripts, set intent "
        "to 'system'. Otherwise set intent to 'conversation'. "
        'Respond ONLY in valid JSON: {"speech": "...", "intent": "conversation|screen'
        '|browser|app|web|system", "action": "open|close|none", "subject": "..."}'
    )

    messages = [{"role": "system", "content": system}]

    # recent conversation memory
    for turn in mem["history"]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    context_block = situation.strip()
    if last_speech:
        context_block += f"\n\nYour previous reply was: \"{last_speech}\""
    user_content = prompt
    if context_block:
        user_content = f"SITUATION REPORT:\n{context_block}\n\nUSER: {prompt}"
    messages.append({"role": "user", "content": user_content})

    default = {
        "speech": "I am having trouble connecting to my logic center.",
        "intent": "conversation",
        "action": "",
        "subject": "",
    }
    try:
        completion = client.chat.completions.create(
            messages=messages,
            model=LLM_MODEL,
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        data = json.loads(completion.choices[0].message.content)
        speech = str(data.get("speech") or default["speech"]).strip()
        out = {
            "speech": speech,
            "intent": data.get("intent") or "conversation",
            "action": data.get("action") or "",
            "subject": str(data.get("subject") or "").lower(),
        }
        add_turn(mem, "user", prompt)
        add_turn(mem, "assistant", out["speech"])
        save_memory(mem)
        return out
    except Exception as e:
        print(f"[Brain error]: {e}")
        return default