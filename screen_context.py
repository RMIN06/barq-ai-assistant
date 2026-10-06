"""
Screen / window / browser-tab awareness.

Barq can know the focused window, list open browser tab titles, and close a
specific tab by keyword - targeting the window whose title contains the tab,
so it never accidentally affects Barq's own UI.
"""
import ctypes
import io
import subprocess
import json
import os
import shutil
from pathlib import Path

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
        "desktop_path": str(Path.home() / "Desktop"),
    }


def format_situation(context) -> str:
    lines = [f"Foreground app: {context.get('foreground_app') or 'unknown'}"]
    lines.append(f"Window/tab title: {context.get('active_tab_or_window') or 'unknown'}")
    lines.append(f"Desktop path: {context.get('desktop_path') or 'unknown'}")
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
    name = (app_name or "").strip()
    if not name or any(c in name for c in "\\/:*?\"<>|"):
        return {"ok": False, "message": "Please name one application to open."}
    target = _APP_SHORTCUTS.get(name.casefold())
    if target and target.startswith("ms-"):
        subprocess.Popen(["cmd", "/c", "start", "", target])
    elif target:
        subprocess.Popen(target)
    else:
        # Windows Store apps have an AppUserModelID rather than a PATH shortcut.
        script = "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
        try:
            raw = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8, check=True).stdout
            apps = json.loads(raw)
            if isinstance(apps, dict):
                apps = [apps]
            matches = [item for item in apps if item.get("Name", "").casefold() == name.casefold()]
            if not matches:
                matches = [item for item in apps if name.casefold() in item.get("Name", "").casefold()]
            if matches:
                subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + matches[0]["AppID"]])
                return {"ok": True, "message": f"Opening {matches[0]['Name']}."}
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        executable = shutil.which(name)
        if not executable:
            return {"ok": False, "message": f"I could not find {name} among installed apps or on PATH."}
        subprocess.Popen([executable])
    return {"ok": True, "message": f"Opening {name}."}


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


# --- File System Operations ---

def _resolve_path(path_str: str) -> Path:
    """Resolve a path string, expanding ~ and environment variables."""
    path = Path(path_str).expanduser()
    # If relative, make it relative to user's home
    if not path.is_absolute():
        path = Path.home() / path
    return path.resolve()


def create_folder(path_str: str) -> dict:
    """Create a folder at the specified path."""
    try:
        path = _resolve_path(path_str)
        path.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "message": f"Created folder: {path}"}
    except Exception as e:
        return {"ok": False, "message": f"Failed to create folder: {e}"}


def delete_folder(path_str: str) -> dict:
    """Delete a folder at the specified path. Requires exact path match."""
    try:
        path = _resolve_path(path_str)
        if path.exists() and path.is_dir() and not path.is_symlink():
            if any(path.iterdir()):
                return {"ok": False, "message": f"Folder is not empty: {path}. Review the contents first."}
            path.rmdir()
            return {"ok": True, "message": f"Deleted folder: {path}"}
        return {"ok": False, "message": f"Folder not found or not a directory: {path}"}
    except Exception as e:
        return {"ok": False, "message": f"Failed to delete folder: {e}"}


def preview_delete(path_str: str) -> dict:
    """Preview what would be deleted without actually deleting."""
    try:
        path = _resolve_path(path_str)
        if path.exists() and path.is_dir():
            items = list(path.iterdir())
            return {
                "ok": True,
                "path": str(path),
                "item_count": len(items),
                "items": [{"name": i.name, "type": "folder" if i.is_dir() else "file"} for i in items[:20]],
                "warning": "This is a preview. Use delete_folder to actually delete."
            }
        return {"ok": False, "message": f"Folder not found or not a directory: {path}"}
    except Exception as e:
        return {"ok": False, "message": f"Failed to preview: {e}"}


def list_folder(path_str: str) -> dict:
    """List contents of a folder."""
    try:
        path = _resolve_path(path_str)
        if not path.exists():
            return {"ok": False, "message": f"Path not found: {path}"}
        items = []
        for item in path.iterdir():
            items.append({
                "name": item.name,
                "type": "folder" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            })
        return {"ok": True, "items": items, "path": str(path)}
    except Exception as e:
        return {"ok": False, "message": f"Failed to list folder: {e}"}


def create_file(path_str: str, content: str = "") -> dict:
    """Create a file with optional content."""
    try:
        path = _resolve_path(path_str)
        if path.exists():
            return {"ok": False, "message": f"File already exists: {path}"}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "message": f"Created file: {path}"}
    except Exception as e:
        return {"ok": False, "message": f"Failed to create file: {e}"}


def read_file(path_str: str) -> dict:
    """Read a file's content."""
    try:
        path = _resolve_path(path_str)
        if not path.exists():
            return {"ok": False, "message": f"File not found: {path}"}
        content = path.read_text(encoding="utf-8")
        return {"ok": True, "content": content, "path": str(path)}
    except Exception as e:
        return {"ok": False, "message": f"Failed to read file: {e}"}


def delete_file(path_str: str) -> dict:
    """Delete a file."""
    try:
        path = _resolve_path(path_str)
        if path.exists():
            path.unlink()
            return {"ok": True, "message": f"Deleted file: {path}"}
        return {"ok": False, "message": f"File not found: {path}"}
    except Exception as e:
        return {"ok": False, "message": f"Failed to delete file: {e}"}
