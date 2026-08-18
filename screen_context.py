"""
Screen / window / browser-tab awareness.

Barq can know the focused window, list open browser tab titles, and close a
specific tab by keyword - targeting the window whose title contains the tab,
so it never accidentally affects Barq's own UI.
"""
import ctypes
import io
import subprocess

import psutil
import pyautogui

BROWSER_APPS = ("chrome", "msedge", "firefox", "brave", "vivaldi", "opera")

user32 = ctypes.windll.user32


def _ext_process_name(pid):
    """Return the lowercased process image name (without .exe)."""
    try:
        p = psutil.Process(pid)
        return (p.name() or "").lower().replace(".exe", "")
    except Exception:
        return ""


def _window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _all_windows():
    results = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_title(hwnd)
        if not title:
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append({"hwnd": hwnd, "title": title, "pid": pid.value})
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return results


def active_window():
    """Return the focused window's title and owning application name."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"title": "", "app": ""}
    title = _window_title(hwnd)
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {"hwnd": hwnd, "title": title, "app": _ext_process_name(pid.value)}


def browser_windows():
    """Visible browser window titles (Chrome/Edge show the active tab title)."""
    out = []
    for w in _all_windows():
        app = _ext_process_name(w["pid"])
        if app in BROWSER_APPS:
            out.append({"hwnd": w["hwnd"], "title": w["title"], "app": app})
    return out


def get_light_context():
    act = active_window()
    tabs = [w["title"] for w in browser_windows()]
    return {
        "foreground_app": act["app"],
        "active_tab_or_window": act["title"],
        "open_browser_tabs": tabs,
    }


def format_situation(context) -> str:
    lines = [f"Foreground app: {context.get('foreground_app') or 'unknown'}"]
    lines.append(f"Window/tab title: {context.get('active_tab_or_window') or 'unknown'}")
    tabs = context.get("open_browser_tabs") or []
    if tabs:
        lines.append("Open tabs: " + ", ".join(tabs[:8]))
    else:
        lines.append("No browser tabs detected.")
    return "\n".join(lines)


def bring_to_front(hwnd):
    user32.SetForegroundWindow(hwnd)
    pyautogui.sleep(0.15)


def close_browser_tab(keyword: str) -> dict:
    target = None
    kw = (keyword or "").lower()
    for w in browser_windows():
        if kw in w["title"].lower():
            target = w
            break
    if not target:
        return {"ok": False, "message": f"No browser tab matching '{keyword}'."}
    bring_to_front(target["hwnd"])
    pyautogui.hotkey("ctrl", "w")
    pyautogui.sleep(0.2)
    return {"ok": True, "message": f"Closed the '{target['title']}' tab."}


def open_browser_tab(url: str) -> dict:
    subprocess.Popen(["cmd", "/c", "start", "", url])
    return {"ok": True, "message": f"Opened {url}."}


_APP_SHORTCUTS = {
    "calculator": "calc",
    "calc": "calc",
    "notepad": "notepad",
    "paint": "mspaint",
    "file explorer": "explorer",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
}


def open_app(app_name: str) -> dict:
    target = _APP_SHORTCUTS.get((app_name or "").lower())
    if not target:
        return {"ok": False, "message": f"No shortcut for {app_name} yet."}
    if target.startswith("ms-"):
        subprocess.Popen(["cmd", "/c", "start", "", target])
    else:
        subprocess.Popen(target)
    return {"ok": True, "message": f"Opening {app_name}."}


def screenshot_png_bytes(max_width=1100) -> bytes:
    """Capture the screen and return compressed PNG bytes (for vision)."""
    img = pyautogui.screenshot()
    w, h = img.size
    if w > max_width:
        ratio = max_width / float(w)
        img = img.resize((max_width, int(h * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()