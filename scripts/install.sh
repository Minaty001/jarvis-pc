#!/usr/bin/env bash
set -Eeuo pipefail

echo "Installing JARVIS Linux Assistant..."

if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

INSTALL_DIR="$HOME/.local/share/jarvis"
VENV_DIR="$INSTALL_DIR/venv"

echo "Creating installation directory at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

echo "Creating virtual environment using uv..."
uv venv "$VENV_DIR" --python 3.12 || uv venv "$VENV_DIR"

echo "Installing JARVIS package into virtual environment..."
uv pip install --python "$VENV_DIR/bin/python" -e .

echo "Installing systemd user service..."
mkdir -p "$HOME/.config/systemd/user"
cp deploy/systemd/jarvis.service "$HOME/.config/systemd/user/jarvis.service"

if command -v systemctl &> /dev/null && [ -d /run/systemd/system ]; then
    systemctl --user daemon-reload || true
fi

echo "JARVIS service file installed to $HOME/.config/systemd/user/jarvis.service"

echo "Running JARVIS doctor..."
"$VENV_DIR/bin/jarvis" doctor || python3 -m jarvis.cli.doctor

echo "Installation complete!"
echo "To enable and start: systemctl --user enable --now jarvis.service"
