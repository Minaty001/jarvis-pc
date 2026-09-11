"""Native X11 desktop automation and vision-guided UI control for Linux."""

from __future__ import annotations

import asyncio
import ctypes
import json
import logging
import os
import re
import shutil
import subprocess  # nosec B404
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.system.process import run_process
from jarvis.tools.builtin.screen import take_screenshot
from jarvis.tools.builtin.vision import analyze_image

logger = logging.getLogger(__name__)

# X11 Constants
CURRENT_TIME = 0
BUTTON_LEFT = 1
BUTTON_MIDDLE = 2
BUTTON_RIGHT = 3
BUTTON_SCROLL_UP = 4
BUTTON_SCROLL_DOWN = 5


class X11Controller:
    """Zero-dependency ctypes wrapper around libX11 and libXtst for desktop input synthesis."""

    def __init__(self):
        self._display = None
        self._x11 = None
        self._xtst = None
        self._available = False
        self._init_libraries()

    def _init_libraries(self):
        try:
            self._x11 = ctypes.CDLL("libX11.so.6")
            self._xtst = ctypes.CDLL("libXtst.so.6")

            self._x11.XOpenDisplay.restype = ctypes.c_void_p
            self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]

            self._x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            self._x11.XFlush.argtypes = [ctypes.c_void_p]

            self._x11.XStringToKeysym.restype = ctypes.c_ulong
            self._x11.XStringToKeysym.argtypes = [ctypes.c_char_p]

            self._x11.XKeysymToKeycode.restype = ctypes.c_ubyte
            self._x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]

            self._xtst.XTestFakeMotionEvent.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_ulong,
            ]
            self._xtst.XTestFakeButtonEvent.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_int,
                ctypes.c_ulong,
            ]
            self._xtst.XTestFakeKeyEvent.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_int,
                ctypes.c_ulong,
            ]

            disp_name = os.environ.get("DISPLAY", ":0").encode("utf-8")
            self._display = self._x11.XOpenDisplay(disp_name)
            if self._display:
                self._available = True
            else:
                logger.debug("Failed to open X11 display: %s", disp_name)
        except Exception as exc:
            logger.debug("X11 library initialization failed: %s", exc)
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def move_mouse(self, x: int, y: int) -> bool:
        if not self._available:
            return False
        try:
            self._xtst.XTestFakeMotionEvent(self._display, -1, int(x), int(y), CURRENT_TIME)
            self._x11.XFlush(self._display)
            return True
        except Exception as exc:
            logger.warning("X11 mouse move failed: %s", exc)
            return False

    def click_mouse(self, x: Optional[int] = None, y: Optional[int] = None, button: int = BUTTON_LEFT, clicks: int = 1) -> bool:
        if not self._available:
            return False
        try:
            if x is not None and y is not None:
                self.move_mouse(x, y)
                time.sleep(0.02)

            for _ in range(clicks):
                # Press
                self._xtst.XTestFakeButtonEvent(self._display, button, 1, CURRENT_TIME)
                self._x11.XFlush(self._display)
                time.sleep(0.03)
                # Release
                self._xtst.XTestFakeButtonEvent(self._display, button, 0, CURRENT_TIME)
                self._x11.XFlush(self._display)
                if clicks > 1:
                    time.sleep(0.05)
            return True
        except Exception as exc:
            logger.warning("X11 mouse click failed: %s", exc)
            return False

    def press_key_code(self, keycode: int, is_press: bool = True) -> bool:
        if not self._available or not keycode:
            return False
        try:
            self._xtst.XTestFakeKeyEvent(self._display, keycode, 1 if is_press else 0, CURRENT_TIME)
            self._x11.XFlush(self._display)
            return True
        except Exception as exc:
            logger.warning("X11 key event failed: %s", exc)
            return False

    def key_combination(self, keys: List[str]) -> bool:
        if not self._available:
            return False
        keycodes = []
        for k in keys:
            sym = self._x11.XStringToKeysym(k.encode("utf-8"))
            if sym:
                kc = self._x11.XKeysymToKeycode(self._display, sym)
                if kc:
                    keycodes.append(kc)

        if not keycodes:
            return False

        # Press in order
        for kc in keycodes:
            self.press_key_code(kc, is_press=True)
            time.sleep(0.01)

        # Release in reverse order
        for kc in reversed(keycodes):
            self.press_key_code(kc, is_press=False)
            time.sleep(0.01)

        return True

    def type_string(self, text: str) -> bool:
        if not self._available:
            return False
        for char in text:
            # Look up keysym for character
            sym_name = char
            if char == "\n":
                sym_name = "Return"
            elif char == "\t":
                sym_name = "Tab"
            elif char == " ":
                sym_name = "space"

            sym = self._x11.XStringToKeysym(sym_name.encode("utf-8"))
            if not sym and len(char) == 1:
                # Fallback to Latin-1 keysym
                sym = ord(char)

            if sym:
                kc = self._x11.XKeysymToKeycode(self._display, sym)
                if kc:
                    self.press_key_code(kc, is_press=True)
                    time.sleep(0.01)
                    self.press_key_code(kc, is_press=False)
                    time.sleep(0.01)
        return True


# Global controller singleton
_CONTROLLER = X11Controller()


async def click_mouse(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    """Click the mouse at desktop coordinates (x, y).

    Args:
        x: Horizontal pixel coordinate.
        y: Vertical pixel coordinate.
        button: Mouse button ('left', 'right', 'middle').
        clicks: Number of clicks (1 for single click, 2 for double click).
    """
    btn_map = {
        "left": BUTTON_LEFT,
        "middle": BUTTON_MIDDLE,
        "right": BUTTON_RIGHT,
    }
    btn_num = btn_map.get(button.lower(), BUTTON_LEFT)

    if _CONTROLLER.is_available:
        ok = _CONTROLLER.click_mouse(x=x, y=y, button=btn_num, clicks=clicks)
        if ok:
            return f"Clicked {button} mouse button at ({x}, {y}) [clicks={clicks}]."

    # CLI fallback if xdotool is present
    if shutil.which("xdotool"):
        btn_arg = "1" if button == "left" else ("3" if button == "right" else "2")
        repeat_arg = ["--repeat", str(clicks)] if clicks > 1 else []
        cmd = ["xdotool", "mousemove", str(x), str(y), "click"] + repeat_arg + [btn_arg]
        res = await run_process(cmd, timeout=5.0)
        if res.returncode == 0:
            return f"Clicked {button} mouse button at ({x}, {y}) via xdotool."

    return f"Mouse click at ({x}, {y}) simulated (Display unavailable or headless)."


async def move_mouse(x: int, y: int) -> str:
    """Move the mouse cursor to (x, y) coordinates."""
    if _CONTROLLER.is_available:
        if _CONTROLLER.move_mouse(x, y):
            return f"Cursor moved to ({x}, {y})."

    if shutil.which("xdotool"):
        await run_process(["xdotool", "mousemove", str(x), str(y)], timeout=5.0)
        return f"Cursor moved to ({x}, {y}) via xdotool."

    return f"Cursor move to ({x}, {y}) simulated."


async def scroll_mouse(direction: str = "down", amount: int = 5) -> str:
    """Scroll the mouse wheel up or down."""
    btn = BUTTON_SCROLL_DOWN if direction.lower() == "down" else BUTTON_SCROLL_UP
    if _CONTROLLER.is_available:
        _CONTROLLER.click_mouse(button=btn, clicks=amount)
        return f"Scrolled mouse {direction} by {amount} clicks."

    if shutil.which("xdotool"):
        btn_arg = "5" if direction.lower() == "down" else "4"
        await run_process(["xdotool", "click", "--repeat", str(amount), btn_arg], timeout=5.0)
        return f"Scrolled mouse {direction} by {amount} clicks via xdotool."

    return f"Mouse scroll {direction} ({amount} clicks) simulated."


async def type_text(text: str) -> str:
    """Type keyboard text into the currently focused window."""
    if _CONTROLLER.is_available:
        if _CONTROLLER.type_string(text):
            return f"Typed {len(text)} characters into focused window."

    if shutil.which("xdotool"):
        res = await run_process(["xdotool", "type", "--delay", "12", text], timeout=10.0)
        if res.returncode == 0:
            return f"Typed {len(text)} characters via xdotool."

    return f"Typing text '{text}' simulated (Display unavailable)."


async def press_key(key: str) -> str:
    """Press a key or key combination (e.g. 'Return', 'Escape', 'Tab', 'ctrl+c', 'alt+F4')."""
    parts = [p.strip() for p in key.replace("+", " ").split()]

    # Normalize key names
    key_name_map = {
        "enter": "Return",
        "return": "Return",
        "esc": "Escape",
        "escape": "Escape",
        "tab": "Tab",
        "backspace": "BackSpace",
        "ctrl": "Control_L",
        "control": "Control_L",
        "alt": "Alt_L",
        "shift": "Shift_L",
        "super": "Super_L",
        "win": "Super_L",
        "space": "space",
        "up": "Up",
        "down": "Down",
        "left": "Left",
        "right": "Right",
    }
    normalized_keys = [key_name_map.get(k.lower(), k) for k in parts]

    if _CONTROLLER.is_available:
        if _CONTROLLER.key_combination(normalized_keys):
            return f"Pressed key combination: '{key}'."

    if shutil.which("xdotool"):
        xdo_combo = "+".join(parts)
        res = await run_process(["xdotool", "key", xdo_combo], timeout=5.0)
        if res.returncode == 0:
            return f"Pressed key '{key}' via xdotool."

    return f"Key press '{key}' simulated."


async def focus_window(window: str) -> str:
    """Focus and bring an open window to the front by ID or title substring."""
    if not shutil.which("wmctrl"):
        return "wmctrl utility is not installed; cannot focus window."

    # If it's a hex ID (e.g. 0x03800003)
    if window.startswith("0x"):
        res = await run_process(["wmctrl", "-i", "-a", window], timeout=5.0)
    else:
        res = await run_process(["wmctrl", "-a", window], timeout=5.0)

    if res.returncode == 0:
        return f"Successfully focused window matching '{window}'."
    return f"Window matching '{window}' not found or could not be focused."


async def locate_and_click(description: str, client: Optional[Any] = None) -> str:
    """Capture screen, visually locate element by description using Vision LLM, and click it."""
    try:
        # 1. Take a screenshot
        screenshot_msg = await take_screenshot()
        match = re.search(r"saved to (/.*?\.png)", screenshot_msg)
        if not match:
            return f"Failed to capture screenshot for visual locator: {screenshot_msg}"

        image_path = match.group(1)

        # 2. Query vision LLM to locate (x, y) coordinates
        prompt = (
            f"Analyze this desktop screenshot to locate the UI element: '{description}'.\n"
            "Return ONLY a JSON object with integer pixel coordinates:\n"
            '{"found": true, "x": 450, "y": 320, "description": "target element"}\n'
            "If the element cannot be found, return:\n"
            '{"found": false, "x": 0, "y": 0, "description": "reason"}'
        )

        response = await analyze_image(image_path, prompt=prompt, client=client)

        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            if data.get("found"):
                x = int(data.get("x", 0))
                y = int(data.get("y", 0))
                click_res = await click_mouse(x=x, y=y)
                return f"Visually located '{description}' at ({x}, {y}) and clicked it: {click_res}"
            else:
                return f"Could not visually locate '{description}': {data.get('description', 'Not visible on screen')}"

        return f"Vision model response was not parseable: {response}"
    except Exception as exc:
        logger.warning("locate_and_click failed: %s", exc)
        return f"Visual locator error: {exc}"
