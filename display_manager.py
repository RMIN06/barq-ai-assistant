"""
Multi-monitor and window management for Barq.
"""
import ctypes
from ctypes import wintypes
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from barqlog import get_logger

log = get_logger("display")

user32 = ctypes.windll.user32
shcore = ctypes.windll.shcore


@dataclass
class MonitorInfo:
    """Information about a monitor."""
    handle: int
    rect: Tuple[int, int, int, int]  # left, top, right, bottom
    work_rect: Tuple[int, int, int, int]  # work area (excludes taskbar)
    dpi: int
    scale_factor: float
    is_primary: bool
    device_name: str


@dataclass
class WindowInfo:
    """Information about a window."""
    hwnd: int
    title: str
    class_name: str
    process_id: int
    process_name: str
    rect: Tuple[int, int, int, int]
    monitor_handle: int
    is_visible: bool
    is_minimized: bool
    is_maximized: bool
    z_order: int


# Windows API constants
MONITOR_DEFAULTTONEAREST = 0x00000002
MONITORINFOF_PRIMARY = 0x00000001
SW_RESTORE = 9
SW_SHOW = 5
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2


def get_all_monitors() -> List[MonitorInfo]:
    """Get information about all connected monitors."""
    monitors = []

    def monitor_enum_proc(hmonitor, hdc, lprect, lparam):
        # Get monitor info
        class MONITORINFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32),
            ]

        mi = MONITORINFOEX()
        mi.cbSize = ctypes.sizeof(MONITORINFOEX)
        user32.GetMonitorInfoW(hmonitor, ctypes.byref(mi))

        # Get DPI
        dpi = 96
        try:
            shcore.GetDpiForMonitor(hmonitor, 0, ctypes.byref(wintypes.UINT()), ctypes.byref(wintypes.UINT()))
        except Exception:
            pass

        scale = dpi / 96.0

        monitors.append(MonitorInfo(
            handle=hmonitor,
            rect=(mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right, mi.rcMonitor.bottom),
            work_rect=(mi.rcWork.left, mi.rcWork.top, mi.rcWork.right, mi.rcWork.bottom),
            dpi=dpi,
            scale_factor=scale,
            is_primary=bool(mi.dwFlags & MONITORINFOF_PRIMARY),
            device_name=mi.szDevice
        ))
        return True

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
        ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
    )

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(monitor_enum_proc), 0)
    return monitors


def get_primary_monitor() -> Optional[MonitorInfo]:
    """Get the primary monitor."""
    for m in get_all_monitors():
        if m.is_primary:
            return m
    return get_all_monitors()[0] if get_all_monitors() else None


def get_monitor_for_window(hwnd: int) -> Optional[MonitorInfo]:
    """Get the monitor a window is on."""
    hmonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not hmonitor:
        return None
    for m in get_all_monitors():
        if m.handle == hmonitor:
            return m
    return None


def get_monitor_at_point(x: int, y: int) -> Optional[MonitorInfo]:
    """Get the monitor at a specific screen coordinate."""
    point = wintypes.POINT(x, y)
    hmonitor = user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST)
    if not hmonitor:
        return None
    for m in get_all_monitors():
        if m.handle == hmonitor:
            return m
    return None


def get_all_windows() -> List[WindowInfo]:
    """Get all visible windows."""
    windows = []

    def enum_proc(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        # Get window title
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        # Get class name
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        class_name = class_buf.value

        # Get process ID
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # Get process name
        process_name = ""
        try:
            import psutil
            p = psutil.Process(pid.value)
            process_name = p.name()
        except Exception:
            pass

        # Get window rect
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        # Get monitor
        hmonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)

        # Check window state
        placement = wintypes.WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(placement)
        user32.GetWindowPlacement(hwnd, ctypes.byref(placement))
        is_minimized = placement.showCmd == 2  # SW_SHOWMINIMIZED
        is_maximized = placement.showCmd == 3  # SW_SHOWMAXIMIZED

        # Get Z-order (approximate)
        z_order = 0
        hwnd_z = hwnd
        while hwnd_z:
            hwnd_z = user32.GetWindow(hwnd_z, 3)  # GW_HWNDPREV
            z_order += 1

        windows.append(WindowInfo(
            hwnd=hwnd,
            title=title,
            class_name=class_name,
            process_id=pid.value,
            process_name=process_name or "",
            rect=(rect.left, rect.top, rect.right, rect.bottom),
            monitor_handle=hmonitor,
            is_visible=True,
            is_minimized=is_minimized,
            is_maximized=is_maximized,
            z_order=z_order
        ))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
    return windows


def find_windows_by_title(keyword: str) -> List[WindowInfo]:
    """Find windows whose title contains keyword (case-insensitive)."""
    keyword = keyword.lower()
    return [w for w in get_all_windows() if keyword in w.title.lower()]


def find_windows_by_process(process_name: str) -> List[WindowInfo]:
    """Find windows belonging to a process."""
    process_name = process_name.lower().replace(".exe", "")
    return [w for w in get_all_windows() if process_name in w.process_name.lower().replace(".exe", "")]


def bring_window_to_front(hwnd: int) -> bool:
    """Bring window to front and focus it."""
    try:
        # Restore if minimized
        placement = wintypes.WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(placement)
        user32.GetWindowPlacement(hwnd, ctypes.byref(placement))
        if placement.showCmd == 2:  # SW_SHOWMINIMIZED
            user32.ShowWindow(hwnd, SW_RESTORE)

        # Bring to top
        user32.SetWindowPos(
            hwnd, HWND_TOP, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        )
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        log.error(f"Failed to bring window to front: {e}")
        return False


def move_window_to_monitor(hwnd: int, target_monitor: MonitorInfo, 
                          x_offset: int = 0, y_offset: int = 0,
                          width: int = None, height: int = None) -> bool:
    """Move window to a specific monitor."""
    try:
        work = target_monitor.work_rect
        x = work[0] + x_offset
        y = work[1] + y_offset
        w = width if width else (work[2] - work[0])
        h = height if height else (work[3] - work[1])

        user32.SetWindowPos(
            hwnd, HWND_TOP, x, y, w, h,
            SWP_SHOWWINDOW
        )
        return True
    except Exception as e:
        log.error(f"Failed to move window: {e}")
        return False


def snap_window(hwnd: int, position: str) -> bool:
    """Snap window to screen edge or corner.
    position: 'left', 'right', 'top', 'bottom', 'topleft', 'topright', 'bottomleft', 'bottomright', 'maximize'
    """
    try:
        monitor = get_monitor_for_window(hwnd)
        if not monitor:
            return False

        work = monitor.work_rect
        w = work[2] - work[0]
        h = work[3] - work[1]

        positions = {
            'left': (work[0], work[1], w // 2, h),
            'right': (work[0] + w // 2, work[1], w // 2, h),
            'top': (work[0], work[1], w, h // 2),
            'bottom': (work[0], work[1] + h // 2, w, h // 2),
            'topleft': (work[0], work[1], w // 2, h // 2),
            'topright': (work[0] + w // 2, work[1], w // 2, h // 2),
            'bottomleft': (work[0], work[1] + h // 2, w // 2, h // 2),
            'bottomright': (work[0] + w // 2, work[1] + h // 2, w // 2, h // 2),
            'maximize': (work[0], work[1], w, h),
        }

        if position not in positions:
            return False

        x, y, nw, nh = positions[position]
        user32.SetWindowPos(hwnd, HWND_TOP, x, y, nw, nh, SWP_SHOWWINDOW)
        return True
    except Exception as e:
        log.error(f"Failed to snap window: {e}")
        return False


def get_window_at_cursor() -> Optional[WindowInfo]:
    """Get the window under the mouse cursor."""
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    hwnd = user32.WindowFromPoint(point)
    if not hwnd:
        return None

    # Get the top-level window
    hwnd = user32.GetAncestor(hwnd, 2)  # GA_ROOT

    windows = get_all_windows()
    for w in windows:
        if w.hwnd == hwnd:
            return w
    return None


def set_window_always_on_top(hwnd: int, always_on_top: bool) -> bool:
    """Set window to always stay on top."""
    try:
        insert_after = HWND_TOPMOST if always_on_top else HWND_NOTOPMOST
        user32.SetWindowPos(
            hwnd, insert_after, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        )
        return True
    except Exception as e:
        log.error(f"Failed to set always on top: {e}")
        return False


def close_window(hwnd: int) -> bool:
    """Close a window gracefully."""
    try:
        user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        return True
    except Exception as e:
        log.error(f"Failed to close window: {e}")
        return False


def minimize_window(hwnd: int) -> bool:
    """Minimize a window."""
    try:
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        return True
    except Exception as e:
        log.error(f"Failed to minimize window: {e}")
        return False


def maximize_window(hwnd: int) -> bool:
    """Maximize a window."""
    try:
        user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
        return True
    except Exception as e:
        log.error(f"Failed to maximize window: {e}")
        return False


def restore_window(hwnd: int) -> bool:
    """Restore a minimized/maximized window."""
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        return True
    except Exception as e:
        log.error(f"Failed to restore window: {e}")
        return False


def get_virtual_screen_size() -> Tuple[int, int]:
    """Get total virtual screen size across all monitors."""
    width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
    return (width, height)


def get_virtual_screen_origin() -> Tuple[int, int]:
    """Get virtual screen origin (top-left of primary monitor in virtual coords)."""
    x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
    y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    return (x, y)


# Convenience function for Barq overlay positioning
def get_overlay_position(preferred_monitor: int = 0, margin: int = 20) -> Tuple[int, int, int, int]:
    """Get recommended position for Barq overlay window.
    Returns (x, y, width, height) for the overlay.
    """
    monitors = get_all_monitors()
    if not monitors:
        return (100, 100, 540, 620)

    monitor = monitors[preferred_monitor] if preferred_monitor < len(monitors) else monitors[0]
    work = monitor.work_rect

    overlay_w = 540
    overlay_h = 620

    # Bottom-right corner by default
    x = work[2] - overlay_w - margin
    y = work[3] - overlay_h - margin

    return (x, y, overlay_w, overlay_h)