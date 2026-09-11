#!/usr/bin/env bash
set -Eeuo pipefail

echo "========================================="
echo "   Installing JARVIS Linux Assistant...   "
echo "========================================="

if ! command -v uv &> /dev/null; then
    echo "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

INSTALL_DIR="${JARVIS_INSTALL_DIR:-$HOME/.local/share/jarvis}"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"

echo "Creating installation directory at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$HOME/.config/jarvis"
mkdir -p "$HOME/.local/state/jarvis"
mkdir -p "$HOME/.cache/jarvis"

echo "Setting up virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    uv venv "$VENV_DIR" --python 3.12 || uv venv "$VENV_DIR"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Install wheel if available in dist/, else install from package directory
WHEEL=$(ls -t "$ROOT_DIR"/dist/jarvis_pc-*.whl 2>/dev/null | head -n1 || true)
if [ -n "$WHEEL" ] && [ -f "$WHEEL" ]; then
    echo "Installing from wheel package: $(basename "$WHEEL")..."
    uv pip install --python "$VENV_DIR/bin/python" "$WHEEL"
else
    echo "Installing JARVIS package into virtual environment..."
    uv pip install --python "$VENV_DIR/bin/python" "$ROOT_DIR"
fi

# Symlink executable into user bin
ln -sf "$VENV_DIR/bin/jarvis" "$BIN_DIR/jarvis"
echo "Binary linked: $BIN_DIR/jarvis"

# Install desktop entry and icon
ICON_SRC="$ROOT_DIR/assets/icons/jarvis.png"
if [ -f "$ICON_SRC" ]; then
    ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
    mkdir -p "$ICON_DIR"
    cp "$ICON_SRC" "$ICON_DIR/jarvis.png"
fi

DESKTOP_SRC="$ROOT_DIR/deploy/desktop/jarvis.desktop"
if [ -f "$DESKTOP_SRC" ]; then
    DESKTOP_DIR="$HOME/.local/share/applications"
    mkdir -p "$DESKTOP_DIR"
    sed -e "s|Exec=jarvis|Exec=$BIN_DIR/jarvis|g" "$DESKTOP_SRC" > "$DESKTOP_DIR/jarvis.desktop"
    chmod +x "$DESKTOP_DIR/jarvis.desktop"
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi
fi

# Install systemd user service
SERVICE_SRC="$ROOT_DIR/deploy/systemd/jarvis.service"
if [ -f "$SERVICE_SRC" ]; then
    mkdir -p "$HOME/.config/systemd/user"
    cp "$SERVICE_SRC" "$HOME/.config/systemd/user/jarvis.service"
    if command -v systemctl &> /dev/null && [ -d /run/systemd/system ]; then
        systemctl --user daemon-reload 2>/dev/null || true
    fi
    echo "JARVIS service file installed to $HOME/.config/systemd/user/jarvis.service"
fi

echo "Running JARVIS doctor..."
"$BIN_DIR/jarvis" doctor || true

echo "========================================="
echo "Installation complete!"
echo "Run directly: jarvis run"
echo "To enable and start as service: systemctl --user enable --now jarvis.service"
echo "========================================="
