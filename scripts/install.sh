#!/usr/bin/env bash
set -euo pipefail

echo "Installing JARVIS Linux Assistant..."
mkdir -p ~/.config/systemd/user
cp deploy/systemd/jarvis.service ~/.config/systemd/user/jarvis.service

systemctl --user daemon-reload
echo "JARVIS service file installed to ~/.config/systemd/user/jarvis.service"
echo "To enable and start: systemctl --user enable --now jarvis.service"
