"""Best-effort Spotify desktop search and playback, with observed UI checks."""
import ctypes
import ctypes.wintypes
import os
import re
import time
from urllib.parse import quote

import pyautogui


def requested_spotify_query(command: str) -> str | None:
    if not re.search(r"\bspotify\b", command, re.I) or not re.search(r"\bplay\b", command, re.I):
        return None
    match = re.search(r"\bplay\s+(.+?)(?:\s+on\s+spotify)?[.!?]*$", command, re.I)
    if not match:
        return None
    query = re.sub(r"^(?:a|an|the)\s+", "", match.group(1).strip(), flags=re.I)
    query = re.sub(r"\s+on\s+spotify$", "", query, flags=re.I).strip()
    return query if query and query.casefold() != "spotify" else None


def _spotify_window():
    from screen_context import _all_windows, _ext_process_name
    for window in _all_windows():
        if _ext_process_name(window["pid"]) == "spotify":
            return window["hwnd"]
    return None


def _top_result_button(image, bounds):
    """Find Spotify's green play circle in the top result card."""
    left, top, right, bottom = bounds
    width, height = right - left, bottom - top
    crop = (int(left + width * .55), int(top + height * .15),
            int(left + width * .79), int(top + height * .41))
    points = []
    for y in range(crop[1], crop[3], 2):
        for x in range(crop[0], crop[2], 2):
            r, g, b = image.getpixel((x, y))[:3]
            if r < 65 and g > 170 and 55 < b < 145:
                points.append((x, y))
    if len(points) < 120:
        return None
    x1, x2 = min(x for x, _ in points), max(x for x, _ in points)
    y1, y2 = min(y for _, y in points), max(y for _, y in points)
    if not (25 <= x2 - x1 <= 110 and 25 <= y2 - y1 <= 110):
        return None
    if not .7 <= (x2 - x1) / (y2 - y1) <= 1.3:
        return None
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def play_spotify_query(query: str) -> dict:
    if not query or len(query) > 120:
        return {"ok": False, "message": "Please name a song, artist, or playlist."}
    try:
        os.startfile("spotify:search:" + quote(query, safe=""))
        hwnd = None
        for _ in range(16):
            time.sleep(.5)
            hwnd = _spotify_window()
            if hwnd:
                break
        if not hwnd:
            return {"ok": False, "message": "Spotify did not open. Check that it is installed and signed in."}
        from screen_context import bring_to_front
        bring_to_front(hwnd)
        rect = ctypes.wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return {"ok": True, "message": f"Opened Spotify search for {query}; I could not verify playback."}
        bounds = (rect.left, rect.top, rect.right, rect.bottom)
        for _ in range(8):
            time.sleep(.5)
            button = _top_result_button(pyautogui.screenshot(), bounds)
            if button:
                pyautogui.click(*button)
                time.sleep(.8)
                center = pyautogui.screenshot().getpixel(button)[:3]
                if center[0] < 65 and center[1] > 170 and 55 < center[2] < 145:
                    return {"ok": True, "message": f"Playing Spotify's top result for {query}."}
                return {"ok": True, "message": f"Selected Spotify's top result for {query}; playback is not verified."}
        return {"ok": True, "message": f"Opened Spotify search for {query}; I could not verify playback."}
    except Exception as exc:
        return {"ok": False, "message": f"Spotify search failed: {exc}"}
