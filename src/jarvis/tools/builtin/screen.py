"""
Screen capture and desktop window inspection tools for Linux Mint / Ubuntu.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.system.process import ProcessError, run_process

logger = logging.getLogger(__name__)

GDK_AVAILABLE = False
Gdk = None
try:
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    GDK_AVAILABLE = True
except (ImportError, ValueError, AttributeError):
    GDK_AVAILABLE = False


def _resolve_output_path(output_path: str | None, prefix: str = "screenshot") -> Path:
    """Validate and resolve target image path inside user's home directory."""
    home = Path.home().resolve()
    if output_path:
        target = Path(output_path).expanduser().resolve()
        try:
            target.relative_to(home)
        except ValueError:
            raise ValueError(
                f"Invalid output path '{output_path}'. Screenshots must be saved within your home directory ({home})."
            )
    else:
        pictures_dir = home / "Pictures" / "jarvis_captures"
        pictures_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = pictures_dir / f"{prefix}_{timestamp}.png"

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


async def take_screenshot(output_path: str | None = None) -> str:
    """Capture the full current screen and save to an image file.

    Requires user confirmation for privacy.

    Args:
        output_path: Destination path (must be inside home). If omitted, saves to
                     ~/Pictures/jarvis_captures/screenshot_YYYYMMDD_HHMMSS.png.

    Returns:
        Confirmation message with path and image size.
    """
    target = _resolve_output_path(output_path, prefix="screenshot")

    # Method 1: Native PyGObject Gdk screen capture (fastest, zero subprocesses)
    if GDK_AVAILABLE and Gdk:
        try:
            root = Gdk.get_default_root_window()
            if root:
                w = root.get_width()
                h = root.get_height()
                pixbuf = Gdk.pixbuf_get_from_window(root, 0, 0, w, h)
                if pixbuf:
                    pixbuf.savev(str(target), "png", [], [])
                    if target.exists() and target.stat().st_size > 0:
                        size_kb = target.stat().st_size / 1024.0
                        return f"Screenshot captured successfully and saved to {target} ({size_kb:.1f} KB)."
        except Exception as exc:
            logger.debug("Native Gdk screenshot capture failed: %s. Trying CLI fallbacks...", exc)

    # Method 2: CLI tool fallbacks
    fallbacks: list[list[str]] = []
    if shutil.which("gnome-screenshot"):
        fallbacks.append(["gnome-screenshot", "-f", str(target)])
    if shutil.which("scrot"):
        fallbacks.append(["scrot", str(target)])
    if shutil.which("import"):
        fallbacks.append(["import", "-window", "root", str(target)])
    if shutil.which("maim"):
        fallbacks.append(["maim", str(target)])

    for cmd in fallbacks:
        try:
            res = await run_process(cmd, timeout=10.0)
            if res.returncode == 0 and target.exists() and target.stat().st_size > 0:
                size_kb = target.stat().st_size / 1024.0
                return f"Screenshot captured successfully and saved to {target} ({size_kb:.1f} KB)."
        except Exception as exc:
            logger.debug("Screenshot command %s failed: %s", cmd[0], exc)

    raise RuntimeError("Failed to capture screenshot: No working capture backend found or display unreachable.")


_ACTIVE_WIN_RE = re.compile(r"_NET_ACTIVE_WINDOW\(WINDOW\):\s*window\s*id\s*#\s*(0x[0-9a-fA-F]+)")
_WM_NAME_RE = re.compile(r'WM_NAME\(\w+\)\s*=\s*"(.*)"')
_WM_CLASS_RE = re.compile(r'WM_CLASS\(\w+\)\s*=\s*(.*)')


async def get_active_window() -> dict[str, Any]:
    """Get the title, application class, and ID of the currently active/focused window.

    Returns:
        Dict containing window_id, title, app_class, or error info.
    """
    if not shutil.which("xprop"):
        return {"error": "xprop utility is not available on this system."}

    try:
        res = await run_process(["xprop", "-root", "_NET_ACTIVE_WINDOW"], timeout=5.0)
        match = _ACTIVE_WIN_RE.search(res.stdout)
        if not match:
            return {"error": "No active window detected."}

        win_id = match.group(1)
        if win_id == "0x0":
            return {"window_id": win_id, "title": "Desktop", "app_class": "Desktop"}

        # Query window properties
        detail_res = await run_process(["xprop", "-id", win_id, "WM_NAME", "WM_CLASS"], timeout=5.0)
        out = detail_res.stdout

        title = "Unknown"
        name_match = _WM_NAME_RE.search(out)
        if name_match:
            title = name_match.group(1)

        app_class = "Unknown"
        class_match = _WM_CLASS_RE.search(out)
        if class_match:
            app_class = class_match.group(1).replace('"', "").strip()

        return {
            "window_id": win_id,
            "title": title,
            "app_class": app_class,
        }
    except Exception as exc:
        logger.warning("Error querying active window: %s", exc)
        return {"error": str(exc)}


async def list_open_windows() -> list[dict[str, Any]]:
    """List all open desktop application windows across workspaces.

    Returns:
        List of dicts with window_id, workspace, class, and title.
    """
    if not shutil.which("wmctrl"):
        return []

    try:
        res = await run_process(["wmctrl", "-lx"], timeout=5.0)
        windows: list[dict[str, Any]] = []
        for line in res.stdout.strip().splitlines():
            parts = line.split(maxsplit=4)
            if len(parts) >= 5:
                win_id, workspace, app_class, host, title = parts
                windows.append({
                    "window_id": win_id,
                    "workspace": workspace,
                    "app_class": app_class,
                    "title": title,
                })
        return windows
    except Exception as exc:
        logger.warning("Error listing open windows via wmctrl: %s", exc)
        return []


async def read_screen_text(query: Optional[str] = None) -> str:
    """Read visible text on the screen using OCR, optionally filtering for a query."""
    from jarvis.brain.vision.ocr import ScreenOCREngine
    ocr = ScreenOCREngine()
    
    # Capture temporary screenshot
    shot_msg = await take_screenshot()
    match_path = None
    for word in shot_msg.split():
        if word.endswith(".png") and Path(word).is_file():
            match_path = Path(word)
            break
    
    if not match_path or not match_path.is_file():
        return "Failed to capture screen for OCR text reading."

    elements = ocr.extract_text_elements(match_path)
    if not elements:
        return "No text detected on screen (or Tesseract OCR is not installed)."

    if query:
        matches = [e for e in elements if query.lower() in e.text.lower()]
        if not matches:
            return f"Query '{query}' was not found in visible screen text."
        lines = [f"Found {len(matches)} match(es) for '{query}':"]
        for m in matches:
            lines.append(f"• '{m.text}' at ({m.bbox.center[0]}, {m.bbox.center[1]}) [box: {m.bbox.width}x{m.bbox.height}]")
        return "\n".join(lines)

    lines = [f"Extracted {len(elements)} text segments from screen:"]
    for e in elements[:40]:
        lines.append(f"• {e.text}")
    return "\n".join(lines)


async def locate_ui_element(element_description: str) -> str:
    """Locate an interactive UI element on screen (button, field, icon) and return its exact coordinates."""
    from jarvis.brain.vision.grounding import VisualGrounder
    grounder = VisualGrounder()

    shot_msg = await take_screenshot()
    match_path = None
    for word in shot_msg.split():
        if word.endswith(".png") and Path(word).is_file():
            match_path = Path(word)
            break

    if not match_path:
        return "Failed to capture screen for visual element localization."

    res = await grounder.locate_element(element_description, match_path)
    if res.get("found"):
        return (
            f"Located UI element '{element_description}':\n"
            f"• Position: ({res['x']}, {res['y']})\n"
            f"• Method:   {res.get('method', 'grounding')}\n"
            f"• Confidence: {int(res.get('confidence', 1.0) * 100)}%"
        )
    return f"Could not locate UI element matching '{element_description}': {res.get('error', 'Not found')}"


async def watch_screen_for_event(event_description: str, timeout_seconds: float = 30.0) -> str:
    """Continuously observe screen state until a target visual event or condition occurs."""
    from jarvis.brain.vision.watcher import ScreenWatcherService
    watcher = ScreenWatcherService()
    res = await watcher.watch_for_event(event_description, timeout_seconds=timeout_seconds)
    if res["triggered"]:
        return f"Event detected after {res['elapsed_seconds']}s: {res['observation']}"
    return f"Watch timed out after {res['elapsed_seconds']}s: {res['observation']}"
