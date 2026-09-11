#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
PKG_ROOT="$ROOT_DIR/build/deb_package"

echo "=================================================="
echo "    Building Standalone Debian (.deb) Package     "
echo "=================================================="

mkdir -p "$DIST_DIR"
uv build --wheel --out-dir "$DIST_DIR"
WHEEL=$(ls -t "$DIST_DIR"/jarvis_pc-*.whl | head -n1)

rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/usr/bin"
mkdir -p "$PKG_ROOT/usr/lib/jarvis/app"
mkdir -p "$PKG_ROOT/usr/lib/jarvis/deps"
mkdir -p "$PKG_ROOT/usr/share/applications"
mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$PKG_ROOT/usr/lib/systemd/user"

# 1. DEBIAN/control
cat <<'CTRL' > "$PKG_ROOT/DEBIAN/control"
Package: jarvis-pc
Version: 1.0.0
Section: utils
Priority: optional
Architecture: all
Maintainer: JARVIS PC Team <jarvis@local>
Depends: python3 (>= 3.10)
Description: JARVIS Personal AI Voice Assistant for Linux
 JARVIS PC is an environment-aware, tool-using AI assistant for Linux desktop.
 Fully bundled and self-contained with zero post-install setup required.
CTRL

# 2. Bundle dependencies and package
echo "Bundling core dependencies..."
uv pip install --target "$PKG_ROOT/usr/lib/jarvis/deps" -r "$ROOT_DIR/requirements.txt"

echo "Bundling JARVIS application code..."
uv pip install --target "$PKG_ROOT/usr/lib/jarvis/app" --no-deps "$WHEEL"

# 3. Native system launcher /usr/bin/jarvis
cat <<'LAUNCHER' > "$PKG_ROOT/usr/bin/jarvis"
#!/usr/bin/env bash
set -Eeuo pipefail

export PYTHONPATH="/usr/lib/jarvis/app:/usr/lib/jarvis/deps:${PYTHONPATH:-}"
exec python3 -m jarvis "$@"
LAUNCHER
chmod 755 "$PKG_ROOT/usr/bin/jarvis"

# 4. Desktop entry & icon
cp "$ROOT_DIR/deploy/desktop/jarvis.desktop" "$PKG_ROOT/usr/share/applications/jarvis.desktop"
chmod 644 "$PKG_ROOT/usr/share/applications/jarvis.desktop"

cp "$ROOT_DIR/assets/icons/jarvis.png" "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/jarvis.png"
chmod 644 "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/jarvis.png"

# 5. Systemd user service
cp "$ROOT_DIR/deploy/systemd/jarvis.service" "$PKG_ROOT/usr/lib/systemd/user/jarvis.service"
chmod 644 "$PKG_ROOT/usr/lib/systemd/user/jarvis.service"

# 6. Post-install script
cat <<'POSTINST' > "$PKG_ROOT/DEBIAN/postinst"
#!/usr/bin/env bash
set -e

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi

echo "=================================================="
echo " JARVIS PC installed successfully!"
echo " Command: jarvis run"
echo " Service: systemctl --user enable --now jarvis.service"
echo "=================================================="
exit 0
POSTINST
chmod 755 "$PKG_ROOT/DEBIAN/postinst"

# 7. Post-remove script
cat <<'POSTRM' > "$PKG_ROOT/DEBIAN/postrm"
#!/usr/bin/env bash
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    rm -rf /usr/lib/jarvis 2>/dev/null || true
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database /usr/share/applications 2>/dev/null || true
    fi
fi
exit 0
POSTRM
chmod 755 "$PKG_ROOT/DEBIAN/postrm"

# Build the .deb
DEB_OUTPUT="$DIST_DIR/jarvis_1.0.0_all.deb"
dpkg-deb --build "$PKG_ROOT" "$DEB_OUTPUT"
rm -rf "$PKG_ROOT"

echo "=================================================="
echo " Successfully created standalone Debian package:"
echo " -> $DEB_OUTPUT ($(du -h "$DEB_OUTPUT" | cut -f1))"
echo " Install with: sudo apt install ./dist/jarvis_1.0.0_all.deb"
echo "=================================================="
