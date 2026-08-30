"""
Computer Control — Abstracted mouse/keyboard/screenshot control.
Uses xdotool for Linux, with policy-gated visual control.
"""

import asyncio
import subprocess
import time
from typing import Any, Optional

from config.logger import get_logger

logger = get_logger("execution.computer_control")


class ComputerControl:
    """Abstracted computer control interface."""

    def __init__(self):
        self._screenshot_tool = self._detect_screenshot_tool()

    def _detect_screenshot_tool(self) -> Optional[str]:
        for tool in ["scrot", "import", "gnome-screenshot"]:
            try:
                subprocess.run(["which", tool], capture_output=True, check=True)
                return tool
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        return None

    async def move_mouse(self, x: int, y: int) -> dict:
        """Move mouse to absolute position."""
        return await self._run_xdotool(["mousemove", str(x), str(y)])

    async def click(self, x: int, y: int, button: int = 1) -> dict:
        """Click at position."""
        await self._run_xdotool(["mousemove", str(x), str(y)])
        return await self._run_xdotool(["click", str(button)])

    async def double_click(self, x: int, y: int) -> dict:
        """Double-click at position."""
        await self._run_xdotool(["mousemove", str(x), str(y)])
        return await self._run_xdotool(["doubleclick", "1"])

    async def type_text(self, text: str) -> dict:
        """Type text using keyboard."""
        return await self._run_xdotool(["type", "--clearmodifiers", text])

    async def press_key(self, key: str) -> dict:
        """Press a single key."""
        return await self._run_xdotool(["key", key])

    async def hotkey(self, *keys: str) -> dict:
        """Press a key combination."""
        combo = "+".join(keys)
        return await self._run_xdotool(["key", combo])

    async def scroll(self, direction: str = "down", amount: int = 3) -> dict:
        """Scroll mouse wheel."""
        key = "5" if direction == "down" else "4"
        results = []
        for _ in range(amount):
            r = await self._run_xdotool(["click", key])
            results.append(r)
            await asyncio.sleep(0.05)
        return {"success": True, "result": f"Scrolled {direction} {amount} times"}

    async def screenshot(self, output_path: str = "/tmp/jarvis_screenshot.png") -> dict:
        """Capture screenshot."""
        if not self._screenshot_tool:
            return {"success": False, "error": "No screenshot tool available"}

        try:
            if self._screenshot_tool == "scrot":
                subprocess.run(["scrot", output_path], check=True, timeout=5)
            elif self._screenshot_tool == "import":
                subprocess.run(["import", "-window", "root", output_path], check=True, timeout=5)

            return {"success": True, "result": output_path, "path": output_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_active_window(self) -> dict:
        """Get active window info."""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=5,
            )
            return {"success": True, "result": result.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _run_xdotool(self, args: list) -> dict:
        """Run an xdotool command."""
        try:
            result = subprocess.run(
                ["xdotool"] + args,
                capture_output=True, text=True, timeout=5,
            )
            return {"success": result.returncode == 0, "result": result.stdout.strip()}
        except FileNotFoundError:
            return {"success": False, "error": "xdotool not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}


computer_control = ComputerControl()
