#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
BUILD_TMP="$ROOT_DIR/build/installer_payload"

echo "=================================================="
echo " Building Self-Contained JARVIS .run Installer    "
echo "=================================================="

mkdir -p "$DIST_DIR"
uv build --wheel --out-dir "$DIST_DIR"
WHEEL=$(ls -t "$DIST_DIR"/jarvis_pc-*.whl | head -n1)

rm -rf "$BUILD_TMP"
mkdir -p "$BUILD_TMP/app"
mkdir -p "$BUILD_TMP/deps"

echo "Bundling dependencies..."
uv pip install --target "$BUILD_TMP/deps" -r "$ROOT_DIR/requirements.txt"

echo "Bundling JARVIS application code..."
uv pip install --target "$BUILD_TMP/app" --no-deps "$WHEEL"

cp "$ROOT_DIR/deploy/desktop/jarvis.desktop" "$BUILD_TMP/jarvis.desktop"
cp "$ROOT_DIR/deploy/systemd/jarvis.service" "$BUILD_TMP/jarvis.service"
cp "$ROOT_DIR/assets/icons/jarvis.png" "$BUILD_TMP/jarvis.png"

# Create internal install script
cat <<'INS' > "$BUILD_TMP/install.sh"
#!/usr/bin/env bash
set -Eeuo pipefail

PAYLOAD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PREFIX="${HOME}/.local"
JARVIS_DIR="${PREFIX}/share/jarvis"
BIN_DIR="${PREFIX}/bin"

show_help() {
    echo "JARVIS PC Linux Installer"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --install           Install JARVIS PC (default)"
    echo "  --uninstall         Remove JARVIS PC installation"
    echo "  --prefix <dir>      Installation prefix (default: ~/.local)"
    echo "  --help              Display this help message"
    exit 0
}

uninstall_jarvis() {
    echo "Uninstalling JARVIS PC..."
    rm -rf "$JARVIS_DIR"
    rm -f "$BIN_DIR/jarvis"
    rm -f "$HOME/.local/share/applications/jarvis.desktop"
    rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/jarvis.png"
    rm -f "$HOME/.config/systemd/user/jarvis.service"
    if command -v systemctl &>/dev/null && [ -d /run/systemd/system ]; then
        systemctl --user daemon-reload 2>/dev/null || true
    fi
    echo "JARVIS PC successfully uninstalled."
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h) show_help ;;
        --uninstall) uninstall_jarvis ;;
        --prefix) PREFIX="$2"; JARVIS_DIR="${PREFIX}/share/jarvis"; BIN_DIR="${PREFIX}/bin"; shift 2 ;;
        --install) shift ;;
        *) shift ;;
    esac
done

echo "========================================="
echo "   Installing JARVIS Linux Assistant     "
echo "========================================="

mkdir -p "$JARVIS_DIR/app"
mkdir -p "$JARVIS_DIR/deps"
mkdir -p "$BIN_DIR"
mkdir -p "$HOME/.config/jarvis"
mkdir -p "$HOME/.local/state/jarvis"
mkdir -p "$HOME/.cache/jarvis"

echo "Copying files to $JARVIS_DIR..."
cp -r "$PAYLOAD_DIR/app"/* "$JARVIS_DIR/app/"
cp -r "$PAYLOAD_DIR/deps"/* "$JARVIS_DIR/deps/"

# Create launcher script
cat <<EOF_LAUNCHER > "$JARVIS_DIR/jarvis"
#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONPATH="$JARVIS_DIR/app:$JARVIS_DIR/deps:\${PYTHONPATH:-}"
exec python3 -m jarvis "\$@"
EOF_LAUNCHER
chmod 755 "$JARVIS_DIR/jarvis"
ln -sf "$JARVIS_DIR/jarvis" "$BIN_DIR/jarvis"
echo "CLI linked to $BIN_DIR/jarvis"

# Icon
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$ICON_DIR"
cp "$PAYLOAD_DIR/jarvis.png" "$ICON_DIR/jarvis.png"

# Desktop file
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
sed -e "s|Exec=jarvis|Exec=$BIN_DIR/jarvis|g" "$PAYLOAD_DIR/jarvis.desktop" > "$DESKTOP_DIR/jarvis.desktop"
chmod +x "$DESKTOP_DIR/jarvis.desktop"
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

# Systemd service
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
cp "$PAYLOAD_DIR/jarvis.service" "$SERVICE_DIR/jarvis.service"
if command -v systemctl &>/dev/null && [ -d /run/systemd/system ]; then
    systemctl --user daemon-reload 2>/dev/null || true
fi

echo ""
echo "Running system verification..."
"$BIN_DIR/jarvis" doctor || true

echo ""
echo "========================================="
echo " JARVIS installation completed!"
echo " Command:  jarvis run"
echo " Service:  systemctl --user enable --now jarvis.service"
echo " Menu:     Search 'JARVIS PC' in Application Menu"
echo "========================================="
INS
chmod +x "$BUILD_TMP/install.sh"

# Create compressed payload
PAYLOAD_TAR="$ROOT_DIR/build/payload.tar.gz"
tar -czf "$PAYLOAD_TAR" -C "$BUILD_TMP" .

# Generate self-extracting .run image
OUTPUT_RUN="$DIST_DIR/jarvis-installer.run"
cat <<'RUN_HEADER' > "$OUTPUT_RUN"
#!/usr/bin/env bash
set -Eeuo pipefail

echo "Extracting JARVIS installer archive..."
TMP_DIR="$(mktemp -d -t jarvis-install-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

ARCHIVE_LINE=$(awk '/^__PAYLOAD_ARCHIVE_BELOW__/ {print NR + 1; exit 0; }' "$0")
tail -n +"$ARCHIVE_LINE" "$0" | tar -xzf - -C "$TMP_DIR"

"$TMP_DIR/install.sh" "$@"
exit 0

__PAYLOAD_ARCHIVE_BELOW__
RUN_HEADER

cat "$PAYLOAD_TAR" >> "$OUTPUT_RUN"
chmod +x "$OUTPUT_RUN"
rm -rf "$BUILD_TMP" "$PAYLOAD_TAR"

echo "=================================================="
echo " Successfully created standalone installer image:"
echo " -> $OUTPUT_RUN ($(du -h "$OUTPUT_RUN" | cut -f1))"
echo " Run anywhere: ./dist/jarvis-installer.run"
echo "=================================================="
