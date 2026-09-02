#!/usr/bin/env bash
set -euo pipefail

echo "Uninstalling JARVIS Linux Assistant service..."
systemctl --user stop jarvis.service || true
systemctl --user disable jarvis.service || true
rm -f ~/.config/systemd/user/jarvis.service
systemctl --user daemon-reload
echo "JARVIS service uninstalled."
