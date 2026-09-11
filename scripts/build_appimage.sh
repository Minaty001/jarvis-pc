#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_DIR="$ROOT_DIR/build/AppDir"

echo "=================================================="
echo "      Building True Standalone JARVIS AppImage    "
echo "=================================================="

mkdir -p "$DIST_DIR"
uv build --wheel --out-dir "$DIST_DIR"
WHEEL=$(ls -t "$DIST_DIR"/jarvis_pc-*.whl | head -n1)

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/lib/jarvis"
mkdir -p "$APP_DIR/usr/lib/jarvis-deps"
mkdir -p "$APP_DIR/usr/share/applications"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/apps"

echo "Bundling core dependencies into AppDir..."
uv pip install --target "$APP_DIR/usr/lib/jarvis-deps" -r "$ROOT_DIR/requirements.txt"

echo "Unpacking JARVIS package into AppDir..."
uv pip install --target "$APP_DIR/usr/lib/jarvis" --no-deps "$WHEEL"

# Create AppRun entrypoint
cat <<'APPRUN' > "$APP_DIR/AppRun"
#!/usr/bin/env bash
set -Eeuo pipefail

HERE="$(dirname "$(readlink -f "${0}")")"
export PYTHONPATH="$HERE/usr/lib/jarvis:$HERE/usr/lib/jarvis-deps:${PYTHONPATH:-}"

# Check for desktop integration command
if [ "${1:-}" = "--install" ]; then
    echo "Integrating JARVIS with Desktop Environment..."
    mkdir -p "$HOME/.local/bin"
    mkdir -p "$HOME/.local/share/applications"
    mkdir -p "$HOME/.local/share/icons/hicolor/256x256/apps"

    APP_PATH="${APPIMAGE:-$(readlink -f "$0")}"
    ln -sf "$APP_PATH" "$HOME/.local/bin/jarvis"

    cp "$HERE/jarvis.png" "$HOME/.local/share/icons/hicolor/256x256/apps/jarvis.png"
    sed -e "s|Exec=jarvis|Exec=$HOME/.local/bin/jarvis|g" "$HERE/jarvis.desktop" > "$HOME/.local/share/applications/jarvis.desktop"
    chmod +x "$HOME/.local/share/applications/jarvis.desktop"

    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi

    echo "=================================================="
    echo " JARVIS AppImage desktop integration complete!"
    echo " CLI:     jarvis --help"
    echo " Menu:    Search 'JARVIS PC' in Application Menu"
    echo " Binary:  $HOME/.local/bin/jarvis"
    echo "=================================================="
    exit 0
fi

if [ $# -eq 0 ]; then
    exec python3 -m jarvis run
else
    exec python3 -m jarvis "$@"
fi
APPRUN
chmod 755 "$APP_DIR/AppRun"

# Copy desktop file and icons
cp "$ROOT_DIR/deploy/desktop/jarvis.desktop" "$APP_DIR/jarvis.desktop"
cp "$ROOT_DIR/deploy/desktop/jarvis.desktop" "$APP_DIR/usr/share/applications/jarvis.desktop"
cp "$ROOT_DIR/assets/icons/jarvis.png" "$APP_DIR/jarvis.png"
cp "$ROOT_DIR/assets/icons/jarvis.png" "$APP_DIR/usr/share/icons/hicolor/256x256/apps/jarvis.png"

# Appimagetool location
APPIMAGE_TOOL="/tmp/squashfs-root/AppRun"
if [ ! -x "$APPIMAGE_TOOL" ]; then
    if ! command -v appimagetool &>/dev/null; then
        echo "Downloading appimagetool..."
        curl -LsSf -o /tmp/appimagetool https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
        chmod +x /tmp/appimagetool
        (cd /tmp && /tmp/appimagetool --appimage-extract >/dev/null)
    fi
fi

APPIMAGE_BIN="${APPIMAGE_TOOL:-appimagetool}"
OUTPUT_APPIMAGE="$DIST_DIR/JARVIS-x86_64.AppImage"

echo "Creating SquashFS AppImage..."
ARCH=x86_64 "$APPIMAGE_BIN" "$APP_DIR" "$OUTPUT_APPIMAGE"
rm -rf "$APP_DIR"

echo "=================================================="
echo " Successfully created standalone AppImage:"
echo " -> $OUTPUT_APPIMAGE ($(du -h "$OUTPUT_APPIMAGE" | cut -f1))"
echo " Instant Run: ./dist/JARVIS-x86_64.AppImage"
echo " Integrate:   ./dist/JARVIS-x86_64.AppImage --install"
echo "=================================================="
