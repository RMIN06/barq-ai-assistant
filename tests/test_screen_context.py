"""Tests for screen_context module."""
from unittest.mock import patch, MagicMock
import pytest


def test_browser_apps_constant():
    from screen_context import BROWSER_APPS
    assert "chrome" in BROWSER_APPS
    assert "msedge" in BROWSER_APPS
    assert "firefox" in BROWSER_APPS


def test_format_situation():
    from screen_context import format_situation
    ctx = {
        "foreground_app": "chrome",
        "active_tab_or_window": "YouTube - Google Chrome",
        "open_browser_tabs": ["YouTube", "GitHub", "Gmail"]
    }
    result = format_situation(ctx)
    assert "chrome" in result.lower()
    assert "youtube" in result.lower()
    assert "github" in result.lower()


def test_format_situation_no_tabs():
    from screen_context import format_situation
    ctx = {
        "foreground_app": "notepad",
        "active_tab_or_window": "Untitled - Notepad",
        "open_browser_tabs": []
    }
    result = format_situation(ctx)
    assert "notepad" in result.lower()
    assert "no browser tabs" in result.lower()


def test_app_shortcuts():
    from screen_context import _APP_SHORTCUTS
    assert "calculator" in _APP_SHORTCUTS
    assert "notepad" in _APP_SHORTCUTS
    assert _APP_SHORTCUTS["calculator"] == "calc"


@patch("screen_context.subprocess.Popen")
def test_open_app_calculator(mock_popen):
    from screen_context import open_app
    result = open_app("calculator")
    assert result["ok"] is True
    mock_popen.assert_called_with("calc")


@patch("screen_context.shutil.which", return_value=None)
@patch("screen_context.subprocess.run")
@patch("screen_context.subprocess.Popen")
def test_open_app_unknown(mock_popen, mock_run, mock_which):
    from screen_context import open_app
    mock_run.return_value.stdout = "[]"
    result = open_app("unknown_app")
    assert result["ok"] is False
    mock_popen.assert_not_called()


@patch("screen_context.subprocess.run")
@patch("screen_context.subprocess.Popen")
def test_open_store_app(mock_popen, mock_run):
    from screen_context import open_app
    mock_run.return_value.stdout = '[{"Name":"Spotify","AppID":"SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"}]'
    result = open_app("spotify")
    assert result["ok"] is True
    mock_popen.assert_called_once_with(["explorer.exe", "shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"])


@patch("screen_context.user32")
def test_active_window(mock_user32):
    from screen_context import active_window, _window_title, _ext_process_name
    mock_hwnd = 12345
    mock_user32.GetForegroundWindow.return_value = mock_hwnd
    mock_user32.GetWindowTextLengthW.return_value = 10
    mock_buf = MagicMock()
    mock_buf.value = "Test Window"
    import ctypes
    ctypes.create_unicode_buffer = MagicMock(return_value=mock_buf)
    mock_user32.GetWindowThreadProcessId.return_value = None
    import psutil
    psutil.Process = MagicMock(return_value=MagicMock(name=MagicMock(return_value="test.exe")))

    result = active_window()
    assert "hwnd" in result
    assert "title" in result
    assert "app" in result


def test_screenshot_png_bytes():
    from screen_context import screenshot_png_bytes
    with patch("screen_context.pyautogui.screenshot") as mock_screenshot, \
         patch("screen_context.io.BytesIO") as mock_bytesio_class:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_img.resize = MagicMock(return_value=mock_img)
        mock_img.save = MagicMock()
        mock_screenshot.return_value = mock_img

        mock_buffer = MagicMock()
        mock_buffer.getvalue.return_value = b"fake png data"
        mock_bytesio_class.return_value = mock_buffer

        result = screenshot_png_bytes()
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result == b"fake png data"
