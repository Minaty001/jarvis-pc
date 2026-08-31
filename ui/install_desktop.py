"""
Install JARVIS as a native Linux Mint app for the current user.

Installs:
  ~/.local/share/applications/jarvis.desktop   (Mint menu entry)
  ~/.local/share/icons/hicolor/256x256/apps/jarvis.png
  ~/.local/bin/jarvis-ui                       (launcher, on PATH)
  ~/.config/autostart/jarvis.desktop           (floats at login)

All per-user (no root needed). Mirrors how other Mint apps install.
"""

import os
import shutil
import stat
import sys
from pathlib import Path

# Make project root importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger_import = None

try:
    from config.logger import get_logger
    logger = get_logger("ui.install")
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ui.install")


def install_user() -> dict:
    """Install per-user. Returns a dict of installed paths."""
    root = Path(__file__).resolve().parent.parent
    home = Path.home()
    installed = {}

    # 1. desktop entry — point Exec at the project launcher (absolute path),
    #    so it works regardless of PATH. This matches how a fixed-location app installs.
    apps_dir = home / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)
    src_desktop = root / "ui" / "jarvis.desktop"
    dst_desktop = apps_dir / "jarvis.desktop"
    desktop_text = src_desktop.read_text()
    launcher_abs = (root / "bin" / "jarvis-ui").resolve()
    # Replace the bare Exec=jarvis-ui with the absolute path to our launcher.
    new_lines = []
    for line in desktop_text.splitlines():
        if line.startswith("Exec="):
            new_lines.append(f"Exec={launcher_abs}")
        else:
            new_lines.append(line)
    dst_desktop.write_text("\n".join(new_lines) + "\n")
    installed["desktop"] = str(dst_desktop)

    # make the project launcher executable (in place)
    src_launcher = root / "bin" / "jarvis-ui"
    if src_launcher.exists():
        src_launcher.chmod(src_launcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        installed["launcher"] = str(src_launcher)

    # 2. icon
    icon_dir = home / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    src_icon = root / "assets" / "jarvis.png"
    dst_icon = icon_dir / "jarvis.png"
    if src_icon.exists():
        shutil.copy(src_icon, dst_icon)
        installed["icon"] = str(dst_icon)

    # 3. autostart (floating orb at login)
    try:
        from ui.linux_mint import install_autostart
        installed["autostart"] = install_autostart()
    except Exception as e:
        logger.warning("autostart install skipped: %s", e)

    logger.info("JARVIS installed for user: %s", home)
    return installed


if __name__ == "__main__":
    res = install_user()
    for k, v in res.items():
        print(f"{k:10s} -> {v}")
    print("Done. You can now launch 'JARVIS' from the Mint menu.")
