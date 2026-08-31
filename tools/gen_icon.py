"""Generate the JARVIS app icon (orb) as a PNG for the .desktop file + autostart."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ui.orb import OrbWidget
import cairo


def main():
    size = 256
    out = os.path.join(ROOT, "assets", "jarvis.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    surf = OrbWidget.render_to_surface(size, "idle", "", phase=0.4)
    surf.write_to_png(out)
    # also a 96px variant for autostart/tray
    small = os.path.join(ROOT, "assets", "jarvis-96.png")
    s2 = OrbWidget.render_to_surface(96, "idle", "", phase=0.4)
    s2.write_to_png(small)
    print("wrote", out, "and", small)


if __name__ == "__main__":
    main()
